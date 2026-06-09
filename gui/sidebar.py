"""Left sidebar with step-by-step parameter controls."""
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QGroupBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal


def parse_elements(text: str) -> list[str]:
    """Parse element input."""
    tokens = re.split(r'[,，;；、\s.]+', text.strip())
    return [t for t in tokens if t]


def parse_stoichiometry(text: str) -> dict[str, tuple[float, float]]:
    """Parse stoichiometry, normalizing to atomic fractions.

    'V:2 O:5' -> V2O5 -> V fraction 2/7, O fraction 5/7 (±15% tolerance).
    'Co:0.8-1.2, O:1.8-2.2' -> normalized by midpoint sum.
    """
    raw = {}
    pattern = re.compile(
        r'([A-Z][a-z]?)\s*[:：=\s]\s*'
        r'(-?\d+(?:\.\d+)?)\s*(?:-\s*(-?\d+(?:\.\d+)?))?'
    )
    for m in pattern.finditer(text):
        el = m.group(1)
        lo = float(m.group(2))
        hi_str = m.group(3)
        if hi_str is not None:
            hi = float(hi_str)
            raw[el] = (min(lo, hi), max(lo, hi))
        else:
            raw[el] = (lo, lo)

    if not raw:
        raise ValueError(
            f"Cannot parse stoichiometry: '{text}'\n"
            f"Expected: 'Co:0.8-1.2, O:1.8-2.2' or 'V:2 O:5'"
        )

    midpoints = {el: (lo + hi) / 2 for el, (lo, hi) in raw.items()}
    total = sum(midpoints.values())

    result = {}
    for el, (lo, hi) in raw.items():
        lo_norm, hi_norm = lo / total, hi / total
        if lo == hi:
            result[el] = (lo_norm * 0.85, lo_norm * 1.15)
        else:
            result[el] = (lo_norm, hi_norm)
    return result


def parse_miller(text: str) -> list[tuple[int, ...]]:
    """Parse Miller indices."""
    text = text.strip()
    text = text.replace('(', '').replace(')', '')
    text = text.replace('（', '').replace('）', '')

    result = []
    tokens = re.split(r'[,，;；、\s.]+', text)
    for s in tokens:
        s = s.strip()
        if not s:
            continue
        if not s.isdigit():
            raise ValueError(
                f"Cannot parse Miller index '{s}'\n"
                f"Expected like '001' or '104' (digits only)"
            )
        result.append(tuple(int(c) for c in s))
    return result


class Sidebar(QWidget):
    """Left parameter panel with step controls."""

    retrieve_clicked = pyqtSignal(dict)
    simulate_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()
    advanced_clicked = pyqtSignal()
    experiment_image_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Step 1
        step1 = QGroupBox("Step 1: Search")
        s1 = QVBoxLayout(step1)

        s1.addWidget(QLabel("Formula (exact):"))
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("V2O5")
        s1.addWidget(self.formula_input)

        s1.addWidget(QLabel("— or Elements —"))
        self.elements_input = QLineEdit()
        self.elements_input.setPlaceholderText("V, O")
        s1.addWidget(self.elements_input)

        s1.addWidget(QLabel("Stoichiometry (optional):"))
        self.stoich_input = QLineEdit()
        self.stoich_input.setPlaceholderText("V:2 O:5")
        s1.addWidget(self.stoich_input)

        s1.addWidget(QLabel("Miller Indices:"))
        self.miller_input = QLineEdit()
        self.miller_input.setPlaceholderText("001 100 110 104")
        s1.addWidget(self.miller_input)

        s1.addWidget(QLabel("Max Candidates:"))
        self.max_candidates_input = QLineEdit("30")
        s1.addWidget(self.max_candidates_input)

        self.retrieve_btn = QPushButton("Start Retrieval")
        self.retrieve_btn.clicked.connect(self._on_retrieve)
        self.retrieve_btn.setStyleSheet(
            "QPushButton { background-color: #0f3460; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; font-size: 13px; }"
            "QPushButton:disabled { background-color: #999; }"
        )
        s1.addWidget(self.retrieve_btn)
        layout.addWidget(step1)

        # Step 2
        step2 = QGroupBox("Step 2: Candidates")
        s2 = QVBoxLayout(step2)
        self.candidate_status = QLabel("No candidates loaded")
        self.candidate_status.setWordWrap(True)
        s2.addWidget(self.candidate_status)
        layout.addWidget(step2)

        # Step 3
        step3 = QGroupBox("Step 3: Simulation")
        s3 = QVBoxLayout(step3)
        self.simulate_btn = QPushButton("Start Simulation")
        self.simulate_btn.clicked.connect(self.simulate_clicked.emit)
        self.simulate_btn.setEnabled(False)
        self.simulate_btn.setStyleSheet(
            "QPushButton { background-color: #e94560; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; font-size: 13px; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        s3.addWidget(self.simulate_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_clicked.emit)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setVisible(False)
        s3.addWidget(self.cancel_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        s3.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        s3.addWidget(self.progress_label)
        layout.addWidget(step3)

        # Step 4
        step4 = QGroupBox("Step 4: Compare")
        s4 = QVBoxLayout(step4)
        up_btn = QPushButton("Upload Experiment Image")
        up_btn.clicked.connect(self._on_upload_experimental)
        s4.addWidget(up_btn)
        self.exp_image_label = QLabel("No image loaded")
        self.exp_image_label.setWordWrap(True)
        s4.addWidget(self.exp_image_label)
        layout.addWidget(step4)

        layout.addStretch()

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
                "Formula: V2O5\n"
                "Elements: V, O\n"
                "Stoichiometry: V:2 O:5"
            )

    def _do_retrieve(self):
        formula = self.formula_input.text().strip()
        elements_text = self.elements_input.text().strip()

        if not formula and not elements_text:
            return

        params = {}

        if formula:
            params["formula"] = formula
        else:
            elements = parse_elements(elements_text)
            if not elements:
                return
            params["elements"] = elements

        stoich_text = self.stoich_input.text().strip()
        if stoich_text and not formula:
            params["stoichiometry"] = parse_stoichiometry(stoich_text)

        miller_text = self.miller_input.text().strip()
        if miller_text:
            params["miller_indices"] = parse_miller(miller_text)

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
        plural = "s" if count != 1 else ""
        self.candidate_status.setText(f"Found {count} candidate{plural}")
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
        self.simulate_btn.setVisible(not active)
        self.cancel_btn.setEnabled(active)
        self.cancel_btn.setVisible(active)
        self.simulate_btn.setText("Simulating..." if active else "Start Simulation")
        if not active:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
