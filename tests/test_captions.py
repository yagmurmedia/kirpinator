from app.models import TranscriptSegment, WordTiming
from app.pipeline.captions import build_ass_captions


def test_builds_one_dialogue_event_per_word(tmp_path):
    seg = TranscriptSegment(
        text="Merhaba dunya",
        start=0.0,
        end=1.0,
        words=[
            WordTiming(word="Merhaba", start=0.0, end=0.4),
            WordTiming(word="dunya", start=0.4, end=1.0),
        ],
    )
    out_path = tmp_path / "captions.ass"
    build_ass_captions([seg], str(out_path), video_width=1080, video_height=1920)

    content = out_path.read_text(encoding="utf-8")
    dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]

    assert len(dialogue_lines) == 2
    assert "Merhaba" in dialogue_lines[0]
    assert "dunya" in dialogue_lines[0]
    # The highlighted word's ASS color-override tag should appear in each line.
    assert "\\c" in dialogue_lines[0]


def test_skips_segments_with_no_word_timings(tmp_path):
    seg = TranscriptSegment(text="no words", start=0.0, end=1.0, words=[])
    out_path = tmp_path / "captions.ass"
    build_ass_captions([seg], str(out_path), video_width=1080, video_height=1920)

    content = out_path.read_text(encoding="utf-8")
    assert "Dialogue:" not in content


def test_word_never_stays_highlighted_more_than_the_hold_cap(tmp_path):
    # Real bug: a trailing pause before the segment's own (late) end time, or
    # before the next segment starts, froze the last word's highlight for
    # several seconds — looked broken rather than "spoken now".
    seg = TranscriptSegment(
        text="Bu cinler.",
        start=0.0,
        end=8.0,  # segment end trails far past the last word
        words=[WordTiming(word="Bu", start=0.0, end=0.3), WordTiming(word="cinler.", start=0.3, end=0.6)],
    )
    out_path = tmp_path / "captions.ass"
    build_ass_captions([seg], str(out_path), video_width=1080, video_height=1920)

    last_line = [l for l in out_path.read_text(encoding="utf-8").splitlines() if "cinler" in l][-1]

    def to_seconds(t: str) -> float:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    # Format: "Dialogue: 0,H:MM:SS.cc,H:MM:SS.cc,..."
    fields = last_line.split(",")
    end_s = to_seconds(fields[2])
    word_actually_ends_at = 0.6  # the word's own WordTiming.end
    assert end_s - word_actually_ends_at <= 1.0 + 1e-6  # hold time is capped, not the 7.4s to seg.end


def test_wrap_style_is_smart_wrap_not_disabled(tmp_path):
    seg = TranscriptSegment(
        text="tek kelime",
        start=0.0, end=1.0,
        words=[WordTiming(word="tek", start=0.0, end=0.5)],
    )
    out_path = tmp_path / "captions.ass"
    build_ass_captions([seg], str(out_path), video_width=1080, video_height=1920)
    assert "WrapStyle: 0" in out_path.read_text(encoding="utf-8")
