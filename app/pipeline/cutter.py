"""Cuts a source video down to a list of KeepRanges (sentence-safe) and
joins them into one continuous clip, re-encoding for frame accuracy.

Consecutive kept ranges are joined with a short crossfade (video `xfade` +
audio `acrossfade`) instead of a hard cut wherever both sides are long
enough to support one cleanly. A run of nothing but hard jump-cuts was
called out directly as looking unpolished ("edit video geçişleri" /
transitions requested) — a quick fade reads as an intentional scene change
instead of a splice.
"""
from __future__ import annotations

import subprocess

from app.models import KeepRange

XFADE_DURATION_S = 0.35
XFADE_TRANSITION = "fade"
# A crossfade eats XFADE_DURATION_S out of each side it touches, so a range
# shorter than double that would go negative/degenerate — skip the fade for
# any range that tight and fall back to a hard cut around it instead.
MIN_RANGE_FOR_XFADE_S = XFADE_DURATION_S * 2


def can_crossfade(ranges: list[KeepRange]) -> bool:
    if len(ranges) < 2:
        return False
    return all(r.duration >= MIN_RANGE_FOR_XFADE_S for r in ranges)


def build_concat_filter(ranges: list[KeepRange]) -> tuple[str, str, str]:
    """Plain hard-cut concat — the original, always-safe fallback."""
    filter_parts = []
    concat_inputs = []
    for i, r in enumerate(ranges):
        filter_parts.append(
            f"[0:v]trim=start={r.start:.3f}:end={r.end:.3f},setpts=PTS-STARTPTS[v{i}];"
        )
        filter_parts.append(
            f"[0:a]atrim=start={r.start:.3f}:end={r.end:.3f},asetpts=PTS-STARTPTS[a{i}];"
        )
        concat_inputs.append(f"[v{i}][a{i}]")

    filter_complex = "".join(filter_parts)
    filter_complex += f"{''.join(concat_inputs)}concat=n={len(ranges)}:v=1:a=1[outv][outa]"
    return filter_complex, "[outv]", "[outa]"


def crossfade_transition_times(ranges: list[KeepRange]) -> list[float]:
    """The output-timeline offset of each crossfade transition — i.e. where
    each `xfade` in build_crossfade_filter starts blending. Exposed
    separately (not just internal to the filter builder) so other stages —
    e.g. a transition sound layered on top — can place themselves exactly
    on each cut without re-deriving the same running-duration math.
    """
    if len(ranges) < 2:
        return []
    times = []
    running_dur = ranges[0].duration
    for i in range(1, len(ranges)):
        times.append(running_dur - XFADE_DURATION_S)
        running_dur = running_dur + ranges[i].duration - XFADE_DURATION_S
    return times


def build_crossfade_filter(ranges: list[KeepRange]) -> tuple[str, str, str]:
    """Chains xfade/acrossfade across every range boundary.

    Each `xfade` needs the running offset into the accumulated clip so far
    (accumulated duration minus every overlap already spent), and each
    `acrossfade` just needs the fixed duration — ffmpeg tracks the audio
    overlap point itself.
    """
    filter_parts = []
    for i, r in enumerate(ranges):
        filter_parts.append(
            f"[0:v]trim=start={r.start:.3f}:end={r.end:.3f},setpts=PTS-STARTPTS[v{i}];"
        )
        filter_parts.append(
            f"[0:a]atrim=start={r.start:.3f}:end={r.end:.3f},asetpts=PTS-STARTPTS[a{i}];"
        )

    offsets = crossfade_transition_times(ranges)
    running_v = "v0"
    running_a = "a0"
    for i in range(1, len(ranges)):
        offset = offsets[i - 1]
        out_v = f"vx{i}"
        out_a = f"ax{i}"
        filter_parts.append(
            f"[{running_v}][v{i}]xfade=transition={XFADE_TRANSITION}:"
            f"duration={XFADE_DURATION_S:.3f}:offset={offset:.3f}[{out_v}];"
        )
        filter_parts.append(
            f"[{running_a}][a{i}]acrossfade=d={XFADE_DURATION_S:.3f}[{out_a}];"
        )
        running_v, running_a = out_v, out_a

    filter_complex = "".join(filter_parts)
    return filter_complex, f"[{running_v}]", f"[{running_a}]"


def render_cut(source_path: str, ranges: list[KeepRange], output_path: str) -> str:
    if not ranges:
        raise ValueError("No KeepRanges to render — refusing to produce an empty video.")

    if len(ranges) == 1 and ranges[0].start == 0.0:
        # Nothing to trim off the head; a single -ss/-to re-encode is enough.
        r = ranges[0]
        cmd = [
            "ffmpeg", "-y",
            "-i", source_path,
            "-ss", f"{r.start:.3f}",
            "-to", f"{r.end:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    if can_crossfade(ranges):
        filter_complex, v_label, a_label = build_crossfade_filter(ranges)
    else:
        filter_complex, v_label, a_label = build_concat_filter(ranges)

    cmd = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-filter_complex", filter_complex,
        "-map", v_label, "-map", a_label,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
