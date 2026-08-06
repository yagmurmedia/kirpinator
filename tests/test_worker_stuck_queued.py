from app import db
from app.jobs import worker


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_worker_stuck.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_queued_video_with_no_source_file_is_marked_failed_not_left_queued(tmp_path, monkeypatch):
    # Regression test for a real busy-loop: process_video raises
    # FileNotFoundError *before* it ever sets status='processing', so
    # without this backstop the video stays 'queued' forever and
    # _process_one_queued picks it right back up every single loop
    # iteration with zero backoff — starving everything else (including the
    # variant backlog) of a turn.
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.set_status(v["id"], "queued")  # local_source_path is still None

    did_work = worker._process_one_queued()

    assert did_work is True
    row = db.get_video(v["id"])
    assert row["status"] == "failed"
    assert row["error"]

    # And critically: it's no longer 'queued', so the very next call finds
    # nothing left to do instead of picking the same video right back up.
    assert worker._process_one_queued() is False
