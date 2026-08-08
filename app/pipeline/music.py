"""Free/royalty-free background music selection and mixing.

The library itself is just a local folder (music_library/) indexed by
music_library/index.json — see music_library/README.md for how to populate it
with zero-cost tracks (YouTube Audio Library, Pixabay Music, etc). No paid API
is ever called; scripts/fetch_pixabay_music.py is an optional helper for users
who add their own free Pixabay API key.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

from app.config import MUSIC_LIBRARY_DIR, settings
from app.models import Highlight, MusicTrack, TranscriptSegment

INDEX_PATH = MUSIC_LIBRARY_DIR / "index.json"

MOOD_KEYWORDS: dict[str, list[str]] = {
    "funny": ["komik", "gül", "haha", "şaka", "eğlen"],
    "exciting": ["hızlı", "koş", "yarış", "heyecan", "macera", "kazandım"],
    "calm": ["sakin", "yavaş", "uyku", "dinlen", "sessiz"],
    "playful": ["oyun", "oyna", "bahçe", "top", "kaydırak", "salıncak"],
}
DEFAULT_MOOD = "playful"  # this is a kids' play channel — playful is a safe default


def load_library() -> list[MusicTrack]:
    if not INDEX_PATH.exists():
        return []
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return [
        MusicTrack(
            path=str(MUSIC_LIBRARY_DIR / t["file"]),
            mood=t.get("mood", DEFAULT_MOOD),
            bpm=t.get("bpm"),
            license=t.get("license", "unknown"),
            attribution=t.get("attribution", ""),
        )
        for t in data
        if (MUSIC_LIBRARY_DIR / t["file"]).exists()
    ]


def classify_mood(segments: list[TranscriptSegment], highlights: list[Highlight]) -> str:
    text = " ".join(s.text.lower() for s in segments)
    scores = {mood: sum(text.count(kw) for kw in kws) for mood, kws in MOOD_KEYWORDS.items()}
    if highlights:
        scores["exciting"] = scores.get("exciting", 0) + len(highlights)
    best_mood = max(scores, key=scores.get) if any(scores.values()) else DEFAULT_MOOD
    return best_mood if scores.get(best_mood, 0) > 0 else DEFAULT_MOOD


def select_track(mood: str) -> MusicTrack | None:
    library = load_library()
    if not library:
        return None
    matching = [t for t in library if t.mood == mood] or library
    return random.choice(matching)


def mix_music(
    video_path: str,
    music_path: str,
    output_path: str,
    *,
    music_volume_db: float | None = None,
    duck_db: float | None = None,
) -> str:
    music_volume_db = music_volume_db if music_volume_db is not None else settings.music_default_volume_db
    duck_db = duck_db if duck_db is not None else settings.music_duck_db

    filter_complex = (
        f"[1:a]aloop=loop=-1:size=2e9,volume={music_volume_db}dB[music];"
        f"[music][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=400:makeup=1[ducked];"
        f"[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def apply_music_if_available(
    video_path: str,
    output_path: str,
    segments: list[TranscriptSegment],
    highlights: list[Highlight],
    *,
    mood_override: str | None = None,
) -> tuple[str, MusicTrack | None]:
    mood = mood_override if mood_override in MOOD_KEYWORDS else classify_mood(segments, highlights)
    track = select_track(mood)
    if track is None:
        return video_path, None
    mix_music(video_path, track.path, output_path)
    return output_path, track
