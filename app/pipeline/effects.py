"""Turns Highlight events into concrete ffmpeg filter fragments and applies them.

Three visual "punch" styles, cycled across highlights for variety, plus a
text sticker for keyword hits:
  - brightness/contrast/saturation pop (bright, punchy flash)
  - vignette pulse (quick radial darkening — reads as a focus/impact beat)
  - chroma pop (a quick saturation/hue spike — colorful, distinct from the
    other two, reads as a "pow!" beat)

Both are simple, independently-gated `enable='between(t,...)'` filters with
no shared/combined expression. A real ffmpeg build crash (access violation)
was hit and confirmed on a real render while an earlier version of this
module tried a single combined time-varying zoom expression (`scale`
with `eval=frame`) — it reproduced consistently for specific highlight
timing patterns regardless of how few highlights were combined, so that
whole approach was pulled rather than chasing an unbounded-risk ffmpeg bug.
Simple per-highlight filters like these have run reliably across many real
video renders.
"""
from __future__ import annotations

import subprocess

from app.models import Highlight

POP_DURATION_S = 0.18
POP_BRIGHTNESS = 0.35
POP_CONTRAST = 1.25
POP_SATURATION = 1.6

VIGNETTE_DURATION_S = 0.22

CHROMA_DURATION_S = 0.16
CHROMA_SATURATION = 2.4
CHROMA_HUE_DEGREES = 25

STICKER_DURATION_S = 1.3
FONT_CANDIDATES = [
    "C\\:/Windows/Fonts/arialbd.ttf",
    "C\\:/Windows/Fonts/arial.ttf",
]
# NOTE: deliberately no emoji here — Arial has no emoji glyphs, and drawtext
# rendered them as empty tofu boxes when tested (verified against a real
# ffmpeg frame render, not assumed). Bold colored text + outline reads as a
# "pop" just as well without the risk of a broken-looking glyph.

# A very long, highlight-heavy video chains a lot of these filters together;
# kept modest as a sanity cap on total command-line/graph size even though
# these simple per-highlight filters haven't shown the crash the combined
# zoom expression did.
MAX_VISUAL_EFFECT_HIGHLIGHTS = 20

# A long video can rack up hundreds of highlights (a 13-minute source hit 298
# in practice) — giving every single one the same small punch reads as flat.
# The handful of genuinely highest-confidence moments get a stronger, distinct
# treatment (pop + vignette together, plus a callout label) instead of just
# another beat in a long, uniform sequence.
TOP_TIER_COUNT = 4
TOP_TIER_LABEL = "İZLE"
TOP_TIER_STICKER_DURATION_S = 1.0


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _pop_filter(h: Highlight) -> str:
    start, end = h.t, h.t + POP_DURATION_S
    return (
        f"eq=brightness={POP_BRIGHTNESS}:contrast={POP_CONTRAST}:saturation={POP_SATURATION}"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def _vignette_filter(h: Highlight) -> str:
    start, end = h.t, h.t + VIGNETTE_DURATION_S
    return f"vignette=angle=PI/3:enable='between(t,{start:.3f},{end:.3f})'"


def _chroma_filter(h: Highlight) -> str:
    start, end = h.t, h.t + CHROMA_DURATION_S
    return (
        f"hue=h={CHROMA_HUE_DEGREES}:s={CHROMA_SATURATION}"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def _sticker_filter(h: Highlight, font_path: str, label: str | None = None, duration: float = STICKER_DURATION_S) -> str:
    start, end = h.t, h.t + duration
    text = _escape_drawtext(f"» {(label or h.label).upper()} «")
    return (
        "drawtext="
        f"fontfile='{font_path}':text='{text}':"
        "fontcolor=0xFFD400:fontsize=70:borderw=5:bordercolor=black@0.9:"
        "x=(w-text_w)/2:y=h*0.76:"
        f"enable='between(t,{start:.3f},{end:.3f})'"
    )


def build_effects_filter(
    highlights: list[Highlight],
    width: int,
    height: int,
    font_path: str = FONT_CANDIDATES[0],
) -> str | None:
    if not highlights:
        return None

    # The genuinely best moments (by confidence) across the *entire* highlight
    # list — not just whatever survives the MAX_VISUAL_EFFECT_HIGHLIGHTS cap
    # below — get a distinct, stronger combo treatment instead of blending
    # into a long run of identical small punches.
    ranked = sorted(highlights, key=lambda h: h.confidence, reverse=True)
    top_tier = ranked[:TOP_TIER_COUNT]
    top_tier_ids = {id(h) for h in top_tier}

    visual = highlights
    if len(visual) > MAX_VISUAL_EFFECT_HIGHLIGHTS:
        visual = sorted(visual, key=lambda h: h.confidence, reverse=True)[:MAX_VISUAL_EFFECT_HIGHLIGHTS]
    visual_ids = {id(h) for h in visual}
    # Guarantee the top-tier moments always get *something* even if the cap
    # above would otherwise have excluded them.
    visual = list(visual) + [h for h in top_tier if id(h) not in visual_ids]
    visual.sort(key=lambda h: h.t)

    filters = []
    punch_index = 0
    for h in visual:
        if id(h) in top_tier_ids:
            filters.append(_pop_filter(h))
            filters.append(_vignette_filter(h))
            filters.append(_chroma_filter(h))
            filters.append(_sticker_filter(h, font_path, label=TOP_TIER_LABEL, duration=TOP_TIER_STICKER_DURATION_S))
            continue
        if h.kind in ("loud_peak", "exclaim"):
            # Cycle between the three punch styles so consecutive highlights
            # don't all look identical.
            punch_style = (_pop_filter, _vignette_filter, _chroma_filter)[punch_index % 3]
            filters.append(punch_style(h))
            punch_index += 1
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
