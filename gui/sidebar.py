"""Left sidebar with step-by-step parameter controls."""
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QGroupBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal


def parse_elements(text: str) -> list[str]:
    """解析元素输入: 'Li,Co,O' / 'Li Co O' / 'Li，Co，O' / 'Li.Co.O'"""
    tokens = re.split(r'[,，;；、\s.]+', text.strip())
    return [t for t in tokens if t]


def parse_stoichiometry(text: str) -> dict[str, tuple[float, float]]:
    """解析化学计量比输入。

    支持:
      'Co:0.8-1.2, O:1.8-2.2'  — 范围
      'V:2  O:5'                — 固定值（自动 ±15% 容差）
      'Co:0.8-1.2;O:1.8-2.2'   — 分号分隔
      'V：2.5'                  — 中文冒号
    """
    result = {}
    # 用正则匹配每个 "元素:数值范围" 片段
    # 元素名: 1-2个字母，首字母大写
    # 值: 数字.数字-数字.数字 或 数字
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
            result[el] = (min(lo, hi), max(lo, hi))
        else:
            result[el] = (lo * 0.85, lo * 1.15)

    if not result:
        raise ValueError(
            f"Cannot parse stoichiometry: '{text}'\n"
            f"Expected format like 'Co:0.8-1.2, O:1.8-2.2' (range)\n"
            f"or 'V:2 O:5' (fixed values)"
        )

    return result


def parse_miller(text: str) -> list[tuple[int, ...]]:
    """解析晶面输入。

    支持:
      '001,100,110'     — 逗号分隔
      '001 100 110'     — 空格分隔
      '104'             — 单个
      '(104)'           — 带括号
      '001，104'        — 中文逗号
    """
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
                "Examples:\n"
                "  Elements: Li,Co,O\n"
                "  Stoichiometry: Co:0.8-1.2  O:1.8-2.2   (or V:2 O:5 for fixed)\n"
                "  Miller: 001 100 110 104"
            )

    def _do_retrieve(self):
        # --- Elements ---
        elements = parse_elements(self.elements_input.text())
        if not elements:
            return
        params = {"elements": elements}

        # --- Stoichiometry ---
        stoich_text = self.stoich_input.text().strip()
        if stoich_text:
            params["stoichiometry"] = parse_stoichiometry(stoich_text)

        # --- Miller indices ---
        miller_text = self.miller_input.text().strip()
        if miller_text:
            params["miller_indices"] = parse_miller(miller_text)

        # --- Max candidates ---
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
