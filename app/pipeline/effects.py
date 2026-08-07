"""Turns Highlight events into concrete ffmpeg filter fragments and applies them.

Text callouts only, on genuine highlights — no full-frame screen effect at
all. Earlier versions tried a brightness/contrast "flash" + vignette-style
edge darkening, then a lighter hue/saturation color-pop as a replacement —
both were explicitly called out and rejected ("ışık patlaması yapan ve arka
planda renk değiştiren efekti komple sil... düzgün başka efekt yoksa
ekleme"): no invented substitute, so ordinary loud/exclaim moments get no
visual effect at all now. The "professional" read comes from real crossfade
transitions between cuts (see cutter.py) and precise callouts on true
highlights (top-tier moments, keyword hits, protected/must-not-miss
moments) — not full-frame screen effects on every loud beat.
"""
from __future__ import annotations

import subprocess

from app.models import Highlight

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
# kept modest as a sanity cap on total command-line/graph size.
MAX_VISUAL_EFFECT_HIGHLIGHTS = 20

# A long video can rack up hundreds of highlights (a 13-minute source hit 298
# in practice) — the handful of genuinely highest-confidence moments get a
# distinct callout label ("İZLE") instead of just another beat in a long,
# uniform sequence.
TOP_TIER_COUNT = 4
TOP_TIER_LABEL = "İZLE"
TOP_TIER_STICKER_DURATION_S = 1.0


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


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
    # below — get the distinct "İZLE" callout instead of blending into a
    # long run of identical keyword stickers.
    ranked = sorted(highlights, key=lambda h: h.confidence, reverse=True)
    top_tier = ranked[:TOP_TIER_COUNT]
    top_tier_ids = {id(h) for h in top_tier}

    visual = highlights
    if len(visual) > MAX_VISUAL_EFFECT_HIGHLIGHTS:
        visual = sorted(visual, key=lambda h: h.confidence, reverse=True)[:MAX_VISUAL_EFFECT_HIGHLIGHTS]
    visual_ids = {id(h) for h in visual}
    # Guarantee the top-tier moments always get their callout even if the
    # cap above would otherwise have excluded them.
    visual = list(visual) + [h for h in top_tier if id(h) not in visual_ids]
    visual.sort(key=lambda h: h.t)

    filters = []
    for h in visual:
        if id(h) in top_tier_ids:
            filters.append(_sticker_filter(h, font_path, label=TOP_TIER_LABEL, duration=TOP_TIER_STICKER_DURATION_S))
        elif h.kind in ("keyword", "protected"):
            filters.append(_sticker_filter(h, font_path))
        # loud_peak/exclaim highlights that aren't top-tier get no visual
        # effect at all — deliberately: no substitute screen effect invented
        # to replace the removed flash/vignette/color-pop.
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
