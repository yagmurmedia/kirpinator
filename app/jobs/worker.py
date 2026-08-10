"""Background worker: polls Drive for new footage and runs the edit pipeline
on anything queued, entirely on its own — no user interaction until a video
reaches 'ready_for_review'.

Two independent threads, not one: process_video() blocks synchronously for
however long a render takes (hours, for a 4K/HDR source) — if Drive polling
shared that same loop, a single long render would starve it completely,
and a video uploaded to Drive mid-render wouldn't be discovered until the
current one finished, sometimes hours later (confirmed happening in
practice: a video sat in Drive undetected for 2+ hours during one render).
Polling now runs on its own timer, unaffected by how long processing takes.
"""
from __future__ import annotations

import logging
import threading
import time

from app import db
from app.config import settings
from app.pipeline.pipeline import process_video

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_drive_poll_thread: threading.Thread | None = None


def _drive_poll_tick() -> None:
    if not settings.drive_folder_id:
        return
    try:
        from app.drive.client import poll_and_queue_new_videos

        poll_and_queue_new_videos()
    except Exception:
        logger.exception("Drive poll failed (will retry next cycle)")


def _drive_poll_loop() -> None:
    logger.info("Drive poll thread started (interval=%ss)", settings.drive_poll_interval_seconds)
    while not _stop_event.is_set():
        _drive_poll_tick()
        _stop_event.wait(settings.drive_poll_interval_seconds)


def _process_one_queued() -> bool:
    queued = db.list_videos(status="queued")
    if not queued:
        return False
    video = queued[-1]  # oldest first (list_videos orders DESC by created_at)
    try:
        process_video(video["id"])
    except Exception:
        logger.exception("Processing failed for %s", video["id"])
        # process_video only sets status='failed' itself once its own main
        # try block starts — a failure before that (e.g. a missing source
        # file) never touches status. Left alone, the video stays 'queued'
        # forever and _process_one_queued picks it right back up next
        # iteration with zero backoff: a real, previously-hit busy-loop that
        # starves every other queued video (and the variant backlog) of a
        # turn. Force it to 'failed' here as a backstop regardless of cause.
        current = db.get_video(video["id"])
        if current and current["status"] == "queued":
            db.set_status(video["id"], "failed", error="Processing failed before it could start — see server logs")
    return True


def _promote_next_variant() -> bool:
    """Only runs once the normal 'queued' list is empty (see _loop), so
    on-demand reprocessing always wins over the variant backlog. Applies the
    next queued profile's toggle overrides on top of whatever the video's
    current toggles/custom_instructions already are, then queues it — the
    existing versioning system (archive_current_version) means each variant
    lands as its own comparable V1/V2/... instead of overwriting the last.
    """
    variant = db.pop_next_variant()
    if not variant:
        return False
    video_id = variant["video_id"]
    row = db.get_video(video_id)
    if not row:
        return True  # video was deleted since being queued — just drop it
    merged_toggles = {**(row.get("toggles") or {}), **variant["toggles"]}
    db.update_video(video_id, toggles=merged_toggles, variant_label=variant["profile_name"])
    db.set_status(video_id, "queued")
    db.log_event(video_id, "variant", f"Applying variant profile '{variant['profile_name']}'")
    return True


def _loop() -> None:
    logger.info("Worker started (poll interval=%ss)", settings.worker_poll_interval_seconds)
    while not _stop_event.is_set():
        try:
            did_work = _process_one_queued()
            if not did_work:
                did_work = _promote_next_variant()
        except Exception:
            # A transient failure here (DB I/O hiccup, unexpected bug, etc.)
            # must never permanently kill the worker thread — that would
            # silently stop all future automation until a manual restart,
            # defeating the whole point of "fully automatic". Log it, back
            # off a bit, and keep going.
            logger.exception("Worker loop iteration failed; will retry")
            did_work = False
        if not did_work:
            _stop_event.wait(settings.worker_poll_interval_seconds)


def start_background_worker() -> None:
    global _worker_thread, _drive_poll_thread
    db.init_db()
    _stop_event.clear()
    if not (_worker_thread and _worker_thread.is_alive()):
        _worker_thread = threading.Thread(target=_loop, name="kirpinator-worker", daemon=True)
        _worker_thread.start()
    if not (_drive_poll_thread and _drive_poll_thread.is_alive()):
        _drive_poll_thread = threading.Thread(target=_drive_poll_loop, name="kirpinator-drive-poll", daemon=True)
        _drive_poll_thread.start()


def stop_background_worker() -> None:
    _stop_event.set()
