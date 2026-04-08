"""
╔══════════════════════════════════════════════════════════════════╗
║         Domebytes AI Video Editor  —  generate.py               ║
║  Developed by: AMAL AJI                                         ║
║  YouTube : https://www.youtube.com/@cyberdomeee                 ║
║  Website : https://domebytes.blogspot.com                       ║
║  Email   : amalajiconnect@gmail.com                             ║
║                                                                 ║
║  © 2026 Domebytes. All rights reserved.                         ║
║  Free for personal use with attribution.                        ║
╚══════════════════════════════════════════════════════════════════╝

Main Orchestrator + Professional Dark-Theme GUI
===============================================
Upgrades:
  - Manual voice selection dropdown (lists all pyttsx3 voices)
  - Unique output filenames (no overwrite)
  - Watermark toggle
  - Full branding in GUI header + footer
  - Voice selection saved to config
  - Modern dark UI with better spacing
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import threading
from pathlib import Path
from typing import Optional

from config import AppConfig, BASE_DIR, OUTPUT_DIR, PROJECTS_DIR
from utils import run_ffmpeg, setup_logging

logger = logging.getLogger(__name__)

# ── Branding constants ───────────────────────────────────────────────────────
APP_NAME    = "Domebytes AI Video Editor"
APP_VERSION = "v3.0 Pro"
DEVELOPER   = "AMAL AJI"
YOUTUBE_URL = "https://www.youtube.com/@cyberdomeee"
WEBSITE_URL = "https://domebytes.blogspot.com"
EMAIL       = "amalajiconnect@gmail.com"


# ─────────────────────────────────────────────────────────────────────────────
# State helpers
# ─────────────────────────────────────────────────────────────────────────────

def _state_path(project_name: str) -> Path:
    return PROJECTS_DIR / f"{project_name}_state.json"


def _save_state(project_name: str, data: dict) -> None:
    path = _state_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")


def _load_state(project_name: str) -> dict:
    path = _state_path(project_name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _clear_state(project_name: str) -> None:
    _state_path(project_name).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Voice helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_pyttsx3_voices() -> list[dict]:
    """Return list of {id, name, gender} dicts for all installed pyttsx3 voices."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        result = []
        for v in voices:
            name = v.name or "Unknown"
            vid  = v.id  or ""
            gender = "female" if any(
                k in name.lower() for k in ["female","zira","hazel","susan","helen","samantha","victoria"]
            ) else "male"
            result.append({"id": vid, "name": name, "gender": gender})
        del engine
        return result
    except Exception as e:
        logger.warning(f"Could not list pyttsx3 voices: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Chapters
# ─────────────────────────────────────────────────────────────────────────────

def export_chapters(storyboard: list[dict], project_name: str, output_dir: Path) -> Path:
    """Export YouTube chapter timestamps from storyboard."""
    chapters_path = output_dir / f"{project_name}_chapters.txt"
    lines = ["0:00 Intro"]
    elapsed = 0.0
    for scene in storyboard:
        dur = float(scene.get("duration", 3.0))
        elapsed += dur
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        label = scene.get("text", f"Scene {scene['scene_id']}")[:55].strip().rstrip(".")
        lines.append(f"{mins}:{secs:02d} {label}")
    chapters_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Chapters saved: {chapters_path}")
    return chapters_path


# ─────────────────────────────────────────────────────────────────────────────
# Local video assignment
# ─────────────────────────────────────────────────────────────────────────────

def assign_local_videos(storyboard: list[dict]) -> list[dict]:
    """Assign local assets/videos/ only to scenes explicitly marked for local assets.

    Normal scenes should still use intro/outro/diagram/Pexels logic in renderer.py.
    This avoids looping local files across the whole video.
    """
    videos_dir = BASE_DIR / "assets" / "videos"
    if not videos_dir.exists():
        return storyboard
    video_files = sorted(videos_dir.glob("*.mp4")) + sorted(videos_dir.glob("*.mov"))
    if not video_files:
        return storyboard

    vi = 0
    for scene in storyboard:
        if scene.get("visual_mode") == "local_asset" and not scene.get("visual_path"):
            scene["visual_path"] = str(video_files[vi % len(video_files)])
            vi += 1

    if vi:
        logger.info(f"Assigned {vi} local video(s) from assets/videos/")
    return storyboard

    vi = 0
    for scene in storyboard:
        if not scene.get("visual_path"):
            scene["visual_path"] = str(video_files[vi % len(video_files)])
            vi += 1

    logger.info(f"Assigned {vi} local video(s) from assets/videos/")
    return storyboard


# ─────────────────────────────────────────────────────────────────────────────
# Full narration track
# ─────────────────────────────────────────────────────────────────────────────

def build_full_narration_track(voice_files: list[Path], output_wav: Path) -> Path:
    """Concatenate all scene WAV files into one full narration track."""
    if not voice_files:
        raise RuntimeError("No voice files to combine")

    list_file = output_wav.with_suffix(".txt")
    lines = [f"file '{str(p).replace(chr(92), '/')}'" for p in voice_files]
    list_file.write_text("\n".join(lines), encoding="utf-8")

    try:
        run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-ar", "44100",
            "-ac", "2",
            str(output_wav),
        ])
    finally:
        list_file.unlink(missing_ok=True)

    return output_wav


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    script: str,
    cfg: AppConfig,
    project_name: str = "my_video",
    extra_images: Optional[list[Path]] = None,
    music_path: Optional[Path] = None,
    title: str = "",
    progress_cb=None,
    resume: bool = False,
    add_watermark: bool = False,
) -> Path:
    """
    Full pipeline:
      script → plan → TTS → visuals → render (unique filename) → subtitles → chapters → final
    """
    from planner import plan_video, save_storyboard
    from renderer import render_video
    from subtitles import burn_subtitles, generate_subtitles
    from tts import generate_scene_voices

    def _p(stage: str, pct: float) -> None:
        logger.info(f"[{pct:3.0f}%] {stage}")
        if progress_cb:
            try:
                progress_cb(stage, pct)
            except Exception:
                pass

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    proj_dir = OUTPUT_DIR / project_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    (BASE_DIR / "assets" / "videos").mkdir(parents=True, exist_ok=True)

    state: dict = _load_state(project_name) if resume else {}

    if "storyboard" in state and resume:
        storyboard: list[dict] = state["storyboard"]
        logger.info(f"Resuming: {len(storyboard)} scenes from state")
        _p("Resuming from saved state", 5)
    else:
        _p("Planning storyboard", 5)
        storyboard = plan_video(script, cfg, extra_images)
        save_storyboard(storyboard, project_name)
        state["storyboard"] = storyboard
        _save_state(project_name, state)

    storyboard = assign_local_videos(storyboard)

    needs_tts = any(
        not s.get("audio_path") or not Path(str(s.get("audio_path", "x"))).exists()
        for s in storyboard
    )
    if needs_tts:
        _p("Generating per-scene voice audio", 12)
        storyboard = generate_scene_voices(
            storyboard,
            cfg,
            output_dir=proj_dir,
            progress_cb=lambda i, n: _p(
                f"TTS scene {min(i+1, n)}/{n}",
                12 + ((i + 1) / max(n, 1)) * 18,
            ),
        )
        state["storyboard"] = storyboard
        _save_state(project_name, state)
    else:
        _p("TTS already done (resuming)", 30)

    if music_path is None and cfg.enable_music:
        for candidate in [
            BASE_DIR / "assets" / "music" / "bg.mp3",
            BASE_DIR / "assets" / "music" / "bg.wav",
        ]:
            if candidate.exists():
                music_path = candidate
                break

    _p("Rendering video", 32)
    final_video = render_video(
        storyboard=storyboard,
        cfg=cfg,
        project_name=project_name,
        music_path=music_path,
        title=title,
        progress_cb=lambda s, p: _p(s, 32 + p * 0.50),
        add_watermark=add_watermark,
    )

    # ── Subtitles ─────────────────────────────────────────────────────────
    _p("Generating subtitles", 84)
    voice_files = [
        Path(s["audio_path"])
        for s in storyboard
        if s.get("audio_path") and Path(str(s["audio_path"])).exists()
    ]

    if voice_files and cfg.subtitle.style != "none":
        try:
            full_text     = " ".join(s.get("text", "") for s in storyboard)
            full_narration = proj_dir / f"{project_name}_full.wav"
            build_full_narration_track(voice_files, full_narration)

            subs = generate_subtitles(
                audio_path=full_narration,
                cfg=cfg,
                output_dir=proj_dir,
                text_hint=full_text,
                storyboard=storyboard,
            )

            if subs.get("srt") and Path(str(subs["srt"])).exists():
                srt_dest = final_video.with_suffix(".srt")
                shutil.copy2(subs["srt"], srt_dest)
                logger.info(f"SRT saved: {srt_dest}")

            if cfg.subtitle.burn_in and subs.get("ass") and Path(str(subs["ass"])).exists():
                _p("Burning subtitles", 91)
                subtitled = final_video.with_name(final_video.stem + "_subtitled.mp4")
                burn_subtitles(final_video, Path(subs["ass"]), subtitled, cfg)
                if subtitled.exists() and subtitled.stat().st_size > 10_000:
                    final_video = subtitled
                    logger.info(f"Using subtitled video: {final_video.name}")
                else:
                    logger.warning("Subtitled file empty, keeping original")
        except Exception as e:
            logger.warning(f"Subtitle stage skipped: {e}")

    _p("Exporting chapters", 97)
    try:
        export_chapters(storyboard, project_name, final_video.parent)
    except Exception as e:
        logger.warning(f"Chapter export failed: {e}")

    _clear_state(project_name)
    _p("Complete!", 100)
    print(f"\n✅  Done → {final_video}")
    return final_video


