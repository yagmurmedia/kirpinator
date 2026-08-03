from app.models import KeepRange
from app.pipeline.segment_planner import select_best_ranges, total_duration


def test_picks_highlight_dense_ranges_over_earliest():
    ranges = [
        KeepRange(start=0.0, end=10.0),   # no highlights, would be picked by naive earliest-first
        KeepRange(start=20.0, end=28.0),  # two strong highlights
        KeepRange(start=40.0, end=48.0),  # one weak highlight
    ]
    highlights = [(22.0, 0.9), (25.0, 0.9), (44.0, 0.3)]

    selected = select_best_ranges(ranges, highlights, max_duration_s=8.0)

    assert len(selected) == 1
    assert selected[0].start == 20.0  # the highlight-dense range, not the first one


def test_output_stays_chronological_even_when_highlights_favor_later_range():
    ranges = [
        KeepRange(start=0.0, end=5.0),
        KeepRange(start=10.0, end=15.0),
    ]
    highlights = [(1.0, 0.9), (12.0, 0.9)]

    selected = select_best_ranges(ranges, highlights, max_duration_s=100.0)

    # Both fit within budget, so both should be kept, in original order.
    assert [r.start for r in selected] == [0.0, 10.0]


def test_no_highlights_falls_back_to_earliest_first():
    ranges = [KeepRange(start=0.0, end=10.0), KeepRange(start=20.0, end=30.0)]
    selected = select_best_ranges(ranges, [], max_duration_s=10.0)
    assert len(selected) == 1
    assert selected[0].start == 0.0


def test_under_budget_returns_all_ranges_unchanged():
    ranges = [KeepRange(start=0.0, end=5.0), KeepRange(start=10.0, end=12.0)]
    selected = select_best_ranges(ranges, [(1.0, 0.9)], max_duration_s=60.0)
    assert selected == ranges
    assert total_duration(selected) == 7.0
