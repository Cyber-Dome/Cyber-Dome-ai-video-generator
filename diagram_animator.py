from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import List, Optional

from diagram_engine import DiagramEngine
from utils import run_ffmpeg


CACHE_VERSION = "v1"


def _video_cache_name(scene_text: str, steps: List[str], diagram_type: str, duration: float, fps: int) -> str:
    raw = f"{CACHE_VERSION}|{scene_text}|{'|'.join(steps)}|{diagram_type}|{duration:.2f}|{fps}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest() + ".mp4"


def generate_animated_diagram_video(
    scene_text: str,
    steps: List[str],
    diagram_type: str,
    output_video: Path,
    duration: float,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> Optional[Path]:
    """
    Generate a simple step-by-step animated diagram video by rendering one
    highlighted diagram PNG per step, converting each to a short clip, then
    concatenating the clips.
    """
    if not steps:
        return None

    output_video.parent.mkdir(parents=True, exist_ok=True)

    engine = DiagramEngine()
    step_duration = max(duration / max(len(steps), 1), 1.0)

    image_paths: List[Path] = []
    for idx in range(len(steps)):
        mermaid_code = engine._text_to_mermaid_with_highlight(
            scene_text,
            diagram_type,
            highlight_step=idx,
            steps=steps,
        )
        if not mermaid_code:
            continue
        png_path = engine._render_mermaid(idx, mermaid_code)
        if png_path and Path(png_path).exists():
            image_paths.append(Path(png_path))

    if not image_paths:
        return None

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        clip_paths: List[Path] = []

        for i, img in enumerate(image_paths):
            clip = tmp / f"diag_step_{i:03d}.mp4"
            run_ffmpeg([
                "-loop", "1",
                "-i", str(img),
                "-vf",
                (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
                ),
                "-t", str(step_duration),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                str(clip),
            ])
            clip_paths.append(clip)

        list_file = tmp / "concat.txt"
        list_file.write_text(
            "\n".join([f"file '{str(c).replace(chr(92), '/')}'" for c in clip_paths]),
            encoding="utf-8",
        )

        run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-t", str(duration),
            str(output_video),
        ])

    return output_video if output_video.exists() else None
