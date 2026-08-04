from app.models import Highlight
from app.pipeline.effects import build_effects_filter


def test_no_highlights_returns_none():
    assert build_effects_filter([], 1080, 1920) is None


def test_loud_peak_gets_zoom_and_brightness_pop():
    highlights = [Highlight(t=2.0, kind="loud_peak", label="loud", confidence=0.7)]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "scale=" in filt
    assert "crop=1080:1920" in filt  # crops back to the fixed output size, not iw/ih
    assert "eq=brightness=" in filt


def test_keyword_gets_zoom_and_text_sticker_not_brightness_pop():
    highlights = [Highlight(t=1.0, kind="keyword", label="harika", confidence=0.9)]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "drawtext=" in filt
    assert "HARIKA" in filt
    assert "eq=brightness=" not in filt


def test_zoom_expression_is_1_outside_punch_windows():
    highlights = [Highlight(t=5.0, kind="loud_peak", label="loud", confidence=0.7)]
    filt = build_effects_filter(highlights, 640, 360)

    # The scale expression must fall back to a factor of 1 (i.e. the `if(...,...,0)`
    # else-branch) when t isn't inside the highlight's punch window — this is
    # what keeps non-punch frames at the original, uncropped size.
    assert ",0)" in filt


def test_multiple_highlights_each_get_their_own_punch_window():
    highlights = [
        Highlight(t=1.0, kind="loud_peak", label="a", confidence=0.7),
        Highlight(t=10.0, kind="exclaim", label="b", confidence=0.5),
    ]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "1.000" in filt
    assert "10.000" in filt
