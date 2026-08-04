"""Comedic sound effects — 100% procedurally synthesized with ffmpeg's own
audio generators (sine/noise sources + envelopes), never sourced from any
external clip library. This is deliberate: real "meme sound" libraries are
almost universally clips lifted from copyrighted shows/games/creators, which
is exactly the kind of copyright risk the channel needs to avoid. Synthesizing
short, original comedic stings sidesteps that entirely while still giving
each highlight a distinct, cartoon-y punctuation sound.

Generated once and cached on disk (they're tiny, deterministic, and never
change), then layered into the video's audio track via adelay + amix — the
same technique app/pipeline/music.py uses for background music.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import Highlight

SFX_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sfx_cache"

# name -> (aevalsrc/anoisesrc expression, duration_s)
_GENERATORS: dict[str, tuple[str, float]] = {
    # Quick rising chirp — reads as a light "pop"/"ping" of surprise.
    "pop": ("sin(2*PI*(500+2200*t)*t)*exp(-6*t)", 0.15),
    # Bell-like tone with a quiet harmonic — a friendly "ding" for a good moment.
    "ding": ("sin(2*PI*880*t)*exp(-4*t)+0.3*sin(2*PI*1760*t)*exp(-4*t)", 0.5),
    # Vibrato-modulated tone with decay — a cartoon "boing"/spring sound.
    "boing": ("sin(2*PI*(260+40*sin(2*PI*9*t))*t)*exp(-3.2*t)", 0.4),
    # Deep punchy bass hit, fast attack/decay — the classic internet "meme
    # boom" used to punctuate the single biggest moment in a video.
    "vineboom": ("sin(2*PI*55*t)*exp(-14*t)", 0.3),
    # Three-harmonic brass buzz — a cheerful hype-horn stinger for a
    # celebratory keyword moment ("harika!", "süper!").
    "airhorn": ("(0.6*sin(2*PI*440*t)+0.3*sin(2*PI*880*t)+0.1*sin(2*PI*1320*t))*exp(-1.4*t)", 0.5),
}

# Which synthesized sound plays for which highlight kind.
SFX_FOR_KIND = {"loud_peak": "pop", "exclaim": "ding", "keyword": "airhorn", "protected": "boing"}

# The single biggest moments (see effects.TOP_TIER_COUNT/protected_moments'
# 0.95 confidence) get a distinct, punchier sting instead of blending into
# the regular kind-based rotation — a "meme boom" reads as intentional
# emphasis rather than just another background ping.
TOP_TIER_SFX_CONFIDENCE = 0.9
TOP_TIER_SFX = "vineboom"

MAX_SFX_PER_VIDEO = 8
SFX_VOLUME_DB = -6.0


def _sfx_name_for(h: Highlight) -> str | None:
    if h.confidence >= TOP_TIER_SFX_CONFIDENCE:
        return TOP_TIER_SFX
    return SFX_FOR_KIND.get(h.kind)


def _ensure_cache() -> dict[str, Path]:
    SFX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, (expr, duration) in _GENERATORS.items():
        path = SFX_CACHE_DIR / f"{name}.wav"
        if not path.exists():
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={expr}:d={duration}:s=44100",
                "-af", f"afade=t=out:st={max(0.0, duration - 0.05):.3f}:d=0.05,volume=0.9",
                str(path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        paths[name] = path
    return paths


def _select_highlights(highlights: list[Highlight]) -> list[Highlight]:
    with_sfx = [h for h in highlights if _sfx_name_for(h)]
    with_sfx.sort(key=lambda h: h.confidence, reverse=True)
    chosen = with_sfx[:MAX_SFX_PER_VIDEO]
    return sorted(chosen, key=lambda h: h.t)


def apply_sound_effects(video_path: str, output_path: str, highlights: list[Highlight]) -> str:
    chosen = _select_highlights(highlights)
    if not chosen:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-c", "copy", output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    sfx_paths = _ensure_cache()

    cmd = ["ffmpeg", "-y", "-i", video_path]
    for h in chosen:
        cmd += ["-i", str(sfx_paths[_sfx_name_for(h)])]

    filter_parts = []
    mix_inputs = ["[0:a]"]
    for i, h in enumerate(chosen, start=1):
        delay_ms = max(0, int(h.t * 1000))
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={SFX_VOLUME_DB}dB[sfx{i}]")
        mix_inputs.append(f"[sfx{i}]")
    filter_complex = ";".join(filter_parts)
    filter_complex += f";{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0[aout]"

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
