from app.models import TranscriptSegment
from app.pipeline.highlight_detector import detect_keyword_highlights


def test_detects_turkish_exclamation_keyword():
    segments = [TranscriptSegment(text="Vay canina bu harika!", start=3.5, end=5.0)]
    highlights = detect_keyword_highlights(segments)

    assert len(highlights) == 1
    assert highlights[0].kind == "keyword"
    assert highlights[0].t == 3.5


def test_bare_exclamation_mark_without_keyword_still_flagged():
    segments = [TranscriptSegment(text="Bu bir test cumlesi!", start=1.0, end=2.0)]
    highlights = detect_keyword_highlights(segments)

    assert len(highlights) == 1
    assert highlights[0].kind == "exclaim"


def test_plain_sentence_produces_no_highlight():
    segments = [TranscriptSegment(text="Bugun parka gittik.", start=0.0, end=1.5)]
    assert detect_keyword_highlights(segments) == []
