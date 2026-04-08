"""
╔══════════════════════════════════════════════════════════════════╗
║         Domebytes AI Video Editor  —  renderer.py               ║
║  Developed by: AMAL AJI                                         ║
║  YouTube : https://www.youtube.com/@cyberdomeee                 ║
║  Website : https://domebytes.blogspot.com                       ║
║  Email   : amalajiconnect@gmail.com                             ║
║                                                                 ║
║  © 2026 Domebytes. All rights reserved.                         ║
║  Free for personal use with attribution.                        ║
╚══════════════════════════════════════════════════════════════════╝

Video Renderer — Professional Production Engine
================================================
Strict upgrades:
  - Category-based visual selection
  - Duplicate avoidance for Pexels videos
  - Strong content filtering for unrelated scenes
  - Video-first priority with safe fallbacks
  - Cinematic fade transitions
  - Branding watermark overlay (optional)
  - Unique output filenames
"""

from __future__ import annotations

import logging
import random
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from config import AppConfig, BASE_DIR, CACHE_DIR
from utils import (
    TempDir,
    create_color_video,
    get_video_duration,
    run_ffmpeg,
    slugify,
)

logger = logging.getLogger(__name__)

BRAND_NAME = "Domebytes AI Video Editor"
BRAND_URL = "domebytes.blogspot.com"

USED_VIDEO_URLS: set[str] = set()
USED_VIDEO_PATHS: set[str] = set()

CATEGORY_QUERY_MAP: dict[str, list[str]] = {
    "coding": [
        "programming laptop",
        "developer coding screen",
        "code editor",
        "software developer typing",
        "programming workspace",
    ],
    "ai": [
        "artificial intelligence",
        "neural network",
        "futuristic technology",
        "machine learning interface",
        "ai digital visualization",
    ],
    "cybersecurity": [
        "cyber security hacker",
        "dark web screen",
        "hacking terminal",
        "digital security interface",
        "cyber defense technology",
    ],
    "tech": [
        "technology workspace",
        "digital interface",
        "modern computer",
        "tech office setup",
        "computer workstation",
    ],
    "business": [
        "startup office",
        "team meeting",
        "entrepreneur work",
        "office laptop meeting",
        "professional presentation",
    ],
    "motivation": [
        "person thinking",
        "working late laptop",
        "success moment",
        "focused workspace",
        "determined person desk",
    ],
    "education": [
        "student studying laptop",
        "learning online",
        "classroom digital",
        "study desk laptop",
        "online class computer",
    ],
}

INTENT_QUERY_HINTS: dict[str, list[str]] = {
    "intro": ["wide", "workspace", "beginning"],
    "struggle": ["focused", "thinking", "problem solving"],
    "learning": ["study", "learning", "reading"],
    "building": ["typing", "coding", "working"],
    "success": ["success", "achievement", "completed"],
    "conclusion": ["reflective", "calm", "final"],
}

BLOCKED_VIDEO_TERMS = {
    "alcohol", "drink", "beer", "wine", "whiskey", "vodka", "cocktail", "bar", "nightclub",
    "party", "dance", "dj", "nightlife",
    "war", "weapon", "gun", "rifle", "explosion", "blast", "fire", "bomb", "military",
    "wedding", "romance", "kiss",
}

COLOR_GRADES: dict[str, list[str]] = {
    "none": [],
    "cinematic": [
        "curves=r='0/0 0.1/0.05 0.9/0.95 1/1':g='0/0 0.1/0.08 0.9/0.92 1/1':b='0/0 0.1/0.15 0.9/0.85 1/1'",
        "eq=contrast=1.05:saturation=0.82:brightness=-0.03",
    ],
    "bright": [
        "eq=contrast=1.1:saturation=1.2:brightness=0.05:gamma=1.1",
    ],
    "vintage": [
        "curves=r='0/0.05 1/0.95':g='0/0 1/0.9':b='0/0.1 1/0.75'",
        "eq=saturation=0.65",
    ],
    "cold": [
        "curves=r='0/0 1/0.82':b='0/0.12 1/1'",
        "eq=saturation=0.88",
    ],
}

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def apply_cinematic_filters(video_path: Path, output: Path) -> Path:
    filters = [
        "vignette=PI/4",
        "unsharp=5:5:1.0:5:5:0.0",
        "eq=contrast=1.05:saturation=1.1:brightness=-0.02",
    ]
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", ",".join(filters),
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        str(output),
    ])
    return output


def get_unique_output_path(output_dir: Path, project_name: str, suffix: str = "_final.mp4") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    n = 1
    while True:
        candidate = output_dir / f"{project_name}_{date_str}_{n:02d}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _is_blocked_text(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in BLOCKED_VIDEO_TERMS)


