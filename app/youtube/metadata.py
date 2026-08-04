"""Rule-based (no paid LLM) title/description/tag generation from the transcript.

Keeps things simple and deterministic: extract the most frequent meaningful
Turkish words from what was actually said, drop them into channel-branded
templates. Good enough for consistent, on-brand Shorts metadata without an
API call.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.config import settings
from app.models import TranscriptSegment

STOPWORDS = {
    "bir", "bu", "şu", "o", "ve", "ile", "de", "da", "çok", "ama", "gibi", "için",
    "ne", "ya", "mi", "mı", "mu", "mü", "ben", "sen", "biz", "siz", "onlar",
    "var", "yok", "evet", "hayır", "şey", "şimdi", "sonra", "önce", "ise",
    "diye", "her", "hep", "daha", "en", "gel", "git", "ol", "yap", "ki",
}

MOOD_TITLE_TEMPLATES = {
    "funny": "{kw} ile Kahkaha Zamanı! 😂",
    "exciting": "{kw} Macerası Başlıyor! 🤩",
    "calm": "{kw} ile Huzurlu Anlar 🌤️",
    "playful": "Yağmur {kw} ile Oynuyor! 🎈",
    None: "Yağmur'un Oyun Bahçesinde {kw}! ✨",
}

DEFAULT_TAGS = [
    "Yağmurun Oyun Bahçesi", "çocuk videoları", "aile", "eğlenceli çocuk videosu",
    "kids video", "family fun", "shorts",
]


@dataclass
class GeneratedMetadata:
    title: str
    description: str
    tags: list[str]


def _top_keywords(segments: list[TranscriptSegment], n: int = 5) -> list[str]:
    text = " ".join(s.text for s in segments).lower()
    words = re.findall(r"[a-zçğıöşü]+", text)
    words = [w for w in words if len(w) > 2 and w not in STOPWORDS]
    counts = Counter(words)
    return [w for w, _ in counts.most_common(n)]


def generate_metadata(
    segments: list[TranscriptSegment], mood: str | None, *, long_form: bool = False
) -> GeneratedMetadata:
    keywords = _top_keywords(segments)
    headline_kw = keywords[0].capitalize() if keywords else "Yağmur"

    template = MOOD_TITLE_TEMPLATES.get(mood, MOOD_TITLE_TEMPLATES[None])
    title = template.format(kw=headline_kw)
    if not long_form and "#shorts" not in title.lower():
        title = f"{title} #Shorts"
    title = title[:100]

    snippet = " ".join(s.text for s in segments[:3]).strip()
    description_lines = [
        snippet or "Yağmur'un Oyun Bahçesi'nden yeni bir video!",
        "",
        settings.channel_hashtags,
    ]
    if keywords:
        description_lines.append("Konular: " + ", ".join(keywords))
    description = "\n".join(description_lines)[:4900]  # YouTube description limit is 5000

    tags = list(dict.fromkeys([*DEFAULT_TAGS, *keywords]))[:20]
    if long_form:
        tags = [t for t in tags if t.lower() != "shorts"]

    return GeneratedMetadata(title=title, description=description, tags=tags)
