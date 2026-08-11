from app import db


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_versions.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_first_run_has_nothing_to_archive(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    assert db.archive_current_version(v["id"]) is None
    assert db.list_versions(v["id"]) == []


def test_reprocess_archives_previous_output_and_bumps_version(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from app import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "THUMBNAIL_DIR", tmp_path)

    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    out1 = tmp_path / "b_out.mp4"
    out1.write_bytes(b"first edit")
    db.update_video(v["id"], output_path=str(out1), title="İlk hali")

    archived_version = db.archive_current_version(v["id"])

    assert archived_version == 1
    versions = db.list_versions(v["id"])
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["title"] == "İlk hali"
    assert (tmp_path / f"{v['id']}_v1.mp4").exists()
    assert (tmp_path / f"{v['id']}_v1.mp4").read_bytes() == b"first edit"

    reloaded = db.get_video(v["id"])
    assert reloaded["version"] == 2


def test_archived_version_captures_the_variant_profile_that_produced_it(tmp_path, monkeypatch):
    # A video can end up with a dozen+ archived versions from the variant
    # batch (V1..V10) — without recording which profile produced each one,
    # they're indistinguishable "V7", "V8"... in the review UI.
    _fresh_db(tmp_path, monkeypatch)
    from app import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "THUMBNAIL_DIR", tmp_path)

    v = db.create_video(drive_file_id="e", source_filename="e.mp4")
    out1 = tmp_path / "e_out.mp4"
    out1.write_bytes(b"first edit")
    db.update_video(v["id"], output_path=str(out1), variant_label="sakin muzikli, yuz takipli")

    db.archive_current_version(v["id"])

    versions = db.list_versions(v["id"])
    assert versions[0]["profile_name"] == "sakin muzikli, yuz takipli"


def test_archived_version_captures_description_and_tags_for_direct_upload(tmp_path, monkeypatch):
    # Needed so a specific archived version can be uploaded on its own
    # (see app.youtube.upload.upload_video's version_row_id path) without
    # falling back to whatever the *current* live video's metadata says.
    _fresh_db(tmp_path, monkeypatch)
    from app import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "THUMBNAIL_DIR", tmp_path)

    v = db.create_video(drive_file_id="f", source_filename="f.mp4")
    out1 = tmp_path / "f_out.mp4"
    out1.write_bytes(b"data")
    db.update_video(
        v["id"], output_path=str(out1),
        title="Bir Başlık", description="Bir açıklama", tags=["etiket1", "etiket2"],
    )

    db.archive_current_version(v["id"])

    versions = db.list_versions(v["id"])
    assert versions[0]["description"] == "Bir açıklama"
    assert versions[0]["tags"] == ["etiket1", "etiket2"]


def test_delete_version_removes_row_and_file(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from app import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "THUMBNAIL_DIR", tmp_path)

    v = db.create_video(drive_file_id="c", source_filename="c.mp4")
    out1 = tmp_path / "c_out.mp4"
    out1.write_bytes(b"data")
    db.update_video(v["id"], output_path=str(out1))
    db.archive_current_version(v["id"])

    version_row = db.list_versions(v["id"])[0]
    archived_path = version_row["output_path"]
    assert archived_path is not None

    assert db.delete_version(v["id"], version_row["id"]) is True
    assert db.list_versions(v["id"]) == []
    from pathlib import Path
    assert not Path(archived_path).exists()


def test_delete_video_also_cleans_up_archived_versions(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from app import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "THUMBNAIL_DIR", tmp_path)
    monkeypatch.setattr(config, "WORKING_DIR", tmp_path / "working")

    v = db.create_video(drive_file_id="d", source_filename="d.mp4")
    out1 = tmp_path / "d_out.mp4"
    out1.write_bytes(b"data")
    db.update_video(v["id"], output_path=str(out1))
    db.archive_current_version(v["id"])
    archived_path = db.list_versions(v["id"])[0]["output_path"]

    db.delete_video(v["id"])

    from pathlib import Path
    assert not Path(archived_path).exists()
