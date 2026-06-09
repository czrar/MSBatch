"""Candidate card list widget with 3D structure viewer."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QCheckBox, QFrame, QDialog, QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView


class CandidateCard(QFrame):
    """Single candidate card with info thumbnail and properties."""
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
            "border: 1px solid #ddd; margin: 3px 0; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Thumbnail: space group + crystal system
        thumb = QFrame()
        thumb.setFixedSize(90, 90)
        thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        thumb.setStyleSheet(
            "QFrame { border: 1px solid #ccc; border-radius: 4px; "
            "background: #f0f4ff; }"
            "QFrame:hover { border-color: #4a90d9; background: #e8f0ff; }"
        )
        thumb_layout = QVBoxLayout(thumb)
        thumb_layout.setContentsMargins(4, 4, 4, 4)
        thumb_layout.setSpacing(2)

        sg = c.get("space_group") or "?"
        cs = c.get("crystal_system") or "?"
        sg_label = QLabel(sg)
        sg_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a1a2e; border: none; background: none;")
        sg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sg_label.setWordWrap(True)
        thumb_layout.addWidget(sg_label)

        cs_label = QLabel(cs)
        cs_label.setStyleSheet("font-size: 10px; color: #666; border: none; background: none;")
        cs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_layout.addWidget(cs_label)

        view_label = QLabel("(click to view 3D)")
        view_label.setStyleSheet("font-size: 8px; color: #aaa; border: none; background: none;")
        view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_layout.addWidget(view_label)

        thumb.mousePressEvent = lambda e: self.thumbnail_clicked.emit(self.material_id)
        layout.addWidget(thumb)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = QLabel(f"{c['formula_pretty']}")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        info_layout.addWidget(title)

        mid = QLabel(f"{self.material_id}  |  #{c['rank']}")
        mid.setStyleSheet("font-size: 11px; color: #888;")
        info_layout.addWidget(mid)

        grid = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        left_col.setSpacing(1)
        right_col.setSpacing(1)

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
            if isinstance(val, float):
                text = f"{val:.3f}"
            elif val is not None:
                text = str(val)
            else:
                text = "—"
            target = left_col if i < 3 else right_col
            lbl = QLabel(f"{label}:  <b>{text}</b>")
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
        self.container_layout.setSpacing(4)
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
                lambda mid, sd=cand.get("structure_data"):
                    self.thumbnail_clicked.emit(mid, sd)
            )
            self._cards[cand["material_id"]] = card
            self.container_layout.insertWidget(self.container_layout.count() - 1, card)

    def get_selected_ids(self):
        return [mid for mid, card in self._cards.items() if card.is_checked()]

    def get_checked_count(self):
        return len(self.get_selected_ids())

    def _on_toggle(self, material_id, checked):
        self.selection_changed.emit()


class StructureViewer(QDialog):
    """Modal 3D crystal structure viewer."""

    def __init__(self, material_id, structure_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Crystal Structure — {material_id}")
        self.resize(700, 550)
        self.setModal(False)  # 非模态，但不挡主界面

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        self._render(structure_data)

    def _render(self, structure_data):
        from pymatgen.core.structure import Structure
        struct = Structure.from_dict(structure_data)
        cif_str = struct.to(fmt="cif")

        html = f"""<!DOCTYPE html>
<html><head>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<style>body{{margin:0;background:#fff}}#v{{width:100%;height:100vh}}</style>
</head><body>
<div id="v"></div>
<script>
let viewer = $3Dmol.createViewer("v", {{defaultcolors: $3Dmol.elementColors.Jmol,
  backgroundColor: "white"}});
viewer.addModel(`{cif_str}`, "cif");
viewer.setStyle({{stick:{{radius:0.12}}, sphere:{{radius:0.4, scale:1.0}}}});
viewer.zoomTo();
viewer.render();
</script></body></html>"""
        self.webview.setHtml(html, QUrl("about:blank"))
