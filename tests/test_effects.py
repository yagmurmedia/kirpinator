from app.models import Highlight
from app.pipeline.effects import build_effects_filter


def test_no_highlights_returns_none():
    assert build_effects_filter([], 1080, 1920) is None


def test_loud_peak_gets_a_punch_filter():
    highlights = [Highlight(t=2.0, kind="loud_peak", label="loud", confidence=0.7)]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "hue=" in filt


def test_keyword_gets_text_sticker_not_a_punch_filter():
    # Several higher-confidence filler highlights so the keyword one (0.3)
    # isn't itself promoted to the top tier — this isolates the plain
    # "keyword -> sticker only" behavior from the separate top-tier combo
    # behavior (covered by its own tests below).
    highlights = [Highlight(t=float(i), kind="loud_peak", label="x", confidence=0.9) for i in range(4)]
    highlights.append(Highlight(t=10.0, kind="keyword", label="harika", confidence=0.3))
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "drawtext=" in filt
    assert "HARIKA" in filt
    assert filt.count("enable='between(t,10.000") == 1  # sticker only, not the top-tier combo


def test_consecutive_loud_peaks_both_get_the_color_pop():
    highlights = [
        Highlight(t=1.0, kind="loud_peak", label="a", confidence=0.7),
        Highlight(t=2.0, kind="exclaim", label="b", confidence=0.7),
    ]
    filt = build_effects_filter(highlights, 1080, 1920)

    assert filt.count("hue=") == 2


def test_top_tier_highlight_gets_combo_treatment():
    highlights = [
        Highlight(t=1.0, kind="loud_peak", label="a", confidence=0.2),
        Highlight(t=2.0, kind="loud_peak", label="best", confidence=0.99),
    ]
    filt = build_effects_filter(highlights, 1080, 1920)

    # The top-tier moment gets the color pop + a callout label, not a
    # brightness flash or vignette darkening (dropped per user feedback).
    assert filt.count("enable='between(t,2.000") == 2
    assert "eq=brightness=" not in filt
    assert "vignette=" not in filt
    assert "İZLE" in filt


def test_top_tier_included_even_if_visual_cap_would_exclude_it():
    # 25 low-confidence highlights (over the visual cap) plus one clear best —
    # the best one must not get silently dropped by the cap.
    from app.pipeline.effects import MAX_VISUAL_EFFECT_HIGHLIGHTS

    highlights = [
        Highlight(t=float(i), kind="loud_peak", label="x", confidence=0.1)
        for i in range(MAX_VISUAL_EFFECT_HIGHLIGHTS + 5)
    ]
    highlights.append(Highlight(t=999.0, kind="loud_peak", label="best", confidence=0.99))

    filt = build_effects_filter(highlights, 1080, 1920)
    assert "999.000" in filt
    assert "İZLE" in filt


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
