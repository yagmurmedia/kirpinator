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


def test_generic_everyday_phrases_no_longer_false_positive():
    # Real bug: these ordinary, extremely common words/phrases were matching
    # as "exclamation keywords" and firing the top-tier İZLE combo effect on
    # completely unremarkable narration. They must not match anymore — true
    # can't-miss moments are found semantically by protected_moments instead.
    segments = [
        TranscriptSegment(text="Arkadaşlar çok güzel olmadı mı sence?", start=0.0, end=3.0),
        TranscriptSegment(text="Aaa bak bu da geldi.", start=3.0, end=5.0),
        TranscriptSegment(text="Tamam bitti, hadi devam edelim.", start=5.0, end=7.0),
        TranscriptSegment(text="İşte böyle yapıyoruz.", start=7.0, end=9.0),
        TranscriptSegment(text="Dışarı çıkıyorum şimdi.", start=9.0, end=11.0),
    ]
    assert detect_keyword_highlights(segments) == []
