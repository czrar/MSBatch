"""QThread workers for background pipeline tasks."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import QThread, pyqtSignal

from src.retriever import MPRetriever
from src.cod_retriever import CODRetriever
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from config.defaults import SIM_CONFIG


class RetrieveWorker(QThread):
    """Background retrieval from MP, COD, or both."""

    candidates_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, elements=None, formula=None, stoichiometry=None,
                 max_candidates=50, database="MP", parent=None):
        super().__init__(parent)
        self.elements = elements
        self.formula = formula
        self.stoichiometry = stoichiometry
        self.max_candidates = max_candidates
        self.database = database  # "MP", "COD", or "Both"

    def run(self):
        try:
            results = []
            if self.database in ("MP", "Both"):
                r = MPRetriever()
                if self.formula:
                    result = r.retrieve_formula(self.formula, max_candidates=self.max_candidates)
                else:
                    result = r.retrieve_elements(
                        self.elements, stoichiometry=self.stoichiometry,
                        max_candidates=self.max_candidates
                    )
                results.append(result)

            if self.database in ("COD", "Both"):
                r = CODRetriever()
                if self.formula:
                    result = r.retrieve_formula(self.formula, max_candidates=self.max_candidates)
                else:
                    result = r.retrieve_elements(
                        self.elements, stoichiometry=self.stoichiometry,
                        max_candidates=self.max_candidates
                    )
                results.append(result)

            if len(results) == 1:
                self.candidates_ready.emit(results[0])
            elif len(results) == 2:
                merged = self._merge_results(results[0], results[1])
                self.candidates_ready.emit(merged)
            else:
                self.candidates_ready.emit({"candidates": []})
        except Exception as e:
            self.error_occurred.emit(str(e))

    @staticmethod
    def _merge_results(a: dict, b: dict) -> dict:
        """Merge two candidate result dicts, interleaving rankings."""
        cands_a = a.get("candidates", [])
        cands_b = b.get("candidates", [])
        # Interleave: alternate MP and COD candidates so both are visible
        merged_cands = []
        max_len = max(len(cands_a), len(cands_b))
        for i in range(max_len):
            if i < len(cands_a):
                cands_a[i]["rank"] = len(merged_cands) + 1
                merged_cands.append(cands_a[i])
            if i < len(cands_b):
                cands_b[i]["rank"] = len(merged_cands) + 1
                merged_cands.append(cands_b[i])

        return {
            "query": {
                "formula": a.get("query", {}).get("formula") or b.get("query", {}).get("formula"),
                "elements": a.get("query", {}).get("elements") or b.get("query", {}).get("elements"),
                "database": "MP + COD",
                "timestamp": a.get("query", {}).get("timestamp", ""),
            },
            "candidates": merged_cands,
        }


class SlabWorker(QThread):
    """Background slab generation."""
    slabs_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, candidates, miller_indices=None, max_rank=20,
                 max_terminations=5, output_dir=None, parent=None):
        super().__init__(parent)
        self.candidates = candidates
        self.miller_indices = miller_indices
        self.max_rank = max_rank
        self.max_terminations = max_terminations
        self.output_dir = output_dir or "data/output"

    def run(self):
        try:
            builder = SlabBuilder()
            manifest = builder.build(
                self.candidates, user_indices=self.miller_indices,
                max_rank=self.max_rank, max_terminations=self.max_terminations,
                output_dir=Path(self.output_dir)
            )
            self.slabs_ready.emit(manifest)
        except Exception as e:
            self.error_occurred.emit(str(e))


class FastProjectWorker(QThread):
    """Background fast Z² projection for instant preview."""
    progress_update = pyqtSignal(str, int, int)
    projections_done = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, slab_manifest, output_dir=None, config=None, parent=None):
        super().__init__(parent)
        self.slab_manifest = slab_manifest
        self.output_dir = output_dir or "data/output"
        self.config = config or SIM_CONFIG

    def run(self):
        try:
            total = len(self.slab_manifest["slabs"])
            self.progress_update.emit("Fast projection...", 0, total)

            sim = STEMSimulator(self.config)
            result = sim.simulate_fast(self.slab_manifest, Path(self.output_dir))
            self.projections_done.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SimulateWorker(QThread):
    """Background STEM simulation with progress."""
    progress_update = pyqtSignal(str, int, int)  # message, current, total
    simulation_done = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, slab_manifest, output_dir=None, config=None,
                 slab_indices=None, parent=None):
        super().__init__(parent)
        self.slab_manifest = slab_manifest
        self.output_dir = output_dir or "data/output"
        self.config = config or SIM_CONFIG
        self.slab_indices = slab_indices  # None = all, or list of int indices

    def run(self):
        try:
            slabs = self.slab_manifest["slabs"]
            if self.slab_indices is not None:
                slabs = [slabs[i] for i in self.slab_indices if i < len(slabs)]
            total = len(slabs)
            self.progress_update.emit("Starting simulation...", 0, total)

            sim = STEMSimulator(self.config)
            results = []
            for i, slab in enumerate(slabs):
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
