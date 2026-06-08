"""Tests for STEMSimulator (Stage 3)."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from pymatgen.core.structure import Structure
from pymatgen.core.lattice import Lattice
from pymatgen.core.surface import SlabGenerator
from pymatgen.io.cif import CifWriter

from src.simulator import STEMSimulator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cu_slab_cif(output_dir: Path, mat_id: str = "mp-cu") -> Path:
    """Create a Cu (001) slab CIF file for testing."""
    cu_bulk = Structure.from_spacegroup(
        "Fm-3m", Lattice.cubic(3.615), ["Cu"], [[0, 0, 0]]
    )
    slab_gen = SlabGenerator(
        initial_structure=cu_bulk,
        miller_index=(0, 0, 1),
        min_slab_size=10.0,
        min_vacuum_size=10.0,
        lll_reduce=False,
        center_slab=True,
    )
    slabs = slab_gen.get_slabs()
    assert slabs, "SlabGenerator produced no slabs"
    slab = slabs[0]

    cif_dir = output_dir / f"{mat_id}_Cu"
    cif_dir.mkdir(parents=True, exist_ok=True)
    cif_path = cif_dir / f"{mat_id}_001.cif"
    CifWriter(slab).write_file(str(cif_path))
    return cif_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEngineDetection:
    """Verify the simulation engine is correctly detected."""

    def test_engine_detection(self):
        """abTEM 1.0.9 is installed in the msbatch environment."""
        sim = STEMSimulator()
        assert sim.engine == "abtem", (
            f"Expected engine 'abtem', got '{sim.engine}'. "
            "Is abTEM installed in the test environment?"
        )


class TestPlaceholderGeneration:
    """Verify placeholder image generation works."""

    def test_placeholder_image_generation(self, tmp_path):
        """Generate a placeholder PNG and check it is valid."""
        sim = STEMSimulator()
        out_path = tmp_path / "placeholder_HAADF.png"
        sim._run_placeholder(str(out_path), sim.config)

        assert out_path.exists(), "Placeholder image was not created"

        img = Image.open(out_path)
        arr = np.array(img)
        assert arr.shape == (256, 256), (
            f"Expected (256, 256), got {arr.shape}"
        )
        assert arr.dtype == np.uint8, (
            f"Expected uint8, got {arr.dtype}"
        )


class TestSimulateCreatesManifest:
    """Verify simulate() produces correct output manifest."""

    def test_simulate_creates_manifest(self, tmp_path):
        """Create a Cu slab CIF, run simulate, check output.

        Uses a minimal config (low gpts, few frozen phonon configs,
        coarse sampling) to keep the test reasonably fast.
        """
        cif_path = make_cu_slab_cif(tmp_path)
        assert cif_path.exists(), f"CIF was not created at {cif_path}"

        manifest = {
            "slabs": [
                {
                    "material_id": "mp-cu",
                    "formula_pretty": "Cu",
                    "miller_index": [0, 0, 1],
                    "cif_path": str(cif_path),
                }
            ]
        }

        output_dir = tmp_path / "output"
        # Lightweight config for fast test execution
        fast_config = {
            "gpts": 128,
            "frozen_phonon_configs": 2,
            "pixel_size_A": 0.5,
            "seed": 42,
        }
        sim = STEMSimulator(config=fast_config)
        result = sim.simulate(manifest, output_dir)

        # --- Check result manifest structure ---
        assert "simulations" in result, (
            "Result manifest missing 'simulations' key"
        )
        assert len(result["simulations"]) >= 1, (
            f"Expected >= 1 simulations, got {len(result['simulations'])}"
        )

        sim_entry = result["simulations"][0]
        assert sim_entry["material_id"] == "mp-cu"
        assert sim_entry["miller_index"] == [0, 0, 1]

        image_path = Path(sim_entry["image_path"])
        assert image_path.exists(), (
            f"Simulated image not found at {image_path}"
        )
        assert image_path.suffix == ".png"

        # --- Check the image is a valid PNG ---
        img = Image.open(image_path)
        arr = np.array(img)
        assert arr.ndim == 2, (
            f"Expected 2D image, got {arr.ndim}D"
        )
        assert arr.dtype == np.uint8

        # --- Check manifest JSON written to disk ---
        manifest_path = output_dir / "sim_images_manifest.json"
        assert manifest_path.exists()
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert loaded["simulations"][0]["material_id"] == "mp-cu"


class TestSimulateIgnoresMissingCIF:
    """Verify simulate() skips slabs with missing CIFs without crashing."""

    def test_simulate_skips_missing_cif(self, tmp_path):
        manifest = {
            "slabs": [
                {
                    "material_id": "mp-nonexistent",
                    "formula_pretty": "Xx",
                    "miller_index": [0, 0, 1],
                    "cif_path": str(tmp_path / "does_not_exist.cif"),
                }
            ]
        }

        output_dir = tmp_path / "output"
        sim = STEMSimulator()
        result = sim.simulate(manifest, output_dir)

        # Should produce an empty simulations list, not crash
        assert result["simulations"] == []
        manifest_path = output_dir / "sim_images_manifest.json"
        assert manifest_path.exists()


class TestNormalizeImage:
    """Verify image normalization helper."""

    def test_normalization(self):
        sim = STEMSimulator()
        raw = np.array([[0.0, 42.0], [100.0, 255.0]], dtype=np.float64)
        norm = sim._normalize_image(raw)
        assert norm.dtype == np.uint8
        assert norm.min() == 0
        assert norm.max() == 255

    def test_normalization_constant_image(self):
        """All-same-value image should not divide by zero."""
        sim = STEMSimulator()
        raw = np.ones((10, 10), dtype=np.float64) * 7.0
        norm = sim._normalize_image(raw)
        assert norm.dtype == np.uint8
        # Should return all zeros (since min == max)
        assert norm.min() == 0
        assert norm.max() == 0
