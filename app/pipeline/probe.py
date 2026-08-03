"""ffprobe wrapper: detects orientation, resolution, fps, codec, duration, HDR."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class ProbeResult:
    width: int
    height: int
    fps: float
    duration_s: float
    codec: str
    audio_codec: str | None
    is_hdr: bool
    orientation: str  # "vertical" | "horizontal" | "square"

    @property
    def target_size(self) -> tuple[int, int]:
        from app.config import settings

        if self.orientation == "vertical":
            w, h = settings.target_aspect_vertical.split("x")
        else:
            w, h = settings.target_aspect_horizontal.split("x")
        return int(w), int(h)


def _run_ffprobe(path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _parse_fps(rate_str: str) -> float:
    if "/" in rate_str:
        num, den = rate_str.split("/")
        den = float(den) or 1.0
        return float(num) / den
    return float(rate_str)


def probe_video(path: str) -> ProbeResult:
    data = _run_ffprobe(path)
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    audio_stream = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)

    width = int(video_stream["width"])
    height = int(video_stream["height"])
    # Respect rotation metadata (phones often store landscape frames + a 90deg rotate tag).
    rotation = 0
    side_data = video_stream.get("side_data_list", [])
    for sd in side_data:
        if "rotation" in sd:
            rotation = abs(int(sd["rotation"]))
    tags_rotate = int(video_stream.get("tags", {}).get("rotate", 0) or 0)
    if tags_rotate in (90, 270):
        rotation = tags_rotate
    if rotation in (90, 270):
        width, height = height, width

    duration_s = float(data["format"].get("duration") or video_stream.get("duration") or 0.0)
    fps = _parse_fps(video_stream.get("avg_frame_rate", "0/1")) or _parse_fps(
        video_stream.get("r_frame_rate", "30/1")
    )

    color_transfer = video_stream.get("color_transfer", "")
    is_hdr = color_transfer in ("smpte2084", "arib-std-b67") or "hdr" in (
        video_stream.get("codec_tag_string", "").lower()
    )

    if width > height:
        orientation = "horizontal"
    elif height > width:
        orientation = "vertical"
    else:
        orientation = "square"

    return ProbeResult(
        width=width,
        height=height,
        fps=round(fps, 3),
        duration_s=duration_s,
        codec=video_stream.get("codec_name", ""),
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        is_hdr=is_hdr,
        orientation=orientation,
    )
