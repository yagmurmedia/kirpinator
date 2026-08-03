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
