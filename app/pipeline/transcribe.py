"""Local, free speech-to-text via faster-whisper (CTranslate2 — no torch, no paid API).

Produces sentence-like segments with word-level timestamps so downstream stages
(silence merging, segment planning) can guarantee cuts never land mid-sentence.
"""
from __future__ import annotations

import logging
import threading

from app.config import settings
from app.models import TranscriptSegment, WordTiming

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel

                logger.info("Loading Whisper model '%s'...", settings.whisper_model_size)
                _model = WhisperModel(
                    settings.whisper_model_size,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                )
    return _model


def transcribe(audio_or_video_path: str) -> list[TranscriptSegment]:
    """Returns sentence-level segments. Whisper already splits on natural sentence
    boundaries (punctuation/pause-aware), so a "segment" here is treated as an
    atomic, never-split-mid-sentence unit by the rest of the pipeline.
    """
    model = _get_model()
    segments, _info = model.transcribe(
        audio_or_video_path,
        language=settings.whisper_language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": int(settings.min_silence_duration_s * 1000)},
    )

    result: list[TranscriptSegment] = []
    for seg in segments:
        words = [
            WordTiming(word=w.word.strip(), start=w.start, end=w.end)
            for w in (seg.words or [])
        ]
        result.append(
            TranscriptSegment(text=seg.text.strip(), start=seg.start, end=seg.end, words=words)
        )
    return result


def transcript_to_plain_text(segments: list[TranscriptSegment]) -> str:
    return " ".join(s.text for s in segments).strip()
