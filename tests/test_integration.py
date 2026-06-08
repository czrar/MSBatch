"""End-to-end pipeline integration test."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymatgen.core.structure import Structure
from pymatgen.core.lattice import Lattice
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from src.reporter import Reporter
from config.defaults import SIM_CONFIG


def make_placeholder_simulator():
    """Create a STEMSimulator forced to use the placeholder engine.

    Integration tests must not depend on abTEM or network access.
    """
    sim = STEMSimulator(SIM_CONFIG)
    sim._engine = "placeholder"
    return sim


def make_test_candidates():
    """Build test candidates with a Cu FCC structure."""
    cu = Structure.from_spacegroup(
        "Fm-3m", Lattice.cubic(3.615), ["Cu"], [[0, 0, 0]]
    )
    return {
        "query": {
            "elements": ["Cu"],
            "timestamp": "2026-01-01T00:00:00",
            "stoichiometry": None,
        },
        "candidates": [
            {
                "rank": 1,
                "material_id": "mp-cu-test",
                "formula_pretty": "Cu",
                "formation_energy_per_atom": -1.0,
                "energy_above_hull": 0.0,
                "band_gap": 0.0,
                "space_group": "Fm-3m",
                "crystal_system": "cubic",
                "n_sites": 1,
                "structure_data": cu.as_dict(),
            }
        ],
    }


def test_full_pipeline(tmp_path):
    """Run all 4 stages end-to-end with a Cu FCC structure."""
    # Stage 1: Candidates (pre-built, no MP API)
    candidates = make_test_candidates()
    (tmp_path / "candidates.json").write_text(json.dumps(candidates, indent=2))
    assert len(candidates["candidates"]) == 1
    assert candidates["candidates"][0]["material_id"] == "mp-cu-test"

    # Stage 2: Slab generation
    slabber = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    slab_manifest = slabber.build(
        candidates, miller_indices=[(0, 0, 1), (1, 1, 1)], output_dir=tmp_path
    )
    assert len(slab_manifest["slabs"]) >= 1
    for s in slab_manifest["slabs"]:
        assert Path(s["cif_path"]).exists()
        assert "material_id" in s
        assert "miller_index" in s

    # Stage 3: Simulation (may use abTEM or placeholder)
    simulator = make_placeholder_simulator()
    sim_manifest = simulator.simulate(slab_manifest, tmp_path)
    assert len(sim_manifest["simulations"]) >= 1
    for s in sim_manifest["simulations"]:
        assert Path(s["image_path"]).exists()
        assert s["image_path"].endswith(".png")

    # Stage 4: Report generation
    reporter = Reporter()
    report_path = reporter.generate(candidates, sim_manifest, tmp_path / "report.html")
    html = Path(report_path).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "mp-cu-test" in html
    assert "Cu" in html
    # Self-contained report
    assert "data:image/png;base64," in html


def test_manifest_chain_consistency(tmp_path):
    """Verify manifest handoff consistency between stages."""
    candidates = make_test_candidates()
    slabber = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    slab_manifest = slabber.build(
        candidates, miller_indices=[(0, 0, 1)], output_dir=tmp_path
    )
    simulator = make_placeholder_simulator()
    sim_manifest = simulator.simulate(slab_manifest, tmp_path)

    # Every sim should reference a slab that exists in the slab manifest
    slab_ids = {(s["material_id"], tuple(s["miller_index"]))
                for s in slab_manifest["slabs"]}
    for sim in sim_manifest["simulations"]:
        key = (sim["material_id"], tuple(sim["miller_index"]))
        assert key in slab_ids, f"Sim {key} has no matching slab"


def test_pipeline_handles_empty_candidates(tmp_path):
    """Pipeline should produce valid output even with zero candidates."""
    empty = {"query": {"elements": ["Xx"]}, "candidates": []}
    slabber = SlabBuilder()
    slab_manifest = slabber.build(empty, output_dir=tmp_path)
    assert slab_manifest["slabs"] == []

    simulator = make_placeholder_simulator()
    sim_manifest = simulator.simulate(slab_manifest, tmp_path)
    assert sim_manifest["simulations"] == []

    reporter = Reporter()
    report_path = reporter.generate(empty, sim_manifest, tmp_path / "report.html")
    html = Path(report_path).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
