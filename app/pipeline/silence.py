"""Dead-air detection via ffmpeg's silencedetect audio filter (free, no extra deps)."""
from __future__ import annotations

import re
import subprocess

from app.config import settings
from app.models import SilenceInterval

_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silence(
    path: str,
    *,
    threshold_db: float | None = None,
    min_duration_s: float | None = None,
) -> list[SilenceInterval]:
    threshold_db = threshold_db if threshold_db is not None else settings.silence_threshold_db
    min_duration_s = min_duration_s if min_duration_s is not None else settings.min_silence_duration_s

    cmd = [
        "ffmpeg",
        "-i",
        path,
        "-af",
        f"silencedetect=noise={threshold_db}dB:d={min_duration_s}",
        "-f",
        "null",
        "-",
    ]
    # ffmpeg writes filter logs to stderr.
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stderr

    intervals: list[SilenceInterval] = []
    pending_start: float | None = None
    for line in log.splitlines():
        m_start = _START_RE.search(line)
        if m_start:
            pending_start = float(m_start.group(1))
            continue
        m_end = _END_RE.search(line)
        if m_end and pending_start is not None:
            intervals.append(SilenceInterval(start=pending_start, end=float(m_end.group(1))))
            pending_start = None

    return intervals
