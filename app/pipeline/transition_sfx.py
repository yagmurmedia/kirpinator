"""A synthesized "whoosh" layered at each crossfade cut point.

100% procedurally generated (filtered/enveloped noise via ffmpeg's own
generators) — same reasoning the project has used throughout: zero
copyright risk, no real audio clips. Distinct in kind from the earlier
per-highlight "pop/ding/boing" stings that were removed as gimmicky: those
punctuated individual reaction moments and read as meme-editing; a whoosh
marks a structural scene change, the same technique used in essentially
all produced video content — it's meant to be felt, not consciously noticed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

WHOOSH_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sfx_cache" / "whoosh.wav"
WHOOSH_DURATION_S = 0.4
WHOOSH_VOLUME_DB = -10.0


def _ensure_whoosh() -> Path:
    WHOOSH_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not WHOOSH_CACHE_PATH.exists():
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={WHOOSH_DURATION_S}:amplitude=0.8",
            "-af", (
                "bandpass=f=1500:width_type=o:w=2,"
                "afade=t=in:d=0.08,"
                f"afade=t=out:st={WHOOSH_DURATION_S - 0.15:.3f}:d=0.15"
            ),
            str(WHOOSH_CACHE_PATH),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    return WHOOSH_CACHE_PATH


def apply_transition_sounds(video_path: str, output_path: str, transition_times: list[float]) -> str:
    """`transition_times` are the *start* offsets of each crossfade (see
    cutter.crossfade_transition_times) — the whoosh is centered on each cut.
    """
    if not transition_times:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-c", "copy", "-movflags", "+faststart", output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    whoosh_path = _ensure_whoosh()
    cmd = ["ffmpeg", "-y", "-i", video_path]
    for _ in transition_times:
        cmd += ["-i", str(whoosh_path)]

    filter_parts = []
    mix_inputs = ["[0:a]"]
    for i, t in enumerate(transition_times, start=1):
        center = max(0.0, t - WHOOSH_DURATION_S / 2)
        delay_ms = int(center * 1000)
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={WHOOSH_VOLUME_DB}dB[wh{i}]")
        mix_inputs.append(f"[wh{i}]")
    filter_complex = ";".join(filter_parts)
    filter_complex += (
        f";{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0[aout]"
    )

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
