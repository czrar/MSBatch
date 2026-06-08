"""MSBatch GUI - startup script.

Usage:
    python gui_main.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gui.main_window import MSBatchMainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("MSBatch")
    app.setOrganizationName("MSBatch")
    app.setStyle("Fusion")

    window = MSBatchMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