def _build_query_pool(scene: dict) -> list[str]:
    category = scene.get("category", "tech")
    intent = scene.get("intent", "learning")
    explicit_query = scene.get("pexels_query")

    pool: list[str] = []
    if explicit_query:
        pool.append(explicit_query)

    pool.extend(CATEGORY_QUERY_MAP.get(category, CATEGORY_QUERY_MAP["tech"]))

    hints = INTENT_QUERY_HINTS.get(intent, [])
    if hints:
        for base in CATEGORY_QUERY_MAP.get(category, CATEGORY_QUERY_MAP["tech"])[:2]:
            for hint in hints[:2]:
                pool.append(f"{base} {hint}")

    seen = set()
    final_pool = []
    for q in pool:
        q2 = q.strip().lower()
        if q2 and q2 not in seen:
            seen.add(q2)
            final_pool.append(q)

    return final_pool[:8]


def fetch_image_pollinations(prompt: str, width: int, height: int, cache_dir: Path) -> Optional[Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = slugify(prompt[:50]) + f"_{width}x{height}.jpg"
    out = cache_dir / fname
    if out.exists() and out.stat().st_size > 5000:
        return out
    try:
        encoded = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={width}&height={height}&nologo=true&model=flux"
        )
        r = requests.get(url, headers=_HTTP_HEADERS, timeout=90)
        r.raise_for_status()
        data = r.content
        if len(data) < 5000:
            raise ValueError(f"Response too small ({len(data)} bytes)")
        out.write_bytes(data)
        logger.info(f"Pollinations image: {out.name}")
        return out
    except Exception as e:
        logger.warning(f"Pollinations failed: {e}")
        return None


def fetch_image_pexels(query: str, api_key: str, cache_dir: Path, width: int = 1920) -> Optional[Path]:
    if not api_key:
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / (slugify(query[:40]) + "_pexels.jpg")
    if out.exists() and out.stat().st_size > 5000:
        return out

    try:
        orient = "landscape" if width >= 1280 else "portrait"
        url = (
            "https://api.pexels.com/v1/search"
            f"?query={urllib.parse.quote(query)}&per_page=5&orientation={orient}"
        )
        headers = dict(_HTTP_HEADERS)
        headers["Authorization"] = api_key

        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        photos = data.get("photos", [])
        if not photos:
            return None

        photo = random.choice(photos[:5])
        img_url = photo["src"].get("large2x") or photo["src"].get("original")
        if not img_url:
            return None

        if _is_blocked_text(img_url):
            return None

        r2 = requests.get(img_url, headers=_HTTP_HEADERS, timeout=45)
        r2.raise_for_status()
        out.write_bytes(r2.content)

        if out.stat().st_size < 5000:
            out.unlink(missing_ok=True)
            return None

        logger.info(f"Pexels image: {out.name}")
        return out
    except Exception as e:
        logger.warning(f"Pexels image failed: {e}")
        return None


def fetch_video_pexels_strict(scene: dict, api_key: str, cache_dir: Path, width: int = 1920) -> Optional[Path]:
    if not api_key:
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    query_pool = _build_query_pool(scene)
    category = scene.get("category", "tech")

    for query in query_pool[:5]:
        try:
            url = (
                "https://api.pexels.com/videos/search"
                f"?query={urllib.parse.quote(query)}&per_page=10&orientation=landscape"
            )
            headers = dict(_HTTP_HEADERS)
            headers["Authorization"] = api_key

            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                logger.warning(f"Pexels video failed for '{query}': HTTP {r.status_code}")
                continue

            data = r.json()
            videos = data.get("videos", [])
            if not videos:
                continue

            random.shuffle(videos)

            for video in videos[:10]:
                video_url_text = " ".join([
                    str(video.get("url", "")),
                    str(video.get("image", "")),
                ]).lower()

                if _is_blocked_text(video_url_text):
                    continue

                if category in {"coding", "ai", "cybersecurity", "tech"}:
                    if any(bad in video_url_text for bad in ["drink", "beer", "wine", "party", "club", "wedding", "beach resort"]):
                        continue

                files = [
                    f for f in video.get("video_files", [])
                    if str(f.get("file_type", "")).lower() == "video/mp4"
                ]
                if not files:
                    continue

                preferred = [f for f in files if int(f.get("width", 99999) or 99999) <= 1280]
                pool = preferred if preferred else files
                pool = sorted(pool, key=lambda f: int(f.get("width", 99999) or 99999))

                chosen = None
                for file_info in pool:
                    vid_url = str(file_info.get("link", "")).strip()
                    if not vid_url:
                        continue
                    if vid_url in USED_VIDEO_URLS:
                        continue
                    if _is_blocked_text(vid_url):
                        continue
                    chosen = file_info
                    break

                if not chosen:
                    continue

                vid_url = chosen.get("link")
                if not vid_url:
                    continue

                out = cache_dir / (slugify(f"{query}_{video.get('id', 'vid')}")[:80] + "_pexels_vid.mp4")
                if str(out) in USED_VIDEO_PATHS:
                    continue

                r2 = requests.get(vid_url, headers=_HTTP_HEADERS, timeout=120, stream=True)
                if r2.status_code != 200:
                    continue

                with open(out, "wb") as f:
                    for chunk in r2.iter_content(1024 * 64):
                        if chunk:
                            f.write(chunk)

                if out.stat().st_size < 100_000:
                    out.unlink(missing_ok=True)
                    continue

                USED_VIDEO_URLS.add(vid_url)
                USED_VIDEO_PATHS.add(str(out))
                logger.info(f"Pexels video [{category}] ({query}): {out.name}")
                return out

        except Exception as e:
            logger.warning(f"Pexels strict video failed for '{query}': {e}")

    return None


