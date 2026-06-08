"""Tests for GUI worker threads."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.worker import RetrieveWorker, SimulateWorker


def test_retrieve_worker_signals(qtbot):
    """检索 worker 完成后发送 candidates_ready 信号."""
    worker = RetrieveWorker(elements=["Cu"], max_candidates=5)
    with qtbot.waitSignal(worker.candidates_ready, timeout=30000) as blocker:
        worker.run()
    result = blocker.args[0]
    assert "candidates" in result
    assert "query" in result
    assert result["query"]["elements"] == ["Cu"]


def test_simulate_worker_progress(qtbot):
    """模拟 worker 发送进度信号."""
    from pymatgen.core.structure import Structure
    from pymatgen.core.lattice import Lattice
    from pymatgen.io.cif import CifWriter
    import tempfile

    cu = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.615), ["Cu"], [[0, 0, 0]])
    tmp = Path(tempfile.mkdtemp())
    slabs_dir = tmp / "slabs" / "mp-cu_Cu"
    slabs_dir.mkdir(parents=True)
    cif_path = slabs_dir / "mp-cu_001.cif"
    CifWriter(cu).write_file(str(cif_path))

    manifest = {"slabs": [{
        "material_id": "mp-cu", "formula_pretty": "Cu",
        "miller_index": [0, 0, 1], "cif_path": str(cif_path)
    }]}

    worker = SimulateWorker(manifest, tmp / "output")
    progress_values = []
    worker.progress_update.connect(lambda msg, cur, total: progress_values.append((cur, total)))

    with qtbot.waitSignal(worker.simulation_done, timeout=60000) as blocker:
        worker.run()

    result = blocker.args[0]
    assert "simulations" in result
    assert len(progress_values) > 0
    assert progress_values[-1] == (1, 1)
