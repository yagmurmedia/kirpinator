from app.models import Highlight
from app.pipeline.sfx import MAX_SFX_PER_VIDEO, SFX_FOR_KIND, _select_highlights


def test_caps_at_max_and_keeps_highest_confidence():
    highlights = [
        Highlight(t=float(i), kind="loud_peak", label="x", confidence=i / 100)
        for i in range(MAX_SFX_PER_VIDEO + 5)
    ]
    selected = _select_highlights(highlights)

    assert len(selected) == MAX_SFX_PER_VIDEO
    # Kept the highest-confidence ones (largest t values here, since confidence = t/100).
    assert min(h.confidence for h in selected) > min(h.confidence for h in highlights)


def test_output_stays_chronological():
    highlights = [
        Highlight(t=5.0, kind="loud_peak", label="a", confidence=0.9),
        Highlight(t=1.0, kind="exclaim", label="b", confidence=0.9),
        Highlight(t=3.0, kind="keyword", label="c", confidence=0.9),
    ]
    selected = _select_highlights(highlights)
    assert [h.t for h in selected] == [1.0, 3.0, 5.0]


def test_ignores_kinds_without_a_mapped_sound():
    # Confidence kept below the top-tier threshold — otherwise the meme-boom
    # override (see test_high_confidence_highlight_gets_the_meme_boom_...)
    # would legitimately give it a sound regardless of kind.
    highlights = [Highlight(t=1.0, kind="something_unmapped", label="x", confidence=0.5)]
    assert _select_highlights(highlights) == []


def test_every_sfx_kind_key_has_a_generator_entry():
    from app.pipeline.sfx import _GENERATORS

    for sound_name in SFX_FOR_KIND.values():
        assert sound_name in _GENERATORS


def test_top_tier_sfx_has_a_generator_entry():
    from app.pipeline.sfx import TOP_TIER_SFX, _GENERATORS

    assert TOP_TIER_SFX in _GENERATORS


def test_high_confidence_highlight_gets_the_meme_boom_regardless_of_kind():
    from app.pipeline.sfx import TOP_TIER_SFX, _sfx_name_for

    # A "protected" moment (confidence 0.95, see protected_moments.py) should
    # get the distinct top-tier sting, not its kind's regular sound.
    h = Highlight(t=1.0, kind="protected", label="diş çıkıyor", confidence=0.95)
    assert _sfx_name_for(h) == TOP_TIER_SFX


def test_low_confidence_highlight_uses_its_kind_mapping():
    from app.pipeline.sfx import _sfx_name_for

    h = Highlight(t=1.0, kind="keyword", label="harika", confidence=0.8)
    assert _sfx_name_for(h) == SFX_FOR_KIND["keyword"]
