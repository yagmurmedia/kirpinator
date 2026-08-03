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
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
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
