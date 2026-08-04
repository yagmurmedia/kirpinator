"""Turns a free-text chat message ("diş videosunu komik ve alt yazılı hazırla")
into a video name to search for, using a small local LLM via Ollama — free,
runs entirely on this PC, no API key.

This deliberately has ONE job: identify which video the user means. Toggle
interpretation ("efektsiz", "alt yazısız", etc.) is intentionally NOT the
LLM's responsibility — app/pipeline/instructions.py's rule-based parser
already reprocesses the full raw message at render time, and in practice the
3B model asked to also emit toggle overrides would confidently set toggles
the user never mentioned (observed repeatedly on real messages: it silently
turned off captions and silence-cutting on requests that never mentioned
either). A wrong "found nothing" is recoverable by asking again; a silently
wrong toggle isn't something the user would even think to check for.
"""
from __future__ import annotations

import dataclasses
import json
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen bir video arama asistanısın. Kullanıcı sana Türkçe, \
serbest metinle bir video hakkında talimat yazacak (hangi videoyu, nasıl \
hazırlamasını istediği). Görevin SADECE o mesajda bahsedilen videoyu \
tanımlayan en kısa, en ayırt edici kelime öbeğini bulmak — dosya adı, \
takma isim ya da açık bir konu olabilir (örn. "diş çekimi", "barbie", \
"salıncak", "3D Pencil").

SADECE şu JSON şemasını üret, başka hiçbir şey yazma:
{"video_query": "<kısa kelime öbeği>"}

Video hakkında ne yapılacağıyla (efekt, müzik, alt yazı vb.) hiç ilgilenme —
sadece hangi videodan bahsedildiğini bul.
"""


@dataclasses.dataclass
class ChatParseResult:
    video_query: str
    toggles: dict
    made_for_kids: bool | None
    raw_text: str
    used_llm: bool


def _fallback_parse(message: str) -> ChatParseResult:
    """No LLM available: treat the whole message as the search query (the
    rule-based parser in instructions.py still picks up toggle phrases from
    the raw message at render time regardless of this path).
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
        return ChatParseResult(
            video_query=video_query, toggles={}, made_for_kids=None, raw_text=message, used_llm=True,
        )
    except Exception:
        logger.warning("Local LLM unavailable/failed, falling back to plain text search", exc_info=True)
        return _fallback_parse(message)
