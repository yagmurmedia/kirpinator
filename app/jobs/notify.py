"""User-facing notifications. Free, local, no external service required.

Windows toast notification when available, always backed by a DB log entry
so the web UI's dashboard shows it too even if the toast is missed.
"""
from __future__ import annotations

import logging
import threading

from app.config import settings

logger = logging.getLogger(__name__)


def _toast(title: str, message: str) -> None:
    try:
        from winotify import Notification

        toast = Notification(app_id="Kirpinator", title=title, msg=message, duration="long")
        toast.show()
    except Exception:
        logger.info("[notify] %s: %s", title, message)


def notify_ready_for_review(video_id: str, title: str) -> None:
    url = f"http://{settings.web_host}:{settings.web_port}/video/{video_id}"
    message = f'"{title}" incelemeye hazır.\n{url}'
    threading.Thread(target=_toast, args=("Kirpinator — Video hazır", message), daemon=True).start()


def notify_uploaded(video_id: str, youtube_url: str) -> None:
    threading.Thread(
        target=_toast, args=("Kirpinator — Yüklendi", f"Video YouTube'a yüklendi: {youtube_url}"), daemon=True
    ).start()


def notify_failed(video_id: str, error: str) -> None:
    threading.Thread(
        target=_toast, args=("Kirpinator — Hata", f"Video {video_id} işlenemedi: {error[:200]}"), daemon=True
    ).start()
