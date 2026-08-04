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
    highlights = [Highlight(t=1.0, kind="something_unmapped", label="x", confidence=0.9)]
    assert _select_highlights(highlights) == []


def test_every_sfx_kind_key_has_a_generator_entry():
    from app.pipeline.sfx import _GENERATORS

    for sound_name in SFX_FOR_KIND.values():
        assert sound_name in _GENERATORS
