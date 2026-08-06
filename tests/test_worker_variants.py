from app import db
from app.jobs import worker


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_worker_variants.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_returns_false_when_queue_empty(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert worker._promote_next_variant() is False


def test_applies_profile_toggles_and_queues_video(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.update_video(
        v["id"],
        toggles={"cut_silence": True, "music": True, "custom_instructions": "kaçırma"},
        custom_instructions="kaçırma",
    )
    db.set_status(v["id"], "ready_for_review")
    db.enqueue_variants(v["id"], [("Sade", {"music": False, "effects": False})])

    assert worker._promote_next_variant() is True

    row = db.get_video(v["id"])
    assert row["status"] == "queued"
    # The profile's overrides applied...
    assert row["toggles"]["music"] is False
    assert row["toggles"]["effects"] is False
    # ...without clobbering fields the profile didn't mention.
    assert row["toggles"]["cut_silence"] is True
    assert row["toggles"]["custom_instructions"] == "kaçırma"


def test_skips_gracefully_if_video_row_vanishes_after_being_popped(tmp_path, monkeypatch):
    # delete_video cleans up variant_queue rows for a normal delete, so to
    # exercise the defensive "video gone" branch in _promote_next_variant we
    # simulate the rarer race directly: a queued row outliving its video.
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.enqueue_variants(v["id"], [("Sade", {"music": False})])
    with db.get_conn() as conn:
        conn.execute("DELETE FROM videos WHERE id = ?", (v["id"],))

    assert worker._promote_next_variant() is True  # drained the row, didn't crash
    assert db.list_variant_queue() == []


def test_delete_video_also_clears_its_pending_variants(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="c", source_filename="c.mp4")
    db.enqueue_variants(v["id"], [("Sade", {"music": False})])

    db.delete_video(v["id"])

    assert db.list_variant_queue() == []