def create_procedural_background(
    duration: float,
    width: int,
    height: int,
    output: Path,
    fps: int = 30,
    style: str = "gradient",
) -> Path:
    style = style.lower()

    if style == "noise":
        vf = (
            f"geq=r='random(1)*255':g='random(1)*120':b='random(1)*80',"
            f"scale={width}:{height},"
            f"gblur=sigma=3"
        )
    elif style == "cyber":
        vf = (
            f"color=c=0x0a0a1a:size={width}x{height}:rate={fps},"
            f"drawgrid=width=80:height=80:thickness=1:color=0x001133@0.6"
        )
    elif style == "plasma":
        vf = (
            f"color=c=black:size={width}x{height}:rate={fps},"
            f"geq="
            f"r='128+127*sin((X/50+T)*0.8)*cos((Y/50+T)*0.6)':"
            f"g='128+127*sin((X/70+T)*0.5)*cos((Y/30+T)*0.9)':"
            f"b='128+127*cos((X/40+T)*1.1)*sin((Y/60+T)*0.7)'"
        )
    else:
        vf = (
            f"color=c=0x1a0533:size={width}x{height}:rate={fps},"
            f"geq="
            f"r='60+40*sin(2*3.14159*(X/{width}+T*0.05))':"
            f"g='20+15*sin(2*3.14159*(Y/{height}+T*0.03))':"
            f"b='120+80*sin(2*3.14159*((X+Y)/{width+height}+T*0.07))'"
        )

    try:
        run_ffmpeg([
            "-f", "lavfi",
            "-i", f"color=c=black:size={width}x{height}:rate={fps}",
            "-vf", vf,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            str(output),
        ])
        return output
    except Exception as e:
        logger.warning(f"Procedural bg '{style}' failed ({e}), using solid color")
        create_color_video("0x1a1a2e", duration, width, height, output, fps)
        return output


_PROC_STYLES = ["gradient", "plasma", "gradient", "cyber", "plasma"]


