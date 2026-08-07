from app.models import Highlight
from app.pipeline.effects import build_effects_filter


def test_no_highlights_returns_none():
    assert build_effects_filter([], 1080, 1920) is None


def test_non_top_tier_loud_peak_gets_no_visual_effect():
    # Deliberate design: an ordinary loud/exclaim moment that isn't one of
    # the top-confidence highlights gets NO visual effect at all — no
    # invented substitute for the removed flash/vignette/color-pop.
    highlights = [Highlight(t=float(i), kind="loud_peak", label="x", confidence=0.9) for i in range(4)]
    highlights.append(Highlight(t=10.0, kind="loud_peak", label="ordinary", confidence=0.3))

    filt = build_effects_filter(highlights, 1080, 1920)

    assert "enable='between(t,10.000" not in filt


def test_keyword_gets_text_sticker():
    # Several higher-confidence filler highlights so the keyword one (0.3)
    # isn't itself promoted to the top tier — isolates the plain
    # "keyword -> sticker" behavior from the separate top-tier behavior
    # (covered by its own tests below).
    highlights = [Highlight(t=float(i), kind="loud_peak", label="x", confidence=0.9) for i in range(4)]
    highlights.append(Highlight(t=10.0, kind="keyword", label="harika", confidence=0.3))
    filt = build_effects_filter(highlights, 1080, 1920)

    assert "drawtext=" in filt
    assert "HARIKA" in filt
    assert filt.count("enable='between(t,10.000") == 1


def test_top_tier_highlight_gets_the_izle_callout_only():
    # Five loud_peak highlights so TOP_TIER_COUNT=4 genuinely excludes one
    # (the lowest-confidence one at t=1.0), isolating "top-tier" from
    # "ordinary, no effect" behavior.
    highlights = [
        Highlight(t=1.0, kind="loud_peak", label="ordinary", confidence=0.2),
        Highlight(t=2.0, kind="loud_peak", label="best", confidence=0.99),
        Highlight(t=20.0, kind="loud_peak", label="c", confidence=0.9),
        Highlight(t=30.0, kind="loud_peak", label="d", confidence=0.85),
        Highlight(t=40.0, kind="loud_peak", label="e", confidence=0.8),
    ]
    filt = build_effects_filter(highlights, 1080, 1920)

    # The top-tier moment gets a text callout only — no full-frame visual
    # effect of any kind (flash/vignette/color-pop were all removed and
    # deliberately not replaced with anything else).
    assert filt.count("enable='between(t,2.000") == 1
    assert "eq=brightness=" not in filt
    assert "vignette=" not in filt
    assert "hue=" not in filt
    assert "İZLE" in filt
    # And the one bumped out of the top tier gets nothing at all.
    assert "enable='between(t,1.000" not in filt


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


def test_many_keyword_highlights_never_crashed_ffmpeg_in_practice():
    # Regression guard: an earlier combined-zoom-expression design crashed a
    # real ffmpeg build (access violation) on exactly this kind of dense,
    # many-highlight input — confirmed and reproduced on a real render before
    # being pulled. These simple independently-gated filters don't share that
    # failure mode; this test just locks in that the filter list still builds
    # cleanly for a large highlight count.
    highlights = [
        Highlight(t=float(i) * 1.5, kind="keyword", label="x", confidence=0.5 + i * 0.01)
        for i in range(15)
    ]
    filt = build_effects_filter(highlights, 1920, 1080)
    assert filt is not None
    assert filt.count("enable=") == 15
