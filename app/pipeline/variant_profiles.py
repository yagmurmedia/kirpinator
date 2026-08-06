"""Shared definition of the "compare a handful of tasteful edit styles"
Shorts variant profiles.

Used both by the one-off admin script (scripts/enqueue_shorts_variants.py)
and automatically for every newly-downloaded video (see
app.drive.client.download_video) — per standing instruction, every new
video should arrive as a batch of distinct, non-gimmicky Shorts variants
for the reviewer to pick from, not a single fixed edit. Each variant only
toggles real, working pipeline knobs (music/effects/face-crop on or off);
cut_silence and captions stay on and long_form stays off (Shorts) in every
profile, since those aren't in dispute.
"""
from __future__ import annotations

SHORTS_VARIANT_PROFILES: list[tuple[str, dict]] = [
    ("Standart", {"cut_silence": True, "face_crop": True, "music": True, "effects": True, "captions": True, "long_form": False}),
    ("Sade (efektsiz, muziksiz)", {"cut_silence": True, "face_crop": True, "music": False, "effects": False, "captions": True, "long_form": False}),
    ("Muzikli, efektsiz", {"cut_silence": True, "face_crop": True, "music": True, "effects": False, "captions": True, "long_form": False}),
    ("Efektli, muziksiz", {"cut_silence": True, "face_crop": True, "music": False, "effects": True, "captions": True, "long_form": False}),
    ("Sabit kadraj (yuz takibi kapali)", {"cut_silence": True, "face_crop": False, "music": True, "effects": True, "captions": True, "long_form": False}),
]
