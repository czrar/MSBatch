"""Candidate card list widget with 3D structure viewer."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QCheckBox, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView


class CandidateCard(QFrame):
    """Single candidate card with thumbnail and properties."""
    toggled = pyqtSignal(str, bool)
    thumbnail_clicked = pyqtSignal(str)

    def __init__(self, candidate, parent=None):
        super().__init__(parent)
        self.material_id = candidate["material_id"]
        self._candidate = candidate
        self._setup_ui(candidate)

    def _setup_ui(self, c):
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "CandidateCard { background: white; border-radius: 6px; "
            "border: 1px solid #ddd; margin: 4px 0; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 3D thumbnail
        thumb = QLabel("3D\nStructure")
        thumb.setFixedSize(80, 80)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            "QLabel { border: 1px solid #ccc; border-radius: 4px; "
            "background: #f9f9f9; color: #999; font-size: 10px; }"
        )
        thumb.mousePressEvent = lambda e: self.thumbnail_clicked.emit(self.material_id)
        layout.addWidget(thumb)

        # Info
        info_layout = QVBoxLayout()

        title = QLabel(f"{c['formula_pretty']}")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(title)

        mid = QLabel(f"{self.material_id}  |  #{c['rank']}")
        mid.setStyleSheet("font-size: 11px; color: #888;")
        info_layout.addWidget(mid)

        grid = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        fields = [
            ("space_group", "Space Group"),
            ("formation_energy_per_atom", "Formation Energy"),
            ("crystal_system", "Crystal System"),
            ("energy_above_hull", "Energy Above Hull"),
            ("band_gap", "Band Gap"),
            ("n_sites", "N Sites"),
        ]
        for i, (key, label) in enumerate(fields):
            val = c.get(key)
            text = f"{val:.3f}" if isinstance(val, float) else str(val or "?")
            target = left_col if i < 3 else right_col
            lbl = QLabel(f"{label}: <b>{text}</b>")
            lbl.setStyleSheet("font-size: 11px;")
            target.addWidget(lbl)

        grid.addLayout(left_col)
        grid.addLayout(right_col)
        info_layout.addLayout(grid)
        layout.addLayout(info_layout, 1)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.toggled.connect(
            lambda checked: self.toggled.emit(self.material_id, checked)
        )
        layout.addWidget(self.checkbox)

    def is_checked(self):
        return self.checkbox.isChecked()


class CandidateView(QWidget):
    """Scrollable list of candidate cards."""
    selection_changed = pyqtSignal()
    thumbnail_clicked = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(6)
        self.container_layout.addStretch()

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def populate(self, candidates_json):
        for card in self._cards.values():
            self.container_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for cand in candidates_json.get("candidates", []):
            card = CandidateCard(cand)
            card.toggled.connect(self._on_toggle)
            card.thumbnail_clicked.connect(
                lambda mid, sd=cand.get("structure_data"): self.thumbnail_clicked.emit(mid, sd)
            )
            self._cards[cand["material_id"]] = card
            self.container_layout.insertWidget(self.container_layout.count() - 1, card)

    def get_selected_ids(self):
        return [mid for mid, card in self._cards.items() if card.is_checked()]

    def get_checked_count(self):
        return len(self.get_selected_ids())

    def _on_toggle(self, material_id, checked):
        self.selection_changed.emit()


class StructureViewer(QWidget):
    """3D crystal structure viewer using py3Dmol + QWebEngineView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crystal Structure Viewer")
        self.resize(600, 500)
        layout = QVBoxLayout(self)
        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

    def load_structure(self, structure_data):
        from pymatgen.core.structure import Structure
        struct = Structure.from_dict(structure_data)
        cif_str = struct.to(fmt="cif")

        html = f"""<!DOCTYPE html>
<html><head>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<style>body{{margin:0}}#viewer{{width:100%;height:100vh}}</style>
</head><body>
<div id="viewer"></div>
<script>
let viewer = $3Dmol.createViewer("viewer", {{defaultcolors: $3Dmol.elementColors.Jmol}});
viewer.addModel(`{cif_str}`, "cif");
viewer.setStyle({{stick:{{}}, sphere:{{radius:0.3}}}});
viewer.zoomTo();
viewer.render();
</script></body></html>"""
        self.webview.setHtml(html, QUrl("about:blank"))
