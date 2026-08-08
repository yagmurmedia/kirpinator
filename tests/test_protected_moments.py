from unittest.mock import Mock, patch

from app.models import TranscriptSegment
from app.pipeline.protected_moments import find_auto_topic_segments, find_protected_segments


def _seg(text, start, end):
    return TranscriptSegment(text=text, start=start, end=end, words=[])


def test_no_trigger_phrase_skips_llm_entirely():
    segments = [_seg("Merhaba dünya.", 0.0, 1.0)]
    with patch("app.pipeline.protected_moments.requests.post") as mock_post:
        result = find_protected_segments("bu video komik olsun", segments)
    assert result == []
    mock_post.assert_not_called()


def test_trigger_phrase_without_diacritics_still_activates():
    # Real bug found in practice: "kacirma" (no ç/ı) must still match
    # "kaçırma" in the trigger list, same as app/pipeline/instructions.py.
    segments = [_seg("Cikiyor.", 240.0, 240.2)]
    with patch("app.pipeline.protected_moments.requests.post") as mock_post:
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"response": '{"line_numbers": [0]}'},
        )
        mock_post.return_value.raise_for_status = lambda: None
        result = find_protected_segments("dis cikma anini kacirma", segments)
    assert len(result) == 1
    mock_post.assert_called_once()


def test_llm_failure_returns_empty_not_an_exception():
    segments = [_seg("Çıkıyor.", 240.0, 240.2)]
    with patch("app.pipeline.protected_moments.requests.post", side_effect=ConnectionError):
        result = find_protected_segments("bu anı kaçırma", segments)
    assert result == []


def test_out_of_range_indices_are_ignored():
    segments = [_seg("Çıkıyor.", 240.0, 240.2)]
    with patch("app.pipeline.protected_moments.requests.post") as mock_post:
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"response": '{"line_numbers": [0, 99, -1]}'},
        )
        mock_post.return_value.raise_for_status = lambda: None
        result = find_protected_segments("bu anı kaçırma", segments)
    assert len(result) == 1
    assert result[0].text == "Çıkıyor."


def test_auto_topic_detection_runs_with_no_instruction_needed():
    # This is the whole point of find_auto_topic_segments: unlike
    # find_protected_segments, it must call the LLM even with zero
    # custom_instructions, since the video's own topic (e.g. a tooth coming
    # out) has to be recognized automatically, not only when someone
    # remembers to type "kaçırma".
    segments = [_seg("Merhaba arkadaşlar.", 0.0, 1.0), _seg("Dişim çıkıyor.", 240.0, 240.2)]
    with patch("app.pipeline.protected_moments.requests.post") as mock_post:
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"response": '{"line_numbers": [0, 1]}'},
        )
        mock_post.return_value.raise_for_status = lambda: None
        result = find_auto_topic_segments(segments)
    mock_post.assert_called_once()
    assert len(result) == 2


def test_auto_topic_detection_llm_failure_returns_empty_not_an_exception():
    segments = [_seg("Merhaba arkadaşlar.", 0.0, 1.0)]
    with patch("app.pipeline.protected_moments.requests.post", side_effect=ConnectionError):
        result = find_auto_topic_segments(segments)
    assert result == []


def test_auto_topic_detection_empty_segments_skips_llm_entirely():
    with patch("app.pipeline.protected_moments.requests.post") as mock_post:
        result = find_auto_topic_segments([])
    assert result == []
    mock_post.assert_not_called()
