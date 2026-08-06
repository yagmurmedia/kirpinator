"""One-off admin script: queues a batch of distinct Shorts-style edit
variants for one or more videos, so the reviewer can compare a handful of
genuinely different, tasteful takes instead of a single fixed edit.

New videos get this automatically now (see app.drive.client.download_video)
— this script is for backfilling videos that were downloaded before that
existed, or re-running the batch on demand.

Usage:
    .venv/Scripts/python.exe -m scripts.enqueue_shorts_variants <video_id> [<video_id> ...]
"""
from __future__ import annotations

import sys

from app import db
from app.pipeline.variant_profiles import SHORTS_VARIANT_PROFILES as PROFILES


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
