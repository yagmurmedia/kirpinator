"""Cuts a source video down to a list of KeepRanges (sentence-safe) and
concatenates them into one continuous clip, re-encoding for frame accuracy.
"""
from __future__ import annotations

import subprocess

from app.models import KeepRange


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
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

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

    cmd = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
