"""Lightweight SQLite persistence layer. Deliberately dependency-free (stdlib sqlite3)
so the app has one less thing that can fail to install.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

from app.config import DATA_DIR

DB_PATH = DATA_DIR / "kirpinator.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    drive_file_id TEXT UNIQUE,
    source_filename TEXT NOT NULL,
    local_source_path TEXT,
    status TEXT NOT NULL DEFAULT 'discovered',
    orientation TEXT,
    duration_s REAL,
    custom_instructions TEXT DEFAULT '',
    toggles_json TEXT NOT NULL DEFAULT '{}',
    made_for_kids INTEGER,
    transcript_json TEXT,
    output_path TEXT,
    thumbnail_path TEXT,
    title TEXT,
    description TEXT,
    tags_json TEXT,
    youtube_video_id TEXT,
    error TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS video_versions (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    output_path TEXT,
    thumbnail_path TEXT,
    title TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos (id)
);

CREATE TABLE IF NOT EXISTS job_events (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos (id)
);

CREATE TABLE IF NOT EXISTS kv_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    message TEXT NOT NULL,
    video_query TEXT,
    video_id TEXT,
    status TEXT NOT NULL,
    reply TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- A standing to-do list of "reprocess this video with this toggle profile"
-- rows, drained one at a time by the worker (see app/jobs/worker.py) once
-- the normal 'queued' list is empty. Each drained row rides the existing
-- pipeline + versioning machinery unchanged, so every variant lands as its
-- own archived version (V1, V2, ...) the user can compare side by side.
CREATE TABLE IF NOT EXISTS variant_queue (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    profile_name TEXT NOT NULL,
    toggles_json TEXT NOT NULL,
    position REAL NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos (id)
);
"""

# Valid status values, in the order a video normally moves through them.
STATUSES = [
    "discovered",       # seen in Drive, not yet downloaded
    "downloading",
    "queued",            # downloaded, waiting for a worker slot
    "processing",         # pipeline running (transcribe/cut/crop/music/effects)
    "ready_for_review",    # rendered, waiting for human approval
    "approved",              # human clicked "Approve & Upload"
    "uploading",
    "uploaded",
    "failed",
]


@contextlib.contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
    recover_stuck_videos()


def _migrate(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS doesn't add new columns to an existing
    table, so anything added to `videos` after the initial release needs an
    explicit ADD COLUMN here, guarded against already having run.
    """
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(videos)")}
    if "version" not in existing_cols:
        conn.execute("ALTER TABLE videos ADD COLUMN version INTEGER NOT NULL DEFAULT 1")


# 'processing' auto-resumes straight to 'queued' — safe to redo from scratch,
# the source file it needs is already downloaded (idempotent: reprocessing
# just overwrites work_dir). 'downloading' is NOT safe to bounce straight to
# 'queued': that used to happen here and it's a real bug that shipped and bit
# a real video — 'queued' means "go straight to editing", so a video whose
# download was interrupted (local_source_path still None) got picked up by
# the worker, immediately raised FileNotFoundError before its status could
# change, and stayed 'queued' forever — a zero-delay busy-loop, since
# _process_one_queued reports "did work" every iteration even on failure, so
# the worker's poll-interval backoff never kicked in and nothing else (any
# other queued video, the variant backlog) ever got a turn. 'downloading'
# instead resets to 'discovered', so poll_and_queue_new_videos's retry pass
# (see app/drive/client.py) re-attempts the actual download on the next poll.
# 'uploading' is deliberately NOT auto-reset: if the app died right after
# YouTube actually accepted the upload but before we recorded that, blindly
# reprocessing and re-approving could publish a duplicate. That case needs a
# human to check YouTube Studio first, so it's left as-is and simply visible
# as a stuck video in the dashboard.
_IN_FLIGHT_PROCESSING = ("processing",)
_IN_FLIGHT_DOWNLOADING = ("downloading",)


def recover_stuck_videos() -> list[str]:
    with get_conn() as conn:
        proc_rows = conn.execute(
            f"SELECT id FROM videos WHERE status IN ({','.join('?' * len(_IN_FLIGHT_PROCESSING))})",
            _IN_FLIGHT_PROCESSING,
        ).fetchall()
        proc_ids = [r["id"] for r in proc_rows]
        if proc_ids:
            conn.executemany(
                "UPDATE videos SET status = 'queued', updated_at = ? WHERE id = ?",
                [(time.time(), vid) for vid in proc_ids],
            )

        dl_rows = conn.execute(
            f"SELECT id FROM videos WHERE status IN ({','.join('?' * len(_IN_FLIGHT_DOWNLOADING))})",
            _IN_FLIGHT_DOWNLOADING,
        ).fetchall()
        dl_ids = [r["id"] for r in dl_rows]
        if dl_ids:
            conn.executemany(
                "UPDATE videos SET status = 'discovered', updated_at = ? WHERE id = ?",
                [(time.time(), vid) for vid in dl_ids],
            )
    for vid in proc_ids:
        log_event(vid, "pipeline", "Resumed after interrupted run (app restart)")
    for vid in dl_ids:
        log_event(vid, "drive", "Download was interrupted by app restart — will retry")
    return proc_ids + dl_ids


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for json_field in ("toggles_json", "transcript_json", "tags_json"):
        if json_field in d and d[json_field]:
            with contextlib.suppress(json.JSONDecodeError):
                d[json_field[: -len("_json")]] = json.loads(d[json_field])
    return d


def create_video(
    *,
    drive_file_id: str | None,
    source_filename: str,
    local_source_path: str | None = None,
    toggles: dict[str, Any] | None = None,
    made_for_kids: bool | None = None,
) -> dict[str, Any]:
    vid = new_id()
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO videos
               (id, drive_file_id, source_filename, local_source_path, status,
                toggles_json, made_for_kids, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'discovered', ?, ?, ?, ?)""",
            (
                vid,
                drive_file_id,
                source_filename,
                local_source_path,
                json.dumps(toggles or {}),
                None if made_for_kids is None else int(made_for_kids),
                now,
                now,
            ),
        )
    return get_video(vid)


