"""YouTube Data API v3 upload — resumable, free-quota only.

IMPORTANT: this module is only ever called after a human has clicked
"Approve & Upload" in the web UI (see app/web/main.py). The pipeline itself
never calls this — it stops at 'ready_for_review'. This is a deliberate
safety gate, not an implementation detail to optimize away.
"""
from __future__ import annotations

import logging

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app import db
from app.config import settings
from app.drive.auth import get_credentials
from app.jobs.notify import notify_failed, notify_uploaded

logger = logging.getLogger(__name__)


def _youtube_service():
    creds = get_credentials("youtube")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(video_id: str) -> str:
    row = db.get_video(video_id)
    if row is None:
        raise ValueError(f"Unknown video_id {video_id}")
    if row["status"] != "approved":
        raise RuntimeError(
            f"Refusing to upload video {video_id}: status is '{row['status']}', not 'approved'. "
            "Uploads must go through the human approval step in the web UI."
        )
    if not row.get("output_path"):
        raise RuntimeError(f"Video {video_id} has no rendered output_path.")

    db.set_status(video_id, "uploading")
    db.log_event(video_id, "youtube", "Starting upload")

    made_for_kids = bool(row.get("made_for_kids", settings.made_for_kids_default))
    tags = row.get("tags") or []

    body = {
        "snippet": {
            "title": row["title"] or row["source_filename"],
            "description": row["description"] or "",
            "tags": tags,
            "categoryId": settings.youtube_category_id,
        },
        "status": {
            "privacyStatus": settings.youtube_privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    try:
        service = _youtube_service()
        media = MediaFileUpload(row["output_path"], chunksize=-1, resumable=True, mimetype="video/mp4")
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info("Upload progress for %s: %d%%", video_id, int(status.progress() * 100))

        youtube_video_id = response["id"]

        if row.get("thumbnail_path"):
            try:
                service.thumbnails().set(
                    videoId=youtube_video_id,
                    media_body=MediaFileUpload(row["thumbnail_path"], mimetype="image/jpeg"),
                ).execute()
            except Exception:
                logger.warning("Thumbnail upload failed for %s (non-fatal)", video_id)

        db.update_video(video_id, youtube_video_id=youtube_video_id)
        db.set_status(video_id, "uploaded")
        db.log_event(video_id, "youtube", f"Uploaded as https://youtube.com/shorts/{youtube_video_id}")
        notify_uploaded(video_id, f"https://youtube.com/shorts/{youtube_video_id}")
        return youtube_video_id

    except Exception as exc:  # noqa: BLE001
        logger.exception("Upload failed for %s", video_id)
        db.set_status(video_id, "failed", error=str(exc))
        db.log_event(video_id, "youtube", f"Upload FAILED: {exc}")
        notify_failed(video_id, str(exc))
        raise
