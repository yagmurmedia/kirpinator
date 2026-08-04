"""Turns Highlight events into concrete ffmpeg filter fragments and applies them.

Three effect types, chained into one filter graph and rendered in a single
pass:
  - zoom "punch": every highlight gets a quick, snappy zoom-in-then-out beat
    (the actual visual reads as "impact" in most editing styles) — built as
    one continuous scale/crop expression covering the whole clip rather than
    N independently-gated filters, which avoids a real bug we hit earlier:
    naively toggling `scale` on/off per-highlight with `enable=` leaves
    `crop`'s width/height referencing the *current* (possibly un-scaled)
    frame size on the frames in between, silently cropping the entire video
    down. A single expression that's just 1.0 outside the punch windows
    sidesteps that.
  - brightness/contrast/saturation "pop": layered on top of the zoom for loud
    moments, for extra punch.
  - bold on-screen text sticker for keyword-triggered highlights.
"""
from __future__ import annotations

import subprocess

from app.models import Highlight

POP_DURATION_S = 0.18
POP_BRIGHTNESS = 0.35
POP_CONTRAST = 1.25
POP_SATURATION = 1.6

ZOOM_PUNCH_DURATION_S = 0.35
ZOOM_PUNCH_AMOUNT = 0.14  # peak zoom = 1 + this, e.g. 0.14 -> 114%

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


def _zoom_expr(highlights: list[Highlight]) -> str:
    """One expression, evaluated every frame, that's 1.0 except for a brief
    smooth (sine-shaped) bump to 1+ZOOM_PUNCH_AMOUNT around each highlight.
    Punches are short and highlight_detector already enforces a minimum gap
    between highlights, so simple summation (no overlap in practice) is safe.
    """
    if not highlights:
        return "1"
    terms = []
    for h in highlights:
        start, end = h.t, h.t + ZOOM_PUNCH_DURATION_S
        terms.append(f"if(between(t,{start:.3f},{end:.3f}),sin(PI*(t-{start:.3f})/{ZOOM_PUNCH_DURATION_S}),0)")
    return f"1+{ZOOM_PUNCH_AMOUNT}*(" + "+".join(terms) + ")"


def _zoom_punch_filter(highlights: list[Highlight], width: int, height: int) -> str | None:
    zoomable = [h for h in highlights if h.kind in ("loud_peak", "exclaim", "keyword")]
    if not zoomable:
        return None
    expr = _zoom_expr(zoomable)
    # Scale up by the (time-varying) zoom factor, then crop back down to the
    # exact, fixed output size — crop's target is a constant, not iw/ih, so
    # frames where the zoom is 1.0 crop out exactly the original frame.
    return (
        f"scale=w='trunc(iw*({expr})/2)*2':h='trunc(ih*({expr})/2)*2':eval=frame,"
        f"crop={width}:{height}"
    )


def build_effects_filter(
    highlights: list[Highlight],
    width: int,
    height: int,
    font_path: str = FONT_CANDIDATES[0],
) -> str | None:
    if not highlights:
        return None
    filters = []
    zoom = _zoom_punch_filter(highlights, width, height)
    if zoom:
        filters.append(zoom)
    for h in highlights:
        if h.kind in ("loud_peak", "exclaim"):
            filters.append(_pop_filter(h))
        elif h.kind == "keyword":
            filters.append(_sticker_filter(h, font_path))
    return ",".join(filters) if filters else None


def render_effects(input_path: str, output_path: str, highlights: list[Highlight], width: int, height: int) -> str:
    filter_str = build_effects_filter(highlights, width, height)
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