def get_visual_for_scene(scene: dict, cfg: AppConfig, tmp_dir: Optional[Path] = None) -> Optional[Path]:
    # ---------- INTRO / OUTRO ----------
    if scene.get("visual_mode") == "intro":
        intro_candidates = [
            BASE_DIR / "assets" / "video" / "intro.mp4",
            BASE_DIR / "intro.mp4",
        ]
        for p in intro_candidates:
            if p.exists():
                logger.info(f"Scene {scene.get('scene_id')}: using intro video {p.name}")
                return p

    if scene.get("visual_mode") == "outro":
        outro_candidates = [
            BASE_DIR / "assets" / "video" / "thanks4watching.mp4",
            BASE_DIR / "thanks4watching.mp4",
        ]
        for p in outro_candidates:
            if p.exists():
                logger.info(f"Scene {scene.get('scene_id')}: using outro video {p.name}")
                return p

    # ---------- DIAGRAM BRANCH ----------
    if scene.get("visual_mode") == "diagram":
        from diagram_engine import DiagramEngine
        from diagram_animator import generate_animated_diagram_video

        engine = DiagramEngine()
        steps = engine._extract_steps(scene.get("diagram_prompt", scene.get("text", "")))
        if not steps:
            steps = ["Start", "Process", "Result"]

        cache_vid = CACHE_DIR / "diagram_videos"
        cache_vid.mkdir(parents=True, exist_ok=True)

        diagram_video = cache_vid / f"diagram_scene_{scene.get('scene_id', 0):03d}.mp4"
        duration = max(float(scene.get("duration", 4.0)), 2.0)

        vid = generate_animated_diagram_video(
            scene_text=scene.get("diagram_prompt", scene.get("text", "")),
            steps=steps,
            diagram_type=scene.get("diagram_type", "auto"),
            output_video=diagram_video,
            duration=duration,
            width=cfg.width,
            height=cfg.height,
            fps=cfg.video.fps,
        )
        if vid and Path(vid).exists():
            logger.info(f"Scene {scene.get('scene_id')}: using animated diagram")
            return Path(vid)

        img_path = engine.generate_diagram(
            scene_id=scene["scene_id"],
            text=scene.get("diagram_prompt", scene.get("text", "")),
            diagram_type=scene.get("diagram_type", "auto")
        )
        if img_path and Path(img_path).exists():
            logger.info(f"Scene {scene.get('scene_id')}: using static diagram fallback")
            return Path(img_path)

        logger.warning(f"Scene {scene.get('scene_id')}: diagram generation failed, falling back to normal visuals")

    # ---------- NORMAL VISUALS ----------
    cache_img = CACHE_DIR / "images"
    cache_vid = CACHE_DIR / "videos"
    prompt = scene.get("image_prompt", "cinematic workspace")
    category = scene.get("category", "tech")
    pexels_query = scene.get("pexels_query") or CATEGORY_QUERY_MAP.get(category, ["technology workspace"])[0]

    use_pexels_video = bool(getattr(cfg, "use_pexels_video", True))
    if use_pexels_video and getattr(cfg, "pexels_api_key", ""):
        vid = fetch_video_pexels_strict(scene, cfg.pexels_api_key, cache_vid, cfg.width)
        if vid:
            return vid

    img = fetch_image_pexels(
        pexels_query,
        cfg.pexels_api_key,
        cache_img,
        cfg.width
    ) if getattr(cfg, "pexels_api_key", "") else None
    if img:
        return img

    img = fetch_image_pollinations(prompt, cfg.width, cfg.height, cache_img)
    if img:
        return img

    # Late fallback: user-provided/local visual_path only if network visuals were not found
    if scene.get("visual_path"):
        p = Path(scene["visual_path"])
        if p.exists():
            logger.info(f"Scene {scene.get('scene_id')}: using local fallback visual {p.name}")
            return p

    logger.warning(f"Scene {scene.get('scene_id')}: no relevant visual found, using procedural background")
    return None


SFX_FILE_MAP: dict[str, list[str]] = {
    "whoosh": ["whoosh", "zoom-move", "futuristic-zoom", "gamma-ray-whoosh", "technology-transition-slide"],
    "notification": ["notification", "technology-notification", "high-tech-bleep", "bleep-confirmation", "modern-technology-select"],
    "ui": ["interface-device-click", "interface-option-select", "alien-technology-button", "ui-zoom-in", "ui-zoom-out", "user-interface-zoom"],
    "alert": ["alarm", "electric-fence-alert", "retro-game-emergency-alarm", "clock-countdown-bleeps"],
    "tech": ["cybernetic-technology", "futuristic-cinematic-sweep", "sci-fi-loading-operative", "technological-futuristic-hum"],
    "ambient": ["futuristic-sci-fi-computer-ambience", "technological-futuristic-hum"],
    "dramatic": ["electric-buzz-glitch", "sci-fi-battle-laser", "futuristic-cinematic-sweep"],
    "typing": ["sci-fi-loading-operative", "cybernetic-technology-affirmation"],
    "explosion": ["electric-buzz-glitch", "sci-fi-battle-laser-shots"],
    "applause": ["high-tech-bleep-confirmation", "cybernetic-technology-affirmation"],
}


def _find_sfx_file(sfx_name: str, sfx_dir: Path) -> Optional[Path]:
    if not sfx_dir.exists():
        return None

    sfx_dir_files = list(sfx_dir.glob("*.wav")) + list(sfx_dir.glob("*.mp3"))
    if not sfx_dir_files:
        return None

    for ext in [".wav", ".mp3"]:
        candidate = sfx_dir / f"{sfx_name}{ext}"
        if candidate.exists():
            return candidate

    keywords = SFX_FILE_MAP.get(sfx_name, [sfx_name])
    for kw in keywords:
        for f in sfx_dir_files:
            if kw.lower() in f.stem.lower():
                logger.debug(f"SFX match: {sfx_name} → {f.name}")
                return f

    if sfx_dir_files:
        return sorted(sfx_dir_files)[0]

    return None


