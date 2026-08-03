"""HDR -> SDR tonemap normalization.

The Galaxy phone sources are sometimes shot in HDR (HEVC, PQ transfer curve).
If that's re-encoded straight to 8-bit x264 without tonemapping, the result
looks washed out or crushed (a very common, easy-to-miss bug in ffmpeg
pipelines). Doing the tonemap once, up front, keeps every later stage
(cut/crop/effects) working with plain SDR bt709 footage.
"""
from __future__ import annotations

import subprocess

# Hable tonemap is a reasonable, filmic-looking default that doesn't require
# per-video tuning; npl=100 targets a typical SDR display's nominal peak luminance.
_TONEMAP_FILTER = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)


def tonemap_to_sdr(source_path: str, output_path: str) -> str:
    cmd = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-vf", _TONEMAP_FILTER,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
