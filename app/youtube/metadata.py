"""Title/description/tag generation from the transcript.

Primary path: the local LLM (already used for /chat and protected-moment
detection) writes natural, content-specific metadata instead of a fixed
template — the old rule-based version always produced the same handful of
generic phrases ("Yağmur X ile Oynuyor! 🎈") regardless of what the video
actually showed, which reads as templated/AI-made rather than the
"professional YouTuber" mission calls for.

Fails safe: any LLM problem (Ollama down, bad JSON, timeout) falls back to
the original deterministic keyword-template generator, so metadata
generation can never block a render.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass

import requests

from app.config import settings
from app.models import TranscriptSegment

logger = logging.getLogger(__name__)

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

_METADATA_SYSTEM_PROMPT = """Sen bir çocuk/aile YouTube kanalı için çalışan profesyonel bir içerik editörüsün. \
Sana bir video konuşma transkripti verilecek. Bu videonun GERÇEK içeriğini yansıtan, \
doğal, ilgi çekici ama abartısız bir YouTube başlığı, açıklaması ve etiket listesi üret.

Kurallar:
- Başlık Türkçe olsun, en fazla 80 karakter, videonun gerçekte ne hakkında olduğunu \
yansıtsın. "Yağmur X ile oynuyor" gibi jenerik kalıp cümleler KULLANMA — transkriptten \
gerçek bir detay/an yakala ve onu başlığa yansıt. Doğal bir YouTuber gibi yaz, \
yapay zeka şablonu gibi durmasın. Merak uyandıran, tıklatan bir başlık üretmekten \
çekinme (ör. bir soru, bir sürpriz an, "sonunda..." gibi bir gerilim) — ama videoda \
GERÇEKTEN olmayan bir şeyi asla iddia etme, abartı yalan olmasın.
- Açıklama 2-4 cümle, samimi bir dille videonun gerçekte ne hakkında olduğunu anlatsın.
- 12-18 etiket ver: çoğu videonun gerçek içeriğine özgü olsun, ayrıca YouTube Shorts \
algoritmasında öne çıkan birkaç genel/trend etiket de ekle (ör. "shorts", "keşfet", \
"viral", "trend", "kesfet", "fyp" gibi — Türkçe kısa video içeriğinde yaygın olanlardan \
uygun olanları seç, hepsini zorla eklemene gerek yok).
- Aile/çocuk içeriği — uygun, güvenli, sıcak bir dil kullan, gerçek dışı iddialarda bulunma.

SADECE şu JSON şemasını üret: {"title": "...", "description": "...", "tags": ["...", ...]}
"""


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


def _generate_metadata_llm(
    segments: list[TranscriptSegment], *, long_form: bool
) -> GeneratedMetadata | None:
    if not segments:
        return None
    transcript_text = " ".join(s.text for s in segments)[:4000]
    format_note = "Bu bir YouTube Shorts videosu — başlığa #Shorts eklemeyi unutma." if not long_form \
        else "Bu uzun format bir YouTube videosu — #Shorts EKLEME."
    prompt = f"{format_note}\n\nTranskript:\n{transcript_text}"

    try:
        resp = requests.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": _METADATA_SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.6},
            },
            timeout=45,
        )
        resp.raise_for_status()
        parsed = json.loads(resp.json()["response"])
        title = str(parsed["title"]).strip()[:100]
        description = str(parsed["description"]).strip()[:4900]
        tags = [str(t).strip() for t in parsed.get("tags") or [] if str(t).strip()][:20]
        if not title or not description or not tags:
            return None
        if not long_form and "#shorts" not in title.lower():
            title = f"{title} #Shorts"[:100]
        return GeneratedMetadata(title=title, description=description, tags=tags)
    except Exception:
        logger.warning("LLM metadata generation unavailable, falling back to templates", exc_info=True)
        return None


def _generate_metadata_rule_based(
    segments: list[TranscriptSegment], mood: str | None, *, long_form: bool
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


def generate_metadata(
    segments: list[TranscriptSegment], mood: str | None, *, long_form: bool = False
) -> GeneratedMetadata:
    llm_result = _generate_metadata_llm(segments, long_form=long_form)
    if llm_result:
        return llm_result
    return _generate_metadata_rule_based(segments, mood, long_form=long_form)
