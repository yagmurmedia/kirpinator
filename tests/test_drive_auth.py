import pytest

from app.drive.auth import SCOPES, _token_path, get_credentials


def test_drive_and_youtube_have_separate_scopes():
    assert SCOPES["drive"] != SCOPES["youtube"]
    assert "drive.readonly" in SCOPES["drive"][0]
    assert any("youtube" in s for s in SCOPES["youtube"])


def test_token_path_is_purpose_specific_and_distinct(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "google_token_file", r"C:\secrets\google_token.json")
    drive_path = _token_path("drive")
    youtube_path = _token_path("youtube")

    assert drive_path != youtube_path
    assert drive_path.name == "google_token_drive.json"
    assert youtube_path.name == "google_token_youtube.json"


def test_unknown_purpose_rejected():
    # Real regression risk: a typo'd purpose string silently reading/writing
    # the wrong token file (or a nonexistent one) instead of a clear error.
    with pytest.raises(ValueError):
        get_credentials("something_else")
