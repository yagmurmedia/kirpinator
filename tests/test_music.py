from unittest.mock import patch

from app.models import MusicTrack, TranscriptSegment
from app.pipeline.music import apply_music_if_available


def _seg(text):
    return TranscriptSegment(text=text, start=0.0, end=1.0, words=[])


def test_mood_override_wins_over_auto_classification():
    # The transcript text would naturally classify as "calm" (no exciting
    # keywords, no highlights) — the variant profile's music_mood override
    # must still be respected instead of the auto-classified mood.
    segments = [_seg("sakin bir gün geçirdik")]
    fake_track = MusicTrack(path="/fake/track.mp3", mood="exciting", bpm=120, license="CC")

    with (
        patch("app.pipeline.music.select_track", return_value=fake_track) as mock_select,
        patch("app.pipeline.music.mix_music") as mock_mix,
    ):
        apply_music_if_available("in.mp4", "out.mp4", segments, [], mood_override="exciting")

    mock_select.assert_called_once_with("exciting")
    mock_mix.assert_called_once()


def test_invalid_mood_override_falls_back_to_auto_classification():
    segments = [_seg("çok komik bir gün geçirdik")]  # classifies as "funny"
    fake_track = MusicTrack(path="/fake/track.mp3", mood="funny", bpm=120, license="CC")

    with (
        patch("app.pipeline.music.select_track", return_value=fake_track) as mock_select,
        patch("app.pipeline.music.mix_music"),
    ):
        apply_music_if_available("in.mp4", "out.mp4", segments, [], mood_override="not_a_real_mood")

    mock_select.assert_called_once_with("funny")


def test_no_override_uses_auto_classification():
    segments = [_seg("çok komik bir gün geçirdik")]  # classifies as "funny"
    fake_track = MusicTrack(path="/fake/track.mp3", mood="funny", bpm=120, license="CC")

    with (
        patch("app.pipeline.music.select_track", return_value=fake_track) as mock_select,
        patch("app.pipeline.music.mix_music"),
    ):
        apply_music_if_available("in.mp4", "out.mp4", segments, [])

    mock_select.assert_called_once_with("funny")
