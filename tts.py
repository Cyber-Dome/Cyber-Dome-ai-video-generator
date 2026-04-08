"""
╔══════════════════════════════════════════════════════════════════╗
║         Domebytes AI Video Editor  —  tts.py                    ║
║  Developed by: AMAL AJI                                         ║
║  YouTube : https://www.youtube.com/@cyberdomeee                 ║
║  Website : https://domebytes.blogspot.com                       ║
║  Email   : amalajiconnect@gmail.com                             ║
╚══════════════════════════════════════════════════════════════════╝

Text-to-Speech Engine
=====================
Upgrades:
  - Respects cfg.tts.selected_voice_id from GUI voice dropdown
  - Auto-lists installed voices (used by GUI)
  - Robust fallback chain: pyttsx3 → gtts
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Optional

from config import AppConfig, CACHE_DIR
from utils import slugify, get_audio_duration, run_ffmpeg

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Engine implementations
# ─────────────────────────────────────────────────────────────────────────────

def _engine_pyttsx3(text: str, output: Path, cfg: AppConfig) -> Path:
    import pyttsx3
    engine = pyttsx3.init()
    voices = engine.getProperty("voices") or []
    gender = cfg.tts.voice_gender.lower()

    # 1. Use specific voice_id if set from GUI dropdown
    selected_id = getattr(cfg.tts, "selected_voice_id", None)
    if selected_id:
        # Verify it actually exists
        if any(v.id == selected_id for v in voices):
            engine.setProperty("voice", selected_id)
            logger.info(f"pyttsx3 using GUI-selected voice: {selected_id}")
        else:
            selected_id = None  # fallback to gender matching

    if not selected_id:
        # 2. Match by gender keyword
        male_kw   = ["male","david","mark","james","george","microsoft david","microsoft mark","zac"]
        female_kw = ["female","zira","hazel","susan","helen","microsoft zira","samantha","victoria"]
        kw_list   = male_kw if gender == "male" else female_kw

        for v in voices:
            vname = (v.name or "").lower()
            if any(k in vname for k in kw_list):
                engine.setProperty("voice", v.id)
                logger.info(f"pyttsx3 voice (gender match): {v.name}")
                break
        else:
            logger.warning("pyttsx3: no matching voice found, using system default")

    rate = engine.getProperty("rate") or 200
    engine.setProperty("rate", max(100, int(rate * getattr(cfg.tts, "speed", 1.0))))

    wav_path = output.with_suffix(".wav")
    engine.save_to_file(text, str(wav_path))
    engine.runAndWait()
    del engine  # release COM object on Windows

    if not wav_path.exists() or wav_path.stat().st_size < 100:
        raise RuntimeError(f"pyttsx3 produced no audio: {wav_path}")

    if output.suffix.lower() != ".wav":
        run_ffmpeg(["-i", str(wav_path), "-ar", "44100", "-ac", "1", str(output)])
        wav_path.unlink(missing_ok=True)
    else:
        if wav_path != output:
            wav_path.replace(output)
    return output


def _engine_gtts(text: str, output: Path, cfg: AppConfig) -> Path:
    from gtts import gTTS
    speed = getattr(cfg.tts, "speed", 1.0)
    tts   = gTTS(text=text, lang=cfg.tts.language, slow=(speed < 0.8))
    mp3_path = output.with_suffix(".mp3")
    tts.save(str(mp3_path))
    run_ffmpeg(["-i", str(mp3_path), "-ar", "44100", "-ac", "1", str(output)])
    mp3_path.unlink(missing_ok=True)
    return output


def _engine_coqui(text: str, output: Path, cfg: AppConfig) -> Path:
    try:
        from TTS.api import TTS
        model   = "tts_models/en/vctk/vits"
        tts     = TTS(model_name=model, progress_bar=False)
        speakers = getattr(tts, "speakers", None) or []
        male_ids   = ["p226","p227","p228","p231","p260","p270","p273","p274","p275","p276"]
        female_ids = ["p225","p229","p230","p233","p236","p239","p240","p243","p244","p245"]
        prefer   = male_ids if cfg.tts.voice_gender == "male" else female_ids
        speaker  = next((s for s in prefer if s in speakers), speakers[0] if speakers else None)
        kwargs   = {"text": text, "file_path": str(output)}
        if speaker:
            kwargs["speaker"] = speaker
        tts.tts_to_file(**kwargs)
        return output
    except ImportError:
        raise RuntimeError("Coqui TTS not installed")


def _engine_bark(text: str, output: Path, cfg: AppConfig) -> Path:
    try:
        from bark import SAMPLE_RATE, generate_audio, preload_models
        import scipy.io.wavfile as wav
        import numpy as np
        preload_models()
        audio = generate_audio(text)
        wav.write(str(output), SAMPLE_RATE, audio.astype(np.float32))
        return output
    except ImportError:
        raise RuntimeError("Bark not installed")


ENGINES: dict[str, object] = {
    "pyttsx3": _engine_pyttsx3,
    "gtts":    _engine_gtts,
    "coqui":   _engine_coqui,
    "bark":    _engine_bark,
}

_FALLBACK = ["pyttsx3", "gtts"]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_voice(
    text: str,
    cfg: AppConfig,
    output_path: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """
    Generate voice audio from text using configured TTS engine.
    Falls back automatically if the primary engine fails.
    """
    cache_dir = CACHE_DIR / "tts"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        key         = slugify(text[:60])
        output_path = cache_dir / f"{key}_{cfg.tts.engine}.wav"

    if output_path.exists() and not force:
        logger.debug(f"TTS cache hit: {output_path.name}")
        return output_path

    chosen = cfg.tts.engine if cfg.tts.engine in ENGINES else "pyttsx3"
    order  = list(dict.fromkeys([chosen] + _FALLBACK))
    last_err: Exception = RuntimeError("All TTS engines failed")

    for eng in order:
        try:
            logger.info(f"TTS [{eng}]: {text[:70].strip()!r}")
            fn     = ENGINES[eng]
            result = fn(text, output_path, cfg)   # type: ignore[operator]
            dur    = get_audio_duration(result)
            if dur < 0.3:
                raise RuntimeError(f"Audio too short ({dur:.2f}s) — likely silent output")
            logger.info(f"TTS done [{eng}]: {result.name} ({dur:.2f}s)")
            return result
        except Exception as e:
            last_err = e
            logger.warning(f"TTS [{eng}] failed: {e}")
            output_path.unlink(missing_ok=True)

    raise RuntimeError(f"All TTS engines failed. Last: {last_err}")


def split_script_to_sentences(script: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", script.strip())
    return [s.strip() for s in sentences if s.strip()]


def generate_scene_voices(
    scenes: list[dict],
    cfg: AppConfig,
    output_dir: Optional[Path] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[dict]:
    """
    Generate per-scene TTS audio.
    Adds 'audio_path' (str) and 'duration' (float) to each scene.
    """
    out_dir = output_dir or (CACHE_DIR / "tts")
    out_dir.mkdir(parents=True, exist_ok=True)

    total   = len(scenes)
    updated: list[dict] = []

    for i, scene in enumerate(scenes):
        if progress_cb:
            try:
                progress_cb(i, total)
            except Exception:
                pass

        text = (scene.get("text") or "").strip()
        if not text:
            scene["audio_path"] = None
            scene["duration"]   = 0.0
            updated.append(scene)
            continue

        out_path = out_dir / f"scene_{i:03d}.wav"

        if out_path.exists():
            dur = get_audio_duration(out_path)
            if dur > 0.3:
                scene["audio_path"] = str(out_path)
                scene["duration"]   = max(dur, 2.0)
                updated.append(scene)
                logger.debug(f"Scene {i}: reusing cached TTS ({dur:.1f}s)")
                continue
            out_path.unlink(missing_ok=True)

        try:
            audio = generate_voice(text, cfg, out_path)
            dur   = get_audio_duration(audio)
            scene["audio_path"] = str(audio)
            scene["duration"]   = max(dur, 2.0)
        except Exception as e:
            logger.error(f"Scene {i} TTS failed: {e} — inserting 3s silence")
            from utils import create_silent_audio
            try:
                silence = out_path.with_name(out_path.stem + "_silence.wav")
                create_silent_audio(3.0, silence)
                scene["audio_path"] = str(silence)
            except Exception:
                scene["audio_path"] = None
            scene["duration"] = 3.0

        updated.append(scene)

    if progress_cb:
        try:
            progress_cb(total, total)
        except Exception:
            pass

    return updated
