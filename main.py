#!/usr/bin/env python3
"""
Domebytes AI Video Editor – Professional Edition
Entry point for the modern PySide6 GUI.
"""
import sys
from PySide6.QtWidgets import QApplication
from ui import MainWindow
from utils import setup_logging

if __name__ == "__main__":
    setup_logging(debug=False)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())