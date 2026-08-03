"""Applies a time-varying crop path (from face_tracker) to re-frame a clip into
the target aspect ratio, then scales/pads to the exact output resolution.

Implemented with ffmpeg's sendcmd filter, which lets us change a named filter's
parameters (crop x/y) at specific timestamps — the standard ffmpeg technique
for keyframed, non-uniform crop panning without external tools.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import CropKeyframe


def _build_sendcmd_script(keyframes: list[CropKeyframe]) -> str:
    lines = []
    for kf in keyframes:
        lines.append(f"{kf.t:.3f} crop@panner x {kf.x}, crop@panner y {kf.y};")
    return "\n".join(lines)


def render_crop(
    input_path: str,
    output_path: str,
    keyframes: list[CropKeyframe],
    output_w: int,
    output_h: int,
    *,
    work_dir: str,
) -> str:
    if not keyframes:
        raise ValueError("No crop keyframes provided.")

    cmds_path = Path(work_dir) / "crop_cmds.txt"
    cmds_path.write_text(_build_sendcmd_script(keyframes), encoding="utf-8")

    w0, h0 = keyframes[0].w, keyframes[0].h
    # sendcmd paths on Windows need forward slashes and escaped colons inside the filtergraph.
    cmds_ff_path = str(cmds_path).replace("\\", "/").replace(":", "\\:")

    filter_complex = (
        f"sendcmd=f='{cmds_ff_path}',"
        f"crop@panner=w={w0}:h={h0}:x={keyframes[0].x}:y={keyframes[0].y},"
        f"scale={output_w}:{output_h}:flags=lanczos,"
        f"setsar=1"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:v", filter_complex,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
