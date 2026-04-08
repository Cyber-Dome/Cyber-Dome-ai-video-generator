"""
Modern SaaS‑style GUI with sidebar, glassmorphism, real‑time log, and threaded rendering.
"""
import threading
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QTextEdit, QComboBox, QSlider, QPushButton, QLabel, QProgressBar,
    QFileDialog, QCheckBox, QLineEdit, QFrame, QSplitter
)
from PySide6.QtGui import QFont, QColor, QTextCursor

from config import AppConfig
from generate import run_pipeline

# ----------------------------------------------------------------------
# Worker thread for rendering (keeps UI responsive)
# ----------------------------------------------------------------------
class RenderThread(QThread):
    progress = Signal(str, int)   # stage, percent
    finished = Signal(str)        # output video path
    error = Signal(str)

    def __init__(self, script, cfg, project_name, extra_images, music_path, title, add_watermark):
        super().__init__()
        self.script = script
        self.cfg = cfg
        self.project_name = project_name
        self.extra_images = extra_images
        self.music_path = music_path
        self.title = title
        self.add_watermark = add_watermark

    def run(self):
        try:
            out = run_pipeline(
                script=self.script,
                cfg=self.cfg,
                project_name=self.project_name,
                extra_images=self.extra_images,
                music_path=self.music_path,
                title=self.title,
                progress_cb=self._progress_cb,
                add_watermark=self.add_watermark,
            )
            self.finished.emit(str(out))
        except Exception as e:
            self.error.emit(str(e))

    def _progress_cb(self, stage, pct):
        self.progress.emit(stage, pct)


