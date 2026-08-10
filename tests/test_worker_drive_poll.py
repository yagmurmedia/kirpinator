from unittest.mock import patch

from app.jobs import worker


def test_skips_when_no_drive_folder_configured():
    with patch("app.jobs.worker.settings") as mock_settings:
        mock_settings.drive_folder_id = ""
        with patch("app.drive.client.poll_and_queue_new_videos") as mock_poll:
            worker._drive_poll_tick()
    mock_poll.assert_not_called()


def test_calls_poll_when_drive_folder_configured():
    with patch("app.jobs.worker.settings") as mock_settings:
        mock_settings.drive_folder_id = "some-folder-id"
        with patch("app.drive.client.poll_and_queue_new_videos") as mock_poll:
            worker._drive_poll_tick()
    mock_poll.assert_called_once()


def test_poll_failure_never_raises():
    # Regression guard for the intended behavior: a Drive/network hiccup
    # must never kill the poll thread, or discovery silently stops forever.
    with patch("app.jobs.worker.settings") as mock_settings:
        mock_settings.drive_folder_id = "some-folder-id"
        with patch("app.drive.client.poll_and_queue_new_videos", side_effect=ConnectionError):
            worker._drive_poll_tick()  # must not raise


def test_process_loop_does_not_call_drive_poll_tick():
    # Regression guard for the real bug this refactor fixed: Drive polling
    # used to live inside the same loop that blocks for however long a
    # render takes (hours, for 4K/HDR sources) — a video uploaded mid-render
    # went undiscovered until the current one finished. Polling now runs on
    # its own thread (_drive_poll_loop), entirely decoupled from _loop.
    import inspect

    source = inspect.getsource(worker._loop)
    assert "_drive_poll_tick" not in source
