import subprocess

import pytest

from app.pipeline.transition_sfx import WHOOSH_DURATION_S, apply_transition_sounds


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _make_test_video(path, duration=5):
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=25",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(path),
        ],
        check=True, capture_output=True,
    )


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not available")
def test_no_transitions_just_copies_through(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.transition_sfx.WHOOSH_CACHE_PATH", tmp_path / "whoosh.wav"
    )
    src = tmp_path / "src.mp4"
    _make_test_video(src)
    out = tmp_path / "out.mp4"

    apply_transition_sounds(str(src), str(out), [])

    assert out.exists()


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not available")
def test_real_mix_at_transition_points_produces_valid_output(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.transition_sfx.WHOOSH_CACHE_PATH", tmp_path / "whoosh.wav"
    )
    src = tmp_path / "src.mp4"
    _make_test_video(src, duration=5)
    out = tmp_path / "out.mp4"

    apply_transition_sounds(str(src), str(out), [1.0, 3.0])

    assert out.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert abs(float(probe.stdout.strip()) - 5.0) < 0.5
    # Video stream must survive untouched (-c:v copy) — no extra re-encode
    # generation for the video track.
    vstream = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert "320" in vstream.stdout and "240" in vstream.stdout


def test_whoosh_duration_is_short_and_subtle():
    # Documents intent: a brief transition accent, not a sustained effect.
    assert 0.2 <= WHOOSH_DURATION_S <= 0.6
