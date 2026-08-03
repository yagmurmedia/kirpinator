"""One-shot setup: creates a venv, installs all Python dependencies, verifies
ffmpeg is on PATH, and scaffolds the .env / secrets files. Everything here is
free/open-source — no paid API keys are required to finish setup.

Usage:  python install.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> Path:
    py = _venv_python()
    if not py.exists():
        print(f"Creating virtual environment at {VENV_DIR} ...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    return py


def pip_install(py: Path) -> None:
    print("Installing Python dependencies (this can take a few minutes)...")
    subprocess.run(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True
    )
    subprocess.run(
        [str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True
    )


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        print(
            "\n[UYARI] ffmpeg PATH üzerinde bulunamadı.\n"
            "Windows: winget install Gyan.FFmpeg  (kurulumdan sonra terminali yeniden açın)\n"
            "ffmpeg olmadan video işleme çalışmaz.\n"
        )
    else:
        print("ffmpeg bulundu: OK")


def scaffold_files() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        shutil.copyfile(ROOT / ".env.example", env_path)
        print("Created .env from .env.example — edit it to set DRIVE_FOLDER_ID etc.")

    secrets_dir = ROOT / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    readme = secrets_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "Google Cloud Console'dan indirdiğiniz OAuth istemci sırrını buraya\n"
            "`google_oauth_client_secret.json` adıyla koyun (Desktop app tipi).\n"
            "İlk çalıştırmada tarayıcı açılıp tek seferlik izin isteyecek; token burada\n"
            "otomatik olarak `google_token.json` adıyla saklanacak.\n",
            encoding="utf-8",
        )

    for d in ("storage/incoming", "storage/working", "storage/output", "storage/thumbnails", "data"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def prewarm_whisper(py: Path) -> None:
    print("Pre-downloading the Whisper speech-to-text model (first run only)...")
    code = (
        "from faster_whisper import WhisperModel;"
        "WhisperModel('small', device='cpu', compute_type='int8')"
    )
    try:
        subprocess.run([str(py), "-c", code], check=True, timeout=900)
        print("Whisper model ready.")
    except Exception as exc:  # noqa: BLE001
        print(f"[UYARI] Whisper modeli önceden indirilemedi ({exc}). İlk video işlenirken otomatik indirilecek.")


def main() -> None:
    py = ensure_venv()
    pip_install(py)
    check_ffmpeg()
    scaffold_files()
    prewarm_whisper(py)

    print("\nKurulum tamamlandı.")
    print(f"Çalıştırmak için: {_venv_python()} run.py")
    print("Ya da Windows'ta START.bat dosyasını çift tıklayın.")
    print(
        "\nGoogle Drive/YouTube yetkilendirmesi: secrets/google_oauth_client_secret.json "
        "dosyasını ekleyip uygulamayı başlattığınızda tarayıcı otomatik açılacak."
    )


if __name__ == "__main__":
    main()
