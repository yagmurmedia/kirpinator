from app import db


def test_create_and_list_chat_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_chat.db")
    db.init_db()

    row = db.create_chat_message(
        message="barbie videosunu hazirla", video_query="barbie", video_id="abc123",
        status="queued", reply="bulundu ve kuyruga alindi",
    )
    assert row["status"] == "queued"

    history = db.list_chat_messages()
    assert len(history) == 1
    assert history[0]["message"] == "barbie videosunu hazirla"
    assert history[0]["video_id"] == "abc123"
