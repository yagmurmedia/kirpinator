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


def test_protected_range_survives_even_with_zero_highlight_score():
    # Real scenario: "diş çıkma anı" is said flatly, no loud audio peak and
    # no fixed-keyword match, so the generic scorer would never pick it —
    # protected_timestamps must guarantee it a spot anyway.
    ranges = [
        KeepRange(start=0.0, end=10.0),   # loud, would normally win on score
        KeepRange(start=20.0, end=22.0),  # the quiet but important moment
    ]
    highlights = [(2.0, 0.9), (5.0, 0.9)]  # all inside the first range

    selected = select_best_ranges(
        ranges, highlights, max_duration_s=10.0, protected_timestamps=[21.0]
    )

    assert any(r.start == 20.0 for r in selected)


def test_protected_range_can_exceed_budget_rather_than_be_dropped():
    ranges = [KeepRange(start=0.0, end=15.0)]
    selected = select_best_ranges(ranges, [], max_duration_s=5.0, protected_timestamps=[7.0])
    assert selected == [ranges[0]]  # kept whole, even though 15s > 5s budget


def test_hook_seconds_keeps_quiet_intro_over_louder_later_range():
    # Real scenario: the opening seconds are the most eye-catching part of the
    # video but have no loud audio peak/keyword yet, so the generic scorer
    # would drop them in favor of a louder range that comes later.
    ranges = [
        KeepRange(start=0.0, end=8.0),    # quiet intro, no highlights
        KeepRange(start=20.0, end=28.0),  # loud, would normally win outright
    ]
    highlights = [(22.0, 0.9), (25.0, 0.9)]

    selected = select_best_ranges(ranges, highlights, max_duration_s=8.0, hook_seconds=10.0)

    assert any(r.start == 0.0 for r in selected)


def test_hook_seconds_zero_keeps_old_behavior():
    ranges = [KeepRange(start=0.0, end=8.0), KeepRange(start=20.0, end=28.0)]
    highlights = [(22.0, 0.9), (25.0, 0.9)]
    selected = select_best_ranges(ranges, highlights, max_duration_s=8.0)
    assert selected[0].start == 20.0
