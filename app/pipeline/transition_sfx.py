"""Synthesized transition sounds layered at each crossfade cut point.

100% procedurally generated (filtered/enveloped noise via ffmpeg's own
generators) — same reasoning the project has used throughout: zero
copyright risk, no real audio clips. Distinct in kind from the earlier
per-highlight "pop/ding/boing" stings that were removed as gimmicky: those
punctuated individual reaction moments and read as meme-editing; a whoosh
marks a structural scene change, the same technique used in essentially
all produced video content — it's meant to be felt, not consciously noticed.

Several variants (different filter center/width/duration) instead of one
fixed sound — user feedback was that a single identical whoosh on every
single cut, in every video, felt thin/repetitive. Still the same restrained
"felt not noticed" aesthetic, just picked with variety instead of being
the exact same clip every time.
"""
from __future__ import annotations

import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

SFX_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sfx_cache"


@dataclass(frozen=True)
class SfxVariant:
    name: str
    duration_s: float
    bandpass_freq: int
    bandpass_width_octaves: float
    volume_db: float


SFX_VARIANTS: list[SfxVariant] = [
    SfxVariant("whoosh", 0.4, 1500, 2.0, -10.0),
    SfxVariant("soft_swell", 0.5, 900, 1.5, -12.0),
    SfxVariant("quick_tick", 0.28, 2400, 2.5, -9.0),
    SfxVariant("low_sweep", 0.45, 650, 1.8, -11.0),
    SfxVariant("bright_swoosh", 0.35, 3000, 2.2, -11.0),
]


def _cache_path(variant: SfxVariant) -> Path:
    return SFX_CACHE_DIR / f"{variant.name}.wav"


def _ensure_variant(variant: SfxVariant) -> Path:
    path = _cache_path(variant)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={variant.duration_s}:amplitude=0.8",
            "-af", (
                f"bandpass=f={variant.bandpass_freq}:width_type=o:w={variant.bandpass_width_octaves},"
                "afade=t=in:d=0.08,"
                f"afade=t=out:st={variant.duration_s - 0.15:.3f}:d=0.15"
            ),
            str(path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    return path


def apply_transition_sounds(video_path: str, output_path: str, transition_times: list[float]) -> str:
    """`transition_times` are the *start* offsets of each crossfade (see
    cutter.crossfade_transition_times) — each gets a randomly picked sfx
    variant centered on the cut, so cuts don't all sound identical.
    """
    if not transition_times:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-c", "copy", "-movflags", "+faststart", output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    picks = [random.choice(SFX_VARIANTS) for _ in transition_times]
    sfx_paths = [_ensure_variant(v) for v in picks]

    cmd = ["ffmpeg", "-y", "-i", video_path]
    for p in sfx_paths:
        cmd += ["-i", str(p)]

    filter_parts = []
    mix_inputs = ["[0:a]"]
    for i, (t, variant) in enumerate(zip(transition_times, picks), start=1):
        center = max(0.0, t - variant.duration_s / 2)
        delay_ms = int(center * 1000)
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={variant.volume_db}dB[wh{i}]")
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