def _get_sfx_category_for_scene(scene: dict) -> str:
    visual_type = scene.get("visual_type", "default")
    keywords = [k.lower() for k in scene.get("keywords", [])]
    text = scene.get("text", "").lower()

    if scene.get("sfx"):
        return scene["sfx"]

    if visual_type == "intro":
        return "whoosh"
    if visual_type == "outro":
        return "notification"

    kw_all = " ".join(keywords) + " " + text
    if any(t in kw_all for t in ["click", "open", "select", "choose", "pick", "button"]):
        return "ui"
    if any(t in kw_all for t in ["danger", "warning", "threat", "attack", "alert", "alarm", "hack", "breach"]):
        return "alert"
    if any(t in kw_all for t in ["transition", "next", "meanwhile", "move", "fast", "speed"]):
        return "whoosh"
    if any(t in kw_all for t in ["type", "code", "program", "write", "keyboard", "computer"]):
        return "typing"
    if any(t in kw_all for t in ["dramatic", "shock", "reveal", "important", "critical", "boom"]):
        return "dramatic"
    if any(t in kw_all for t in ["tech", "cyber", "ai", "digital", "system", "network", "data"]):
        return "tech"

    return "ambient"


def get_sfx_for_scene(sfx_name: str, sfx_dir: Path, tmp_dir: Path) -> Optional[Path]:
    if not sfx_name:
        return None

    sfx_dir.mkdir(parents=True, exist_ok=True)

    real_file = _find_sfx_file(sfx_name, sfx_dir)
    if real_file:
        return real_file

    logger.debug(f"No SFX file for '{sfx_name}' — generating tone fallback")
    tone_path = tmp_dir / f"sfx_{sfx_name}.wav"
    return _generate_tone_sfx(sfx_name, tone_path)


def _generate_tone_sfx(sfx_name: str, output: Path, duration: float = 0.4) -> Optional[Path]:
    freq_map = {
        "whoosh": "500",
        "notification": "880",
        "dramatic": "220",
        "typing": "1200",
        "applause": "300",
        "alert": "660",
        "ui": "1000",
        "tech": "440",
        "ambient": "200",
    }
    freq = freq_map.get(sfx_name, "440")
    try:
        run_ffmpeg([
            "-f", "lavfi",
            "-i", f"sine=frequency={freq}:duration={duration}",
            "-af", f"afade=t=out:st=0:d={max(duration * 0.7, 0.1):.3f}",
            "-ar", "44100",
            "-ac", "2",
            str(output),
        ])
        return output
    except Exception:
        return None


def _anim_ken_burns(dur: float, w: int, h: int, fps: int) -> str:
    frames = max(int(dur * fps), 2)
    return (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='min(zoom+0.0007,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        f"scale={w}:{h}"
    )


def _anim_zoom_in(dur: float, w: int, h: int, fps: int) -> str:
    frames = max(int(dur * fps), 2)
    return (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='1+0.0012*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        f"scale={w}:{h}"
    )


def _anim_zoom_out(dur: float, w: int, h: int, fps: int) -> str:
    frames = max(int(dur * fps), 2)
    return (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='max(1.25-0.0012*on,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        f"scale={w}:{h}"
    )


def _anim_pan_left(dur: float, w: int, h: int, fps: int) -> str:
    frames = max(int(dur * fps), 2)
    return (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='1.1':x='iw/zoom/2+on*({w}/zoom/{frames})':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        f"scale={w}:{h}"
    )


def _anim_pan_right(dur: float, w: int, h: int, fps: int) -> str:
    frames = max(int(dur * fps), 2)
    return (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='1.1':x='iw-iw/zoom/2-on*({w}/zoom/{frames})':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        f"scale={w}:{h}"
    )


def _anim_diagram_static(dur: float, w: int, h: int, fps: int) -> str:
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    )


_ANIM_FN = {
    "ken_burns": _anim_ken_burns,
    "zoom_in": _anim_zoom_in,
    "zoom_out": _anim_zoom_out,
    "pan_left": _anim_pan_left,
    "pan_right": _anim_pan_right,
    "diagram_static": _anim_diagram_static,
}


def image_to_animated_video(
    image_path: Path,
    duration: float,
    output: Path,
    width: int,
    height: int,
    fps: int = 30,
    animation: str = "ken_burns",
) -> Path:
    anim_fn = _ANIM_FN.get(animation, _anim_ken_burns)
    vf = anim_fn(max(duration, 1.0), width, height, fps)
    run_ffmpeg([
        "-loop", "1",
        "-i", str(image_path),
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(output),
    ])
    return output


