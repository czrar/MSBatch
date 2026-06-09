"""QThread workers for background pipeline tasks."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import QThread, pyqtSignal

from src.retriever import MPRetriever
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from config.defaults import SIM_CONFIG


class RetrieveWorker(QThread):
    """Background MP retrieval."""
    candidates_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, elements=None, formula=None, stoichiometry=None,
                 max_candidates=50, parent=None):
        super().__init__(parent)
        self.elements = elements
        self.formula = formula
        self.stoichiometry = stoichiometry
        self.max_candidates = max_candidates

    def run(self):
        try:
            r = MPRetriever()
            if self.formula:
                result = r.retrieve_formula(self.formula, max_candidates=self.max_candidates)
            else:
                result = r.retrieve_elements(
                    self.elements, stoichiometry=self.stoichiometry,
                    max_candidates=self.max_candidates
                )
            self.candidates_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SlabWorker(QThread):
    """Background slab generation."""
    slabs_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, candidates, miller_indices=None, max_rank=20,
                 output_dir=None, parent=None):
        super().__init__(parent)
        self.candidates = candidates
        self.miller_indices = miller_indices
        self.max_rank = max_rank
        self.output_dir = output_dir or "data/output"

    def run(self):
        try:
            builder = SlabBuilder()
            manifest = builder.build(
                self.candidates, user_indices=self.miller_indices,
                max_rank=self.max_rank, output_dir=Path(self.output_dir)
            )
            self.slabs_ready.emit(manifest)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SimulateWorker(QThread):
    """Background STEM simulation with progress."""
    progress_update = pyqtSignal(str, int, int)  # message, current, total
    simulation_done = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, slab_manifest, output_dir=None, config=None, parent=None):
        super().__init__(parent)
        self.slab_manifest = slab_manifest
        self.output_dir = output_dir or "data/output"
        self.config = config or SIM_CONFIG

    def run(self):
        try:
            total = len(self.slab_manifest["slabs"])
            self.progress_update.emit("Starting simulation...", 0, total)

            sim = STEMSimulator(self.config)
            results = []
            for i, slab in enumerate(self.slab_manifest["slabs"]):
                if self.isInterruptionRequested():
                    break

                mid = slab["material_id"]
                hkl = "".join(str(x) for x in slab["miller_index"])
                self.progress_update.emit(f"Simulating {mid} ({hkl})  [{i+1}/{total}]", i + 1, total)

                single_manifest = {"slabs": [slab]}
                single_result = sim.simulate(single_manifest, Path(self.output_dir))
                results.extend(single_result["simulations"])

            manifest = {"simulations": results}
            self.simulation_done.emit(manifest)
        except Exception as e:
            self.error_occurred.emit(str(e))
