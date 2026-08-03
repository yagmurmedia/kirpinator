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
