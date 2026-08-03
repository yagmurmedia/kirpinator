"""Plain dataclasses used to pass structured data between pipeline stages.
(Not ORM models — persistence goes through app.db's plain dict rows.)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


@dataclass
class TranscriptSegment:
    """One sentence-like chunk from Whisper, with word-level timings."""

    text: str
    start: float
    end: float
    words: list[WordTiming] = field(default_factory=list)


@dataclass
class SilenceInterval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class KeepRange:
    """A time range from the source video that survives the edit, with sentence-safe bounds."""

    start: float
    end: float
    reason: str = "speech"

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class CropKeyframe:
    t: float
    x: int
    y: int
    w: int
    h: int


@dataclass
class Highlight:
    t: float
    kind: str  # "laugh" | "exclaim" | "loud_peak" | "keyword"
    label: str
    confidence: float = 0.5


@dataclass
class MusicTrack:
    path: str
    mood: str
    bpm: int | None
    license: str
    attribution: str = ""


@dataclass
class VideoToggles:
    cut_silence: bool = True
    face_crop: bool = True
    music: bool = True
    effects: bool = True
    made_for_kids: bool | None = None  # None => use channel default
    custom_instructions: str = ""

    @classmethod
    def from_dict(cls, d: dict | None) -> "VideoToggles":
        d = d or {}
        return cls(
            cut_silence=d.get("cut_silence", True),
            face_crop=d.get("face_crop", True),
            music=d.get("music", True),
            effects=d.get("effects", True),
            made_for_kids=d.get("made_for_kids"),
            custom_instructions=d.get("custom_instructions", ""),
        )

    def to_dict(self) -> dict:
        return {
            "cut_silence": self.cut_silence,
            "face_crop": self.face_crop,
            "music": self.music,
            "effects": self.effects,
            "made_for_kids": self.made_for_kids,
            "custom_instructions": self.custom_instructions,
        }