# ─────────────────────────────────────────────────────────────────────────────
# Batch mode
# ─────────────────────────────────────────────────────────────────────────────

def run_batch(scripts_folder: Path, cfg: AppConfig, progress_cb=None) -> list[Path]:
    txt_files = sorted(scripts_folder.glob("*.txt"))
    if not txt_files:
        logger.warning(f"No .txt files in {scripts_folder}")
        return []
    results: list[Path] = []
    for i, f in enumerate(txt_files):
        name   = f.stem
        script = f.read_text(encoding="utf-8").strip()
        logger.info(f"Batch [{i+1}/{len(txt_files)}]: {name}")
        if progress_cb:
            progress_cb(f"Batch {i+1}/{len(txt_files)}: {name}", (i / len(txt_files)) * 100)
        try:
            out = run_pipeline(script, cfg, project_name=name, progress_cb=progress_cb)
            results.append(out)
        except Exception as e:
            logger.error(f"Batch '{name}' failed: {e}")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Professional Dark GUI — Domebytes branded
# ─────────────────────────────────────────────────────────────────────────────

def launch_gui() -> None:
    try:
        from ui import MainWindow
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except ImportError:
        print("PySide6 not installed. Falling back to Tkinter.")
        # ... existing Tkinter code ...

    cfg = AppConfig.load()
    root = tk.Tk()
    root.title(f"🎬 {APP_NAME} {APP_VERSION}")
    root.geometry("1260x960")
    root.resizable(True, True)

    # ── Colour palette ───────────────────────────────────────────────────────
    BG       = "#0a0a14"   # near-black background
    CARD     = "#13132a"   # card/panel background
    CARD2    = "#1a1a35"   # slightly lighter card
    ACCENT   = "#e94560"   # red accent (Domebytes brand)
    ACCENT2  = "#7b2fbe"   # purple accent
    TEXT     = "#e8e8f8"   # primary text
    MUTED    = "#6060a0"   # muted/secondary text
    INPUT_BG = "#0e0e24"   # input field background
    SUCCESS  = "#00cc88"   # success green
    BORDER   = "#2a2a50"   # subtle border

    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "TProgressbar",
        thickness=8,
        troughcolor=CARD2,
        background=ACCENT,
        bordercolor=CARD,
        lightcolor=ACCENT,
        darkcolor=ACCENT2,
    )
    style.configure(
        "TCombobox",
        fieldbackground=INPUT_BG,
        background=INPUT_BG,
        foreground=TEXT,
        selectbackground=ACCENT2,
        arrowcolor=TEXT,
    )
    root.configure(bg=BG)

    # ── Header ───────────────────────────────────────────────────────────────
    hdr = tk.Frame(root, bg=ACCENT, height=62)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)

    tk.Label(
        hdr,
        text=f"🎬  {APP_NAME}",
        font=("Arial", 18, "bold"),
        bg=ACCENT,
        fg="white",
    ).pack(side="left", padx=20, pady=14)

    tk.Label(
        hdr,
        text=f"{APP_VERSION}  •  by {DEVELOPER}  •  {WEBSITE_URL}",
        font=("Arial", 9),
        bg=ACCENT,
        fg="#ffd0db",
    ).pack(side="right", padx=20)

    # ── Main paned layout ────────────────────────────────────────────────────
    pane = tk.PanedWindow(root, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
    pane.pack(fill="both", expand=True, padx=10, pady=(8, 0))

    left  = tk.Frame(pane, bg=CARD,  bd=0)
    right = tk.Frame(pane, bg=CARD2, bd=0)
    pane.add(left,  minsize=680)
    pane.add(right, minsize=380)

    # ── Helper: section label ────────────────────────────────────────────────
    def section(parent, text: str) -> None:
        f = tk.Frame(parent, bg=BORDER, height=1)
        f.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(parent, text=text, font=("Arial", 9, "bold"),
                 bg=CARD, fg=ACCENT).pack(anchor="w", padx=14, pady=(4, 2))

    # ── Script input ─────────────────────────────────────────────────────────
    section(left, "📝  VOICEOVER SCRIPT")
    script_box = scrolledtext.ScrolledText(
        left, height=9, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
        font=("Consolas", 11), relief="flat", wrap="word", bd=0,
    )
    script_box.pack(fill="x", padx=14, pady=(0, 6))
    script_box.insert(
        "1.0",
        "Welcome to Domebytes!\n\n"
        "Today we explore how AI is revolutionizing cybersecurity and the digital world.\n\n"
        "From dark web threats to AI-powered defenses, let's uncover the full picture.",
    )

    # ── Settings grid ────────────────────────────────────────────────────────
    section(left, "⚙️  SETTINGS")
    sg = tk.Frame(left, bg=CARD)
    sg.pack(fill="x", padx=14, pady=(2, 4))

    def combo(parent, label: str, opts: list, default: str, width: int = 13) -> tk.StringVar:
        f = tk.Frame(parent, bg=CARD)
        f.pack(side="left", padx=(0, 10))
        tk.Label(f, text=label, font=("Arial", 8), bg=CARD, fg=MUTED).pack(anchor="w")
        v = tk.StringVar(value=default)
        cb = ttk.Combobox(f, textvariable=v, values=opts, width=width, state="readonly")
        cb.pack()
        return v

    tts_v    = combo(sg, "TTS Engine",   ["pyttsx3", "gtts", "coqui", "bark"],           cfg.tts.engine)
    ratio_v  = combo(sg, "Format",       ["16:9", "9:16", "1:1"],                        cfg.video.aspect_ratio, 8)
    grade_v  = combo(sg, "Color Grade",  ["cinematic", "bright", "vintage", "cold", "none"], cfg.video.color_grade, 10)
    sub_v    = combo(sg, "Subtitles",    ["cinematic", "bold", "minimal", "social", "none"], cfg.subtitle.style, 10)
    res_v    = combo(sg, "Resolution",   ["1080p", "720p", "4K"],                        cfg.video.resolution, 8)
    anim_v   = combo(
        sg, "Animation",
        ["ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right", "random"],
        getattr(cfg, "default_animation", "ken_burns"), 11,
    )

    # ── Voice selection row ───────────────────────────────────────────────────
    section(left, "🎤  VOICE SELECTION")
    vr = tk.Frame(left, bg=CARD)
    vr.pack(fill="x", padx=14, pady=(2, 4))

    tk.Label(vr, text="Voice:", font=("Arial", 9), bg=CARD, fg=MUTED).pack(side="left")
    voice_v = tk.StringVar(value=cfg.tts.voice_gender)

    # Enumerate installed voices for dropdown
    _installed_voices = get_pyttsx3_voices()
    _voice_labels = ["auto:male", "auto:female"] + [
        f"{v['gender']}:{v['name'][:45]}" for v in _installed_voices
    ]
    if not _voice_labels:
        _voice_labels = ["auto:male", "auto:female"]

    voice_dropdown = ttk.Combobox(
        vr, textvariable=voice_v,
        values=_voice_labels,
        width=38, state="readonly",
    )
    voice_dropdown.pack(side="left", padx=(6, 16))

    tk.Label(vr, text="Transition:", font=("Arial", 9), bg=CARD, fg=MUTED).pack(side="left")
    trans_v = combo(vr, "", ["fade", "slide", "zoom", "wipe", "none"], cfg.video.transition, 9)

    # ── Project / title row ───────────────────────────────────────────────────
    section(left, "🏷️  PROJECT")
    pr = tk.Frame(left, bg=CARD)
    pr.pack(fill="x", padx=14, pady=(4, 2))

    tk.Label(pr, text="Name:", font=("Arial", 9), bg=CARD, fg=MUTED).pack(side="left")
    name_v = tk.StringVar(value="my_video")
    tk.Entry(
        pr, textvariable=name_v, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
        font=("Consolas", 10), relief="flat", bd=4, width=18,
    ).pack(side="left", padx=(4, 14))

    tk.Label(pr, text="Title overlay:", font=("Arial", 9), bg=CARD, fg=MUTED).pack(side="left")
    title_v = tk.StringVar(value="")
    tk.Entry(
        pr, textvariable=title_v, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
        font=("Consolas", 10), relief="flat", bd=4, width=28,
    ).pack(side="left", padx=4)

    # ── File pickers ──────────────────────────────────────────────────────────
    section(left, "📁  MEDIA FILES")
    fr = tk.Frame(left, bg=CARD)
    fr.pack(fill="x", padx=14, pady=4)

    imgs_v  = tk.StringVar(value="No images/videos selected")
    music_v = tk.StringVar(value=str(BASE_DIR / "assets" / "music" / "bg.mp3"))
    sel_imgs: list[Path] = []

    def pick_imgs():
        paths = filedialog.askopenfilenames(
            title="Select images / videos",
            filetypes=[("Media", "*.jpg *.jpeg *.png *.mp4 *.mov"), ("All", "*.*")],
        )
        if paths:
            sel_imgs.clear()
            sel_imgs.extend(Path(p) for p in paths)
            imgs_v.set(f"{len(paths)} file(s) selected")

    def pick_music():
        p = filedialog.askopenfilename(
            title="Select background music",
            filetypes=[("Audio", "*.mp3 *.wav *.aac"), ("All", "*.*")],
        )
        if p:
            music_v.set(p)

    tk.Button(
        fr, text="📁 Images/Videos", command=pick_imgs, bg=CARD2, fg=TEXT,
        relief="flat", cursor="hand2", font=("Arial", 9), padx=8, pady=4,
    ).pack(side="left")
    tk.Label(fr, textvariable=imgs_v, bg=CARD, fg=MUTED, font=("Arial", 8)).pack(side="left", padx=6)
    tk.Button(
        fr, text="🎵 Music", command=pick_music, bg=CARD2, fg=TEXT,
        relief="flat", cursor="hand2", font=("Arial", 9), padx=8, pady=4,
    ).pack(side="left", padx=(12, 0))
    tk.Label(fr, textvariable=music_v, bg=CARD, fg=MUTED, font=("Arial", 8)).pack(side="left", padx=6)

    # ── Toggles ───────────────────────────────────────────────────────────────
    section(left, "🔧  OPTIONS")
    ck = tk.Frame(left, bg=CARD)
    ck.pack(fill="x", padx=14, pady=(2, 6))

    burn_v     = tk.BooleanVar(value=cfg.subtitle.burn_in)
    music_en   = tk.BooleanVar(value=cfg.enable_music)
    sfx_en     = tk.BooleanVar(value=cfg.enable_sfx)
    norm_v     = tk.BooleanVar(value=cfg.audio.normalize_audio)
    pexvid_v   = tk.BooleanVar(value=bool(getattr(cfg, "use_pexels_video", True)))
    wm_v       = tk.BooleanVar(value=False)

    for lbl, var in [
        ("Burn subtitles", burn_v),
        ("BG Music", music_en),
        ("SFX", sfx_en),
        ("Normalize audio", norm_v),
        ("Pexels video", pexvid_v),
        ("Watermark", wm_v),
    ]:
        tk.Checkbutton(
            ck, text=lbl, variable=var,
            bg=CARD, fg=TEXT, selectcolor=INPUT_BG,
            activebackground=CARD, font=("Arial", 9),
        ).pack(side="left", padx=(0, 12))

    # ── Progress ──────────────────────────────────────────────────────────────
    prog_v   = tk.DoubleVar(value=0)
    prog_lbl = tk.StringVar(value="Ready — configure settings and click Render")
    tk.Label(
        left, textvariable=prog_lbl, font=("Arial", 9),
        bg=CARD, fg=MUTED,
    ).pack(anchor="w", padx=14, pady=(6, 0))
    ttk.Progressbar(left, variable=prog_v, maximum=100).pack(fill="x", padx=14, pady=(2, 6))

    # ── Render button ─────────────────────────────────────────────────────────
    render_btn = tk.Button(
        left,
        text="▶  RENDER VIDEO",
        font=("Arial", 13, "bold"),
        bg=ACCENT,
        fg="white",
        relief="flat",
        cursor="hand2",
        activebackground="#c73652",
        pady=12,
    )
    render_btn.pack(fill="x", padx=14, pady=(4, 8))

    # ── Right panel: log ──────────────────────────────────────────────────────
    tk.Label(
        right, text="📋  Render Log",
        font=("Arial", 10, "bold"), bg=CARD2, fg=TEXT,
    ).pack(anchor="w", padx=12, pady=(12, 2))

    log_box = scrolledtext.ScrolledText(
        right, bg="#06060f", fg=SUCCESS,
        font=("Consolas", 9), relief="flat", bd=0, state="disabled",
    )
    log_box.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    out_v = tk.StringVar(value=str(OUTPUT_DIR))
    tk.Label(right, text="Output:", font=("Arial", 8), bg=CARD2, fg=MUTED).pack(anchor="w", padx=12)
    tk.Label(
        right, textvariable=out_v, font=("Consolas", 8), bg=CARD2, fg=SUCCESS,
        wraplength=350, justify="left",
    ).pack(anchor="w", padx=12, pady=(0, 4))

    # ── Footer branding ───────────────────────────────────────────────────────
    footer = tk.Frame(root, bg=CARD, height=28)
    footer.pack(fill="x", side="bottom")
    footer.pack_propagate(False)
    tk.Label(
        footer,
        text=f"  {APP_NAME} {APP_VERSION}  •  Developed by {DEVELOPER}  "
             f"•  {YOUTUBE_URL}  •  {WEBSITE_URL}",
        font=("Arial", 8), bg=CARD, fg=MUTED,
    ).pack(side="left", pady=5)

    # ── Log helper ────────────────────────────────────────────────────────────
    def _log(msg: str) -> None:
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")
        root.update_idletasks()

    # ── Render action ─────────────────────────────────────────────────────────
    def on_render():
        raw = script_box.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("No script", "Please enter a voiceover script.")
            return

        # Apply settings to config
        cfg.tts.engine           = tts_v.get()
        cfg.video.aspect_ratio   = ratio_v.get()
        cfg.video.color_grade    = grade_v.get()
        cfg.video.resolution     = res_v.get()
        cfg.video.transition     = trans_v.get()
        cfg.subtitle.style       = sub_v.get()
        cfg.subtitle.burn_in     = burn_v.get()
        cfg.enable_sfx           = sfx_en.get()
        cfg.enable_music         = music_en.get()
        cfg.audio.normalize_audio = norm_v.get()
        cfg.default_animation    = anim_v.get()
        cfg.use_pexels_video     = pexvid_v.get()

        # Handle voice selection
        voice_sel = voice_v.get()
        if ":" in voice_sel:
            gender_part = voice_sel.split(":", 1)[0]
            voice_name  = voice_sel.split(":", 1)[1]
            cfg.tts.voice_gender = gender_part
            # Store specific voice id in config for tts.py to use
            for v in _installed_voices:
                if v["name"][:45] == voice_name:
                    cfg.tts.selected_voice_id = v["id"]
                    break
            else:
                cfg.tts.selected_voice_id = None
        else:
            cfg.tts.voice_gender = voice_sel
            cfg.tts.selected_voice_id = None

        mus      = Path(music_v.get())
        mus_path = mus if (music_en.get() and mus.exists()) else None
        imgs     = sel_imgs if sel_imgs else None

        render_btn.configure(state="disabled", text="⏳  Rendering…")
        prog_v.set(0)

        def _run():
            try:
                def cb(stage, pct):
                    prog_v.set(pct)
                    prog_lbl.set(stage)
                    _log(f"[{pct:3.0f}%] {stage}")

                out = run_pipeline(
                    script=raw,
                    cfg=cfg,
                    project_name=name_v.get() or "my_video",
                    extra_images=imgs,
                    music_path=mus_path,
                    title=title_v.get(),
                    progress_cb=cb,
                    add_watermark=wm_v.get(),
                )
                out_v.set(str(out))
                root.after(0, lambda: messagebox.showinfo(
                    "Done! 🎬", f"Video ready:\n{out}\n\nDeveloped by {DEVELOPER}"
                ))
            except Exception as e:
                logger.exception("Pipeline error")
                err_msg = str(e)
                root.after(0, lambda msg=err_msg: messagebox.showerror("Render Error", msg))
            finally:
                root.after(0, lambda: render_btn.configure(state="normal", text="▶  RENDER VIDEO"))

        threading.Thread(target=_run, daemon=True).start()

    render_btn.configure(command=on_render)

    # ── GUI log handler ───────────────────────────────────────────────────────
    class _GUIHandler(logging.Handler):
        def emit(self, record):
            try:
                root.after(0, lambda m=self.format(record): _log(m))
            except Exception:
                pass

    gh = _GUIHandler()
    gh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(gh)

    root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} {APP_VERSION} — by {DEVELOPER}"
    )
    parser.add_argument("--gui",         action="store_true", help="Launch GUI")
    parser.add_argument("--topic",       type=str,  help="Auto-generate script for topic")
    parser.add_argument("--script",      type=str,  help="Inline script text")
    parser.add_argument("--script-file", type=str,  help="Path to .txt script file")
    parser.add_argument("--name",        type=str,  default="my_video")
    parser.add_argument("--title",       type=str,  default="")
    parser.add_argument("--music",       type=str)
    parser.add_argument("--images",      nargs="*")
    parser.add_argument("--config",      type=str,  default="config.json")
    parser.add_argument("--resume",      action="store_true")
    parser.add_argument("--batch",       type=str,  help="Folder of .txt scripts")
    parser.add_argument("--tts",         type=str)
    parser.add_argument("--watermark",   action="store_true", help="Add Domebytes watermark")
    parser.add_argument("--debug",       action="store_true")
    args = parser.parse_args()

    cfg = AppConfig.load(args.config)
    if args.debug:
        cfg.debug = True
    if args.tts:
        cfg.tts.engine = args.tts
    setup_logging(cfg.debug)

    if args.gui:
        launch_gui()
        return

    if args.batch:
        folder = Path(args.batch)
        if not folder.is_dir():
            print(f"❌  Not a folder: {folder}")
            sys.exit(1)
        results = run_batch(folder, cfg)
        print(f"\n✅  Batch: {len(results)} videos done")
        return

    script = ""
    if args.topic:
        script = (
            f"Welcome to this video about {args.topic}.\n\n"
            f"Let's explore everything you need to know about {args.topic}.\n\n"
            f"By the end you will have a complete understanding of {args.topic} and why it matters."
        )
    elif args.script:
        script = args.script
    elif args.script_file:
        script = Path(args.script_file).read_text(encoding="utf-8")

    if not script:
        parser.print_help()
        print(f"\n❌  Provide --topic, --script, --script-file, or --gui")
        sys.exit(1)

    music  = Path(args.music) if args.music else None
    images = [Path(p) for p in args.images] if args.images else None

    try:
        from tqdm import tqdm

        pbar = tqdm(total=100, desc="Rendering", unit="%", ncols=72, colour="green")
        last = [0]

        def _cb(stage, pct):
            delta = int(pct) - last[0]
            if delta > 0:
                pbar.update(delta)
                last[0] = int(pct)
            pbar.set_description(stage[:42])

        out = run_pipeline(
            script, cfg, args.name, images, music, args.title,
            _cb, args.resume, add_watermark=args.watermark,
        )
        pbar.close()
    except ImportError:
        out = run_pipeline(
            script, cfg, args.name, images, music, args.title,
            None, args.resume, add_watermark=args.watermark,
        )

    print(f"\n🎬  Output: {out}")
    print(f"   {APP_NAME} {APP_VERSION} — {WEBSITE_URL}")


if __name__ == "__main__":
    main()
