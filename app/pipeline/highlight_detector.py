"""Rule-based highlight ("funny/emphasized moment") detection.

v1 is intentionally simple and deterministic, per spec — it can be swapped for
a learned model later without touching the rest of the pipeline, since callers
only depend on the Highlight dataclass shape.

Two independent signals, merged:
  1. Audio energy peaks (RMS in dB) well above the clip's local baseline —
     catches laughter, shouting, sudden excited reactions.
  2. Turkish exclamation / excitement keyword spotting on the transcript.
"""
from __future__ import annotations

import subprocess

import numpy as np

from app.models import Highlight, TranscriptSegment

SAMPLE_RATE = 16000
WINDOW_S = 0.25
PEAK_DB_ABOVE_BASELINE = 7.0
MIN_GAP_BETWEEN_PEAKS_S = 1.0

EXCLAMATION_KEYWORDS = [
    # Kept deliberately to distinctive, low-frequency-in-ordinary-speech
    # exclamations. Generic words/phrases ("çok güzel", "oldu", "geldi",
    # "bitti", "aaa", "hop", "işte böyle") were tried here and pulled after
    # they matched routine narration constantly, firing the top-tier "İZLE"
    # combo effect on completely unremarkable lines. True can't-miss payoff
    # moments (e.g. "the tooth is coming out") are now found by
    # app.pipeline.protected_moments (semantic, instruction-driven) instead
    # of by bare substring match here.
    "vay", "vay canına", "harika", "süper", "muhteşem", "inanılmaz", "vov", "wov",
    "yaşasın", "bravo", "aferin", "işte oldu", "hurra",
    "vayy", "mükemmel", "wow", "yuhu",
    "başardım", "başardık", "tamamdır", "buldum",
]


def _extract_pcm(path: str) -> np.ndarray:
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", path,
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def _rms_db_windows(audio: np.ndarray) -> list[tuple[float, float]]:
    window = int(SAMPLE_RATE * WINDOW_S)
    if window <= 0 or len(audio) < window:
        return []
    n_windows = len(audio) // window
    out = []
    for i in range(n_windows):
        chunk = audio[i * window : (i + 1) * window]
        rms = float(np.sqrt(np.mean(np.square(chunk)) + 1e-12))
        db = 20 * np.log10(rms + 1e-12)
        out.append((i * WINDOW_S, db))
    return out


def detect_audio_peaks(path: str) -> list[Highlight]:
    try:
        audio = _extract_pcm(path)
    except subprocess.CalledProcessError:
        return []
    windows = _rms_db_windows(audio)
    if len(windows) < 4:
        return []

    dbs = np.array([db for _, db in windows])
    baseline = float(np.median(dbs))

    highlights: list[Highlight] = []
    last_peak_t = -1e9
    for t, db in windows:
        if db - baseline >= PEAK_DB_ABOVE_BASELINE and (t - last_peak_t) >= MIN_GAP_BETWEEN_PEAKS_S:
            highlights.append(
                Highlight(t=t, kind="loud_peak", label="loud moment", confidence=0.6)
            )
            last_peak_t = t
    return highlights


def detect_keyword_highlights(segments: list[TranscriptSegment]) -> list[Highlight]:
    highlights: list[Highlight] = []
    for seg in segments:
        text_lower = seg.text.lower()
        matched = next((kw for kw in EXCLAMATION_KEYWORDS if kw in text_lower), None)
        has_exclaim_mark = "!" in seg.text
        if matched:
            highlights.append(
                Highlight(t=seg.start, kind="keyword", label=matched, confidence=0.8)
            )
        elif has_exclaim_mark:
            highlights.append(
                Highlight(t=seg.start, kind="exclaim", label=seg.text[:24], confidence=0.5)
            )
    return highlights


def detect_highlights(video_path: str, segments: list[TranscriptSegment]) -> list[Highlight]:
    highlights = detect_audio_peaks(video_path) + detect_keyword_highlights(segments)
    highlights.sort(key=lambda h: h.t)

    # De-duplicate highlights that landed within a second of each other.
    deduped: list[Highlight] = []
    for h in highlights:
        if deduped and h.t - deduped[-1].t < 1.0:
            if h.confidence > deduped[-1].confidence:
                deduped[-1] = h
            continue
        deduped.append(h)
    return deduped


def to_timestamp_tuples(highlights: list[Highlight]) -> list[tuple[float, float]]:
    """Flattens Highlights into (t, confidence) pairs for segment_planner's
    highlight-aware range selection.
    """
    return [(h.t, h.confidence) for h in highlights]
