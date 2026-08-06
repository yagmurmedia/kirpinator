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
