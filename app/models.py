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
    captions: bool = True
    long_form: bool = False  # False = YouTube Shorts (<=~60s); True = regular long-form video
    made_for_kids: bool | None = None  # None => use channel default
    custom_instructions: str = ""
    # None => auto-classify from transcript/highlights (app.pipeline.music);
    # set to force a specific mood ("playful"/"funny"/"exciting"/"calm") —
    # used by the Shorts variant profiles to offer genuinely different music
    # takes of the same edit instead of just on/off.
    music_mood: str | None = None

    @classmethod
    def from_dict(cls, d: dict | None) -> "VideoToggles":
        d = d or {}
        return cls(
            cut_silence=d.get("cut_silence", True),
            face_crop=d.get("face_crop", True),
            music=d.get("music", True),
            effects=d.get("effects", True),
            captions=d.get("captions", True),
            long_form=d.get("long_form", False),
            made_for_kids=d.get("made_for_kids"),
            custom_instructions=d.get("custom_instructions", ""),
            music_mood=d.get("music_mood"),
        )

    def to_dict(self) -> dict:
        return {
            "cut_silence": self.cut_silence,
            "face_crop": self.face_crop,
            "music": self.music,
            "effects": self.effects,
            "captions": self.captions,
            "long_form": self.long_form,
            "made_for_kids": self.made_for_kids,
            "custom_instructions": self.custom_instructions,
            "music_mood": self.music_mood,
        }
