"""Background worker: polls Drive for new footage and runs the edit pipeline
on anything queued, entirely on its own — no user interaction until a video
reaches 'ready_for_review'.
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
_last_drive_poll = 0.0


def _drive_poll_tick() -> None:
    global _last_drive_poll
    if not settings.drive_folder_id:
        return
    now = time.time()
    if now - _last_drive_poll < settings.drive_poll_interval_seconds:
        return
    _last_drive_poll = now
    try:
        from app.drive.client import poll_and_queue_new_videos

        poll_and_queue_new_videos()
    except Exception:
        logger.exception("Drive poll failed (will retry next cycle)")


def _process_one_queued() -> bool:
    queued = db.list_videos(status="queued")
    if not queued:
        return False
    video = queued[-1]  # oldest first (list_videos orders DESC by created_at)
    try:
        process_video(video["id"])
    except Exception:
        logger.exception("Processing failed for %s", video["id"])
    return True


def _loop() -> None:
    logger.info("Worker started (poll interval=%ss)", settings.worker_poll_interval_seconds)
    while not _stop_event.is_set():
        try:
            _drive_poll_tick()
            did_work = _process_one_queued()
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
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    db.init_db()
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_loop, name="kirpinator-worker", daemon=True)
    _worker_thread.start()


def stop_background_worker() -> None:
    _stop_event.set()
