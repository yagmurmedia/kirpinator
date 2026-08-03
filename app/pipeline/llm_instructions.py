"""Turns a free-text chat message ("diş videosunu komik ve alt yazılı hazırla")
into a video name to look up plus toggle overrides, using a small local LLM
via Ollama — free, runs entirely on this PC, no API key.

This only has one job: pull structure out of loose natural language. The
actual toggle semantics (what "efektsiz" means, etc.) still live in
app/pipeline/instructions.py, which independently reprocesses whatever text
ends up in custom_instructions at render time — so if the LLM is unavailable
or returns something odd, the rule-based parser is still a real fallback, not
just an error message.
"""
from __future__ import annotations

import dataclasses
import json
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen bir video düzenleme asistanısın. Kullanıcı sana Türkçe, \
serbest metinle hangi videoyu ve nasıl hazırlamasını istediğini yazacak. \
Görevin SADECE şu JSON şemasını üretmek, başka hiçbir şey yazma:

{"video_query": "<videoyu tanımlayan kısa anahtar kelime/isim parçası>", \
"toggles": {"cut_silence": true|false, "face_crop": true|false, "music": true|false, \
"effects": true|false, "captions": true|false}, \
"made_for_kids": true|false|null}

Kurallar:
- video_query: kullanıcının bahsettiği video dosyasını bulmaya yarayacak en \
kısa, en ayırt edici kelime öbeği (örn. "diş çekimi", "barbie", "salıncak").
- toggles: sadece kullanıcının AÇIKÇA belirttiği özellikleri dahil et \
(örn. "alt yazısız" -> captions:false). Belirtilmeyenleri toggles objesine \
HİÇ ekleme.
- made_for_kids: sadece açıkça belirtilmişse true/false, yoksa null.
- Sadece geçerli JSON döndür, açıklama/markdown/kod bloğu ekleme.
"""


@dataclasses.dataclass
class ChatParseResult:
    video_query: str
    toggles: dict
    made_for_kids: bool | None
    raw_text: str
    used_llm: bool


def _fallback_parse(message: str) -> ChatParseResult:
    """No LLM available: treat the whole message as both the search query and
    the free-text instructions (the rule-based parser in instructions.py will
    still pick up toggle phrases from it at render time).
    """
    return ChatParseResult(
        video_query=message.strip(), toggles={}, made_for_kids=None, raw_text=message, used_llm=False
    )


def parse_chat_message(message: str) -> ChatParseResult:
    try:
        resp = requests.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": SYSTEM_PROMPT,
                "prompt": message,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            # First call after Ollama starts (or after 5min idle) has to load
            # the model into RAM, which alone can take 15-20s on a CPU-only
            # setup — a short timeout here would make /chat flaky.
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json()["response"]
        parsed = json.loads(raw)
        video_query = str(parsed.get("video_query") or "").strip()
        if not video_query:
            return _fallback_parse(message)
        toggles = parsed.get("toggles") or {}
        toggles = {k: bool(v) for k, v in toggles.items() if k in
                   {"cut_silence", "face_crop", "music", "effects", "captions"}}
        made_for_kids = parsed.get("made_for_kids")
        if made_for_kids is not None:
            made_for_kids = bool(made_for_kids)
        return ChatParseResult(
            video_query=video_query, toggles=toggles, made_for_kids=made_for_kids,
            raw_text=message, used_llm=True,
        )
    except Exception:
        logger.warning("Local LLM unavailable/failed, falling back to plain text search", exc_info=True)
        return _fallback_parse(message)
