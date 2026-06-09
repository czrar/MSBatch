"""Left sidebar with step-by-step parameter controls."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QGroupBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal


class Sidebar(QWidget):
    """Left parameter panel with step controls."""

    retrieve_clicked = pyqtSignal(dict)
    simulate_clicked = pyqtSignal()
    advanced_clicked = pyqtSignal()
    experiment_image_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Step 1: Retrieval
        step1 = QGroupBox("Step 1: Element Retrieval")
        step1_layout = QVBoxLayout(step1)

        step1_layout.addWidget(QLabel("Elements (comma-separated):"))
        self.elements_input = QLineEdit()
        self.elements_input.setPlaceholderText("Li, Co, O")
        step1_layout.addWidget(self.elements_input)

        step1_layout.addWidget(QLabel("Stoichiometry (optional):"))
        self.stoich_input = QLineEdit()
        self.stoich_input.setPlaceholderText("Co:0.8-1.2, O:1.8-2.2")
        step1_layout.addWidget(self.stoich_input)

        step1_layout.addWidget(QLabel("Miller Indices:"))
        self.miller_input = QLineEdit()
        self.miller_input.setPlaceholderText("001, 100, 110, 111")
        step1_layout.addWidget(self.miller_input)

        step1_layout.addWidget(QLabel("Max Candidates:"))
        self.max_candidates_input = QLineEdit("50")
        step1_layout.addWidget(self.max_candidates_input)

        self.retrieve_btn = QPushButton("Start Retrieval")
        self.retrieve_btn.clicked.connect(self._on_retrieve)
        self.retrieve_btn.setStyleSheet(
            "QPushButton { background-color: #0f3460; color: white; padding: 8px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:disabled { background-color: #999; }"
        )
        step1_layout.addWidget(self.retrieve_btn)
        layout.addWidget(step1)

        # Step 2: Candidate status
        step2 = QGroupBox("Step 2: Select Candidates")
        step2_layout = QVBoxLayout(step2)
        self.candidate_status = QLabel("No candidates loaded")
        self.candidate_status.setWordWrap(True)
        step2_layout.addWidget(self.candidate_status)
        layout.addWidget(step2)

        # Step 3: Simulation
        step3 = QGroupBox("Step 3: Simulate && Compare")
        step3_layout = QVBoxLayout(step3)
        self.simulate_btn = QPushButton("Start Simulation")
        self.simulate_btn.clicked.connect(self.simulate_clicked.emit)
        self.simulate_btn.setEnabled(False)
        self.simulate_btn.setStyleSheet(
            "QPushButton { background-color: #e94560; color: white; padding: 8px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        step3_layout.addWidget(self.simulate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        step3_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        step3_layout.addWidget(self.progress_label)
        layout.addWidget(step3)

        # Step 4: Experimental image
        step4 = QGroupBox("Step 4: Experimental Image")
        step4_layout = QVBoxLayout(step4)
        up_btn = QPushButton("Upload Image")
        up_btn.clicked.connect(self._on_upload_experimental)
        step4_layout.addWidget(up_btn)
        self.exp_image_label = QLabel("No image loaded")
        self.exp_image_label.setWordWrap(True)
        step4_layout.addWidget(self.exp_image_label)
        layout.addWidget(step4)

        layout.addStretch()

        # Advanced settings
        adv_btn = QPushButton("Advanced Settings")
        adv_btn.clicked.connect(self.advanced_clicked.emit)
        layout.addWidget(adv_btn)

    def _on_retrieve(self):
        try:
            self._do_retrieve()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Input Error",
                f"Failed to parse input:\n\n{e}\n\n"
                "Stoichiometry format: Co:0.8-1.2,O:1.8-2.2\n"
                "Miller format: 001,100,110,111"
            )

    def _do_retrieve(self):
        elements = [e.strip() for e in self.elements_input.text().split(",") if e.strip()]
        if not elements:
            return

        params = {"elements": elements}

        stoich_text = self.stoich_input.text().strip()
        if stoich_text:
            stoich = {}
            for part in stoich_text.split(","):
                part = part.strip()
                if ":" not in part:
                    raise ValueError(f"Invalid stoichiometry part: '{part}' (expected 'El:lo-hi')")
                el, rng = part.split(":", 1)
                # 用 rsplit 从右侧分割，支持负值范围如 "-1.2-0.8"
                rng = rng.strip()
                if "-" in rng.lstrip("-"):  # 排除前导负号
                    parts = rng.rsplit("-", 1)
                else:
                    raise ValueError(f"Invalid range in '{part}': expected 'lo-hi' format")
                lo, hi = float(parts[0].strip()), float(parts[1].strip())
                stoich[el.strip()] = (lo, hi)
            params["stoichiometry"] = stoich

        miller_text = self.miller_input.text().strip()
        if miller_text:
            miller_list = []
            for s in miller_text.split(","):
                s = s.strip()
                if len(s) != 3 or not s.isdigit():
                    raise ValueError(f"Invalid Miller index: '{s}' (expected 3 digits like '001')")
                miller_list.append(tuple(int(c) for c in s))
            params["miller_indices"] = miller_list

        try:
            params["max_candidates"] = int(self.max_candidates_input.text())
        except ValueError:
            params["max_candidates"] = 50

        self.retrieve_clicked.emit(params)

    def _on_upload_experimental(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Experimental Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif);;All Files (*)"
        )
        if path:
            self.exp_image_label.setText(f"Loaded: {Path(path).name}")
            self.experiment_image_dropped.emit(path)

    def set_candidate_count(self, count):
        self.candidate_status.setText(f"Found {count} candidates")
        self.simulate_btn.setEnabled(count > 0)

    def set_progress(self, message, current, total):
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)

    def set_retrieving(self, active=True):
        self.retrieve_btn.setEnabled(not active)
        self.retrieve_btn.setText("Retrieving..." if active else "Start Retrieval")

    def set_simulating(self, active=True):
        self.simulate_btn.setEnabled(not active)
        self.simulate_btn.setText("Simulating..." if active else "Start Simulation")
        if not active:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
