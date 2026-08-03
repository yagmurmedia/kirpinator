"""Local web UI (FastAPI + Jinja2) — dashboard, per-video controls, settings,
and the human "Approve & Upload" gate. Runs on localhost only.
"""
from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db, settings_store
from app.config import INCOMING_DIR, settings
from app.jobs.worker import start_background_worker
from app.models import VideoToggles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kirpinator")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    start_background_worker()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    videos = db.list_videos()
    return templates.TemplateResponse("dashboard.html", {"request": request, "videos": videos})


@app.get("/video/{video_id}", response_class=HTMLResponse)
def video_detail(request: Request, video_id: str):
    video = db.get_video(video_id)
    if not video:
        return HTMLResponse("Video bulunamadı", status_code=404)
    events = db.get_events(video_id)
    toggles = VideoToggles.from_dict(video.get("toggles"))
    return templates.TemplateResponse(
        "video_detail.html",
        {"request": request, "video": video, "events": events, "toggles": toggles},
    )


@app.post("/video/{video_id}/update")
def update_video(
    video_id: str,
    cut_silence: bool = Form(False),
    face_crop: bool = Form(False),
    music: bool = Form(False),
    effects: bool = Form(False),
    captions: bool = Form(False),
    made_for_kids: str = Form("default"),
    custom_instructions: str = Form(""),
    reprocess: bool = Form(False),
):
    made_for_kids_value = {"yes": True, "no": False}.get(made_for_kids)  # "default" -> None
    toggles = {
        "cut_silence": cut_silence,
        "face_crop": face_crop,
        "music": music,
        "effects": effects,
        "captions": captions,
        "made_for_kids": made_for_kids_value,
        "custom_instructions": custom_instructions,
    }
    db.update_video(video_id, toggles=toggles, custom_instructions=custom_instructions)
    if reprocess:
        db.set_status(video_id, "queued")
        db.log_event(video_id, "ui", "Reprocess requested by user")
    return RedirectResponse(f"/video/{video_id}", status_code=303)


@app.post("/video/{video_id}/approve")
def approve_and_upload(video_id: str):
    video = db.get_video(video_id)
    if not video or video["status"] != "ready_for_review":
        return RedirectResponse(f"/video/{video_id}", status_code=303)

    db.set_status(video_id, "approved")
    db.log_event(video_id, "ui", "Approved by user — starting upload")

    def _run():
        from app.youtube.upload import upload_video

        try:
            upload_video(video_id)
        except Exception:
            logger.exception("Upload failed for %s", video_id)

    threading.Thread(target=_run, daemon=True).start()
    return RedirectResponse(f"/video/{video_id}", status_code=303)


@app.post("/video/{video_id}/reprocess")
def reprocess(video_id: str):
    db.set_status(video_id, "queued")
    db.log_event(video_id, "ui", "Reprocess requested by user")
    return RedirectResponse(f"/video/{video_id}", status_code=303)


@app.get("/video/{video_id}/stream")
def stream_video(video_id: str):
    video = db.get_video(video_id)
    if not video:
        return HTMLResponse("Bulunamadı", status_code=404)
    path = video.get("output_path") or video.get("local_source_path")
    if not path or not Path(path).exists():
        return HTMLResponse("Dosya henüz hazır değil", status_code=404)
    return FileResponse(path, media_type="video/mp4")


@app.get("/video/{video_id}/thumbnail")
def thumbnail(video_id: str):
    video = db.get_video(video_id)
    if not video or not video.get("thumbnail_path") or not Path(video["thumbnail_path"]).exists():
        return HTMLResponse(status_code=404)
    return FileResponse(video["thumbnail_path"], media_type="image/jpeg")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    values = settings_store.get_all()
    return templates.TemplateResponse("settings.html", {"request": request, "s": values, "env": settings})


@app.post("/settings")
def save_settings(
    drive_folder_id: str = Form(""),
    made_for_kids_default: bool = Form(False),
    feature_cut_silence: bool = Form(False),
    feature_face_crop: bool = Form(False),
    feature_music: bool = Form(False),
    feature_effects: bool = Form(False),
    feature_captions: bool = Form(False),
    youtube_privacy_status: str = Form("public"),
    youtube_category_id: str = Form("24"),
):
    settings_store.set_all(
        {
            "drive_folder_id": drive_folder_id,
            "made_for_kids_default": made_for_kids_default,
            "feature_cut_silence": feature_cut_silence,
            "feature_face_crop": feature_face_crop,
            "feature_music": feature_music,
            "feature_effects": feature_effects,
            "feature_captions": feature_captions,
            "youtube_privacy_status": youtube_privacy_status,
            "youtube_category_id": youtube_category_id,
        }
    )
    return RedirectResponse("/settings", status_code=303)


@app.post("/upload_manual")
async def upload_manual(file: UploadFile):
    """Optional convenience: add a video by hand instead of waiting on Drive."""
    row = db.create_video(
        drive_file_id=None,
        source_filename=file.filename,
        toggles=settings_store.default_toggles_for_new_video(),
    )
    dest = INCOMING_DIR / f"{row['id']}_{file.filename}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    db.update_video(row["id"], local_source_path=str(dest))
    db.set_status(row["id"], "queued")
    return RedirectResponse(f"/video/{row['id']}", status_code=303)
