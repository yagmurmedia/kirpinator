"""Turns (transcript segments + silence intervals) into a final list of KeepRanges.

Core rule the whole feature is built around: a cut can only land in a gap that is
*both* outside every transcript sentence *and* padded away from sentence
boundaries. This guarantees speech is never clipped mid-word or mid-sentence.
"""
from __future__ import annotations

from app.config import settings
from app.models import KeepRange, SilenceInterval, TranscriptSegment


def _merge_ranges(ranges: list[KeepRange]) -> list[KeepRange]:
    if not ranges:
        return []
    ranges = sorted(ranges, key=lambda r: r.start)
    merged = [ranges[0]]
    for r in ranges[1:]:
        last = merged[-1]
        if r.start <= last.end:
            merged[-1] = KeepRange(start=last.start, end=max(last.end, r.end), reason=last.reason)
        else:
            merged.append(r)
    return merged


def build_keep_ranges(
    transcript_segments: list[TranscriptSegment],
    silence_intervals: list[SilenceInterval],
    duration_s: float,
    *,
    pad_s: float | None = None,
    min_silence_duration_s: float | None = None,
) -> list[KeepRange]:
    pad_s = pad_s if pad_s is not None else settings.sentence_pad_s
    min_silence_duration_s = (
        min_silence_duration_s if min_silence_duration_s is not None else settings.min_silence_duration_s
    )

    if not transcript_segments:
        # No speech detected at all — keep everything untouched rather than risk
        # deleting non-verbal content (laughter, music, action shots).
        return [KeepRange(start=0.0, end=duration_s, reason="no_transcript")]

    # 1. Sentence keep-ranges, padded and clamped.
    speech_ranges = [
        KeepRange(
            start=max(0.0, seg.start - pad_s),
            end=min(duration_s, seg.end + pad_s),
            reason="speech",
        )
        for seg in transcript_segments
    ]
    speech_ranges = _merge_ranges(speech_ranges)

    # 2. Fill the gaps between sentences. A gap is only droppable if it's long
    #    enough AND ffmpeg's silencedetect independently confirms it's dead air —
    #    this avoids trimming quiet-but-meaningful audio (e.g. soft background sound).
    final_ranges: list[KeepRange] = []
    cursor = 0.0
    for sr in speech_ranges:
        gap_start, gap_end = cursor, sr.start
        if gap_end > gap_start:
            gap_duration = gap_end - gap_start
            is_confirmed_silence = any(
                _overlap(gap_start, gap_end, si.start, si.end) > gap_duration * 0.6
                for si in silence_intervals
            )
            if gap_duration >= min_silence_duration_s and is_confirmed_silence:
                pass  # drop this gap — confirmed dead air
            else:
                # Too short or not actually silent: keep it, merged with the
                # following sentence, rather than risk an audible jump-cut.
                final_ranges.append(KeepRange(start=gap_start, end=gap_end, reason="short_pause"))
        final_ranges.append(sr)
        cursor = sr.end

    # 3. Trailing gap after the last sentence.
    if duration_s > cursor:
        gap_duration = duration_s - cursor
        is_confirmed_silence = any(
            _overlap(cursor, duration_s, si.start, si.end) > gap_duration * 0.6
            for si in silence_intervals
        )
        if not (gap_duration >= min_silence_duration_s and is_confirmed_silence):
            final_ranges.append(KeepRange(start=cursor, end=duration_s, reason="trailing"))

    return _merge_ranges(final_ranges)


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def total_duration(ranges: list[KeepRange]) -> float:
    return sum(r.duration for r in ranges)


def trim_to_max_duration(ranges: list[KeepRange], max_duration_s: float) -> list[KeepRange]:
    """Drops whole trailing KeepRanges (never splits one) until the total fits.
    Used for the Shorts <=60s constraint. Simple earliest-first fallback for
    when there's no highlight information to prioritize by (see
    select_best_ranges for the highlight-aware version).
    """
    if total_duration(ranges) <= max_duration_s:
        return ranges
    kept: list[KeepRange] = []
    running = 0.0
    for r in ranges:
        if running + r.duration > max_duration_s:
            break
        kept.append(r)
        running += r.duration
    return kept or ranges[:1]


def select_best_ranges(
    ranges: list[KeepRange],
    highlight_timestamps: list[tuple[float, float]],
    max_duration_s: float,
    *,
    protected_timestamps: list[float] | None = None,
) -> list[KeepRange]:
    """Picks the subset of KeepRanges that packs in the most/highest-confidence
    highlight moments (loud reactions, exclamations) within the Shorts budget,
    instead of blindly keeping whichever sentences happen to come first.

    `highlight_timestamps` is a list of (t, confidence) pairs on the SAME
    timeline as `ranges` (i.e. the original source video, before any cutting).
    Ranges are still emitted in chronological order so the final edit still
    plays back naturally — only *which* sentences survive is reprioritized.

    `protected_timestamps` (from app.pipeline.protected_moments — a user
    instruction matched against the transcript) are guaranteed a spot
    regardless of how the generic highlight scoring would otherwise rate
    them; this can push the total slightly over max_duration_s rather than
    silently drop something the user explicitly said not to cut.
    """
    if total_duration(ranges) <= max_duration_s:
        return ranges

    protected_timestamps = protected_timestamps or []
    protected_ranges = [
        r for r in ranges if any(r.start <= t <= r.end for t in protected_timestamps)
    ]
    other_ranges = [r for r in ranges if r not in protected_ranges]

    selected = list(protected_ranges)
    running = total_duration(protected_ranges)

    if highlight_timestamps:
        def score(r: KeepRange) -> float:
            return sum(conf for t, conf in highlight_timestamps if r.start <= t <= r.end)

        other_ranges = sorted(other_ranges, key=score, reverse=True)

    for r in other_ranges:
        if running + r.duration > max_duration_s:
            continue
        selected.append(r)
        running += r.duration

    if not selected:
        return trim_to_max_duration(ranges, max_duration_s)
    return sorted(selected, key=lambda r: r.start)
