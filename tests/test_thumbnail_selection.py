from fastapi.responses import HTMLResponse

from app import db
from app.web import main


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_thumb.db")
    with db.get_conn() as conn:
        conn.executescript(db.SCHEMA)


def _make_candidates(tmp_path, n=3):
    paths = []
    for i in range(n):
        p = tmp_path / f"cand_{i}.jpg"
        p.write_bytes(f"img{i}".encode())
        paths.append(str(p))
    return paths


def test_select_thumbnail_sets_selected_path(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    candidates = _make_candidates(tmp_path)
    v = db.create_video(drive_file_id="a", source_filename="a.mp4")
    db.update_video(v["id"], thumbnail_candidates=candidates)

    main.select_thumbnail(v["id"], index=1)

    row = db.get_video(v["id"])
    assert row["selected_thumbnail_path"] == candidates[1]


def test_select_thumbnail_out_of_range_is_noop(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    candidates = _make_candidates(tmp_path)
    v = db.create_video(drive_file_id="b", source_filename="b.mp4")
    db.update_video(v["id"], thumbnail_candidates=candidates)

    main.select_thumbnail(v["id"], index=99)

    row = db.get_video(v["id"])
    assert row["selected_thumbnail_path"] is None


def test_select_thumbnail_unknown_video_is_noop(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    # Should not raise even though the video doesn't exist.
    main.select_thumbnail("does-not-exist", index=0)


def test_thumbnail_candidate_serves_matching_file(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    candidates = _make_candidates(tmp_path)
    v = db.create_video(drive_file_id="c", source_filename="c.mp4")
    db.update_video(v["id"], thumbnail_candidates=candidates)

    response = main.thumbnail_candidate(v["id"], 0)

    assert response.path == candidates[0]


def test_thumbnail_candidate_out_of_range_returns_404(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    candidates = _make_candidates(tmp_path)
    v = db.create_video(drive_file_id="d", source_filename="d.mp4")
    db.update_video(v["id"], thumbnail_candidates=candidates)

    response = main.thumbnail_candidate(v["id"], 5)

    assert isinstance(response, HTMLResponse)
    assert response.status_code == 404
