"""Simulation image grid view with zoom."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QFrame, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap


class ImageCard(QFrame):
    """Single simulated image with label. Click to zoom."""
    clicked = pyqtSignal(str, str)  # image_path, title

    def __init__(self, image_path, miller_index, material_id, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self._miller = miller_index
        self._mid = material_id

        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "ImageCard { background: white; border-radius: 4px; "
            "border: 1px solid #eee; padding: 6px; }"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        img_label = QLabel()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pixmap)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        hkl_str = f"({miller_index[0]}{miller_index[1]}{miller_index[2]})"
        label = QLabel(f"{material_id} {hkl_str}")
        label.setStyleSheet("font-size: 10px; color: #666;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def mousePressEvent(self, event):
        hkl_str = f"({self._miller[0]}{self._miller[1]}{self._miller[2]})"
        title = f"{self._mid} {hkl_str}"
        self.clicked.emit(self.image_path, title)


class ImageZoomDialog(QDialog):
    """Full-size image popup."""
    def __init__(self, image_path, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        img_label = QLabel()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(780, 580, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pixmap)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)


class SimulationView(QWidget):
    """Grid view of all simulated HAADF images."""

    _COLS = 3  # images per row

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("No simulations yet")
        self.status_label.setStyleSheet("color: #999; padding: 20px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")
        self.scroll.setVisible(False)

        self.grid = QWidget()
        self.grid_layout = QGridLayout(self.grid)
        self.grid_layout.setSpacing(8)

        self.scroll.setWidget(self.grid)
        layout.addWidget(self.scroll)
        layout.addStretch()

    def populate(self, sim_manifest):
        # Clear old cards
        for card in self._cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        sims = sim_manifest.get("simulations", [])
        if not sims:
            self.status_label.setText("No simulations found")
            self.status_label.setVisible(True)
            self.scroll.setVisible(False)
            return

        self.status_label.setVisible(False)
        self.scroll.setVisible(True)

        for i, sim in enumerate(sims):
            card = ImageCard(sim["image_path"], sim["miller_index"], sim["material_id"])
            card.clicked.connect(
                lambda path, title: ImageZoomDialog(path, title, self).exec()
            )
            row, col = divmod(i, self._COLS)
            self.grid_layout.addWidget(card, row, col)
            self._cards.append(card)
