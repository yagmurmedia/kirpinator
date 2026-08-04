"""Regression test for the manual HTTP Range support in app/web/main.py.

Found in the wild: without this, a phone on mobile data (via Tailscale)
couldn't play videos at all — the installed Starlette version doesn't
implement Range/206 in FileResponse, so browsers either stalled trying to
fetch the whole file or refused to play. Tested here directly against the
helper (not through the full app) to avoid spinning up the background
worker/Drive polling that the app's startup event triggers.
"""
import asyncio

from starlette.requests import Request

from app.web.main import _range_aware_file_response


def _make_request(range_header: str | None) -> Request:
    headers = [(b"range", range_header.encode())] if range_header else []
    scope = {"type": "http", "method": "GET", "headers": headers}
    return Request(scope)


def _collect_body(response) -> bytes:
    async def _run():
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        return b"".join(chunks)

    return asyncio.run(_run())


def test_partial_range_returns_206_with_exact_slice(tmp_path):
    path = tmp_path / "video.mp4"
    full_data = bytes(range(256)) * 40  # 10240 bytes, easy to verify by content
    path.write_bytes(full_data)

    response = _range_aware_file_response(str(path), _make_request("bytes=10-19"), media_type="video/mp4")

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 10-19/10240"
    assert response.headers["content-length"] == "10"
    body = _collect_body(response)
    assert body == full_data[10:20]  # only the requested 10-byte slice, not the whole file


def test_open_ended_range_returns_rest_of_file(tmp_path):
    path = tmp_path / "video.mp4"
    data = bytes(range(256)) * 4  # 1024 bytes
    path.write_bytes(data)

    response = _range_aware_file_response(str(path), _make_request("bytes=1000-"), media_type="video/mp4")

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 1000-1023/1024"
    assert response.headers["content-length"] == "24"


def test_no_range_header_falls_back_to_full_file_response(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"x" * 100)

    response = _range_aware_file_response(str(path), _make_request(None), media_type="video/mp4")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"


def test_out_of_bounds_range_returns_416(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"x" * 100)

    response = _range_aware_file_response(str(path), _make_request("bytes=500-600"), media_type="video/mp4")

    assert response.status_code == 416
