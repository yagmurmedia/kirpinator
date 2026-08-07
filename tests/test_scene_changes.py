import subprocess

import pytest

from app.pipeline.highlight_detector import SCENE_CHANGE_CONFIDENCE, detect_scene_changes


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not available")
def test_detects_a_real_scene_cut(tmp_path):
    # Real, not mocked: two visually distinct 3s color clips concatenated —
    # a genuine hard cut at t=3.0s that a human would also call a scene change.
    video_path = tmp_path / "two_scenes.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=red:size=320x240:duration=3:rate=25",
        "-f", "lavfi", "-i", "color=c=blue:size=320x240:duration=3:rate=25",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
        "-map", "[outv]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    highlights = detect_scene_changes(str(video_path))

    assert len(highlights) == 1
    assert highlights[0].kind == "scene_change"
    assert highlights[0].confidence == SCENE_CHANGE_CONFIDENCE
    assert abs(highlights[0].t - 3.0) < 0.2


def test_missing_file_fails_soft_returns_empty_list():
    assert detect_scene_changes("this/path/does/not/exist.mp4") == []


def test_confidence_stays_below_every_other_signal_and_top_tier_threshold():
    # Documents the deliberate design: a bare scene cut must never outrank a
    # real audio/keyword highlight, and must stay under the ~0.9 top-tier
    # threshold in effects.py so a routine camera cut alone can never
    # trigger the "İZLE" callout.
    assert SCENE_CHANGE_CONFIDENCE < 0.5  # below exclaim (0.5), loud_peak (0.6), keyword (0.8)
    assert SCENE_CHANGE_CONFIDENCE < 0.9
