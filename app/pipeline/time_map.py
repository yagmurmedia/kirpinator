"""Maps timestamps from the original source timeline into the post-cut timeline.

Because KeepRanges are built directly from (padded, merged) transcript
sentences, every transcript segment is guaranteed to fall entirely inside
exactly one KeepRange — cutting only ever removes the gaps *between*
sentences, never part of one. That guarantee is what makes this a safe,
lossless remap instead of an approximation.
"""
from __future__ import annotations

from app.models import KeepRange


def build_time_mapper(ranges: list[KeepRange], *, crossfade_s: float = 0.0):
    """`crossfade_s` must match whatever cutter.render_cut actually used —
    each crossfade transition eats that many seconds out of the output
    timeline (see cutter.build_crossfade_filter's offset math), so every
    range after the first needs its offset shifted back by one
    crossfade_s per transition or captions/effects drift out of sync with
    the real video more and more with each cut.
    """
    ranges = sorted(ranges, key=lambda r: r.start)
    offsets = []
    running = 0.0
    for i, r in enumerate(ranges):
        offsets.append(running)
        running += r.duration
        if crossfade_s > 0 and i < len(ranges) - 1:
            running -= crossfade_s

    def map_time(t: float) -> float:
        for r, offset in zip(ranges, offsets):
            if r.start <= t <= r.end:
                return offset + (t - r.start)
        # Fell in a removed gap (shouldn't happen for sentence starts, but be safe):
        # snap to the nearest range edge.
        before = [(r, o) for r, o in zip(ranges, offsets) if r.end <= t]
        if before:
            r, o = before[-1]
            return o + r.duration
        return 0.0

    return map_time
