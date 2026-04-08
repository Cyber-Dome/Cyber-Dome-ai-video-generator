# 🎬 Domebytes AI Video Editor — Pro v3

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/FFmpeg-Required-green?style=for-the-badge"/>
</p>

<p align="center">
  <b>🚀 AI-Powered Video Generation Tool for Tech Creators</b>
</p>

---

## 🧠 About AI Video generator

Domebytes AI Video Editor is a **next-generation AI video automation system** that converts plain text scripts into:

🎥 Cinematic videos  
📊 Animated diagrams  
🎙 Natural voice narration  
📝 Auto subtitles  
🎵 Smart audio mix  

👉 Built for **YouTube creators, developers, and educators**

---

## 🔥 Demo Flow

```
Script → Scenes → Voice → Visuals → Diagrams → FFmpeg → Final Video
```

---

## ✨ Premium Features

- 🎬 Scene-based intelligent rendering
- 📊 Diagram generation (Kroki + Mermaid)
- 🎥 Hybrid visuals (Pexels + AI + assets)
- 🎙 Multi-engine TTS (pyttsx3, gTTS, Edge)
- 🧠 Smart scene understanding
- 📝 Subtitle sync (Whisper-ready)
- 🎵 Auto-ducking background music
- 🔊 Context-aware SFX
- 🎨 Cinematic transitions
- 🚀 No overwrite output system

---

## 🎬 Visual Intelligence System

| Scene Type | Output |
|----------|--------|
| Intro | 🎬 Custom intro.mp4 |
| Explanation | 📊 Animated diagrams |
| Normal | 🎥 Pexels footage |
| Outro | 🎬 Branding outro |

---

## ⚙️ Installation

```bash
git clone https://github.com/Cyber-Dome/ai-video-generator.git
cd ai-video-generator
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Optional:
```bash
pip install openai-whisper torch
```

---

## ▶️ Usage

### GUI Mode
```bash
python generate.py --gui
```

### CLI Mode
```bash
python generate.py --script-file script.txt --name output_video
```

---

## 📂 Project Architecture

```
generate.py           # Main engine
planner.py            # Scene intelligence
renderer.py           # FFmpeg rendering
diagram_engine.py     # Diagram logic
diagram_animator.py   # Animated diagrams
tts.py                # Voice system
subtitles.py          # Subtitle engine
utils.py              # Helpers
config.py             # Settings

assets/
  video/
  music/
  sfx/

output/
cache/
```

---

## 🎧 Audio System

- Voice = Priority
- Music = Auto-ducked
- SFX = Scene-based trigger

---

## 📦 Output Example

```
output/
  my_video_2026-04-08_01_final.mp4
  subtitles.srt
```

---

## ⚠️ Requirements

- Python 3.10+
- FFmpeg installed
- Internet (Pexels + Kroki)

---

## 👨‍💻 Author

**Amal Aji**  
YouTube: https://www.youtube.com/@cyberdomeee  
Website: https://domebytes.blogspot.com  

---

## ⭐ Support

If you like this project:

- ⭐ Star this repo
- 📺 Subscribe on YouTube
- 🚀 Share with developers

---

## 🏁 Future Roadmap

- 🎥 AI voice sync diagrams
- 🎬 Advanced cinematic transitions
- 🤖 LLM-based script planning
- 🌐 Web version (SaaS)

---

## 📜 License

© 2026 Amal Aji / Domebytes

Free for personal use.  
Commercial use requires attribution:

"Domebytes AI Video Editor by Amal Aji"
