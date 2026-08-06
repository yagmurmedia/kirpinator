"""Polls a Google Drive folder for new source videos and downloads them locally."""
from __future__ import annotations

import difflib
import io
import logging

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app import db, settings_store
from app.config import INCOMING_DIR, settings
from app.drive.auth import get_credentials
from app.pipeline.variant_profiles import SHORTS_VARIANT_PROFILES

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

    # Also retry any video still sitting in 'discovered' without a local
    # file — covers both the rows just created above and ones left over
    # from a previous download that never finished (e.g. an app restart
    # mid-download resets it back to 'discovered', see recover_stuck_videos).
    to_download = [r for r in db.list_videos(status="discovered") if not r.get("local_source_path")]
    for row in to_download:
        try:
            download_video(row["id"], row["drive_file_id"], row["source_filename"])
        except Exception as exc:  # noqa: BLE001 - keep polling even if one file fails
            logger.exception("Failed to download %s", row["source_filename"])
            db.set_status(row["id"], "failed", error=str(exc))

    return new_rows


def find_video_by_name(query: str) -> dict | None:
    """Finds a video by (partial, fuzzy) name match. Phone camera filenames
    are usually just timestamps ("20260724_213117.mp4"), so a query like
    "diş çekimi" can only match a video's *filename* if it was renamed in
    Drive — for already-processed videos, this also matches against the
    generated title/description, which is usually the more useful signal.
    Checks already-known videos first, then searches the live Drive folder
    for a brand-new match and downloads it if found. Returns the DB row, or
    None if nothing matches anywhere.
    """
    query_norm = query.strip().lower()
    if not query_norm:
        return None

    known = db.list_videos()

    def _haystacks(v: dict) -> list[str]:
        return [v["source_filename"], v.get("title") or "", v.get("description") or ""]

    substring_matches = [v for v in known if any(query_norm in h.lower() for h in _haystacks(v))]
    if substring_matches:
        return substring_matches[0]

    close = difflib.get_close_matches(
        query_norm, [v["source_filename"].lower() for v in known], n=1, cutoff=0.6
    )
    if close:
        return next(v for v in known if v["source_filename"].lower() == close[0])

    if not settings.drive_folder_id:
        return None

    service = _drive_service()
    drive_query = (
        f"'{settings.drive_folder_id}' in parents and trashed = false "
        f"and name contains '{query_norm}'"
    )
    resp = service.files().list(q=drive_query, fields=LIST_FIELDS, pageSize=10).execute()
    candidates = [f for f in resp.get("files", []) if f.get("mimeType", "").startswith(VIDEO_MIME_PREFIXES)]
    if not candidates:
        return None

    f = candidates[0]
    existing = db.get_video_by_drive_id(f["id"])
    if existing:
        return existing

    row = db.create_video(
        drive_file_id=f["id"],
        source_filename=f["name"],
        toggles=settings_store.default_toggles_for_new_video(),
    )
    logger.info("Found video by name search: %s (%s)", f["name"], f["id"])
    download_video(row["id"], row["drive_file_id"], row["source_filename"])
    return db.get_video(row["id"])


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
    db.log_event(video_id, "drive", f"Downloaded to {dest_path}")

    # Every new video gets the same standing treatment: a batch of distinct
    # Shorts edit variants to choose from, not a single fixed edit — per
    # explicit instruction to apply this uniformly going forward, no
    # per-video judgment calls. Status goes to 'discovered' (not 'queued')
    # so the worker's variant-queue drain (see app.jobs.worker) is what
    # advances it, one profile at a time.
    db.enqueue_variants(video_id, SHORTS_VARIANT_PROFILES)
    db.set_status(video_id, "discovered")
    db.log_event(
        video_id, "variant",
        f"Queued {len(SHORTS_VARIANT_PROFILES)} Shorts variant profiles for comparison",
    )
    return str(dest_path)