def build_scene_visual(scene: dict, cfg: AppConfig, tmp_dir: Path, idx: int) -> Path:
    duration = max(float(scene.get("duration", 4.0)), 2.0)
    animation = scene.get("animation", getattr(cfg, "default_animation", "ken_burns"))

    if scene.get("visual_mode") == "diagram":
        animation = "diagram_static"
    elif animation == "random":
        pool = [k for k in _ANIM_FN.keys() if k != "diagram_static"]
        animation = random.choice(pool)
    w, h, fps = cfg.width, cfg.height, cfg.video.fps

    visual = get_visual_for_scene(scene, cfg, tmp_dir)
    base_vid = tmp_dir / f"s{idx:03d}_base.mp4"

    if visual:
        suf = visual.suffix.lower()
        if suf in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
            image_to_animated_video(visual, duration, base_vid, w, h, fps, animation)
        elif suf in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
            run_ffmpeg([
                "-stream_loop", "-1",
                "-i", str(visual),
                "-t", str(duration),
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-an",
                str(base_vid),
            ])
        else:
            _make_proc_bg(duration, w, h, fps, base_vid, idx)
    else:
        _make_proc_bg(duration, w, h, fps, base_vid, idx)

    return base_vid


def _make_proc_bg(duration: float, w: int, h: int, fps: int, output: Path, idx: int) -> None:
    style = _PROC_STYLES[idx % len(_PROC_STYLES)]
    create_procedural_background(duration, w, h, output, fps, style)


def build_scene_audio(scene: dict, cfg: AppConfig, tmp_dir: Path, idx: int, duration: float) -> Path:
    out_wav = tmp_dir / f"s{idx:03d}_audio.wav"

    audio_path = scene.get("audio_path")
    narr_exists = bool(audio_path and Path(str(audio_path)).exists())

    sfx_path: Optional[Path] = None
    if cfg.enable_sfx:
        sfx_cat = _get_sfx_category_for_scene(scene)
        if sfx_cat:
            sfx_path = get_sfx_for_scene(
                sfx_cat,
                sfx_dir=BASE_DIR / "assets" / "sfx",
                tmp_dir=tmp_dir,
            )

    sfx_vol = min(float(cfg.audio.sfx_volume), 0.18)
    narr_vol = float(cfg.audio.voice_volume)
    sfx_trim_dur = min(1.0, duration * 0.25)

    if narr_exists and sfx_path:
        run_ffmpeg([
            "-i", str(audio_path),
            "-i", str(sfx_path),
            "-filter_complex", (
                f"[0:a]aresample=44100,aformat=channel_layouts=stereo,"
                f"volume={narr_vol},"
                f"apad=whole_dur={duration:.4f},"
                f"atrim=duration={duration:.4f}[narr];"
                f"[1:a]aresample=44100,aformat=channel_layouts=stereo,"
                f"volume={sfx_vol},"
                f"atrim=duration={sfx_trim_dur:.4f},"
                f"apad=whole_dur={duration:.4f},"
                f"afade=t=out:st={max(0.0, sfx_trim_dur-0.2):.3f}:d=0.2,"
                f"atrim=duration={duration:.4f}[sfx];"
                f"[narr][sfx]amix=inputs=2:duration=longest:dropout_transition=0[aout]"
            ),
            "-map", "[aout]",
            "-ar", "44100",
            "-ac", "2",
            "-t", str(duration),
            str(out_wav),
        ])
    elif narr_exists:
        run_ffmpeg([
            "-i", str(audio_path),
            "-filter_complex", (
                f"[0:a]aresample=44100,aformat=channel_layouts=stereo,"
                f"volume={narr_vol},"
                f"apad=whole_dur={duration:.4f},"
                f"atrim=duration={duration:.4f}[aout]"
            ),
            "-map", "[aout]",
            "-ar", "44100",
            "-ac", "2",
            "-t", str(duration),
            str(out_wav),
        ])
    elif sfx_path:
        run_ffmpeg([
            "-i", str(sfx_path),
            "-filter_complex", (
                f"[0:a]aresample=44100,aformat=channel_layouts=stereo,"
                f"volume={sfx_vol},"
                f"apad=whole_dur={duration:.4f},"
                f"atrim=duration={duration:.4f}[aout]"
            ),
            "-map", "[aout]",
            "-ar", "44100",
            "-ac", "2",
            "-t", str(duration),
            str(out_wav),
        ])
    else:
        run_ffmpeg([
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-ar", "44100",
            "-ac", "2",
            str(out_wav),
        ])

    return out_wav


