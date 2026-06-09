"""Experimental vs simulated comparison view."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap


class ComparisonView(QWidget):
    """Left: experimental image. Right: simulated image grid."""
    export_report_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._experimental_path = None
        self._row_widgets = []  # track widgets for cleanup
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top bar
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Comparison Report</b>"))
        top.addStretch()
        export_btn = QPushButton("Export HTML Report")
        export_btn.clicked.connect(self.export_report_clicked.emit)
        top.addWidget(export_btn)
        main_layout.addLayout(top)

        # Content
        content = QHBoxLayout()

        # Left: experimental image
        self.exp_container = QFrame()
        self.exp_container.setFrameStyle(QFrame.Shape.StyledPanel)
        self.exp_container.setStyleSheet(
            "QFrame { background: white; border: 2px dashed #ccc; "
            "border-radius: 8px; min-width: 300px; }"
        )
        exp_layout = QVBoxLayout(self.exp_container)

        self.exp_title = QLabel("Experimental Image")
        self.exp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.exp_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        exp_layout.addWidget(self.exp_title)

        self.exp_image = QLabel("Drop or upload\nexperimental image")
        self.exp_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.exp_image.setMinimumSize(300, 400)
        self.exp_image.setStyleSheet("color: #999; font-size: 14px;")
        exp_layout.addWidget(self.exp_image)

        up_btn = QPushButton("Upload Image")
        up_btn.clicked.connect(self._upload_experimental)
        exp_layout.addWidget(up_btn)
        content.addWidget(self.exp_container)

        # Right: simulated images
        self.sim_scroll = QScrollArea()
        self.sim_scroll.setWidgetResizable(True)
        self.sim_scroll.setStyleSheet("QScrollArea { border: none; }")

        self.sim_grid = QWidget()
        self.sim_layout = QVBoxLayout(self.sim_grid)
        self.sim_layout.setSpacing(8)
        self.sim_layout.addStretch()
        self.sim_scroll.setWidget(self.sim_grid)

        content.addWidget(self.sim_scroll, 1)
        main_layout.addLayout(content, 1)

    def set_experimental_image(self, path):
        self._experimental_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(300, 400, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.exp_image.setPixmap(pixmap)
            self.exp_title.setText(f"Experimental: {Path(path).name}")

    def set_sim_images(self, sim_manifest):
        # Clean up old widgets
        for w in self._row_widgets:
            self.sim_layout.removeWidget(w)
            w.deleteLater()
        self._row_widgets.clear()

        for sim in sim_manifest.get("simulations", []):
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)

            img_label = QLabel()
            pixmap = QPixmap(sim["image_path"])
            if not pixmap.isNull():
                pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                img_label.setPixmap(pixmap)

            hkl = sim["miller_index"]
            info = QLabel(f"{sim['material_id']}\n({hkl[0]}{hkl[1]}{hkl[2]})")
            info.setStyleSheet("font-size: 11px; color: #555;")

            row.addWidget(img_label)
            row.addWidget(info)
            self._row_widgets.append(row_widget)
            self.sim_layout.insertWidget(self.sim_layout.count() - 1, row_widget)

    def _upload_experimental(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Experimental Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif);;All Files (*)"
        )
        if path:
            self.set_experimental_image(path)

    @property
    def experimental_path(self):
        return self._experimental_path
