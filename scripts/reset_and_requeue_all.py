"""One-off admin script: wipes every video's edited output/version history
back to an unedited state — source file kept, nothing re-downloaded — and
re-queues the current best variant batch (10 Shorts profiles, plus 3
long-form profiles if the source qualifies). Used to regenerate everything
with the latest pipeline (auto topic/greeting protection, color grade,
transition whoosh, face-safe static crop, faststart streaming fix, etc.)
instead of leaving old pre-fix renders mixed in with new ones.

Usage:
    .venv/Scripts/python.exe -m scripts.reset_and_requeue_all
"""
from __future__ import annotations

from pathlib import Path

from app import db
from app.pipeline import probe
from app.pipeline.variant_profiles import (
    LONG_FORM_MIN_DURATION_S,
    LONG_FORM_VARIANT_PROFILES,
    SHORTS_VARIANT_PROFILES,
)


def reset_video(video_id: str) -> str:
    row = db.get_video(video_id)
    if not row:
        return "not found"
    if not row.get("local_source_path") or not Path(row["local_source_path"]).exists():
        return "skipped: source file missing, can't reprocess without re-download"

    for v in db.list_versions(video_id):
        db.delete_version(video_id, v["id"])

    for key in ("output_path", "thumbnail_path"):
        p = row.get(key)
        if p and Path(p).exists():
            Path(p).unlink(missing_ok=True)

    db.clear_variant_queue(video_id)
    db.update_video(
        video_id,
        version=1,
        variant_label=None,
        output_path=None,
        thumbnail_path=None,
        title=None,
        description=None,
        tags=None,
        error="",
    )
    db.set_status(video_id, "discovered")
    db.log_event(
        video_id, "variant",
        "Full reset: cleared all edited output/versions, re-queuing fresh batch with latest pipeline",
    )

    duration_s = probe.probe_video(row["local_source_path"]).duration_s
    db.enqueue_variants(video_id, SHORTS_VARIANT_PROFILES)
    queued_note = f"queued {len(SHORTS_VARIANT_PROFILES)} Shorts"
    if duration_s >= LONG_FORM_MIN_DURATION_S:
        db.enqueue_variants(video_id, LONG_FORM_VARIANT_PROFILES, priority="low")
        queued_note += f" + {len(LONG_FORM_VARIANT_PROFILES)} long-form (low priority)"
    return f"reset OK, {queued_note} ({duration_s:.0f}s source)"


def main() -> None:
    videos = db.list_videos()
    print(f"{len(videos)} video(s) found.")
    for r in videos:
        result = reset_video(r["id"])
        print(f"{r['id']} ({r.get('source_filename')}): {result}")


if __name__ == "__main__":
    main()
