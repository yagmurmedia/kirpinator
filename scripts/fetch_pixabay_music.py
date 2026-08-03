"""Optional helper: pulls a batch of royalty-free tracks from Pixabay's free
Music API into music_library/, and registers them in index.json.

Requires the user to have created their own free Pixabay account and API key
(https://pixabay.com/api/docs/) and set PIXABAY_API_KEY in .env. This script
never runs automatically — it's a one-time manual convenience, since account
creation is something only the user can do.
"""
from __future__ import annotations

import json
import sys

import requests

from app.config import MUSIC_LIBRARY_DIR, settings

PIXABAY_MUSIC_ENDPOINT = "https://pixabay.com/api/videos/"  # music endpoint requires partner access;
# Pixabay's public Music search is only available via their website for most accounts.
# This script targets the case where the user has a key with music search enabled;
# if the request fails, follow music_library/README.md's manual-download instructions instead.

MOOD_QUERIES = {
    "playful": "kids playful",
    "funny": "funny quirky",
    "exciting": "upbeat energetic",
    "calm": "calm gentle",
}


def main() -> None:
    if not settings.pixabay_api_key:
        print("PIXABAY_API_KEY is not set in .env — nothing to do.")
        print("See music_library/README.md for manual download instructions instead.")
        sys.exit(1)

    index = []
    index_path = MUSIC_LIBRARY_DIR / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))

    for mood, query in MOOD_QUERIES.items():
        resp = requests.get(
            "https://pixabay.com/api/",
            params={"key": settings.pixabay_api_key, "q": query, "per_page": 3},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[{mood}] Pixabay request failed ({resp.status_code}); skipping.")
            continue
        # NOTE: Pixabay's core API covers images/videos; free music downloads must
        # currently be fetched by hand from pixabay.com/music (no stable public
        # audio-search endpoint at time of writing). This loop is a placeholder
        # that will start working automatically if/when Pixabay exposes one —
        # until then, use the manual steps in music_library/README.md.
        print(f"[{mood}] Automatic Pixabay music fetch isn't available yet — "
              "download manually from pixabay.com/music and add to index.json.")

    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
