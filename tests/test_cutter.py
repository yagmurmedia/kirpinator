from app.models import KeepRange
from app.pipeline.cutter import (
    MIN_RANGE_FOR_XFADE_S,
    XFADE_DURATION_S,
    build_concat_filter,
    build_crossfade_filter,
    can_crossfade,
)


def test_single_range_cannot_crossfade():
    assert can_crossfade([KeepRange(start=0.0, end=10.0)]) is False


def test_short_range_falls_back_to_concat():
    ranges = [KeepRange(start=0.0, end=10.0), KeepRange(start=20.0, end=20.0 + MIN_RANGE_FOR_XFADE_S / 2)]
    assert can_crossfade(ranges) is False


def test_two_long_ranges_can_crossfade():
    ranges = [KeepRange(start=0.0, end=10.0), KeepRange(start=20.0, end=30.0)]
    assert can_crossfade(ranges) is True


def test_crossfade_filter_chains_offsets_correctly():
    ranges = [
        KeepRange(start=0.0, end=10.0),   # duration 10
        KeepRange(start=20.0, end=28.0),  # duration 8
        KeepRange(start=40.0, end=45.0),  # duration 5
    ]
    filter_complex, v_label, a_label = build_crossfade_filter(ranges)

    # First xfade offset = 10 - 0.35 = 9.65
    assert "offset=9.650" in filter_complex
    # Running duration after first fade = 10 + 8 - 0.35 = 17.65;
    # second xfade offset = 17.65 - 0.35 = 17.300
    assert "offset=17.300" in filter_complex
    assert filter_complex.count("xfade=") == 2
    assert filter_complex.count("acrossfade=") == 2
    assert v_label == "[vx2]"
    assert a_label == "[ax2]"


def test_concat_filter_still_available_as_fallback():
    ranges = [KeepRange(start=0.0, end=1.0), KeepRange(start=5.0, end=5.2)]
    filter_complex, v_label, a_label = build_concat_filter(ranges)
    assert "concat=n=2:v=1:a=1" in filter_complex
    assert v_label == "[outv]"
    assert a_label == "[outa]"
