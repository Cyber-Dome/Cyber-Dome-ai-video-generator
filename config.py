"""
╔══════════════════════════════════════════════════════════════════╗
║         Domebytes AI Video Editor  —  config.py                 ║
║  Developed by: AMAL AJI                                         ║
║  YouTube : https://www.youtube.com/@cyberdomeee                 ║
║  Website : https://domebytes.blogspot.com                       ║
║  Email   : amalajiconnect@gmail.com                             ║
╚══════════════════════════════════════════════════════════════════╝

Configuration — Typed dataclass system
=======================================
Upgrades:
  - TTSConfig now has selected_voice_id (from GUI voice dropdown)
  - All fields forward-compatible with v3 GUI
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).parent
ASSETS_DIR   = BASE_DIR / "assets"
CACHE_DIR    = BASE_DIR / "cache"
OUTPUT_DIR   = BASE_DIR / "output"
PROJECTS_DIR = BASE_DIR / "projects"
BUILD_DIR    = BASE_DIR / "build"

for _d in [
    ASSETS_DIR / "music",
    ASSETS_DIR / "sfx",
    ASSETS_DIR / "videos",
    ASSETS_DIR / "images",
    CACHE_DIR  / "images",
    CACHE_DIR  / "tts",
    CACHE_DIR  / "subtitles",
    CACHE_DIR  / "videos",
    OUTPUT_DIR,
    PROJECTS_DIR,
    BUILD_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-configs
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TTSConfig:
    engine:            Literal["pyttsx3", "gtts", "coqui", "bark"] = "pyttsx3"
    voice_gender:      Literal["male", "female"] = "male"
    speed:             float = 1.0
    pitch:             float = 1.0
    language:          str   = "en"
    selected_voice_id: Optional[str] = None  # set from GUI voice dropdown


@dataclass
class SubtitleConfig:
    style:         Literal["minimal", "bold", "cinematic", "social", "none"] = "cinematic"
    font:          str  = "Arial"
    font_size:     int  = 32
    color:         str  = "white"
    outline_color: str  = "black"
    outline_width: int  = 2
    position:      Literal["bottom", "top", "center"] = "bottom"
    karaoke_mode:  bool = False
    burn_in:       bool = True


@dataclass
class VideoConfig:
    resolution:          Literal["1080p", "720p", "4K"] = "1080p"
    aspect_ratio:        Literal["16:9", "9:16", "1:1"] = "16:9"
    fps:                 int   = 30
    color_grade:         Literal["none", "cinematic", "bright", "vintage", "cold"] = "cinematic"
    transition:          Literal["fade", "slide", "zoom", "wipe", "none"] = "fade"
    transition_duration: float = 0.5
    export_preset:       Literal["youtube", "shorts", "instagram", "tiktok", "podcast"] = "youtube"


@dataclass
class AudioConfig:
    music_volume:        float = 0.15
    sfx_volume:          float = 0.15   # lowered default: voice is primary
    voice_volume:        float = 1.0
    normalize_audio:     bool  = False
    music_fade_duration: float = 2.0
    freesound_api_key:   str   = ""


# ─────────────────────────────────────────────────────────────────────────────
# Root config
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AppConfig:
    tts:      TTSConfig      = field(default_factory=TTSConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    video:    VideoConfig    = field(default_factory=VideoConfig)
    audio:    AudioConfig    = field(default_factory=AudioConfig)

    output_dir:  str = str(OUTPUT_DIR)
    cache_dir:   str = str(CACHE_DIR)

    project_name: str  = "my_video"
    use_gpu:      bool = False
    debug:        bool = False

    image_provider:   Literal["pollinations", "huggingface", "pexels", "unsplash"] = "pollinations"
    pexels_api_key:   str  = ""
    unsplash_api_key: str  = ""

    use_pexels_video: bool = True
    proc_bg_style:    str  = "random"

    enable_sfx:        bool = True
    enable_music:      bool = False
    per_scene_audio:   bool = True
    default_animation: str  = "ken_burns"

    # ── Persistence ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path | str = BASE_DIR / "config.json") -> "AppConfig":
        path = Path(path)
        if not path.exists():
            logger.info("config.json not found — using defaults")
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            cfg = cls()
            for sub, klass in [
                ("tts",      TTSConfig),
                ("subtitle", SubtitleConfig),
                ("video",    VideoConfig),
                ("audio",    AudioConfig),
            ]:
                if sub in raw:
                    try:
                        setattr(cfg, sub, klass(**raw[sub]))
                    except TypeError as e:
                        logger.warning(f"Config[{sub}] partial load: {e}")
                        known = {k: v for k, v in raw[sub].items()
                                 if k in klass.__dataclass_fields__}
                        setattr(cfg, sub, klass(**known))

            top_fields = [
                "output_dir", "cache_dir", "project_name", "use_gpu", "debug",
                "image_provider", "pexels_api_key", "unsplash_api_key",
                "use_pexels_video", "proc_bg_style",
                "enable_sfx", "enable_music", "per_scene_audio", "default_animation",
            ]
            for k in top_fields:
                if k in raw:
                    setattr(cfg, k, raw[k])
            logger.info(f"Config loaded: {path}")
            return cfg
        except Exception as e:
            logger.warning(f"Config load failed ({e}) — using defaults")
            return cls()

    def save(self, path: Path | str = BASE_DIR / "config.json") -> None:
        path = Path(path)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        logger.info(f"Config saved: {path}")

    # ── Resolution helpers ────────────────────────────────────────────────────

    @property
    def width(self) -> int:
        base = {"1080p": 1920, "720p": 1280, "4K": 3840}[self.video.resolution]
        if self.video.aspect_ratio == "9:16":
            return base // 2
        if self.video.aspect_ratio == "1:1":
            return {"1080p": 1080, "720p": 720, "4K": 2160}[self.video.resolution]
        return base

    @property
    def height(self) -> int:
        base = {"1080p": 1080, "720p": 720, "4K": 2160}[self.video.resolution]
        if self.video.aspect_ratio == "9:16":
            return int({"1080p": 1920, "720p": 1280, "4K": 3840}[self.video.resolution])
        if self.video.aspect_ratio == "1:1":
            return base
        return base
