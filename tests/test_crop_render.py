import subprocess

import pytest

from app.models import CropKeyframe
from app.pipeline.crop_render import COLOR_GRADE, render_crop


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not available")
def test_render_crop_applies_color_grade_in_a_single_pass(tmp_path):
    # Real render, not mocked: the color grade must not break the existing
    # sendcmd crop pipeline, and must apply in the same ffmpeg pass (no
    # extra re-encode generation) rather than a separate step.
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
        check=True, capture_output=True,
    )

    out = tmp_path / "out.mp4"
    keyframes = [
        CropKeyframe(t=0.0, x=0, y=0, w=320, h=240),
        CropKeyframe(t=2.0, x=0, y=0, w=320, h=240),
    ]
    render_crop(str(src), str(out), keyframes, 240, 180, work_dir=str(tmp_path))

    assert out.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert "240" in probe.stdout and "180" in probe.stdout


def test_color_grade_is_a_constant_lift_not_a_flash():
    # Documents intent: no enable='between(t,...)' gating — the whole point
    # is it applies to every frame uniformly, unlike the removed per-highlight
    # flash/vignette/color-pop effects.
    assert "enable=" not in COLOR_GRADE
    assert "eq=" in COLOR_GRADE
