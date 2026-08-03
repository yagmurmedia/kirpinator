"""Populates music_library/ from Incompetech (Kevin MacLeod's royalty-free
catalog) — no API key or account needed, and the whole catalog is licensed
either Creative Commons BY 4.0 (free with attribution) or via a separately
purchasable standard license. We use the free CC BY 4.0 path.

This is a one-time/occasional curation script, not part of the runtime
pipeline: it downloads a broad, mood-tagged, kid-appropriate selection into
music_library/ and writes index.json with the exact attribution text
Incompetech's own license-generator page requires.

Run manually: python scripts/build_music_library.py
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

from app.config import MUSIC_LIBRARY_DIR

CATALOG_URL = "https://incompetech.com/music/royalty-free/pieces.json"
DOWNLOAD_BASE = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Kirpinator music library builder)"}

# Genre ids (from the site's own genre list) we skip entirely regardless of
# feel tags — not appropriate for a children's channel or too seasonal/niche.
EXCLUDED_GENRE_IDS = {"10", "9"}  # Horror, Holiday

# Any piece whose feel/description/title mentions these is skipped, even if it
# also matches a target mood keyword (kid-safety filter takes priority).
EXCLUDE_KEYWORDS = [
    "horror", "dark", "scary", "macabre", "gloom", "eerie", "unnerving",
    "noire", "suspense", "creepy", "haunt", "death", "violent", "war",
    "sad", "sorrow", "grief", "funeral", "evil", "menace", "villain",
]

MOOD_FEEL_KEYWORDS = {
    "playful": ["bouncy", "bright", "grooving", "uplifting", "playful", "whimsical"],
    "funny": ["humorous", "comedic", "funny", "quirky", "goofy", "silly"],
    "exciting": ["action", "driving", "epic", "intense", "energetic", "triumphant", "adventurous"],
    "calm": ["calm", "calming", "relaxed", "gentle", "soft", "peaceful", "serene"],
}

TARGET_PER_MOOD = 8
MAX_LENGTH_SECONDS = 4 * 60  # skip anything longer than 4 minutes (faster downloads, easy looping)


def _length_to_seconds(length_str: str) -> int:
    parts = [int(p) for p in length_str.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def _text_blob(piece: dict) -> str:
    return " ".join(
        str(piece.get(k, "") or "") for k in ("title", "description", "feel", "instruments")
    ).lower()


def _is_kid_safe(piece: dict) -> bool:
    if str(piece.get("genre", "")) in EXCLUDED_GENRE_IDS:
        return False
    blob = _text_blob(piece)
    return not any(bad in blob for bad in EXCLUDE_KEYWORDS)


def _matches_mood(piece: dict, mood: str) -> bool:
    feel = str(piece.get("feel", "") or "").lower()
    return any(kw in feel for kw in MOOD_FEEL_KEYWORDS[mood])


def pick_tracks(catalog: list[dict]) -> dict[str, list[dict]]:
    picked: dict[str, list[dict]] = {mood: [] for mood in MOOD_FEEL_KEYWORDS}
    seen_filenames: set[str] = set()

    for mood in MOOD_FEEL_KEYWORDS:
        for piece in catalog:
            if len(picked[mood]) >= TARGET_PER_MOOD:
                break
            filename = piece.get("filename")
            if not filename or filename in seen_filenames:
                continue
            if not _is_kid_safe(piece):
                continue
            if _length_to_seconds(piece.get("length", "0:00")) > MAX_LENGTH_SECONDS:
                continue
            if not _matches_mood(piece, mood):
                continue
            picked[mood].append(piece)
            seen_filenames.add(filename)
    return picked


def attribution_text(title: str) -> str:
    return (
        f'"{title}"\n'
        "Kevin MacLeod (incompetech.com)\n"
        "Licensed under Creative Commons: By Attribution 4.0\n"
        "http://creativecommons.org/licenses/by/4.0/"
    )


def download_track(filename: str, dest: Path) -> bool:
    url = DOWNLOAD_BASE + urllib.parse.quote(filename)
    resp = requests.get(url, headers=HEADERS, timeout=60)
    if resp.status_code != 200 or not resp.content:
        print(f"  FAILED ({resp.status_code}): {filename}")
        return False
    dest.write_bytes(resp.content)
    return True


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name.strip()


def main() -> None:
    print("Fetching Incompetech catalog...")
    catalog = requests.get(CATALOG_URL, headers=HEADERS, timeout=60).json()
    print(f"Catalog has {len(catalog)} pieces.")

    picked = pick_tracks(catalog)
    for mood, pieces in picked.items():
        print(f"{mood}: {len(pieces)} tracks selected")

    index: list[dict] = []
    for mood, pieces in picked.items():
        for piece in pieces:
            src_filename = piece["filename"]
            safe_filename = sanitize_filename(src_filename)
            dest_path = MUSIC_LIBRARY_DIR / safe_filename
            print(f"Downloading [{mood}] {src_filename} ...")
            ok = download_track(src_filename, dest_path)
            if not ok:
                continue
            index.append(
                {
                    "file": safe_filename,
                    "mood": mood,
                    "bpm": int(piece["bpm"]) if str(piece.get("bpm", "")).isdigit() else None,
                    "license": "CC BY 4.0 - Kevin MacLeod (incompetech.com)",
                    "attribution": attribution_text(piece["title"]),
                }
            )
            time.sleep(0.5)  # be a polite, low-rate client

    index_path = MUSIC_LIBRARY_DIR / "index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(index)} tracks to {index_path}")


if __name__ == "__main__":
    main()
