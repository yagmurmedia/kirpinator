"""Speech-to-text. Two backends behind one function:

  - ElevenLabs Scribe (paid, used automatically if ELEVENLABS_API_KEY is set)
    — noticeably more accurate in practice, worth it for a channel that's
    leaning on word-synced captions as a core feature.
  - faster-whisper (free, local, always available as a fallback)

Both produce the same TranscriptSegment/WordTiming shape the rest of the
pipeline depends on (sentence-safe cutting, caption sync), so nothing else
needs to know which backend actually ran. If ElevenLabs is configured but the
API call fails for any reason (bad key, quota, network), transcription
silently falls back to Whisper rather than failing the whole video — a
transcription provider hiccup shouldn't be why a video doesn't get made.
"""
from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import threading
from pathlib import Path

import requests

from app.config import settings
from app.models import TranscriptSegment, WordTiming

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

_SENTENCE_END_RE = re.compile(r"[.!?…]\s*$")
_MAX_GAP_FOR_SAME_SENTENCE_S = 1.2


def _get_whisper_model():
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


def _transcribe_whisper(audio_or_video_path: str) -> list[TranscriptSegment]:
    model = _get_whisper_model()
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


def _extract_audio_for_upload(video_path: str) -> str:
    """ElevenLabs' STT endpoint accepts audio/video directly, but extracting a
    plain audio track keeps the upload small and fast for long source videos.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
    tmp.close()
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "aac", "-b:a", "128k",
        tmp.name,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return tmp.name


def _group_words_into_sentences(words: list[WordTiming]) -> list[TranscriptSegment]:
    """ElevenLabs returns a flat word list, not pre-grouped sentences. Groups
    on sentence-ending punctuation and on unusually long gaps between words
    (a natural pause/new thought) — same idea as Whisper's own segmentation,
    since the rest of the pipeline treats each returned segment as an atomic,
    never-split-mid-sentence unit.
    """
    segments: list[TranscriptSegment] = []
    current: list[WordTiming] = []

    def flush():
        if not current:
            return
        text = " ".join(w.word for w in current).strip()
        if text:
            segments.append(TranscriptSegment(text=text, start=current[0].start, end=current[-1].end, words=list(current)))
        current.clear()

    for w in words:
        if current and (w.start - current[-1].end) > _MAX_GAP_FOR_SAME_SENTENCE_S:
            flush()
        current.append(w)
        if _SENTENCE_END_RE.search(w.word):
            flush()
    flush()
    return segments


def _transcribe_elevenlabs(audio_or_video_path: str) -> list[TranscriptSegment]:
    audio_path = _extract_audio_for_upload(audio_or_video_path)
    try:
        with open(audio_path, "rb") as f:
            resp = requests.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": settings.elevenlabs_api_key},
                data={
                    "model_id": settings.elevenlabs_stt_model,
                    "language_code": settings.whisper_language,
                    "timestamps_granularity": "word",
                },
                files={"file": (Path(audio_path).name, f, "audio/m4a")},
                timeout=300,
            )
        resp.raise_for_status()
        data = resp.json()
    finally:
        Path(audio_path).unlink(missing_ok=True)

    words = [
        WordTiming(word=str(w["text"]).strip(), start=float(w["start"]), end=float(w["end"]))
        for w in data.get("words", [])
        if w.get("type", "word") == "word" and str(w.get("text", "")).strip()
    ]
    return _group_words_into_sentences(words)


def transcribe(audio_or_video_path: str) -> list[TranscriptSegment]:
    """Returns sentence-level segments with word-level timestamps."""
    if settings.elevenlabs_api_key:
        try:
            return _transcribe_elevenlabs(audio_or_video_path)
        except Exception:
            logger.warning("ElevenLabs transcription failed, falling back to local Whisper", exc_info=True)
    return _transcribe_whisper(audio_or_video_path)


def transcript_to_plain_text(segments: list[TranscriptSegment]) -> str:
    return " ".join(s.text for s in segments).strip()
