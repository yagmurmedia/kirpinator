from app import db


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_recover.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_stuck_processing_and_downloading_reset_to_queued(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v1 = db.create_video(drive_file_id="a", source_filename="a.mp4")
    v2 = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.set_status(v1["id"], "processing")
    db.set_status(v2["id"], "downloading")

    recovered = db.recover_stuck_videos()

    assert set(recovered) == {v1["id"], v2["id"]}
    assert db.get_video(v1["id"])["status"] == "queued"
    assert db.get_video(v2["id"])["status"] == "queued"


def test_uploading_is_left_alone(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="c", source_filename="c.mp4")
    db.set_status(v["id"], "uploading")

    recovered = db.recover_stuck_videos()

    assert recovered == []
    assert db.get_video(v["id"])["status"] == "uploading"


def test_ready_for_review_untouched(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="d", source_filename="d.mp4")
    db.set_status(v["id"], "ready_for_review")

    db.recover_stuck_videos()

    assert db.get_video(v["id"])["status"] == "ready_for_review"
