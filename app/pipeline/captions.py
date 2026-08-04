"""Burned-in, word-synced captions ("TikTok-style" highlighted captions).

Uses the word-level timestamps faster-whisper already produces, so each word
lights up on screen at the exact moment it's spoken — no separate alignment
step needed. Rendered as an ASS subtitle track (styling lives in the file
itself) and burned in with ffmpeg's `subtitles` filter (libass).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import TranscriptSegment

FONT_NAME = "Arial"
BASE_COLOR = "&H00FFFFFF"  # white
HIGHLIGHT_COLOR = "&H0000D7FF"  # bright yellow (BGR order in ASS)
OUTLINE_COLOR = "&H00000000"  # black

# A word never stays highlighted longer than this, even if the next word is
# much further away (long pause) or it's the last word in a segment whose
# nominal end time trails off — otherwise a caption can visibly freeze on one
# word for several seconds, reading as broken rather than "spoken now".
MAX_WORD_HOLD_S = 1.0

ASS_HEADER_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fontsize},{base_color},{base_color},{outline_color},&H00000000,1,0,0,0,100,100,0,0,1,{outline},1,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _fmt_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "").replace("}", "")


def build_ass_captions(
    segments: list[TranscriptSegment],
    output_path: str,
    video_width: int,
    video_height: int,
) -> str:
    fontsize = max(28, int(video_height * 0.055))
    outline = max(2, int(fontsize * 0.08))
    margin_v = int(video_height * 0.12)

    header = ASS_HEADER_TEMPLATE.format(
        width=video_width,
        height=video_height,
        font=FONT_NAME,
        fontsize=fontsize,
        base_color=BASE_COLOR,
        outline_color=OUTLINE_COLOR,
        outline=outline,
        margin_v=margin_v,
    )

    lines = [header]
    for seg in segments:
        words = [w for w in seg.words if w.word]
        if not words:
            continue
        for i, w in enumerate(words):
            start = w.start
            natural_end = words[i + 1].start if i + 1 < len(words) else max(w.end, seg.end)
            end = min(natural_end, w.end + MAX_WORD_HOLD_S)
            end = max(end, start + 0.05)
            if end <= start:
                continue
            parts = []
            for j, w2 in enumerate(words):
                token = _escape_ass_text(w2.word.strip())
                if j == i:
                    parts.append(f"{{\\c{HIGHLIGHT_COLOR}}}{token}{{\\c{BASE_COLOR}}}")
                else:
                    parts.append(token)
            text = " ".join(parts)
            lines.append(
                f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{text}"
            )

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


def burn_captions(video_path: str, ass_path: str, output_path: str) -> str:
    ass_ff_path = str(Path(ass_path)).replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles=filename='{ass_ff_path}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
