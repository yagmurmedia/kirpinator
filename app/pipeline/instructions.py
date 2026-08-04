"""Rule-based parsing of free-text per-video instructions into toggle overrides.

This is deliberately keyword matching, not an LLM — it stays within the
project's zero-paid-API constraint. It only recognizes a fixed set of common
Turkish phrasings; anything it doesn't recognize is left as-is and the raw
text is still shown to the reviewer in the UI so nothing is silently dropped.

Matching uses word boundaries (so "müzik ekle" doesn't false-match inside
"müzik ekleme") and is first-match-wins per field, with each field's negative
("kapat/yapma") phrases listed before its positive phrases — that ordering is
what breaks ties for phrases that are genuine prefixes of one another (e.g.
"çocuk içeriği" is a real substring of "çocuk içeriği değil").

Both the phrase list and the incoming text are diacritic-normalized before
matching (ü->u, ş->s, etc.) — found in practice that a real message ("muzik
olmasin", typed without Turkish characters) silently failed to match
"müzik olmasın" otherwise, which is a very common way people actually type
on phones.
"""
from __future__ import annotations

import re

from app.models import VideoToggles

_TR_FOLD = str.maketrans("üöçşğıÜÖÇŞĞİ", "uocsgiuocsgi")


def _normalize(text: str) -> str:
    return text.translate(_TR_FOLD)

_RULES: list[tuple[tuple[str, ...], str, bool]] = [
    (("müzik ekleme", "müziksiz", "müzik yok", "müzik olmasın"), "music", False),
    (("müzik ekle", "müzik olsun", "müzikli"), "music", True),
    (("efekt istemiyorum", "efektsiz", "efekt yok", "efekt olmasın"), "effects", False),
    (("efekt ekle", "efektli", "efekt olsun"), "effects", True),
    (("sessizlik kesme", "kesme yapma", "kırpma yapma", "kesim yapma"), "cut_silence", False),
    (("sessizlikleri kes", "boşlukları kes"), "cut_silence", True),
    (("kadraj yapma", "kırpma yapma yüz", "takip etme", "yüz takibi yapma"), "face_crop", False),
    (("yüz takip et", "kadrajla"), "face_crop", True),
    (("made for kids kapalı", "çocuk içeriği değil", "kids off"), "made_for_kids", False),
    (("made for kids açık", "çocuk içeriği"), "made_for_kids", True),
    (("alt yazı ekleme", "alt yazısız", "alt yazı yok", "alt yazı olmasın"), "captions", False),
    (("alt yazı ekle", "alt yazılı", "alt yazı olsun"), "captions", True),
    (
        ("shorts olmayacak", "shorts değil", "uzun video", "uzun youtube videosu", "kısa video olmasın"),
        "long_form", True,
    ),
    (("shorts olsun", "kısa video olsun", "shorts videosu"), "long_form", False),
]

_compiled = [
    ([re.compile(rf"\b{re.escape(_normalize(p))}\b", re.IGNORECASE) for p in phrases], field, value)
    for phrases, field, value in _RULES
]


def apply_instructions(toggles: VideoToggles, instructions_text: str) -> VideoToggles:
    text = _normalize(instructions_text or "")
    already_set: set[str] = set()
    for patterns, field, value in _compiled:
        if field in already_set:
            continue
        if any(p.search(text) for p in patterns):
            setattr(toggles, field, value)
            already_set.add(field)
    return toggles
