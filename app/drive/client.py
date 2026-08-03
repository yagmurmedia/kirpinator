"""Polls a Google Drive folder for new source videos and downloads them locally."""
from __future__ import annotations

import io
import logging

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app import db, settings_store
from app.config import INCOMING_DIR, settings
from app.drive.auth import get_credentials

logger = logging.getLogger(__name__)

VIDEO_MIME_PREFIXES = ("video/",)

# Drive files report these to distinguish real footage from Google Docs/Sheets etc.
LIST_FIELDS = "files(id, name, mimeType, size, createdTime, videoMediaMetadata)"


def _drive_service():
    creds = get_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def poll_and_queue_new_videos() -> list[dict]:
    """Look at the configured Drive folder, register any video not seen before,
    and download it into storage/incoming. Returns the list of newly created
    video DB rows (empty if nothing new).
    """
    if not settings.drive_folder_id:
        logger.debug("No drive_folder_id configured — skipping Drive poll.")
        return []

    service = _drive_service()
    query = f"'{settings.drive_folder_id}' in parents and trashed = false"
    new_rows: list[dict] = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=query,
                fields=f"nextPageToken, {LIST_FIELDS}",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        for f in resp.get("files", []):
            if not f.get("mimeType", "").startswith(VIDEO_MIME_PREFIXES):
                continue
            existing = db.get_video_by_drive_id(f["id"])
            if existing:
                continue
            row = db.create_video(
                drive_file_id=f["id"],
                source_filename=f["name"],
                toggles=settings_store.default_toggles_for_new_video(),
            )
            logger.info("Discovered new Drive video: %s (%s)", f["name"], f["id"])
            new_rows.append(row)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    for row in new_rows:
        try:
            download_video(row["id"], row["drive_file_id"], row["source_filename"])
        except Exception as exc:  # noqa: BLE001 - keep polling even if one file fails
            logger.exception("Failed to download %s", row["source_filename"])
            db.set_status(row["id"], "failed", error=str(exc))

    return new_rows


def download_video(video_id: str, drive_file_id: str, filename: str) -> str:
    db.set_status(video_id, "downloading")
    service = _drive_service()
    request = service.files().get_media(fileId=drive_file_id)

    dest_path = INCOMING_DIR / f"{video_id}_{filename}"
    buffer = io.FileIO(dest_path, "wb")
    downloader = MediaIoBaseDownload(buffer, request, chunksize=1024 * 1024 * 8)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logger.info("Downloading %s: %d%%", filename, int(status.progress() * 100))
    buffer.close()

    db.update_video(video_id, local_source_path=str(dest_path))
    db.set_status(video_id, "queued")
    db.log_event(video_id, "drive", f"Downloaded to {dest_path}")
    return str(dest_path)
