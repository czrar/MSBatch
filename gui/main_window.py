"""Main window assembling sidebar and tabbed views."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTabWidget, QStatusBar, QApplication, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt

from gui.sidebar import Sidebar, parse_miller
from gui.candidate_view import CandidateView, StructureViewer
from gui.simulation_view import SimulationView
from gui.comparison_view import ComparisonView
from gui.dialogs import AdvancedSettingsDialog
from gui.worker import RetrieveWorker, SlabWorker, SimulateWorker
from src.reporter import Reporter


class MSBatchMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSBatch - STEM-HAADF Structure Identification")
        self.resize(1200, 750)
        self._candidates = None
        self._slab_manifest = None
        self._sim_manifest = None
        self._sim_config = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Right: tab widget
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget()
        self.candidate_view = CandidateView()
        self.simulation_view = SimulationView()
        self.comparison_view = ComparisonView()

        self.tabs.addTab(self.candidate_view, "Candidate Structures")
        self.tabs.addTab(self.simulation_view, "Simulated Images")
        self.tabs.addTab(self.comparison_view, "Comparison Report")

        right_layout.addWidget(self.tabs)
        main_layout.addWidget(right, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Enter elements and click Retrieve.")

    def _connect_signals(self):
        self.sidebar.retrieve_clicked.connect(self._on_retrieve)
        self.sidebar.simulate_clicked.connect(self._on_simulate)
        self.sidebar.cancel_clicked.connect(self._on_cancel)
        self.sidebar.advanced_clicked.connect(self._on_advanced_settings)
        self.sidebar.experiment_image_dropped.connect(
            self.comparison_view.set_experimental_image
        )
        self.candidate_view.thumbnail_clicked.connect(self._on_show_structure)
        self.candidate_view.selection_changed.connect(self._on_selection_changed)
        self.comparison_view.export_report_clicked.connect(self._on_export_report)

    def _on_retrieve(self, params):
        self.status_bar.showMessage("Retrieving from Materials Project...")
        self.sidebar.set_retrieving(True)
        self._candidates = None
        # 清空旧卡片，避免显示过期结果
        self.candidate_view.populate({"candidates": []})

        # 断开旧 worker（防止僵尸线程干扰）
        if hasattr(self, "_retrieve_worker") and self._retrieve_worker.isRunning():
            self._retrieve_worker.candidates_ready.disconnect()
            self._retrieve_worker.error_occurred.disconnect()

        self._retrieve_worker = RetrieveWorker(
            elements=params.get("elements"),
            formula=params.get("formula"),
            stoichiometry=params.get("stoichiometry"),
            max_candidates=params.get("max_candidates", 50)
        )
        self._retrieve_worker.candidates_ready.connect(self._on_candidates_ready)
        self._retrieve_worker.error_occurred.connect(self._on_error)
        self._retrieve_worker.start()

    def _on_candidates_ready(self, result):
        self._candidates = result
        self.candidate_view.populate(result)
        n = len(result.get("candidates", []))
        self.sidebar.set_candidate_count(n)
        self.sidebar.set_retrieving(False)
        self.status_bar.showMessage(f"Retrieved {n} candidates")
        self.tabs.setCurrentIndex(0)

    def _on_simulate(self):
        if not self._candidates:
            return

        selected_ids = set(self.candidate_view.get_selected_ids())
        selected = [c for c in self._candidates["candidates"]
                    if c["material_id"] in selected_ids]
        if not selected:
            QMessageBox.warning(self, "No Selection",
                                "Please select at least one candidate.")
            return

        self.sidebar.set_simulating(True)
        self.status_bar.showMessage("Generating slabs...")

        miller_text = self.sidebar.miller_input.text().strip()
        user_indices = None
        if miller_text:
            try:
                user_indices = parse_miller(miller_text)
            except ValueError:
                user_indices = None

        filtered = dict(self._candidates)
        filtered["candidates"] = selected

        self._slab_worker = SlabWorker(
            filtered, miller_indices=user_indices,
            output_dir="data/output"
        )
        self._slab_worker.slabs_ready.connect(self._on_slabs_ready)
        self._slab_worker.error_occurred.connect(self._on_error)
        self._slab_worker.start()

    def _on_slabs_ready(self, manifest):
        self._slab_manifest = manifest
        n = len(manifest["slabs"])
        self.status_bar.showMessage(f"Generated {n} slabs. Starting simulation...")

        self._sim_worker = SimulateWorker(
            manifest, output_dir="data/output",
            config=self._sim_config
        )
        self._sim_worker.progress_update.connect(self.sidebar.set_progress)
        self._sim_worker.simulation_done.connect(self._on_simulation_done)
        self._sim_worker.error_occurred.connect(self._on_error)
        self._sim_worker.start()

    def _on_simulation_done(self, manifest):
        self._sim_manifest = manifest
        self.simulation_view.populate(manifest)
        self.comparison_view.set_sim_images(manifest)
        self.sidebar.set_simulating(False)
        n = len(manifest.get("simulations", []))
        self.status_bar.showMessage(f"Completed {n} simulations")
        self.tabs.setCurrentIndex(1)

    def _on_advanced_settings(self):
        dialog = AdvancedSettingsDialog(current_config=self._sim_config, parent=self)
        if dialog.exec() == AdvancedSettingsDialog.DialogCode.Accepted:
            self._sim_config = dialog.get_config()
            self.status_bar.showMessage("Advanced settings saved", 3000)

    def _on_show_structure(self, material_id, structure_data):
        if not structure_data:
            return
        viewer = StructureViewer(material_id, structure_data, self)
        viewer.show()

    def _on_selection_changed(self):
        n = self.candidate_view.get_checked_count()
        total = len(self._candidates["candidates"]) if self._candidates else 0
        self.sidebar.candidate_status.setText(
            f"Found {total} candidates  |  {n} selected"
        )

    def _on_export_report(self):
        if not self._candidates or not self._sim_manifest:
            QMessageBox.warning(self, "No Data",
                                "Run retrieval and simulation first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "report.html",
            "HTML (*.html);;All Files (*)"
        )
        if path:
            r = Reporter()
            r.generate(self._candidates, self._sim_manifest, path,
                       experimental_image=self.comparison_view.experimental_path)
            self.status_bar.showMessage(f"Report saved to {path}", 5000)
            QMessageBox.information(self, "Done", f"Report saved:\n{path}")

    def _on_cancel(self):
        if hasattr(self, "_sim_worker") and self._sim_worker.isRunning():
            self._sim_worker.requestInterruption()
            self._sim_worker.quit()
            self._sim_worker.wait(3000)
        self.sidebar.set_simulating(False)
        self.status_bar.showMessage("Simulation cancelled")

    def _on_error(self, msg):
        self.sidebar.set_retrieving(False)
        self.sidebar.set_simulating(False)
        self.status_bar.showMessage(f"Error: {msg}")
        QMessageBox.critical(self, "Error", msg)
