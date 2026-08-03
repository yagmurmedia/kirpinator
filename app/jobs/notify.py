"""User-facing notifications. Free, no paid service required.

Two channels, both best-effort (never block or fail the pipeline):
  - Windows toast — only seen if you're at the PC.
  - ntfy.sh push notification — reaches your phone anywhere, as long as
    NTFY_TOPIC is set and the ntfy app is subscribed to that topic.

Always backed by a DB log entry too, so the web UI's dashboard shows it even
if both notification channels are missed.
"""
from __future__ import annotations

import logging
import threading

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def _toast(title: str, message: str) -> None:
    try:
        from winotify import Notification

        toast = Notification(app_id="Kirpinator", title=title, msg=message, duration="long")
        toast.show()
    except Exception:
        logger.debug("Windows toast unavailable", exc_info=True)


def _ntfy(title: str, message: str) -> None:
    if not settings.ntfy_topic:
        return
    try:
        requests.post(
            f"{settings.ntfy_server}/{settings.ntfy_topic}",
            data=message.encode("utf-8"),
            headers={"Title": title.encode("utf-8"), "Priority": "default"},
            timeout=10,
        )
    except Exception:
        logger.exception("ntfy push failed")


def _send(title: str, message: str) -> None:
    logger.info("[notify] %s: %s", title, message)
    _toast(title, message)
    _ntfy(title, message)


def _send_async(title: str, message: str) -> None:
    threading.Thread(target=_send, args=(title, message), daemon=True).start()


def notify_ready_for_review(video_id: str, title: str) -> None:
    url = f"http://{settings.web_host}:{settings.web_port}/video/{video_id}"
    message = f'"{title}" incelemeye hazır.\n{url}'
    _send_async("Kirpinator — Video hazır", message)


def notify_uploaded(video_id: str, youtube_url: str) -> None:
    _send_async("Kirpinator — Yüklendi", f"Video YouTube'a yüklendi: {youtube_url}")


def notify_failed(video_id: str, error: str) -> None:
    _send_async("Kirpinator — Hata", f"Video {video_id} işlenemedi: {error[:200]}")
