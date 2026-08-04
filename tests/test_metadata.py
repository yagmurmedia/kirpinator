from app.models import TranscriptSegment
from app.youtube.metadata import generate_metadata


def test_generates_title_with_shorts_tag_and_keyword():
    segments = [
        TranscriptSegment(text="Bugun bahcede salincakla oynuyoruz.", start=0.0, end=2.0),
        TranscriptSegment(text="Salincak cok eglenceli.", start=2.0, end=4.0),
    ]
    meta = generate_metadata(segments, mood="playful")

    assert "#shorts" in meta.title.lower()
    assert len(meta.title) <= 100
    assert "salincak" in meta.tags
    assert meta.description  # never empty


def test_handles_empty_transcript_gracefully():
    meta = generate_metadata([], mood=None)
    assert meta.title
    assert "#shorts" in meta.title.lower()
    assert isinstance(meta.tags, list) and meta.tags


def test_long_form_omits_shorts_tag_and_shorts_keyword():
    segments = [TranscriptSegment(text="Bugun parkta oynuyoruz.", start=0.0, end=2.0)]
    meta = generate_metadata(segments, mood="playful", long_form=True)

    assert "#shorts" not in meta.title.lower()
    assert "shorts" not in [t.lower() for t in meta.tags]
