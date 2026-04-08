# Domebytes AI Video Editor — subtitles.py
# Developed by AMAL AJI | https://domebytes.blogspot.com
# YouTube: https://www.youtube.com/@cyberdomeee | © 2026 Domebytes
"""
AI Video Editor Pro v2 - Subtitle Engine (UPDATED)
==================================================
Updates:
  - full-video subtitle coverage now prefers storyboard timing
  - Whisper is optional fallback, not the main path when storyboard exists
  - ASS burn remains Windows-safe and falls back safely
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from config import AppConfig, CACHE_DIR
from utils import check_ffmpeg

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Style presets
# ─────────────────────────────────────────────────────────────────────────────

SUBTITLE_STYLES: dict[str, dict] = {
    "minimal": {
        "FontName": "Arial",
        "FontSize": "26",
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "Outline": "1",
        "Shadow": "0",
        "Bold": "0",
        "Alignment": "2",
        "MarginV": "32",
    },
    "bold": {
        "FontName": "Impact",
        "FontSize": "38",
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "Outline": "3",
        "Shadow": "1",
        "Bold": "1",
        "Alignment": "2",
        "MarginV": "40",
    },
    "cinematic": {
        "FontName": "Georgia",
        "FontSize": "32",
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H80000000",
        "Outline": "2",
        "Shadow": "2",
        "Bold": "0",
        "Alignment": "2",
        "MarginV": "52",
    },
    "social": {
        "FontName": "Arial Black",
        "FontSize": "36",
        "PrimaryColour": "&H0000FFFF",
        "OutlineColour": "&H00000000",
        "Outline": "2",
        "Shadow": "0",
        "Bold": "1",
        "Alignment": "8",
        "MarginV": "80",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Time formatters
# ─────────────────────────────────────────────────────────────────────────────

def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _wrap_line(text: str, max_chars: int = 32) -> str:
    if len(text) <= max_chars:
        return text
    mid = len(text) // 2
    left = text.rfind(" ", 0, mid)
    right = text.find(" ", mid)
    if left == -1 and right == -1:
        return text
    split = left if (right == -1 or abs(left - mid) <= abs(right - mid)) else right
    return text[:split] + "\n" + text[split + 1:]


# ─────────────────────────────────────────────────────────────────────────────
# Transcription / timing generation
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_with_whisper(audio_path: Path, language: str = "en") -> list[dict]:
    try:
        import whisper

        logger.info("Loading Whisper base model…")
        model = whisper.load_model("base")
        logger.info(f"Transcribing {audio_path.name}…")
        result = model.transcribe(str(audio_path), language=language, word_timestamps=True)
        segments = [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
                "words": seg.get("words", []),
            }
            for seg in result.get("segments", [])
        ]
        logger.info(f"Whisper: {len(segments)} segments")
        return segments
    except ImportError:
        logger.info("Whisper not installed — using storyboard timing")
        return []
    except Exception as e:
        logger.warning(f"Whisper failed: {e}")
        return []


def build_segments_from_storyboard(storyboard: list[dict]) -> list[dict]:
    """
    Build subtitle segments from all storyboard scenes.
    This is now the preferred method when storyboard is available,
    so subtitles cover the full video instead of only the first scene.
    """
    segments: list[dict] = []
    cursor = 0.0

    for scene in storyboard:
        text = (scene.get("text") or "").strip()
        duration = float(scene.get("duration") or 0.0)

        if not text or duration <= 0:
            cursor += duration
            continue

        words = text.split()
        chunk_sz = max(4, min(8, len(words) // max(1, round(duration / 3.5))))
        chunks = [" ".join(words[i:i + chunk_sz]) for i in range(0, len(words), chunk_sz)]

        if not chunks:
            cursor += duration
            continue

        time_per_chunk = duration / len(chunks)
        for chunk in chunks:
            segments.append({
                "start": cursor,
                "end": cursor + time_per_chunk,
                "text": chunk,
                "words": [],
            })
            cursor += time_per_chunk

    return segments


def estimate_timing_from_text(text: str, start: float = 0.0) -> list[dict]:
    wps = 2.5
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    segs: list[dict] = []
    t = start
    for sent in sents:
        if not sent:
            continue
        dur = max(len(sent.split()) / wps, 1.0)
        segs.append({"start": t, "end": t + dur, "text": sent, "words": []})
        t += dur + 0.1
    return segs


# ─────────────────────────────────────────────────────────────────────────────
# Format converters
# ─────────────────────────────────────────────────────────────────────────────

def segments_to_srt(segments: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        text = _wrap_line(seg["text"])
        lines += [str(i), f"{_srt_time(seg['start'])} --> {_srt_time(seg['end'])}", text, ""]
    return "\n".join(lines)


def segments_to_ass(
    segments: list[dict],
    style_name: str = "cinematic",
    cfg: Optional[AppConfig] = None,
) -> str:
    s = dict(SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["cinematic"]))
    if cfg:
        s["FontName"] = cfg.subtitle.font
        s["FontSize"] = str(cfg.subtitle.font_size)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nTimer: 100.0000\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{s['FontName']},{s['FontSize']},{s['PrimaryColour']},"
        f"&H000000FF,{s['OutlineColour']},&H00000000,{s['Bold']},0,0,0,"
        f"100,100,0,0,1,{s['Outline']},{s['Shadow']},{s['Alignment']},10,10,{s['MarginV']},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = "\n".join(
        f"Dialogue: 0,{_ass_time(seg['start'])},{_ass_time(seg['end'])},Default,,0,0,0,,"
        f"{_wrap_line(seg['text']).replace(chr(10), chr(92) + 'N')}"
        for seg in segments
    )
    return header + events + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# Main subtitle generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_subtitles(
    audio_path: Path,
    cfg: AppConfig,
    output_dir: Optional[Path] = None,
    text_hint: Optional[str] = None,
    storyboard: Optional[list[dict]] = None,
) -> dict:
    """
    Priority:
      1. storyboard timing (preferred for full-video coverage)
      2. Whisper full-audio transcription
      3. text estimation fallback
    """
    if cfg.subtitle.style == "none":
        return {"srt": None, "ass": None, "segments": []}

    out_dir = output_dir or (CACHE_DIR / "subtitles")
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = audio_path.stem
    srt_path = out_dir / f"{stem}.srt"
    ass_path = out_dir / f"{stem}.ass"

    segments: list[dict] = []

    if storyboard:
        logger.info("Using FULL storyboard subtitles")
        segments = build_segments_from_storyboard(storyboard)

    if not segments and audio_path.exists():
        segments = transcribe_with_whisper(audio_path, language=cfg.tts.language)

    if not segments and text_hint:
        logger.info("Using text-estimation subtitle timing")
        segments = estimate_timing_from_text(text_hint)

    if not segments:
        logger.warning("No subtitle segments generated")
        return {"srt": srt_path, "ass": ass_path, "segments": []}

    srt_path.write_text(segments_to_srt(segments), encoding="utf-8")
    ass_path.write_text(segments_to_ass(segments, cfg.subtitle.style, cfg), encoding="utf-8")
    logger.info(f"Subtitles: {len(segments)} segments → {srt_path.name}, {ass_path.name}")

    return {"srt": srt_path, "ass": ass_path, "segments": segments}


# ─────────────────────────────────────────────────────────────────────────────
# Burn-in — Windows-safe
# ─────────────────────────────────────────────────────────────────────────────

def _burn_ass_windows_safe(
    video_path: Path,
    ass_path: Path,
    output_path: Path,
    cfg: AppConfig,
) -> bool:
    ffmpeg = check_ffmpeg()
    with tempfile.TemporaryDirectory(prefix="avpsubs_") as td:
        safe_ass = Path(td) / "subs.ass"
        shutil.copy2(ass_path, safe_ass)

        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path),
            "-vf", "ass=subs.ass",
            "-c:a", "copy",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=td,
            )
            if result.returncode == 0:
                return True
            logger.warning(f"ASS burn failed (code {result.returncode}): {result.stderr[-800:]}")
            return False
        except Exception as e:
            logger.warning(f"ASS burn exception: {e}")
            return False


def _burn_srt_fallback(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    cfg: AppConfig,
) -> bool:
    ffmpeg = check_ffmpeg()
    with tempfile.TemporaryDirectory(prefix="avpsrt_") as td:
        safe_srt = Path(td) / "subs.srt"
        shutil.copy2(srt_path, safe_srt)

        force_style = (
            f"FontName={cfg.subtitle.font},"
            f"FontSize={cfg.subtitle.font_size},"
            f"PrimaryColour=&H00FFFFFF,"
            f"OutlineColour=&H00000000,Outline=2"
        )
        filter_str = f"subtitles=subs.srt:force_style='{force_style}'"

        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path),
            "-vf", filter_str,
            "-c:a", "copy",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=td,
            )
            if result.returncode == 0:
                return True
            logger.warning(f"SRT burn failed (code {result.returncode}): {result.stderr[-800:]}")
            return False
        except Exception as e:
            logger.warning(f"SRT burn exception: {e}")
            return False


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    cfg: AppConfig,
) -> Path:
    """
    Burn subtitles into video.
    Tries ASS first, then SRT, then copies original video.
    """
    suffix = subtitle_path.suffix.lower()
    srt_sibling = subtitle_path.with_suffix(".srt")

    if suffix == ".ass":
        logger.info("Burning ASS subtitles (Windows-safe cwd method)…")
        if _burn_ass_windows_safe(video_path, subtitle_path, output_path, cfg):
            logger.info(f"Subtitles burned (ASS): {output_path.name}")
            return output_path
        if srt_sibling.exists():
            logger.info("ASS failed, trying SRT fallback…")
            if _burn_srt_fallback(video_path, srt_sibling, output_path, cfg):
                logger.info(f"Subtitles burned (SRT fallback): {output_path.name}")
                return output_path
    elif suffix == ".srt":
        if _burn_srt_fallback(video_path, subtitle_path, output_path, cfg):
            logger.info(f"Subtitles burned (SRT): {output_path.name}")
            return output_path

    logger.warning("All subtitle burn methods failed — copying video without subtitles")
    shutil.copy2(video_path, output_path)
    return output_path