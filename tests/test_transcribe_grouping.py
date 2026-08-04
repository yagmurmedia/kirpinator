from app.models import WordTiming
from app.pipeline.transcribe import _group_words_into_sentences


def test_splits_on_sentence_ending_punctuation():
    words = [
        WordTiming(word="Merhaba", start=0.0, end=0.4),
        WordTiming(word="dünya.", start=0.4, end=0.8),
        WordTiming(word="Nasılsın", start=1.0, end=1.4),
        WordTiming(word="bugün?", start=1.4, end=1.8),
    ]
    segments = _group_words_into_sentences(words)

    assert len(segments) == 2
    assert segments[0].text == "Merhaba dünya."
    assert segments[1].text == "Nasılsın bugün?"


def test_splits_on_long_pause_even_without_punctuation():
    words = [
        WordTiming(word="Devam", start=0.0, end=0.4),
        WordTiming(word="ediyor", start=0.4, end=0.8),
        # 2s gap here, longer than the max-same-sentence threshold
        WordTiming(word="Sonra", start=2.8, end=3.2),
        WordTiming(word="durdu", start=3.2, end=3.6),
    ]
    segments = _group_words_into_sentences(words)

    assert len(segments) == 2
    assert segments[0].text == "Devam ediyor"
    assert segments[1].text == "Sonra durdu"


def test_preserves_word_level_timings_within_a_segment():
    words = [
        WordTiming(word="Bir", start=0.0, end=0.3),
        WordTiming(word="iki.", start=0.3, end=0.6),
    ]
    segments = _group_words_into_sentences(words)

    assert len(segments) == 1
    assert segments[0].start == 0.0
    assert segments[0].end == 0.6
    assert len(segments[0].words) == 2


def test_empty_input_returns_no_segments():
    assert _group_words_into_sentences([]) == []
