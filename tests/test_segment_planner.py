from app.models import SilenceInterval, TranscriptSegment
from app.pipeline.segment_planner import build_keep_ranges, total_duration, trim_to_max_duration


def _seg(text, start, end):
    return TranscriptSegment(text=text, start=start, end=end, words=[])


def test_drops_confirmed_dead_air_between_sentences():
    segments = [_seg("Merhaba.", 0.0, 2.0), _seg("Bugun hava cok guzel.", 10.0, 13.0)]
    silences = [SilenceInterval(start=2.2, end=9.8)]
    ranges = build_keep_ranges(segments, silences, duration_s=13.0, pad_s=0.1, min_silence_duration_s=0.6)

    # The long confirmed-silent gap must be gone; both sentences fully preserved.
    assert total_duration(ranges) < 13.0
    assert any(r.start <= 0.0 <= r.end + 0.01 for r in ranges)
    covered = [(r.start, r.end) for r in ranges]
    assert any(a <= 0.0 and b >= 2.0 for a, b in covered)
    assert any(a <= 10.0 and b >= 13.0 for a, b in covered)


def test_never_cuts_inside_a_sentence_even_if_quiet():
    # A "silent" span reported by ffmpeg that overlaps a spoken sentence must never
    # cause that sentence's own time range to be dropped.
    segments = [_seg("Uzun bir cumle soyluyorum simdi.", 0.0, 5.0)]
    silences = [SilenceInterval(start=1.0, end=1.8)]  # a brief in-sentence quiet dip
    ranges = build_keep_ranges(segments, silences, duration_s=5.0, pad_s=0.1)

    assert len(ranges) == 1
    assert ranges[0].start <= 0.0
    assert ranges[0].end >= 5.0


def test_short_gap_is_kept_not_dropped():
    segments = [_seg("Bir.", 0.0, 1.0), _seg("Iki.", 1.3, 2.3)]
    silences = [SilenceInterval(start=1.05, end=1.25)]  # too short to count as dead air
    ranges = build_keep_ranges(segments, silences, duration_s=2.3, pad_s=0.05, min_silence_duration_s=0.6)

    assert total_duration(ranges) == 2.3 - ranges[0].start  # nothing dropped in the middle
    assert len(ranges) == 1


def test_no_transcript_keeps_everything():
    ranges = build_keep_ranges([], [SilenceInterval(0, 5)], duration_s=10.0)
    assert len(ranges) == 1
    assert ranges[0].start == 0.0
    assert ranges[0].end == 10.0


def test_trim_to_max_duration_drops_whole_trailing_ranges_only():
    # Each sentence is 1.5s, separated by a 1.0s confirmed-silent gap so
    # build_keep_ranges actually drops the gaps and leaves 10 distinct ranges.
    segments = [_seg(f"Cumle {i}.", i * 2.5, i * 2.5 + 1.5) for i in range(10)]
    silences = [SilenceInterval(start=i * 2.5 + 1.5, end=i * 2.5 + 2.5) for i in range(9)]
    ranges = build_keep_ranges(segments, silences, duration_s=24.0, pad_s=0.0)
    assert len(ranges) == 10  # sanity check on the fixture itself

    trimmed = trim_to_max_duration(ranges, max_duration_s=6.0)

    assert total_duration(trimmed) <= 6.0
    # Every kept range must be an exact, untouched original range (no mid-sentence trim).
    original_starts = {r.start for r in ranges}
    assert all(r.start in original_starts for r in trimmed)