def render_scene_clip(scene: dict, cfg: AppConfig, tmp_dir: Path, idx: int) -> Optional[Path]:
    duration = max(float(scene.get("duration", 4.0)), 2.0)
    fps = cfg.video.fps

    base_vid = build_scene_visual(scene, cfg, tmp_dir, idx)
    audio_wav = build_scene_audio(scene, cfg, tmp_dir, idx, duration)

    av_out = tmp_dir / f"s{idx:03d}_av.mp4"
    run_ffmpeg([
        "-i", str(base_vid),
        "-i", str(audio_wav),
        "-t", str(duration),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        str(av_out),
    ])

    fade_dur = min(float(cfg.video.transition_duration), duration * 0.12)
    if cfg.video.transition != "none" and duration > max(3.5, fade_dur * 2 + 0.5):
        faded = tmp_dir / f"s{idx:03d}_faded.mp4"
        out_st = max(0.0, duration - fade_dur)
        run_ffmpeg([
            "-i", str(av_out),
            "-vf", (
                f"fade=t=in:st=0:d={fade_dur:.3f},"
                f"fade=t=out:st={out_st:.3f}:d={fade_dur:.3f}"
            ),
            "-af", (
                f"afade=t=in:ss=0:d={fade_dur:.3f},"
                f"afade=t=out:st={out_st:.3f}:d={fade_dur:.3f}"
            ),
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            str(faded),
        ])
        return faded

    return av_out


def concat_scene_clips(clip_paths: list[Path], output: Path) -> Path:
    list_file = output.parent / "_concat_list.txt"
    lines = [f"file '{str(p).replace(chr(92), '/')}'" for p in clip_paths]
    list_file.write_text("\n".join(lines), encoding="utf-8")

    run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        str(output),
    ])
    list_file.unlink(missing_ok=True)
    return output


def apply_color_grade(video_path: Path, output: Path, grade: str) -> Path:
    filters = COLOR_GRADES.get(grade, [])
    if not filters:
        shutil.copy2(video_path, output)
        return output
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", ",".join(filters),
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        str(output),
    ])
    return output


def mix_background_music_with_ducking(
    video_path: Path,
    music_path: Path,
    output: Path,
    music_vol: float = 0.15,
    ducked_vol: float = 0.04,
    fade_dur: float = 2.0,
) -> Path:
    dur = get_video_duration(video_path)
    run_ffmpeg([
        "-i", str(video_path),
        "-stream_loop", "-1",
        "-i", str(music_path),
        "-filter_complex", (
            f"[1:a]aresample=44100,aformat=channel_layouts=stereo,"
            f"volume={ducked_vol},"
            f"afade=t=in:ss=0:d={fade_dur},"
            f"afade=t=out:st={max(0.0, dur - fade_dur):.3f}:d={fade_dur},"
            f"atrim=duration={dur:.4f}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        ),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        str(output),
    ])
    return output


def normalize_audio(video_path: Path, output: Path) -> Path:
    run_ffmpeg([
        "-i", str(video_path),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "copy",
        "-ar", "44100",
        "-ac", "2",
        str(output),
    ])
    return output


def add_title_overlay(
    video_path: Path,
    output: Path,
    title: str,
    start: float = 0.5,
    end: float = 4.0,
    font_size: int = 68,
) -> Path:
    safe = title.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")
    fadein = f"(t-{start})/0.6"
    fadeout = f"({end}-t)/0.6"
    alpha = (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{start+0.6:.2f}),{fadein},"
        f"if(gt(t,{end-0.6:.2f}),{fadeout},1)))"
    )
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", (
            f"drawtext=text='{safe}':fontsize={font_size}:fontcolor=white:"
            f"x=(w-text_w)/2:y=h/2-text_h:"
            f"enable='between(t,{start},{end})':"
            f"alpha='{alpha}':"
            f"box=1:boxcolor=black@0.35:boxborderw=14"
        ),
        "-c:a", "copy",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        str(output),
    ])
    return output


def add_branding_watermark(video_path: Path, output: Path) -> Path:
    try:
        brand_text = BRAND_URL
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", (
                f"drawtext=text='{brand_text}':"
                f"fontsize=20:fontcolor=white@0.35:"
                f"x=w-text_w-18:y=h-text_h-14:"
                f"box=0"
            ),
            "-c:a", "copy",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            str(output),
        ])
        return output
    except Exception as e:
        logger.warning(f"Watermark failed (non-critical): {e}")
        shutil.copy2(video_path, output)
        return output


