from app.models import KeepRange
from app.pipeline.time_map import build_time_mapper


def test_maps_times_across_dropped_gaps():
    ranges = [KeepRange(start=0.0, end=2.0), KeepRange(start=10.0, end=13.0)]
    m = build_time_mapper(ranges)

    assert m(0.0) == 0.0
    assert abs(m(1.0) - 1.0) < 1e-6
    assert abs(m(2.0) - 2.0) < 1e-6
    # 10.0 in the source timeline immediately follows the first kept range in the output.
    assert abs(m(10.0) - 2.0) < 1e-6
    assert abs(m(11.5) - 3.5) < 1e-6
    assert abs(m(13.0) - 5.0) < 1e-6


def test_crossfade_s_shifts_offsets_to_match_actual_overlapped_output():
    # Mirrors cutter.build_crossfade_filter's offset math exactly: each
    # transition eats crossfade_s out of the output timeline, so later
    # ranges must start crossfade_s earlier than a naive concat would map
    # them to, or captions/effects drift out of sync with the real video.
    ranges = [
        KeepRange(start=0.0, end=10.0),   # duration 10
        KeepRange(start=20.0, end=28.0),  # duration 8
        KeepRange(start=40.0, end=45.0),  # duration 5
    ]
    m = build_time_mapper(ranges, crossfade_s=0.35)

    assert abs(m(0.0) - 0.0) < 1e-6
    # Second range starts at output offset (10 - 0.35), matching cutter's xfade offset.
    assert abs(m(20.0) - 9.65) < 1e-6
    # Third range starts at (10 + 8 - 2*0.35).
    assert abs(m(40.0) - 17.3) < 1e-6
