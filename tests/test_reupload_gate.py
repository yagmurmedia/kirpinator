"""Regression test: a video that was already uploaded once (e.g. to the
wrong YouTube account before the Drive/YouTube OAuth split) must still be
re-uploadable to the correct channel. The /approve route used to only allow
'ready_for_review', which permanently locked out any video whose status had
already flipped to 'uploaded'.
"""
from unittest.mock import patch

from app import db
from app.web import main


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_reupload.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


class _SyncThread:
    """Runs the target immediately instead of spawning a real thread, so the
    test can assert on the outcome without waiting/polling."""

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        self._target()


def test_already_uploaded_video_can_be_reapproved(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "threading", type("T", (), {"Thread": _SyncThread}))

    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.update_video(v["id"], output_path="/fake/out.mp4")
    db.update_video(v["id"], youtube_video_id="wrong-channel-id")
    db.set_status(v["id"], "uploaded")

    with patch("app.youtube.upload.upload_video", return_value="new-id") as mock_upload:
        main.approve_and_upload(v["id"])

    mock_upload.assert_called_once_with(v["id"])


def test_busy_video_cannot_be_reapproved(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "threading", type("T", (), {"Thread": _SyncThread}))

    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.update_video(v["id"], output_path="/fake/out.mp4")
    db.set_status(v["id"], "processing")

    with patch("app.youtube.upload.upload_video") as mock_upload:
        main.approve_and_upload(v["id"])

    mock_upload.assert_not_called()
    assert db.get_video(v["id"])["status"] == "processing"
