from __future__ import annotations

# Domebytes AI Video Editor — planner.py
# Developed by AMAL AJI | https://domebytes.blogspot.com
# YouTube: https://www.youtube.com/@cyberdomeee | © 2026 Domebytes
"""
AI Video Editor Pro v3 - Scene Planner & Storyboard Generator
Produces a rich, multi-scene storyboard with per-scene animation, transitions,
visual type, SFX hints, cinematic image prompts, strict category mapping,
scene intent, and smart Pexels queries.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from config import AppConfig, PROJECTS_DIR

# ---------- DIAGRAM / VISUAL MODE DETECTION ----------
TECH_KEYWORDS = [
    "api", "request", "response",
    "authentication", "login", "auth",
    "database", "sql", "query",
    "dns", "network", "server", "client",
]

PROCESS_KEYWORDS = [
    "how it works", "step by step", "workflow", "process", "flow",
    "first", "then", "finally", "next", "after that",
    "request", "response", "login", "authentication", "token",
    "database", "query", "dns", "network", "api", "server", "client",
    "architecture", "pipeline", "sequence",
]

def _detect_diagram_type(txt: str) -> str:
    lower = txt.lower()

    if any(kw in lower for kw in ["api", "request", "response", "client", "server"]):
        return "sequence"

    if any(kw in lower for kw in ["auth", "login", "authentication", "database", "sql", "query", "dns", "network", "ip"]):
        return "flowchart"

    return "auto"


def _choose_visual_mode(text: str, scene_idx: int, total: int, intent: str) -> str:
    if scene_idx == 0:
        return "intro"
    if scene_idx == total - 1:
        return "outro"

    lower = text.lower()
    process_hits = sum(1 for kw in PROCESS_KEYWORDS if kw in lower)
    tech_hits = sum(1 for kw in TECH_KEYWORDS if kw in lower)
    long_enough = len(text.split()) >= 12
    explanation_intent = intent in {"learning", "building"}

    if long_enough and ((explanation_intent and process_hits >= 2 and tech_hits >= 1) or process_hits >= 4):
        return "diagram"

    return "auto"



logger = logging.getLogger(__name__)


SOUND_EFFECT_KEYWORDS: dict[str, list[str]] = {
    "explosion":    ["explode", "blast", "boom", "detonate", "crash"],
    "applause":     ["applause", "clap", "crowd", "cheer", "audience", "success"],
    "whoosh":       ["fly", "swoosh", "speed", "fast", "rush", "wind", "launch", "transition", "next", "meanwhile", "cut"],
    "typing":       ["type", "keyboard", "code", "write", "text", "program"],
    "notification": ["alert", "ping", "notify", "ding", "message"],
    "water":        ["ocean", "rain", "river", "splash", "water", "sea"],
    "nature":       ["forest", "bird", "nature", "outdoor", "trees", "grass"],
    "city":         ["city", "traffic", "urban", "street", "cars", "downtown"],
    "dramatic":     ["dramatic", "intense", "powerful", "epic", "reveal", "shocking"],
}

ANIMATION_TYPES = ["ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right"]

TRANSITION_MAP: dict[str, str] = {
    "introduce": "fade",
    "first": "fade",
    "welcome": "fade",
    "begin": "fade",
    "next": "slide",
    "then": "slide",
    "after": "slide",
    "meanwhile": "slide",
    "finally": "zoom",
    "conclusion": "zoom",
    "result": "zoom",
    "end": "zoom",
    "important": "wipe",
    "key": "wipe",
    "critical": "wipe",
    "remember": "wipe",
}

PROMPT_STYLE = (
    "cinematic photography, ultra detailed, 8K resolution, "
    "dramatic lighting, shallow depth of field, professional color grading, "
    "photorealistic, no text, no watermarks, award winning"
)

INTRO_WORDS = {"welcome", "hello", "today", "introducing", "greetings", "start", "begin", "first"}
OUTRO_WORDS = {"conclusion", "finally", "summary", "end", "last", "wrap", "goodbye", "thanks", "thank"}
ACTION_WORDS = {"discover", "explore", "learn", "understand", "achieve", "build", "create", "master"}

_STOP: set[str] = {
    "about", "which", "these", "their", "there", "would", "could", "should", "other",
    "every", "after", "before", "where", "while", "today", "artificial", "intelligence",
    "changing", "becoming", "without", "right", "using", "going", "being", "having",
    "this", "that", "with", "from", "they", "have", "will", "what", "when", "your",
    "into", "over", "also", "just", "make", "more", "some", "than", "then", "been",
    "were", "said", "each", "much", "many", "most", "only", "even", "well", "very",
    "such", "both", "does", "must", "need", "take", "give", "come", "here", "know",
}

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
        "business laptop workspace",
        "office presentation",
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
        "online course screen",
        "study desk laptop",
    ],
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "code", "coding", "developer", "programming", "python", "javascript",
        "bug", "debug", "terminal", "software", "app", "project", "build", "github"
    ],
    "ai": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural", "automation", "gpt", "llm", "chatbot", "model"
    ],
    "cybersecurity": [
        "hacker", "hack", "hacking", "cyber", "cybersecurity", "security",
        "dark web", "darkweb", "phishing", "malware", "breach", "exploit", "vpn", "tor"
    ],
    "business": [
        "business", "startup", "company", "office", "team", "market", "sales",
        "revenue", "profit", "customer", "brand", "meeting", "entrepreneur"
    ],
    "education": [
        "education", "student", "teacher", "learning", "study", "course", "class",
        "school", "college", "university", "lesson", "knowledge"
    ],
    "tech": [
        "technology", "digital", "computer", "laptop", "device", "system",
        "internet", "interface", "network", "data", "screen"
    ],
    "motivation": [
        "struggle", "dream", "success", "failure", "journey", "focus", "growth",
        "mindset", "effort", "progress", "believe", "keep going"
    ],
}


def extract_keywords(text: str, top_n: int = 6) -> list[str]:
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        if w not in _STOP and w not in seen:
            seen.add(w)
            result.append(w)
    return result[:top_n]


def detect_scene_category(text: str, keywords: list[str]) -> str:
    combined = f"{text.lower()} {' '.join(keywords).lower()}"
    scores: dict[str, int] = {}

    for category, triggers in CATEGORY_KEYWORDS.items():
        score = 0
        for trigger in triggers:
            if trigger in combined:
                score += 2 if " " in trigger else 1
        if score:
            scores[category] = score

    if scores:
        best = max(scores.items(), key=lambda x: x[1])[0]
        return best

    return "motivation"


def detect_scene_intent(text: str, scene_idx: int, total: int) -> str:
    lower = text.lower()

    if scene_idx == 0 or any(w in lower for w in ["welcome", "introducing", "today", "start", "begin"]):
        return "intro"
    if scene_idx == total - 1 or any(w in lower for w in ["lesson", "conclusion", "finally", "in the end", "the only difference"]):
        return "conclusion"
    if any(w in lower for w in ["stuck", "frustration", "failed", "failure", "error", "broke", "problem", "difficult"]):
        return "struggle"
    if any(w in lower for w in ["learn", "understand", "watching tutorials", "reading", "practice"]):
        return "learning"
    if any(w in lower for w in ["build", "building", "project", "create", "started", "working on"]):
        return "building"
    if any(w in lower for w in ["success", "proud", "achieved", "finished", "running", "worked"]):
        return "success"

    return "learning"


def build_category_query(category: str, intent: str, keywords: list[str]) -> str:
    pool = CATEGORY_QUERY_MAP.get(category, CATEGORY_QUERY_MAP["tech"])

    if category in {"coding", "tech", "ai", "cybersecurity"}:
        if intent == "struggle":
            return pool[0]
        if intent == "building":
            return pool[min(1, len(pool) - 1)]
        if intent == "success":
            return pool[min(2, len(pool) - 1)]
        return pool[0]

    if category == "motivation":
        if intent == "struggle":
            return "person thinking laptop"
        if intent == "success":
            return "success moment laptop"
        return pool[0]

    if category == "education":
        if intent == "learning":
            return "student studying laptop"
        return pool[0]

    if category == "business":
        if intent == "success":
            return "professional office success"
        return pool[0]

    return pool[0]


def build_image_prompt(scene_text: str, keywords: list[str], visual_type: str, category: str, intent: str) -> str:
    kw_str = ", ".join(keywords[:4]) if keywords else "cinematic workspace"

    framing_map = {
        "intro": "wide establishing shot",
        "outro": "aerial wide shot, golden hour",
        "action": "dynamic close-up shot",
        "default": "medium shot",
    }
    framing = framing_map.get(visual_type, framing_map["default"])

    category_subject = {
        "coding": "programmer at laptop",
        "ai": "futuristic AI interface",
        "cybersecurity": "cyber security analyst",
        "tech": "modern computer workspace",
        "business": "professional office team",
        "motivation": "focused person at desk",
        "education": "student learning on laptop",
    }

    intent_flavor = {
        "intro": "beginning of a journey",
        "struggle": "serious mood, problem solving",
        "learning": "focused learning atmosphere",
        "building": "hands-on creation, productive workflow",
        "success": "achievement, confidence, progress",
        "conclusion": "reflective, inspiring final moment",
    }

    subject = category_subject.get(category, "professional workspace")
    flavor = intent_flavor.get(intent, "professional atmosphere")

    return f"{framing} of {subject}, {kw_str}, {flavor}, {PROMPT_STYLE}"


def split_into_scenes(script: str, min_chars: int = 60) -> list[str]:
    script = script.strip()

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", script) if p.strip()]
    if len(paragraphs) >= 2:
        merged: list[str] = []
        buf = ""
        for p in paragraphs:
            if buf:
                if len(buf) < min_chars:
                    buf = buf + " " + p
                else:
                    merged.append(buf)
                    buf = p
            else:
                buf = p
        if buf:
            merged.append(buf)
        if len(merged) >= 2:
            return merged

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if not sentences:
        return [script]

    group_size = 2 if len(sentences) <= 8 else 3
    groups: list[str] = []
    for i in range(0, len(sentences), group_size):
        group = " ".join(sentences[i:i + group_size])
        groups.append(group)
    return groups if groups else [script]


def _classify_visual_type(text: str, scene_idx: int, total: int) -> str:
    lower = text.lower()
    words = set(lower.split())
    if scene_idx == 0 or words & INTRO_WORDS:
        return "intro"
    if scene_idx == total - 1 or words & OUTRO_WORDS:
        return "outro"
    if words & ACTION_WORDS:
        return "action"
    return "default"


def _pick_animation(visual_type: str, scene_idx: int, cfg_anim: str) -> str:
    if cfg_anim and cfg_anim != "random":
        return cfg_anim
    anim_map = {
        "intro": "zoom_in",
        "outro": "zoom_out",
        "action": "ken_burns",
        "default": ANIMATION_TYPES[scene_idx % len(ANIMATION_TYPES)],
    }
    return anim_map.get(visual_type, "ken_burns")


def _detect_sfx(text: str, category: str, intent: str) -> Optional[str]:
    lower = text.lower()

    for sfx, triggers in SOUND_EFFECT_KEYWORDS.items():
        if any(t in lower for t in triggers):
            return sfx

    if category in {"coding", "tech", "ai", "cybersecurity"} and intent in {"building", "learning"}:
        return "typing"
    if intent == "success":
        return "notification"
    if intent == "intro":
        return "whoosh"

    return None


def _detect_transition(text: str, default: str = "fade") -> str:
    lower = text.lower()
    for word, trans in TRANSITION_MAP.items():
        if word in lower:
            return trans
    return default


def plan_video(
    script: str,
    cfg: AppConfig,
    extra_images: Optional[list[Path]] = None,
) -> list[dict]:
    logger.info("Planning video storyboard...")
    scenes_text = split_into_scenes(script)
    total = len(scenes_text)
    storyboard: list[dict] = []

    default_anim = getattr(cfg, "default_animation", "ken_burns")

    for i, text in enumerate(scenes_text):
        keywords = extract_keywords(text)
            # ✅ ADD THIS BLOCK HERE
        from content_analyzer import analyze_scene
        ai = analyze_scene(text, keywords)
        category = detect_scene_category(text, keywords)
        intent = detect_scene_intent(text, i, total)
        visual_type = _classify_visual_type(text, i, total)
        animation = _pick_animation(visual_type, i, default_anim)
        pexels_query = build_category_query(category, intent, keywords)
        image_prompt = build_image_prompt(text, keywords, visual_type, category, intent)
        transition = _detect_transition(text, cfg.video.transition)
        sfx = _detect_sfx(text, category, intent)

        visual_path: Optional[str] = None
        if extra_images and i < len(extra_images):
            p = extra_images[i]
            if p.exists():
                visual_path = str(p)

        visual_mode = _choose_visual_mode(text, i, total, intent)
        diagram_type = _detect_diagram_type(text) if visual_mode == "diagram" else "auto"

        scene: dict = {
            "scene_id": i,
            "text": text,
            "keywords": keywords,
            "category": ai["category"],
            "intent": ai["intent"],
            "pexels_query": ai["pexels_query"],
            "image_prompt": image_prompt,
            "animation": animation,
            "transition": transition,
            "visual_type": visual_type,
            "sfx": sfx,
            "duration": 0.0,
            "audio_path": None,
            "visual_path": visual_path,
            "visual_mode": visual_mode,
            "diagram_type": diagram_type,
            "diagram_prompt": text,
        }
        storyboard.append(scene)
        logger.debug(
            f"Scene {i} cat={category} intent={intent} visual_type={visual_type} "
            f"anim={animation} query={pexels_query} kw={keywords[:3]}"
        )

    logger.info(f"Storyboard: {total} scene(s) planned")
    return storyboard


def save_storyboard(storyboard: list[dict], project_name: str) -> Path:
    out = PROJECTS_DIR / f"{project_name}_storyboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(storyboard, indent=2, default=str), encoding="utf-8")
    logger.info(f"Storyboard saved: {out}")
    return out


def load_storyboard(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))