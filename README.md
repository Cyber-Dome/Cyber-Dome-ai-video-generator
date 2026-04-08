# 🎬 Domebytes AI Video Editor — Pro v3

> **Developed by AMAL AJI**
> 📺 YouTube: [https://www.youtube.com/@cyberdomeee](https://www.youtube.com/@cyberdomeee)
> 🌐 Website: [https://domebytes.blogspot.com](https://domebytes.blogspot.com)
> 📧 Email: amalajiconnect@gmail.com

---

Professional AI-powered video generation pipeline.
Give it a script → get a YouTube-ready MP4 with intelligent visuals, voice, subtitles, and music.

**100% free. No paid APIs. Topic-aware visuals. Per-scene audio. Auto-subtitles. Never overwrites output.**

---

## ✨ What's New in v3 Pro

| Feature | v2 | v3 Pro |
|---------|----|----|
| Visual selection | Raw keywords | **Topic-aware** (cyber → hacking visuals, tech → tech visuals) |
| SFX system | Generic lookup | **Maps to real mixkit files** in assets/sfx/ |
| Background music | Simple mix | **Auto-ducking** (reduces under voice, smooth fade) |
| Voice selection | Gender only | **Full dropdown** of all installed pyttsx3 voices |
| Output naming | Fixed filename (overwrites!) | **Unique per render** (my_video_2026-04-07_01.mp4) |
| UI | Basic dark | **Professional dark theme** with branding |
| Watermark | None | Optional **Domebytes watermark** overlay |
| SFX timing | Full scene | **Scene start only** (0–1s), voice always primary |
| Transitions | Video only | **Audio + video fade** together |
| Branding | None | **Full Domebytes branding** in GUI + code |

---

## Quick Start (Windows)

### 1. Install FFmpeg
```bash
winget install Gyan.FFmpeg
```
Restart terminal after install.

### 2. Set up Python environment
```bash
cd ai-video-pro
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. (Optional) Install Whisper for accurate subtitles
```bash
pip install openai-whisper torch
```

### 4. Run
```bash
# GUI (recommended):
python generate.py --gui

# CLI with topic (intelligent visual selection):
python generate.py --topic "The Dark Web Explained" --name darkweb

# CLI with script file:
python generate.py --script-file myscript.txt --name my_video

# With watermark:
python generate.py --topic "AI Security" --watermark

# With music and images:
python generate.py --script "Your script" --images img1.jpg --music bg.mp3

# Resume an interrupted render:
python generate.py --resume --name my_video

# Batch mode (folder of .txt files):
python generate.py --batch scripts/
```

---

## Folder Structure

```
ai-video-pro/
├── generate.py        ← Run this (orchestrator + GUI)
├── planner.py         ← Multi-scene storyboard builder
├── tts.py             ← Per-scene TTS with voice selection
├── subtitles.py       ← Whisper + storyboard-synced subtitles
├── renderer.py        ← FFmpeg renderer (smart visuals, SFX, ducking)
├── config.py          ← Typed dataclass config
├── utils.py           ← FFmpeg wrapper, helpers
├── config.json        ← Edit this to change settings
├── requirements.txt
├── assets/
│   ├── music/
│   │   └── bg.mp3       ← Drop background music here
│   ├── sfx/
│   │   └── mixkit-*.wav ← Your existing SFX files (auto-detected!)
│   ├── videos/          ← Drop local MP4 loops here (used first)
│   └── images/          ← Optional local images
├── cache/
│   ├── images/          ← AI images cached here
│   ├── tts/             ← TTS WAV files cached here
│   ├── videos/          ← Pexels video cache
│   └── subtitles/       ← SRT/ASS files cached here
├── output/              ← Final videos (never overwritten!)
│   └── my_video_2026-04-07_01.mp4
│   └── my_video_2026-04-07_02.mp4
└── projects/            ← Storyboard JSON + resume state
```

---

## 🎬 Intelligent Visual Selection

v3 automatically detects your topic and fetches **relevant** visuals:

| Script topic | Visuals fetched |
|---|---|
| "AI" / "machine learning" | Neural networks, AI, data science |
| "cybersecurity" / "hacking" | Cyber attacks, hacker terminals, dark screens |
| "dark web" / "tor" | Anonymous hacker, neon dark web |
| "business" / "startup" | Modern offices, meetings, entrepreneurs |
| "finance" / "crypto" | Stock charts, trading, financial graphics |
| "space" | Galaxy, cosmos, rockets |
| "health" / "medical" | Healthcare, hospitals, doctors |
| general | Best available cinematic clips |

**Video-first priority:**
1. Local `assets/videos/` files
2. Pexels video (topic-specific query)
3. Pollinations AI image
4. Pexels image
5. Procedural animated background

---

## 🎧 SFX System (assets/sfx/)

v3 maps your existing **mixkit** WAV files to scene categories:

| Category | Matched files |
|---|---|
| `whoosh` | `*gamma-ray-whoosh*`, `*zoom-move*`, `*technology-transition-slide*` |
| `notification` | `*technology-notification*`, `*high-tech-bleep*` |
| `ui` | `*interface-device-click*`, `*alien-technology-button*`, `*ui-zoom*` |
| `alert` | `*alarm*`, `*electric-fence-alert*`, `*clock-countdown-bleeps*` |
| `tech` | `*cybernetic-technology*`, `*futuristic-cinematic-sweep*` |
| `ambient` | `*futuristic-sci-fi-computer-ambience*` |
| `dramatic` | `*electric-buzz-glitch*`, `*sci-fi-battle-laser*` |

**Rules:**
- SFX only plays at **scene start** (first 0–1 second)
- SFX volume: 0.12–0.18 (subtle)
- Voice always remains primary (volume 1.0)
- No SFX downloads — only uses your local files

---

## 🎤 Voice Selection (GUI)

The GUI now shows a dropdown of **all installed voices** on your system:

```
auto:male         ← picks best male voice
auto:female       ← picks best female voice
male:Microsoft David    ← specific voice
female:Microsoft Zira   ← specific voice
...
```

Selection is applied immediately to the TTS engine.

---

## 📁 Output Naming (No Overwrite)

Every render gets a **unique filename**:

```
output/
  my_video_2026-04-07_01_final.mp4
  my_video_2026-04-07_01_final_subtitled.mp4
  my_video_2026-04-07_02_final.mp4
  my_video_2026-04-07_02_final_subtitled.mp4
```

Format: `{project_name}_{YYYY-MM-DD}_{NN}_final.mp4`

---

## Configuration (config.json)

### TTS
| Key | Options | Notes |
|---|---|---|
| `tts.engine` | `pyttsx3`, `gtts`, `coqui`, `bark` | pyttsx3 = offline |
| `tts.voice_gender` | `male`, `female` | overridden by GUI voice dropdown |
| `tts.speed` | `0.5`–`2.0` | 1.0 = normal |

### Video
| Key | Options |
|---|---|
| `video.aspect_ratio` | `16:9` (YouTube), `9:16` (Shorts), `1:1` (Instagram) |
| `video.color_grade` | `cinematic`, `bright`, `vintage`, `cold`, `none` |
| `video.transition` | `fade`, `slide`, `zoom`, `wipe`, `none` |
| `video.resolution` | `1080p`, `720p`, `4K` |
| `default_animation` | `ken_burns`, `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `random` |

### Audio
| Key | Default | Notes |
|---|---|---|
| `audio.music_volume` | `0.15` | Full volume when no voice. Ducked to ~0.04 under voice. |
| `audio.sfx_volume` | `0.15` | Kept low — voice is always primary |
| `enable_music` | `false` | Toggle background music |
| `enable_sfx` | `true` | Toggle SFX |
| `audio.normalize_audio` | `false` | Loudness normalization |

---

## How It Works (v3)

```
Script text
     │
     ▼
Planner (splits scenes, extracts keywords, detects topic cluster,
         assigns animation, SFX hint, transition per scene)
     │
     ▼
TTS (per-scene WAV using selected voice from GUI)
     │
     ▼
Renderer:
  ├─ get_smart_pexels_query() → topic-aware search
  ├─ Video-first: local → Pexels video → Pollinations → Pexels image → procedural
  ├─ Animate (ken_burns / zoom_in / zoom_out / pan_left / pan_right / random)
  ├─ SFX from assets/sfx/ (scene start only, 0.12 volume)
  ├─ Smooth fade transitions (audio + video)
  ├─ Concatenate all scene clips
  ├─ Color grade
  ├─ Title overlay
  ├─ Background music (auto-ducked under voice)
  ├─ Audio normalize
  └─ Optional Domebytes watermark
     │
     ▼
Subtitle Engine → Storyboard timing → burn into video
     │
     ▼
Output: my_video_2026-04-07_01_final_subtitled.mp4  ← unique, never overwrites
        my_video_2026-04-07_01.srt
        my_video_2026-04-07_01_thumbnail.jpg
        my_video_chapters.txt
```

---

## License & Attribution

© 2026 **AMAL AJI** / Domebytes. All rights reserved.

Free for personal use. For commercial use or redistribution, credit required:
- Credit: **Domebytes AI Video Editor by AMAL AJI**
- Link: https://domebytes.blogspot.com

Do not redistribute without this attribution notice.
