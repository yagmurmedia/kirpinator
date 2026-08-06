from app import db


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_recover.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_stuck_processing_resets_to_queued(tmp_path, monkeypatch):
    # Safe to bounce straight to 'queued': its source file is already
    # downloaded, so the worker can pick it right back up and re-edit.
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.set_status(v["id"], "processing")

    recovered = db.recover_stuck_videos()

    assert recovered == [v["id"]]
    assert db.get_video(v["id"])["status"] == "queued"


def test_stuck_downloading_resets_to_discovered_not_queued(tmp_path, monkeypatch):
    # Regression test: this used to reset straight to 'queued', which sent an
    # undownloaded video (local_source_path still None) straight to the
    # editing worker. process_video raises FileNotFoundError *before* it can
    # change the status, so the video stayed 'queued' forever and the worker
    # busy-looped on it with zero backoff, starving every other video
    # (including the variant queue) of a turn. 'discovered' lets the Drive
    # poll's retry pass actually redownload it instead.
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.set_status(v["id"], "downloading")

    recovered = db.recover_stuck_videos()

    assert recovered == [v["id"]]
    assert db.get_video(v["id"])["status"] == "discovered"


def test_both_processing_and_downloading_recovered_together(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v1 = db.create_video(drive_file_id="e", source_filename="e.mp4")
    v2 = db.create_video(drive_file_id="f", source_filename="f.mp4")
    db.set_status(v1["id"], "processing")
    db.set_status(v2["id"], "downloading")

    recovered = db.recover_stuck_videos()

    assert set(recovered) == {v1["id"], v2["id"]}
    assert db.get_video(v1["id"])["status"] == "queued"
    assert db.get_video(v2["id"])["status"] == "discovered"


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
