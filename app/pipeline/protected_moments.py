"""Finds transcript segments that match a "don't cut this" instruction, so
segment_planner can guarantee they survive selection regardless of how the
generic highlight scoring (audio peaks + a fixed keyword list) rates them.

Why this exists: the generic highlight detector only catches loud/excited
moments and a fixed excitement-word list. A video's actual payoff moment
("diş çıktığı an" — the moment a tooth comes out) might be said matter-of-
factly rather than shouted, and use vocabulary specific to that video that no
fixed keyword list will ever cover. Rather than trying to hand-write keywords
for every possible video topic, this asks the local LLM (already used for
/chat) to match the instruction against the actual transcript — a semantic
matching task it's much better suited for than the toggle-extraction it
proved unreliable at.

Fails safe: only activates when the instruction text contains an explicit
"don't cut/skip/miss this" phrase, and any failure (LLM unavailable, bad
response, no match) just means zero protected segments — the pipeline
degrades to its normal highlight-based selection, never crashes.
"""
from __future__ import annotations

import json
import logging

import requests

from app.config import settings
from app.models import TranscriptSegment
from app.pipeline.instructions import _normalize

logger = logging.getLogger(__name__)

_TRIGGER_PHRASES = (
    "kaçırma", "silme", "kesme", "atlama", "çıkartma", "çıkarma", "sakın",
)

_SYSTEM_PROMPT = """Sana bir video talimatı ve o videonun konuşma transkripti \
verilecek. Talimatta "bu anı kaçırma/silme" gibi belirtilen önemli anın, \
transkriptteki hangi satır numaralarına denk geldiğini bul.

SADECE şu JSON şemasını üret: {"line_numbers": [<int>, ...]}

En fazla 5 satır numarası ver. Eminsen ver, emin değilsen boş liste döndür — \
tahmin yürütme.
"""


def _triggered(instructions_text: str) -> bool:
    text = _normalize(instructions_text or "").lower()
    return any(_normalize(phrase) in text for phrase in _TRIGGER_PHRASES)


def find_protected_segments(
    instructions_text: str, segments: list[TranscriptSegment]
) -> list[TranscriptSegment]:
    if not segments or not _triggered(instructions_text):
        return []

    transcript_block = "\n".join(f"{i}: {s.text}" for i, s in enumerate(segments))
    prompt = f"Talimat: {instructions_text}\n\nTranskript:\n{transcript_block}"

    try:
        resp = requests.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": _SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            timeout=60,
        )
        resp.raise_for_status()
        parsed = json.loads(resp.json()["response"])
        indices = parsed.get("line_numbers") or []
    except Exception:
        logger.warning("Protected-moment detection unavailable, skipping", exc_info=True)
        return []

    protected = []
    for i in indices:
        if isinstance(i, int) and 0 <= i < len(segments):
            protected.append(segments[i])
    if protected:
        logger.info(
            "Protected %d transcript segment(s) from instruction: %s",
            len(protected), [s.text[:40] for s in protected],
        )
    return protected
