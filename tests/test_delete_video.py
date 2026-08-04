from app import db


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_delete.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_delete_video_removes_row_and_events(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.log_event(v["id"], "pipeline", "started")

    assert db.delete_video(v["id"]) is True
    assert db.get_video(v["id"]) is None
    assert db.get_events(v["id"]) == []


def test_delete_video_removes_associated_files(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)

    src = tmp_path / "source.mp4"
    out = tmp_path / "output.mp4"
    thumb = tmp_path / "thumb.jpg"
    for p in (src, out, thumb):
        p.write_bytes(b"x")

    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.update_video(v["id"], local_source_path=str(src), output_path=str(out), thumbnail_path=str(thumb))

    db.delete_video(v["id"])

    assert not src.exists()
    assert not out.exists()
    assert not thumb.exists()


def test_delete_nonexistent_video_returns_false(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert db.delete_video("does-not-exist") is False


def test_delete_video_nulls_out_chat_message_references(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="c", source_filename="c.mp4")
    db.create_chat_message(message="hi", video_query="c", video_id=v["id"], status="queued", reply="ok")

    db.delete_video(v["id"])

    history = db.list_chat_messages()
    assert len(history) == 1
    assert history[0]["video_id"] is None
