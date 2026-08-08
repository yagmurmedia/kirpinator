"""Shared definition of the "compare a handful of tasteful edit styles"
Shorts variant profiles.

Used both by the one-off admin script (scripts/enqueue_shorts_variants.py)
and automatically for every newly-downloaded video (see
app.drive.client.download_video) — per standing instruction, every new
video should arrive as a batch of distinct, non-gimmicky Shorts variants
for the reviewer to pick from, not a single fixed edit.

Ten combinations: 5 music takes (off + 4 real mood overrides — see
app.pipeline.music.MOOD_KEYWORDS) x 2 framing styles (face-tracked vs
static center crop). cut_silence and captions stay on in every profile
(neither is in dispute); long_form stays off (Shorts); no visual/sound
"punch" effect is varied — that whole category was removed outright, not
made into a toggle.
"""
from __future__ import annotations

_MUSIC_TAKES: list[tuple[str, dict]] = [
    ("muziksiz", {"music": False, "music_mood": None}),
    ("sakin muzikli", {"music": True, "music_mood": "calm"}),
    ("oyuncu muzikli", {"music": True, "music_mood": "playful"}),
    ("komik muzikli", {"music": True, "music_mood": "funny"}),
    ("enerjik muzikli", {"music": True, "music_mood": "exciting"}),
]

_FRAMING_TAKES: list[tuple[str, dict]] = [
    ("yuz takipli", {"face_crop": True}),
    ("sabit kadraj", {"face_crop": False}),
]

_BASE_TOGGLES = {"cut_silence": True, "effects": True, "captions": True, "long_form": False}

SHORTS_VARIANT_PROFILES: list[tuple[str, dict]] = [
    (f"{music_name}, {framing_name}", {**_BASE_TOGGLES, **music_overrides, **framing_overrides})
    for framing_name, framing_overrides in _FRAMING_TAKES
    for music_name, music_overrides in _MUSIC_TAKES
]
