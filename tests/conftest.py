"""Shared fixtures and configuration for GUI tests.

Must import QWebEngineView / set AA_ShareOpenGLContexts *before* pytest-qt
creates the QApplication instance.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Required: set before any QCoreApplication is instantiated (pytest-qt
# creates one at plugin init time). Without this flag, importing
# QWebEngineWidgets *after* QApplication creation raises ImportError.
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
