"""Central configuration. All values are overridable via .env — see .env.example."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
INCOMING_DIR = STORAGE_DIR / "incoming"
WORKING_DIR = STORAGE_DIR / "working"
OUTPUT_DIR = STORAGE_DIR / "output"
THUMBNAIL_DIR = STORAGE_DIR / "thumbnails"
DATA_DIR = ROOT_DIR / "data"
SECRETS_DIR = ROOT_DIR / "secrets"
MUSIC_LIBRARY_DIR = ROOT_DIR / "music_library"

for d in (INCOMING_DIR, WORKING_DIR, OUTPUT_DIR, THUMBNAIL_DIR, DATA_DIR, SECRETS_DIR):
    d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Channel identity ---
    channel_name: str = "Yagmurun Oyun Bahcesi"
    channel_hashtags: str = "#YagmurunOyunBahcesi #Shorts #cocuk #aile"

    # --- Google Drive ---
    drive_folder_id: str = ""
    drive_poll_interval_seconds: int = 300
    google_oauth_client_secret_file: str = str(SECRETS_DIR / "google_oauth_client_secret.json")
    google_token_file: str = str(SECRETS_DIR / "google_token.json")

    # --- YouTube ---
    youtube_category_id: str = "24"  # Entertainment
    youtube_privacy_status: str = "public"  # public | unlisted | private (applied only after human approval)
    made_for_kids_default: bool = True

    # --- Whisper (speech-to-text, free/local default) ---
    whisper_model_size: str = "small"  # tiny/base/small/medium — small is a good CPU-friendly default
    whisper_language: str = "tr"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # --- ElevenLabs Scribe (optional, paid, used if you set an API key) ---
    # More accurate than local Whisper in practice — if set, transcription
    # uses this instead. Falls back to Whisper automatically if the API call
    # fails for any reason, so a bad/expired key never blocks a video.
    elevenlabs_api_key: str = ""
    elevenlabs_stt_model: str = "scribe_v1"

    # --- Editing defaults (overridable per-video from the UI) ---
    target_aspect_vertical: str = "1080x1920"
    target_aspect_horizontal: str = "1920x1080"
    silence_threshold_db: float = -35.0
    min_silence_duration_s: float = 0.6  # dead air shorter than this is left alone
    sentence_pad_s: float = 0.15  # buffer kept around a sentence so speech is never clipped
    max_shorts_duration_s: float = 59.0
    max_long_form_duration_s: float = 1200.0  # 20 min safety cap for non-Shorts videos

    # --- Feature toggles (global defaults; per-video overrides live in the DB) ---
    feature_cut_silence: bool = True
    feature_face_crop: bool = True
    feature_music: bool = True
    feature_effects: bool = True
    feature_captions: bool = True

    # --- Music ---
    pixabay_api_key: str = ""  # optional — if set, scripts/fetch_pixabay_music.py can pull more royalty-free tracks
    music_default_volume_db: float = -18.0
    music_duck_db: float = -12.0

    # --- Web UI ---
    web_host: str = "127.0.0.1"
    web_port: int = 8765
    web_auth_username: str = "yagmur"
    web_auth_password: str = ""  # empty = auth disabled; set to require a login

    # --- Push notifications (ntfy.sh — free, no account needed) ---
    # Empty = disabled. Set to a random, hard-to-guess topic name; anyone who
    # knows the exact topic can read your notifications, so treat it like a
    # password. Subscribe to the same topic in the ntfy phone app.
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"

    # --- Local LLM (Ollama — free, runs on this PC, no API key) ---
    # Used by the /chat page to turn free-text instructions into toggle
    # overrides. Falls back to the plain rule-based parser in
    # app/pipeline/instructions.py if Ollama isn't running.
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"

    # --- Job worker ---
    worker_poll_interval_seconds: int = 10
    worker_concurrency: int = 1


settings = Settings()
