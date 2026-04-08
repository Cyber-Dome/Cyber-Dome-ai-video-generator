# Domebytes AI Video Editor — utils.py
# Developed by AMAL AJI | https://domebytes.blogspot.com
# YouTube: https://www.youtube.com/@cyberdomeee | © 2026 Domebytes
"""
AI Video Editor Pro v2 - Utilities (UPDATED)
============================================
Changes:
  - create_color_video now accepts optional fps parameter (renderer passes it)
  - create_silent_audio outputs 44100 Hz stereo (consistent with renderer)
  - setup_logging unchanged
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from config import BASE_DIR


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    fmt   = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    log_dir = BASE_DIR / "build"
    log_dir.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=5_000_000, backupCount=3, encoding="utf-8",
        ),
    ]
    for h in handlers:
        h.setFormatter(logging.Formatter(fmt))
    logging.basicConfig(level=level, handlers=handlers, force=True)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("gtts").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg
# ─────────────────────────────────────────────────────────────────────────────

def check_ffmpeg() -> str:
    """Return ffmpeg executable path or raise RuntimeError."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg not found.\n"
            "  Windows: winget install Gyan.FFmpeg  (then restart terminal)\n"
            "  Linux:   sudo apt install ffmpeg\n"
            "  macOS:   brew install ffmpeg"
        )
    return ffmpeg


def run_ffmpeg(
    args: list[str],
    progress_cb: Optional[Callable[[float], None]] = None,
    timeout: int = 3600,
) -> subprocess.CompletedProcess:
    """
    Run FFmpeg with the given args list.
    Automatically prepends 'ffmpeg -y'.
    Raises RuntimeError on non-zero exit code.
    """
    ffmpeg = check_ffmpeg()
    cmd    = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
    logger.debug("ffmpeg: %s", " ".join(str(a) for a in cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr_tail = (result.stderr or "")[-2000:]
            logger.error("FFmpeg error:\n%s", stderr_tail)
            raise RuntimeError(f"FFmpeg exited with code {result.returncode}:\n{stderr_tail}")
        return result
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"FFmpeg timed out after {timeout}s")


def get_video_duration(path: Path) -> float:
    """Return media duration in seconds using ffprobe."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        ff = shutil.which("ffmpeg") or ""
        ffprobe = ff.replace("ffmpeg", "ffprobe")
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Duration check failed for {path}: {e}")
        return 0.0


def get_audio_duration(path: Path) -> float:
    return get_video_duration(path)


# ─────────────────────────────────────────────────────────────────────────────
# Temp directory
# ─────────────────────────────────────────────────────────────────────────────

class TempDir:
    """Context manager: creates a temp directory and removes it on exit."""
    def __init__(self, prefix: str = "avp_") -> None:
        self.prefix = prefix
        self.path: Optional[Path] = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.path

    def __exit__(self, *_) -> None:
        if self.path and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Path / text helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 40) -> str:
    import re
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len] or "item"


def safe_copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def human_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes:.1f} TB"


def retry(
    func: Callable,
    retries: int = 3,
    delay: float = 2.0,
    *args,
    **kwargs,
):
    """Retry a callable up to `retries` times with `delay` seconds between attempts."""
    last_err: Exception = RuntimeError("unknown")
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            logger.warning(f"Attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_err


# ─────────────────────────────────────────────────────────────────────────────
# Audio / video generation helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_silent_audio(duration: float, output: Path) -> Path:
    """
    Create a WAV file of silence for the given duration.
    Output: 44100 Hz stereo PCM (consistent with renderer audio pipeline).
    """
    run_ffmpeg([
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-ar", "44100",
        "-ac", "2",
        str(output),
    ])
    return output


def create_color_video(
    color: str,
    duration: float,
    width: int,
    height: int,
    output: Path,
    fps: int = 30,          # ← now accepts fps (was missing in original)
) -> Path:
    """Create a solid-colour video (no audio)."""
    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c={color}:size={width}x{height}:rate={fps}",
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output),
    ])
    return output
