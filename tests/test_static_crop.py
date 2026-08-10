from unittest.mock import patch

from app.pipeline.face_tracker import _target_crop_size, build_static_crop_keyframes


def test_target_crop_size_matches_target_aspect_and_fits_source():
    # 1920x1080 source -> 1080x1920 target (Shorts): width-limited crop.
    crop_w, crop_h = _target_crop_size(1920, 1080, 1080, 1920)
    assert crop_w <= 1920 and crop_h <= 1080
    assert abs((crop_w / crop_h) - (1080 / 1920)) < 1e-3  # integer pixel rounding


def test_falls_back_to_geometric_center_when_no_face_detected():
    with patch("app.pipeline.face_tracker._detect_face_centers", return_value=[]):
        keyframes = build_static_crop_keyframes("fake.mp4", 1920, 1080, 1080, 1920, duration_s=10.0)

    crop_w, crop_h = _target_crop_size(1920, 1080, 1080, 1920)
    expected_x = (1920 - crop_w) // 2
    expected_y = (1080 - crop_h) // 2
    assert keyframes[0].x == expected_x
    assert keyframes[0].y == expected_y


def test_real_bug_face_off_center_must_not_be_cropped_out():
    # The bug being fixed: a subject sitting well off the frame's geometric
    # center (here, far to the left) must still end up inside the crop
    # window instead of the crop blindly centering on the whole frame and
    # cutting them out.
    source_w, source_h = 1920, 1080
    # Face detected consistently at the left third of the frame.
    detections = [(float(i), 0.15, 0.5) for i in range(5)]
    with patch("app.pipeline.face_tracker._detect_face_centers", return_value=detections):
        keyframes = build_static_crop_keyframes("fake.mp4", source_w, source_h, 1080, 1920, duration_s=5.0)

    x, w = keyframes[0].x, keyframes[0].w
    face_px = 0.15 * source_w
    assert x <= face_px <= x + w  # the face's x position falls inside the crop window

    # And it's genuinely different from the blind geometric-center crop —
    # otherwise this whole fix would be a no-op for this exact scenario.
    crop_w, _ = _target_crop_size(source_w, source_h, 1080, 1920)
    geometric_center_x = (source_w - crop_w) // 2
    assert x != geometric_center_x


def test_output_is_a_single_fixed_window_not_a_dynamic_pan():
    detections = [(0.0, 0.3, 0.5), (5.0, 0.7, 0.5)]  # face moves across the clip
    with patch("app.pipeline.face_tracker._detect_face_centers", return_value=detections):
        keyframes = build_static_crop_keyframes("fake.mp4", 1920, 1080, 1080, 1920, duration_s=5.0)

    # "Static" means one fixed window for the whole clip, not a per-frame pan.
    assert len(keyframes) == 2
    assert (keyframes[0].x, keyframes[0].y) == (keyframes[1].x, keyframes[1].y)
