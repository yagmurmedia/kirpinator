"""Runtime-editable settings layered on top of app.config.settings.

.env holds install-time/secret configuration (OAuth paths, ports). Anything the
user should be able to change from the web UI without restarting lives here,
backed by the kv_settings table.
"""
from __future__ import annotations

import json
from typing import Any

from app import db
from app.config import settings

_KEY = "runtime_settings"

_DEFAULTS: dict[str, Any] = {
    "drive_folder_id": settings.drive_folder_id,
    "made_for_kids_default": settings.made_for_kids_default,
    "feature_cut_silence": settings.feature_cut_silence,
    "feature_face_crop": settings.feature_face_crop,
    "feature_music": settings.feature_music,
    "feature_effects": settings.feature_effects,
    "youtube_privacy_status": settings.youtube_privacy_status,
    "youtube_category_id": settings.youtube_category_id,
}


def get_all() -> dict[str, Any]:
    raw = db.kv_get(_KEY)
    if not raw:
        return dict(_DEFAULTS)
    stored = json.loads(raw)
    merged = dict(_DEFAULTS)
    merged.update(stored)
    return merged


def set_all(values: dict[str, Any]) -> None:
    merged = get_all()
    merged.update(values)
    db.kv_set(_KEY, json.dumps(merged))
    # Keep drive_folder_id usable by the worker without a restart.
    if "drive_folder_id" in values:
        settings.drive_folder_id = values["drive_folder_id"]


def default_toggles_for_new_video() -> dict[str, Any]:
    s = get_all()
    return {
        "cut_silence": s["feature_cut_silence"],
        "face_crop": s["feature_face_crop"],
        "music": s["feature_music"],
        "effects": s["feature_effects"],
        "made_for_kids": None,  # None => use made_for_kids_default at render time
        "custom_instructions": "",
    }
