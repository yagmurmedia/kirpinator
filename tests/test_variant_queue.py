import pytest

from app import db


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_variants.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def test_pop_returns_none_when_empty(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert db.pop_next_variant() is None


def test_enqueue_and_pop_preserves_fifo_order(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.enqueue_variants(
        v["id"],
        [
            ("Sade", {"music": False, "effects": False}),
            ("Muzikli", {"music": True, "effects": False}),
            ("Efektli", {"music": False, "effects": True}),
        ],
    )

    first = db.pop_next_variant()
    second = db.pop_next_variant()
    third = db.pop_next_variant()

    assert [first["profile_name"], second["profile_name"], third["profile_name"]] == [
        "Sade", "Muzikli", "Efektli",
    ]
    assert first["toggles"] == {"music": False, "effects": False}
    assert db.pop_next_variant() is None


def test_pop_removes_the_row(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.enqueue_variants(v["id"], [("Sade", {"music": False})])

    assert len(db.list_variant_queue(v["id"])) == 1
    db.pop_next_variant()
    assert db.list_variant_queue(v["id"]) == []


def test_list_variant_queue_filters_by_video(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v1 = db.create_video(drive_file_id="c", source_filename="c.mp4")
    v2 = db.create_video(drive_file_id="d", source_filename="d.mp4")
    db.enqueue_variants(v1["id"], [("A", {}), ("B", {})])
    db.enqueue_variants(v2["id"], [("C", {})])

    assert len(db.list_variant_queue(v1["id"])) == 2
    assert len(db.list_variant_queue(v2["id"])) == 1
    assert len(db.list_variant_queue()) == 3


def test_clear_variant_queue_only_affects_that_video(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v1 = db.create_video(drive_file_id="e", source_filename="e.mp4")
    v2 = db.create_video(drive_file_id="f", source_filename="f.mp4")
    db.enqueue_variants(v1["id"], [("A", {}), ("B", {})])
    db.enqueue_variants(v2["id"], [("C", {})])

    removed = db.clear_variant_queue(v1["id"])

    assert removed == 2
    assert db.list_variant_queue(v1["id"]) == []
    assert len(db.list_variant_queue(v2["id"])) == 1


def test_clear_variant_queue_on_empty_video_returns_zero(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="g", source_filename="g.mp4")
    assert db.clear_variant_queue(v["id"]) == 0


def test_low_priority_variants_wait_for_normal_priority_ones_from_any_video(tmp_path, monkeypatch):
    # Real scenario: video A gets its long-form batch queued low-priority,
    # then video B (discovered later) gets a normal-priority Shorts batch —
    # B's Shorts must still be drained before A's long-form takes, since
    # Shorts are the system-wide priority regardless of enqueue order.
    _fresh_db(tmp_path, monkeypatch)
    a = db.create_video(drive_file_id="h", source_filename="h.mp4")
    b = db.create_video(drive_file_id="i", source_filename="i.mp4")

    db.enqueue_variants(a["id"], [("uzun video: standart", {})], priority="low")
    db.enqueue_variants(b["id"], [("muziksiz, yuz takipli", {})])  # normal, enqueued after

    first = db.pop_next_variant()
    second = db.pop_next_variant()

    assert first["video_id"] == b["id"]
    assert second["video_id"] == a["id"]


def test_invalid_priority_rejected(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    v = db.create_video(drive_file_id="j", source_filename="j.mp4")
    with pytest.raises(AssertionError):
        db.enqueue_variants(v["id"], [("X", {})], priority="urgent")
