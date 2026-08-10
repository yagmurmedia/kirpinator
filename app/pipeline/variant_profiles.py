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

# A source long enough to have real long-form material also gets 3 long-form
# takes queued (low priority — see db.enqueue_variants — so the whole Shorts
# backlog across every video drains first). No formal spec gave an exact
# cutoff; 5 minutes is a judgment call: comfortably longer than the
# phone-clip Shorts candidates seen in practice (~1-3 min), short enough to
# not gate long-form treatment on genuinely long footage.
LONG_FORM_MIN_DURATION_S = 300.0

_LONG_FORM_BASE_TOGGLES = {"cut_silence": True, "effects": True, "captions": True, "long_form": True}

LONG_FORM_VARIANT_PROFILES: list[tuple[str, dict]] = [
    ("uzun video: standart", {**_LONG_FORM_BASE_TOGGLES, "music": True, "music_mood": None, "face_crop": True}),
    ("uzun video: sade (muziksiz)", {**_LONG_FORM_BASE_TOGGLES, "music": False, "music_mood": None, "face_crop": True}),
    ("uzun video: sabit kadraj", {**_LONG_FORM_BASE_TOGGLES, "music": True, "music_mood": None, "face_crop": False}),
]
