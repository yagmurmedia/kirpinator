"""One-off admin script: queues a batch of distinct Shorts-style edit
variants for one or more videos, so the reviewer can compare a handful of
genuinely different, tasteful takes instead of a single fixed edit.

Each variant only varies toggles that are real, working pipeline knobs
(music/effects/face-crop on or off) — no gimmicky/random effects, per
explicit direction to keep it professional. cut_silence and captions stay
on in every variant (both are unconditionally wanted); long_form stays off
(Shorts); each video's existing custom_instructions (e.g. a "don't cut this
moment" protection) is left untouched.

Usage:
    .venv/Scripts/python.exe scripts/enqueue_shorts_variants.py <video_id> [<video_id> ...]
"""
from __future__ import annotations

import sys

from app import db

PROFILES: list[tuple[str, dict]] = [
    ("Standart", {"cut_silence": True, "face_crop": True, "music": True, "effects": True, "captions": True, "long_form": False}),
    ("Sade (efektsiz, muziksiz)", {"cut_silence": True, "face_crop": True, "music": False, "effects": False, "captions": True, "long_form": False}),
    ("Muzikli, efektsiz", {"cut_silence": True, "face_crop": True, "music": True, "effects": False, "captions": True, "long_form": False}),
    ("Efektli, muziksiz", {"cut_silence": True, "face_crop": True, "music": False, "effects": True, "captions": True, "long_form": False}),
    ("Sabit kadraj (yuz takibi kapali)", {"cut_silence": True, "face_crop": False, "music": True, "effects": True, "captions": True, "long_form": False}),
]


def main() -> None:
    video_ids = sys.argv[1:]
    if not video_ids:
        print("Usage: enqueue_shorts_variants.py <video_id> [<video_id> ...]")
        sys.exit(1)

    for video_id in video_ids:
        row = db.get_video(video_id)
        if not row:
            print(f"skip {video_id}: not found")
            continue
        db.enqueue_variants(video_id, PROFILES)
        db.log_event(video_id, "variant", f"Queued {len(PROFILES)} Shorts variant profiles for comparison")
        print(f"{video_id} ({row.get('source_filename')}): queued {len(PROFILES)} variants")


if __name__ == "__main__":
    main()
