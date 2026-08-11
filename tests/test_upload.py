from unittest.mock import Mock, patch

import pytest

from app import db
from app.youtube.upload import upload_video


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_upload.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def _mock_youtube_service(video_id="yt123"):
    service = Mock()
    request = Mock()
    request.next_chunk.return_value = (None, {"id": video_id})
    service.videos.return_value.insert.return_value = request
    service.thumbnails.return_value.set.return_value.execute.return_value = None
    return service


def test_refuses_upload_unless_approved(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.update_video(v["id"], output_path="/fake/out.mp4")
    db.set_status(v["id"], "ready_for_review")  # not 'approved'

    with pytest.raises(RuntimeError, match="not 'approved'"):
        upload_video(v["id"])


def test_default_uploads_current_live_output(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.update_video(
        v["id"], output_path="/fake/live.mp4", title="Canlı Başlık",
        description="Canlı açıklama", tags=["canli"],
    )
    db.set_status(v["id"], "approved")

    with patch("app.youtube.upload._youtube_service", return_value=_mock_youtube_service()) as mock_svc:
        with patch("app.youtube.upload.MediaFileUpload"):
            result = upload_video(v["id"])

    assert result == "yt123"
    body = mock_svc.return_value.videos.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["title"] == "Canlı Başlık"
    assert body["snippet"]["tags"] == ["canli"]

    row = db.get_video(v["id"])
    assert row["status"] == "uploaded"
    assert row["youtube_video_id"] == "yt123"


def test_version_row_id_uploads_that_versions_data_not_the_live_one(tmp_path, monkeypatch):
    # The real point of this feature: the reviewer picks a specific archived
    # variant, not whatever happens to be the current live output.
    _fresh_db(tmp_path, monkeypatch)
    from app import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "THUMBNAIL_DIR", tmp_path)

    v = db.create_video(drive_file_id="c", source_filename="c.mp4")
    out1 = tmp_path / "v1.mp4"
    out1.write_bytes(b"v1 data")
    db.update_video(
        v["id"], output_path=str(out1), title="V1 Başlık",
        description="V1 açıklama", tags=["v1tag"],
    )
    db.archive_current_version(v["id"])  # archives the above as version 1
    version_row = db.list_versions(v["id"])[0]

    # Now the live video has moved on to something else entirely.
    db.update_video(
        v["id"], output_path="/fake/v2.mp4", title="V2 Başlık",
        description="V2 açıklama", tags=["v2tag"],
    )
    db.set_status(v["id"], "approved")

    with patch("app.youtube.upload._youtube_service", return_value=_mock_youtube_service()) as mock_svc:
        with patch("app.youtube.upload.MediaFileUpload"):
            upload_video(v["id"], version_row_id=version_row["id"])

    body = mock_svc.return_value.videos.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["title"] == "V1 Başlık"
    assert body["snippet"]["tags"] == ["v1tag"]


def test_unknown_version_row_id_raises(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="d", source_filename="d.mp4")
    db.set_status(v["id"], "approved")

    with pytest.raises(RuntimeError, match="not found"):
        upload_video(v["id"], version_row_id="does-not-exist")