def generate_thumbnail(video_path: Path, output: Path, title: str = "", timestamp: float = 2.5) -> Path:
    run_ffmpeg([
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output),
    ])
    if title:
        safe = title.replace("'", "\\'").replace(":", "\\:")
        titled = output.with_name(output.stem + "_titled.jpg")
        run_ffmpeg([
            "-i", str(output),
            "-vf", (
                f"drawtext=text='{safe}':fontsize=72:fontcolor=white:"
                f"x=(w-text_w)/2:y=h-text_h-50:"
                f"box=1:boxcolor=black@0.55:boxborderw=12"
            ),
            "-q:v", "2",
            str(titled),
        ])
        return titled
    return output


def finalize_video(
    concat_path: Path,
    output_path: Path,
    cfg: AppConfig,
    music_path: Optional[Path],
    title: str,
    tmp: Path,
    progress_cb,
    add_watermark: bool = False,
) -> Path:
    def _p(stage: str, pct: float) -> None:
        logger.info(f"[{pct:3.0f}%] {stage}")
        if progress_cb:
            try:
                progress_cb(stage, pct)
            except Exception:
                pass

    current = concat_path

    _p("Applying color grade", 64)
    graded = tmp / "graded.mp4"
    current = apply_color_grade(current, graded, cfg.video.color_grade)

    if cfg.video.color_grade == "cinematic":
        _p("Applying cinematic filters (vignette + sharpen)", 66)
        filtered = tmp / "filtered.mp4"
        current = apply_cinematic_filters(current, filtered)

    if title:
        _p("Adding title overlay", 70)
        titled = tmp / "titled.mp4"
        current = add_title_overlay(current, titled, title)

    if music_path and music_path.exists() and cfg.enable_music:
        _p("Mixing music with auto-ducking", 74)
        with_music = tmp / "with_music.mp4"
        current = mix_background_music_with_ducking(
            current,
            music_path,
            with_music,
            music_vol=cfg.audio.music_volume,
            ducked_vol=max(0.03, cfg.audio.music_volume * 0.25),
            fade_dur=cfg.audio.music_fade_duration,
        )

    if cfg.audio.normalize_audio:
        _p("Normalizing audio", 82)
        normalized = tmp / "normalized.mp4"
        current = normalize_audio(current, normalized)

    if add_watermark:
        _p("Adding branding watermark", 88)
        watermarked = tmp / "watermarked.mp4"
        current = add_branding_watermark(current, watermarked)

    _p("Finalizing output", 92)
    shutil.copy2(current, output_path)
    return output_path


def render_video(
    storyboard: list[dict],
    cfg: AppConfig,
    project_name: str,
    music_path: Optional[Path] = None,
    title: str = "",
    progress_cb=None,
    add_watermark: bool = False,
) -> Path:
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    USED_VIDEO_URLS.clear()
    USED_VIDEO_PATHS.clear()

    final_out = get_unique_output_path(output_dir, project_name, "_final.mp4")
    logger.info(f"Output will be: {final_out.name}")

    def _p(stage: str, pct: float) -> None:
        logger.info(f"[{pct:3.0f}%] {stage}")
        if progress_cb:
            try:
                progress_cb(stage, pct)
            except Exception:
                pass

    with TempDir("avp_render_") as tmp:
        _p("Rendering scene clips", 5)
        clip_paths: list[Path] = []
        n = len(storyboard)

        for i, scene in enumerate(storyboard):
            _p(f"Scene {i+1}/{n} — {scene.get('visual_type', '')}", 5 + (i / max(n, 1)) * 48)
            try:
                clip = render_scene_clip(scene, cfg, tmp, i)
                if clip and clip.exists():
                    clip_paths.append(clip)
                    logger.info(f"Scene {i+1} rendered: {clip.name}")
            except Exception as e:
                logger.error(f"Scene {i+1} render failed: {e}", exc_info=True)

        if not clip_paths:
            raise RuntimeError("No clips rendered — check logs")

        _p("Concatenating clips", 56)
        concat = tmp / "concat.mp4"
        concat_scene_clips(clip_paths, concat)

        final_out = finalize_video(
            concat_path=concat,
            output_path=final_out,
            cfg=cfg,
            music_path=music_path,
            title=title,
            tmp=tmp,
            progress_cb=progress_cb,
            add_watermark=add_watermark,
        )

        _p("Generating thumbnail", 97)
        try:
            thumb = output_dir / f"{final_out.stem}_thumbnail.jpg"
            generate_thumbnail(final_out, thumb, title)
        except Exception as e:
            logger.warning(f"Thumbnail failed: {e}")

    _p("Render complete", 100)
    logger.info(f"✅ Final video: {final_out}")
    return final_out