def get_video(video_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    return row_to_dict(row) if row else None


def get_video_by_drive_id(drive_file_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE drive_file_id = ?", (drive_file_id,)
        ).fetchone()
    return row_to_dict(row) if row else None


def list_videos(status: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM videos WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
    return [row_to_dict(r) for r in rows]


def get_display_numbers() -> dict[str, int]:
    """A stable "#1, #2, #3..." label per video, oldest first, so a video's
    number never shifts as newer ones arrive — used so the reviewer and the
    assistant can refer to "video 3" instead of an opaque id.
    """
    with get_conn() as conn:
        rows = conn.execute("SELECT id FROM videos ORDER BY created_at ASC").fetchall()
    return {row["id"]: i + 1 for i, row in enumerate(rows)}


def update_video(video_id: str, **fields: Any) -> None:
    if not fields:
        return
    for json_field in ("toggles", "transcript", "tags"):
        if json_field in fields:
            fields[f"{json_field}_json"] = json.dumps(fields.pop(json_field))
    if "made_for_kids" in fields and isinstance(fields["made_for_kids"], bool):
        fields["made_for_kids"] = int(fields["made_for_kids"])
    fields["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE videos SET {set_clause} WHERE id = ?", (*fields.values(), video_id)
        )


def set_status(video_id: str, status: str, *, error: str | None = None) -> None:
    assert status in STATUSES, f"unknown status {status!r}"
    update_video(video_id, status=status, error=error or "")


def log_event(video_id: str, stage: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO job_events (id, video_id, stage, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), video_id, stage, message, time.time()),
        )


def get_events(video_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM job_events WHERE video_id = ? ORDER BY created_at ASC", (video_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_video(video_id: str) -> bool:
    """Removes a video's DB record, job history, every archived version, and
    every file any of that produced (source download, working-directory
    intermediates, output, thumbnails). Only ever called from a route the
    user explicitly clicked — this module never deletes anything on its own
    initiative.
    """
    import shutil
    from pathlib import Path

    from app.config import WORKING_DIR

    row = get_video(video_id)
    if not row:
        return False

    for key in ("local_source_path", "output_path", "thumbnail_path"):
        path = row.get(key)
        if path:
            with contextlib.suppress(OSError):
                Path(path).unlink(missing_ok=True)

    for version in list_versions(video_id):
        for key in ("output_path", "thumbnail_path"):
            path = version.get(key)
            if path:
                with contextlib.suppress(OSError):
                    Path(path).unlink(missing_ok=True)

    work_dir = WORKING_DIR / video_id
    if work_dir.exists():
        with contextlib.suppress(OSError):
            shutil.rmtree(work_dir)

    with get_conn() as conn:
        conn.execute("DELETE FROM job_events WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM video_versions WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM variant_queue WHERE video_id = ?", (video_id,))
        conn.execute("UPDATE chat_messages SET video_id = NULL WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    return True


def archive_current_version(video_id: str) -> int | None:
    """Snapshots the video's *current* output/thumbnail/title into
    video_versions under its current version number, then bumps the live
    version counter — called right before a reprocess overwrites
    output_path, so old edits aren't silently lost. Returns the archived
    version number, or None if there was nothing to archive yet (first run).
    """
    import shutil
    from pathlib import Path

    from app.config import OUTPUT_DIR, THUMBNAIL_DIR

    row = get_video(video_id)
    if not row or not row.get("output_path"):
        return None

    old_version = row.get("version", 1)
    archived_output = None
    archived_thumb = None

    src_output = Path(row["output_path"])
    if src_output.exists():
        archived_output = OUTPUT_DIR / f"{video_id}_v{old_version}{src_output.suffix}"
        with contextlib.suppress(OSError):
            shutil.copyfile(src_output, archived_output)

    src_thumb = row.get("thumbnail_path")
    if src_thumb and Path(src_thumb).exists():
        archived_thumb = THUMBNAIL_DIR / f"{video_id}_v{old_version}{Path(src_thumb).suffix}"
        with contextlib.suppress(OSError):
            shutil.copyfile(src_thumb, archived_thumb)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO video_versions (id, video_id, version, output_path, thumbnail_path, title, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                new_id(), video_id, old_version,
                str(archived_output) if archived_output else None,
                str(archived_thumb) if archived_thumb else None,
                row.get("title"),
                time.time(),
            ),
        )
        conn.execute("UPDATE videos SET version = ? WHERE id = ?", (old_version + 1, video_id))
    return old_version


def list_versions(video_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM video_versions WHERE video_id = ? ORDER BY version DESC", (video_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_version(video_id: str, version_row_id: str) -> bool:
    from pathlib import Path

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM video_versions WHERE id = ? AND video_id = ?", (version_row_id, video_id)
        ).fetchone()
        if not row:
            return False
        for key in ("output_path", "thumbnail_path"):
            path = row[key]
            if path:
                with contextlib.suppress(OSError):
                    Path(path).unlink(missing_ok=True)
        conn.execute("DELETE FROM video_versions WHERE id = ?", (version_row_id,))
    return True


def enqueue_variants(video_id: str, profiles: list[tuple[str, dict]]) -> None:
    """Queues a batch of (profile_name, toggle_overrides) pairs for `video_id`.
    Drained strictly in insertion order by the worker — see pop_next_variant.
    """
    with get_conn() as conn:
        base = time.time()
        conn.executemany(
            "INSERT INTO variant_queue (id, video_id, profile_name, toggles_json, position, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (new_id(), video_id, name, json.dumps(overrides), base + i * 1e-6, base)
                for i, (name, overrides) in enumerate(profiles)
            ],
        )


def clear_variant_queue(video_id: str) -> int:
    """Drops every not-yet-started variant-queue row for `video_id` (e.g. to
    replace a stale batch with a newer profile set) — does not touch a
    variant already popped and mid-render. Returns how many rows were removed.
    """
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM variant_queue WHERE video_id = ?", (video_id,))
        return cur.rowcount


def pop_next_variant() -> dict[str, Any] | None:
    """Removes and returns the oldest pending variant-queue row (FIFO across
    every video), or None if the queue is empty.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM variant_queue ORDER BY position ASC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM variant_queue WHERE id = ?", (row["id"],))
    d = dict(row)
    d["toggles"] = json.loads(d["toggles_json"])
    return d


def list_variant_queue(video_id: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if video_id:
            rows = conn.execute(
                "SELECT * FROM variant_queue WHERE video_id = ? ORDER BY position ASC", (video_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM variant_queue ORDER BY position ASC").fetchall()
    return [dict(r) for r in rows]


def kv_get(key: str, default: str | None = None) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM kv_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO kv_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def create_chat_message(
    *, message: str, video_query: str | None, video_id: str | None, status: str, reply: str
) -> dict[str, Any]:
    row_id = new_id()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, message, video_query, video_id, status, reply, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row_id, message, video_query, video_id, status, reply, time.time()),
        )
    return {"id": row_id, "message": message, "video_query": video_query, "video_id": video_id,
            "status": status, "reply": reply, "created_at": time.time()}


def list_chat_messages(limit: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
