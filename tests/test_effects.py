from app.models import Highlight
from app.pipeline.effects import build_effects_filter


def test_no_highlights_returns_none():
    assert build_effects_filter([], 1080, 1920) is None


def test_loud_peak_gets_a_punch_filter():
    highlights = [Highlight(t=2.0, kind="loud_peak", label="loud", confidence=0.7)]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "eq=brightness=" in filt or "vignette=" in filt


def test_keyword_gets_text_sticker_not_a_punch_filter():
    highlights = [Highlight(t=1.0, kind="keyword", label="harika", confidence=0.9)]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "drawtext=" in filt
    assert "HARIKA" in filt
    assert "eq=brightness=" not in filt
    assert "vignette=" not in filt


def test_consecutive_punches_alternate_style():
    highlights = [
        Highlight(t=1.0, kind="loud_peak", label="a", confidence=0.7),
        Highlight(t=2.0, kind="exclaim", label="b", confidence=0.7),
    ]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "eq=brightness=" in filt
    assert "vignette=" in filt


def test_many_highlights_never_crashed_ffmpeg_in_practice():
    # Regression guard: an earlier combined-zoom-expression design crashed a
    # real ffmpeg build (access violation) on exactly this kind of dense,
    # many-highlight input — confirmed and reproduced on a real render before
    # being pulled. These simple independently-gated filters don't share that
    # failure mode; this test just locks in that the filter list still builds
    # cleanly for a large highlight count.
    highlights = [
        Highlight(t=float(i) * 1.5, kind="loud_peak", label="x", confidence=0.5 + i * 0.01)
        for i in range(15)
    ]
    filt = build_effects_filter(highlights, 1920, 1080)
    assert filt is not None
    assert filt.count("enable=") >= 15
