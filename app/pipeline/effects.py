"""Turns Highlight events into concrete ffmpeg filter fragments and applies them.

v1 effects are deliberately simple and cheap to reason about:
  - loud_peak / exclaim -> quick brightness "pop" (reads as an emphasis beat)
  - keyword               -> short on-screen text sticker with the matched word

Both are plain filters gated with `enable='between(t,...)'`, so any number of
highlights can be chained into a single filter graph and rendered in one pass.
"""
from __future__ import annotations

import subprocess

from app.models import Highlight

POP_DURATION_S = 0.18
POP_BRIGHTNESS = 0.35
POP_CONTRAST = 1.25
POP_SATURATION = 1.6
STICKER_DURATION_S = 1.3
FONT_CANDIDATES = [
    "C\\:/Windows/Fonts/arialbd.ttf",
    "C\\:/Windows/Fonts/arial.ttf",
]
# NOTE: deliberately no emoji here — Arial has no emoji glyphs, and drawtext
# rendered them as empty tofu boxes when tested (verified against a real
# ffmpeg frame render, not assumed). Bold colored text + outline reads as a
# "pop" just as well without the risk of a broken-looking glyph.


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _pop_filter(h: Highlight) -> str:
    start, end = h.t, h.t + POP_DURATION_S
    return (
        f"eq=brightness={POP_BRIGHTNESS}:contrast={POP_CONTRAST}:saturation={POP_SATURATION}"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def _sticker_filter(h: Highlight, font_path: str) -> str:
    start, end = h.t, h.t + STICKER_DURATION_S
    label = _escape_drawtext(f"» {h.label.upper()} «")
    return (
        "drawtext="
        f"fontfile='{font_path}':text='{label}':"
        "fontcolor=0xFFD400:fontsize=70:borderw=5:bordercolor=black@0.9:"
        "x=(w-text_w)/2:y=h*0.76:"
        f"enable='between(t,{start:.3f},{end:.3f})'"
    )


def build_effects_filter(highlights: list[Highlight], font_path: str = FONT_CANDIDATES[0]) -> str | None:
    if not highlights:
        return None
    filters = []
    for h in highlights:
        if h.kind in ("loud_peak", "exclaim"):
            filters.append(_pop_filter(h))
        elif h.kind == "keyword":
            filters.append(_sticker_filter(h, font_path))
    return ",".join(filters) if filters else None


def render_effects(input_path: str, output_path: str, highlights: list[Highlight]) -> str:
    filter_str = build_effects_filter(highlights)
    if not filter_str:
        # Nothing to do — just copy through untouched.
        cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:v", filter_str,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
