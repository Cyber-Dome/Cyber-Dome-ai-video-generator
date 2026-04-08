# UPGRADED VERSION

import re
from typing import List, Tuple
import random

TOPIC_MAP = {
    "coding": {
        "keywords": ["code", "coding", "developer", "python", "javascript", "programming", "debug"],
        "queries": ["developer coding laptop", "code editor screen", "programming workspace"]
    },
    "ai": {
        "keywords": ["ai", "machine learning", "neural", "gpt", "automation"],
        "queries": ["artificial intelligence interface", "neural network", "ai technology"]
    },
    "cybersecurity": {
        "keywords": ["hacker", "hacking", "darkweb", "phishing", "security", "breach"],
        "queries": ["cyber security hacker", "hacking terminal", "dark web screen"]
    },
    "business": {
        "keywords": ["business", "startup", "company", "sales", "office"],
        "queries": ["startup office", "business meeting", "entrepreneur workspace"]
    },
    "education": {
        "keywords": ["study", "learning", "student", "course"],
        "queries": ["student studying laptop", "online learning", "education workspace"]
    },
    "motivation": {
        "keywords": ["struggle", "success", "goal", "dream", "focus"],
        "queries": ["focused person laptop", "working late night", "success moment"]
    }
}


def detect_intent(text: str) -> str:
    t = text.lower()

    if any(w in t for w in ["error", "problem", "stuck", "failed"]):
        return "struggle"
    if any(w in t for w in ["learn", "study", "understand"]):
        return "learning"
    if any(w in t for w in ["build", "create", "project"]):
        return "building"
    if any(w in t for w in ["success", "worked", "achieved"]):
        return "success"

    return "learning"


def detect_category(text: str) -> str:
    text = text.lower()
    scores = {}

    for topic, data in TOPIC_MAP.items():
        score = sum(1 for kw in data["keywords"] if kw in text)
        if score:
            scores[topic] = score

    if scores:
        return max(scores, key=scores.get)

    return "motivation"


def generate_query(category: str, intent: str) -> str:
    base_queries = TOPIC_MAP.get(category, {}).get("queries", ["technology workspace"])

    base = random.choice(base_queries)

    intent_map = {
        "struggle": "frustrated",
        "learning": "learning",
        "building": "working",
        "success": "success"
    }

    return f"{base} {intent_map.get(intent, '')}".strip()


def analyze_scene(scene_text: str, keywords: List[str]) -> dict:
    """
    PRO ANALYSIS
    """
    category = detect_category(scene_text)
    intent = detect_intent(scene_text)
    query = generate_query(category, intent)

    return {
        "category": category,
        "intent": intent,
        "pexels_query": query
    }