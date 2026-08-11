import json
from unittest.mock import Mock, patch

from app.models import TranscriptSegment
from app.youtube.metadata import generate_metadata

# All these tests mock Ollama's HTTP call so they stay fast/deterministic
# and don't depend on a real Ollama server being up — same pattern used for
# protected_moments.py. Tests that force a ConnectionError specifically
# exercise the rule-based fallback path (the original, always-available
# generator); tests with a mocked successful response exercise the
# LLM-first path.


def _mock_llm_response(title: str, description: str, tags: list[str]):
    resp = Mock(status_code=200, json=lambda: {
        "response": json.dumps({"title": title, "description": description, "tags": tags})
    })
    resp.raise_for_status = lambda: None
    return resp


def test_falls_back_to_rule_based_when_llm_unavailable():
    segments = [
        TranscriptSegment(text="Bugun bahcede salincakla oynuyoruz.", start=0.0, end=2.0),
        TranscriptSegment(text="Salincak cok eglenceli.", start=2.0, end=4.0),
    ]
    with patch("app.youtube.metadata.requests.post", side_effect=ConnectionError):
        meta = generate_metadata(segments, mood="playful")

    assert "#shorts" in meta.title.lower()
    assert len(meta.title) <= 100
    assert "salincak" in meta.tags
    assert meta.description  # never empty


def test_empty_transcript_skips_llm_and_falls_back():
    with patch("app.youtube.metadata.requests.post") as mock_post:
        meta = generate_metadata([], mood=None)
    mock_post.assert_not_called()  # nothing to send the LLM with no transcript
    assert meta.title
    assert "#shorts" in meta.title.lower()
    assert isinstance(meta.tags, list) and meta.tags


def test_long_form_fallback_omits_shorts_tag_and_shorts_keyword():
    segments = [TranscriptSegment(text="Bugun parkta oynuyoruz.", start=0.0, end=2.0)]
    with patch("app.youtube.metadata.requests.post", side_effect=ConnectionError):
        meta = generate_metadata(segments, mood="playful", long_form=True)

    assert "#shorts" not in meta.title.lower()
    assert "shorts" not in [t.lower() for t in meta.tags]


def test_llm_result_used_when_available():
    segments = [TranscriptSegment(text="Bugun dis fircaladik ve cok eglendik.", start=0.0, end=2.0)]
    with patch("app.youtube.metadata.requests.post") as mock_post:
        mock_post.return_value = _mock_llm_response(
            "Diş Fırçalama Zamanı Eğlenceye Dönüştü",
            "Bugün diş fırçalarken işler beklenmedik şekilde eğlenceye döndü.",
            ["diş fırçalama", "günlük rutin", "aile", "çocuk videoları"],
        )
        meta = generate_metadata(segments, mood="playful")

    assert meta.title.startswith("Diş Fırçalama Zamanı")
    assert "#shorts" in meta.title.lower()  # appended since missing and not long_form
    assert "diş fırçalama" in meta.tags
    mock_post.assert_called_once()


def test_llm_long_form_does_not_get_shorts_tag_appended():
    segments = [TranscriptSegment(text="Bugun parkta uzun bir gezinti yaptik.", start=0.0, end=2.0)]
    with patch("app.youtube.metadata.requests.post") as mock_post:
        mock_post.return_value = _mock_llm_response(
            "Parkta Uzun Bir Gün", "Parkta geçirdiğimiz keyifli bir gün.", ["park", "aile", "gezinti"],
        )
        meta = generate_metadata(segments, mood="playful", long_form=True)

    assert "#shorts" not in meta.title.lower()


def test_llm_incomplete_response_falls_back_to_rule_based():
    # Missing "tags" entirely — must not crash, must fall back cleanly.
    segments = [TranscriptSegment(text="Bugun salincakla oynuyoruz cok eglenceli.", start=0.0, end=2.0)]
    resp = Mock(status_code=200, json=lambda: {
        "response": json.dumps({"title": "Bir Başlık", "description": "Bir açıklama"})
    })
    resp.raise_for_status = lambda: None
    with patch("app.youtube.metadata.requests.post", return_value=resp):
        meta = generate_metadata(segments, mood="playful")

    # Fell back to the rule-based generator (which always produces tags).
    assert "salincakla" in meta.tags
