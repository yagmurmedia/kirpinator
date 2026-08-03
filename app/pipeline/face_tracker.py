"""Face-aware auto-crop: samples frames, finds the main subject's face with
MediaPipe, and produces a smoothed crop path that keeps them in frame while
re-cropping the source to the target aspect ratio (vertical or horizontal).

Falls back to a static center crop if no face is ever detected (e.g. subject
turned away) so the pipeline never hard-fails on this stage.
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

from app.models import CropKeyframe

logger = logging.getLogger(__name__)

SAMPLE_FPS = 2.0  # how often we run face detection — 2/s is plenty for smooth panning
EMA_ALPHA = 0.25  # higher = snappier tracking, lower = smoother/slower pans
MIN_DETECTION_CONFIDENCE = 0.5


def _detect_face_centers(video_path: str, sample_fps: float) -> list[tuple[float, float, float]]:
    """Returns (t, cx_norm, cy_norm) for each sampled frame where a face was found,
    with cx/cy normalized to [0, 1] of frame width/height.
    """
    import mediapipe as mp

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, round(fps / sample_fps))

    detections: list[tuple[float, float, float]] = []
    with mp.solutions.face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=MIN_DETECTION_CONFIDENCE
    ) as detector:
        frame_idx = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if frame_idx % frame_interval == 0:
                ok, frame = cap.retrieve()
                if ok:
                    t = frame_idx / fps
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = detector.process(rgb)
                    if result.detections:
                        # Pick the largest face — assumed to be the main subject (Yagmur),
                        # who is filmed close-up/foreground in these clips.
                        best = max(
                            result.detections,
                            key=lambda d: d.location_data.relative_bounding_box.width
                            * d.location_data.relative_bounding_box.height,
                        )
                        box = best.location_data.relative_bounding_box
                        cx = box.xmin + box.width / 2
                        cy = box.ymin + box.height / 2
                        detections.append((t, cx, cy))
            frame_idx += 1
    cap.release()
    return detections


def _smooth_centers(
    detections: list[tuple[float, float, float]], alpha: float = EMA_ALPHA
) -> list[tuple[float, float, float]]:
    if not detections:
        return []
    smoothed = [detections[0]]
    for t, cx, cy in detections[1:]:
        _, px, py = smoothed[-1]
        smoothed.append((t, alpha * cx + (1 - alpha) * px, alpha * cy + (1 - alpha) * py))
    return smoothed


def build_crop_path(
    video_path: str,
    source_w: int,
    source_h: int,
    target_w: int,
    target_h: int,
    duration_s: float,
) -> list[CropKeyframe]:
    # Crop box: the largest window matching the target aspect ratio that fits inside the source frame.
    target_aspect = target_w / target_h
    source_aspect = source_w / source_h
    if source_aspect > target_aspect:
        crop_h = source_h
        crop_w = int(round(crop_h * target_aspect))
    else:
        crop_w = source_w
        crop_h = int(round(crop_w / target_aspect))
    crop_w = min(crop_w, source_w)
    crop_h = min(crop_h, source_h)

    detections = _detect_face_centers(video_path, SAMPLE_FPS)
    smoothed = _smooth_centers(detections)

    if not smoothed:
        logger.warning("No faces detected in %s — falling back to static center crop.", video_path)
        x = (source_w - crop_w) // 2
        y = (source_h - crop_h) // 2
        return [
            CropKeyframe(t=0.0, x=x, y=y, w=crop_w, h=crop_h),
            CropKeyframe(t=duration_s, x=x, y=y, w=crop_w, h=crop_h),
        ]

    keyframes: list[CropKeyframe] = []
    for t, cx_norm, cy_norm in smoothed:
        cx_px = cx_norm * source_w
        cy_px = cy_norm * source_h
        x = int(np.clip(cx_px - crop_w / 2, 0, source_w - crop_w))
        y = int(np.clip(cy_px - crop_h / 2, 0, source_h - crop_h))
        keyframes.append(CropKeyframe(t=t, x=x, y=y, w=crop_w, h=crop_h))

    # Ensure coverage of the full clip duration for the sendcmd renderer.
    if keyframes[0].t > 0.0:
        first = keyframes[0]
        keyframes.insert(0, CropKeyframe(t=0.0, x=first.x, y=first.y, w=crop_w, h=crop_h))
    if keyframes[-1].t < duration_s:
        last = keyframes[-1]
        keyframes.append(CropKeyframe(t=duration_s, x=last.x, y=last.y, w=crop_w, h=crop_h))

    return keyframes