# ----------------------------------------------------------------------
# Main Window
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = AppConfig.load()
        self.selected_images = []      # list of Path
        self.setWindowTitle("Domebytes AI Video Editor Pro")
        self.setGeometry(100, 100, 1400, 900)
        self.setup_ui()
        self.apply_stylesheet()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------- Sidebar ----------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setSpacing(10)

        logo = QLabel("🎬 Domebytes")
        logo.setObjectName("logo")
        sidebar_layout.addWidget(logo)

        self.nav_btns = {}
        for name in ["Script", "Voice", "Video", "Media", "Render"]:
            btn = QPushButton(name)
            btn.setObjectName("nav_btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self.switch_page(n))
            sidebar_layout.addWidget(btn)
            self.nav_btns[name] = btn
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # ---------- Main content (stacked pages) ----------
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        self.script_page = self.create_script_page()
        self.stack.addWidget(self.script_page)

        self.voice_page = self.create_voice_page()
        self.stack.addWidget(self.voice_page)

        self.video_page = self.create_video_page()
        self.stack.addWidget(self.video_page)

        self.media_page = self.create_media_page()
        self.stack.addWidget(self.media_page)

        self.render_page = self.create_render_page()
        self.stack.addWidget(self.render_page)

        self.switch_page("Script")
        self.nav_btns["Script"].setChecked(True)

        # ---------- Right side log panel ----------
        log_panel = QFrame()
        log_panel.setObjectName("log_panel")
        log_panel.setFixedWidth(320)
        log_layout = QVBoxLayout(log_panel)
        log_label = QLabel("📋 Render Log")
        log_label.setObjectName("log_label")
        log_layout.addWidget(log_label)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("log_text")
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_panel)

    # ------------------------------------------------------------------
    # Page: Script
    # ------------------------------------------------------------------
    def create_script_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("📝 Voiceover Script")
        title.setObjectName("page_title")
        layout.addWidget(title)
        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText(
            "Enter your script here...\n\nExample:\n"
            "Welcome to Domebytes AI Video Editor.\n"
            "Today we explore the future of content creation..."
        )
        self.script_edit.setObjectName("script_edit")
        layout.addWidget(self.script_edit)
        return page

    # ------------------------------------------------------------------
    # Page: Voice Settings (Edge TTS + pyttsx3)
    # ------------------------------------------------------------------
    def create_voice_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🎙️ Voice Settings")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # Engine
        eng_layout = QHBoxLayout()
        eng_layout.addWidget(QLabel("TTS Engine:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["edge", "pyttsx3", "gtts"])
        self.engine_combo.setCurrentText(self.cfg.tts.engine)
        eng_layout.addWidget(self.engine_combo)
        layout.addLayout(eng_layout)

        # Gender
        gen_layout = QHBoxLayout()
        gen_layout.addWidget(QLabel("Voice Gender:"))
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["male", "female"])
        self.gender_combo.setCurrentText(self.cfg.tts.voice_gender)
        gen_layout.addWidget(self.gender_combo)
        layout.addLayout(gen_layout)

        # Speed
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(int(self.cfg.tts.speed * 100))
        self.speed_label = QLabel(f"{self.cfg.tts.speed:.1f}x")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"{v/100:.1f}x"))
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_label)
        layout.addLayout(speed_layout)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page: Video Settings
    # ------------------------------------------------------------------
    def create_video_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🎥 Video Settings")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # Aspect Ratio
        ar_layout = QHBoxLayout()
        ar_layout.addWidget(QLabel("Aspect Ratio:"))
        self.ar_combo = QComboBox()
        self.ar_combo.addItems(["16:9", "9:16", "1:1"])
        self.ar_combo.setCurrentText(self.cfg.video.aspect_ratio)
        ar_layout.addWidget(self.ar_combo)
        layout.addLayout(ar_layout)

        # Resolution
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["1080p", "720p", "4K"])
        self.res_combo.setCurrentText(self.cfg.video.resolution)
        res_layout.addWidget(self.res_combo)
        layout.addLayout(res_layout)

        # Color Grade
        grade_layout = QHBoxLayout()
        grade_layout.addWidget(QLabel("Color Grade:"))
        self.grade_combo = QComboBox()
        self.grade_combo.addItems(["cinematic", "bright", "vintage", "cold", "none"])
        self.grade_combo.setCurrentText(self.cfg.video.color_grade)
        grade_layout.addWidget(self.grade_combo)
        layout.addLayout(grade_layout)

        # Animation
        anim_layout = QHBoxLayout()
        anim_layout.addWidget(QLabel("Animation:"))
        self.anim_combo = QComboBox()
        self.anim_combo.addItems(["ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right", "random"])
        self.anim_combo.setCurrentText(self.cfg.default_animation)
        anim_layout.addWidget(self.anim_combo)
        layout.addLayout(anim_layout)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page: Media Files
    # ------------------------------------------------------------------
    def create_media_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("📁 Media")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # Music
        music_layout = QHBoxLayout()
        music_layout.addWidget(QLabel("Background Music:"))
        self.music_path_edit = QLineEdit()
        self.music_path_edit.setReadOnly(True)
        music_btn = QPushButton("Browse")
        music_btn.clicked.connect(self.select_music)
        music_layout.addWidget(self.music_path_edit)
        music_layout.addWidget(music_btn)
        layout.addLayout(music_layout)

        # Custom images/videos
        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Custom Images/Videos:"))
        self.img_path_edit = QLineEdit()
        self.img_path_edit.setReadOnly(True)
        img_btn = QPushButton("Select Files")
        img_btn.clicked.connect(self.select_images)
        img_layout.addWidget(self.img_path_edit)
        img_layout.addWidget(img_btn)
        layout.addLayout(img_layout)

        self.music_enabled = QCheckBox("Enable Background Music")
        self.music_enabled.setChecked(self.cfg.enable_music)
        layout.addWidget(self.music_enabled)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page: Render & Progress
    # ------------------------------------------------------------------
    def create_render_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("⚡ Render")
        title.setObjectName("page_title")
        layout.addWidget(title)

        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("Project name")
        self.project_name_edit.setText(self.cfg.project_name)
        layout.addWidget(QLabel("Project Name:"))
        layout.addWidget(self.project_name_edit)

        self.title_overlay = QLineEdit()
        self.title_overlay.setPlaceholderText("Optional title overlay")
        layout.addWidget(QLabel("Title Overlay:"))
        layout.addWidget(self.title_overlay)

        self.watermark_check = QCheckBox("Add Domebytes Watermark")
        layout.addWidget(self.watermark_check)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.render_btn = QPushButton("▶ RENDER VIDEO")
        self.render_btn.setObjectName("render_btn")
        self.render_btn.clicked.connect(self.start_render)
        layout.addWidget(self.render_btn)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # File pickers
    # ------------------------------------------------------------------
    def select_music(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Music", "", "Audio Files (*.mp3 *.wav)")
        if path:
            self.music_path_edit.setText(path)

    def select_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Images/Videos", "",
                                                "Media Files (*.jpg *.png *.mp4 *.mov)")
        if paths:
            self.img_path_edit.setText("; ".join(Path(p).name for p in paths))
            self.selected_images = [Path(p) for p in paths]

    # ------------------------------------------------------------------
    # Render orchestration (threaded)
    # ------------------------------------------------------------------
    def start_render(self):
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.log("❌ Script is empty", error=True)
            return

        # Update config from UI
        self.cfg.tts.engine = self.engine_combo.currentText()
        self.cfg.tts.voice_gender = self.gender_combo.currentText()
        self.cfg.tts.speed = self.speed_slider.value() / 100.0
        self.cfg.video.aspect_ratio = self.ar_combo.currentText()
        self.cfg.video.resolution = self.res_combo.currentText()
        self.cfg.video.color_grade = self.grade_combo.currentText()
        self.cfg.default_animation = self.anim_combo.currentText()
        self.cfg.enable_music = self.music_enabled.isChecked()
        self.cfg.project_name = self.project_name_edit.text().strip() or "my_video"

        music_path = Path(self.music_path_edit.text()) if self.music_path_edit.text() and self.music_enabled.isChecked() else None
        extra_images = self.selected_images if self.selected_images else None

        self.render_btn.setEnabled(False)
        self.render_btn.setText("⏳ Rendering...")
        self.progress_bar.setValue(0)
        self.log_text.clear()

        self.render_thread = RenderThread(
            script=script,
            cfg=self.cfg,
            project_name=self.cfg.project_name,
            extra_images=extra_images,
            music_path=music_path,
            title=self.title_overlay.text(),
            add_watermark=self.watermark_check.isChecked()
        )
        self.render_thread.progress.connect(self.update_progress)
        self.render_thread.finished.connect(self.render_finished)
        self.render_thread.error.connect(self.render_error)
        self.render_thread.start()

    def update_progress(self, stage, pct):
        self.progress_bar.setValue(pct)
        self.log(f"[{pct}%] {stage}")

    def render_finished(self, output_path):
        self.render_btn.setEnabled(True)
        self.render_btn.setText("▶ RENDER VIDEO")
        self.log(f"✅ Video ready: {output_path}")

    def render_error(self, error_msg):
        self.render_btn.setEnabled(True)
        self.render_btn.setText("▶ RENDER VIDEO")
        self.log(f"❌ Error: {error_msg}", error=True)

    def log(self, message, error=False):
        color = "red" if error else "#00cc88"
        self.log_text.setTextColor(QColor(color))
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.End)

    def switch_page(self, name):
        pages = {"Script": 0, "Voice": 1, "Video": 2, "Media": 3, "Render": 4}
        self.stack.setCurrentIndex(pages[name])
        for btn in self.nav_btns.values():
            btn.setChecked(False)
        self.nav_btns[name].setChecked(True)

    # ------------------------------------------------------------------
    # Modern dark stylesheet (glassmorphism + rounded corners)
    # ------------------------------------------------------------------
    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a0a14;
            }
            #sidebar {
                background-color: #0f0f1a;
                border-right: 1px solid #1e1e2a;
            }
            #logo {
                font-size: 20px;
                font-weight: bold;
                color: #e94560;
                padding: 20px;
            }
            #nav_btn {
                background-color: transparent;
                color: #c0c0e0;
                text-align: left;
                padding: 10px 20px;
                border: none;
                font-size: 14px;
            }
            #nav_btn:hover {
                background-color: #1e1e2e;
            }
            #nav_btn:checked {
                background-color: #e94560;
                color: white;
            }
            #page_title {
                font-size: 22px;
                font-weight: bold;
                color: #e94560;
                margin-bottom: 20px;
            }
            #script_edit {
                background-color: #0e0e24;
                color: #e8e8f8;
                border: 1px solid #2a2a50;
                border-radius: 8px;
                font-family: monospace;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QSlider {
                background-color: #0e0e24;
                color: #e8e8f8;
                border: 1px solid #2a2a50;
                border-radius: 5px;
                padding: 5px;
            }
            QCheckBox {
                color: #e8e8f8;
            }
            #render_btn {
                background-color: #e94560;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 12px;
                font-size: 16px;
            }
            #render_btn:hover {
                background-color: #c73652;
            }
            #log_panel {
                background-color: #06060f;
                border-left: 1px solid #1e1e2a;
            }
            #log_label {
                color: #e94560;
                font-weight: bold;
                padding: 10px;
            }
            #log_text {
                background-color: #06060f;
                color: #00cc88;
                border: none;
                font-family: monospace;
            }
        """)