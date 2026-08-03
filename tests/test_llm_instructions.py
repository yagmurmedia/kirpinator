from app.config import settings
from app.pipeline.llm_instructions import parse_chat_message


def test_falls_back_gracefully_when_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:1")  # nothing listens here
    result = parse_chat_message("barbie videosunu efektsiz hazirla")

    assert result.used_llm is False
    assert result.video_query == "barbie videosunu efektsiz hazirla"
    assert result.toggles == {}
    assert result.made_for_kids is None
