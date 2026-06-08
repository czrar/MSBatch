"""Tests for Stage 4: HTML reporter module."""
import numpy as np
from PIL import Image

from src.reporter import Reporter


def make_test_data(tmp_path):
    """Create a minimal candidates_json and sim_manifest with one test image."""
    img = np.random.default_rng(42).integers(0, 255, (32, 32)).astype(np.uint8)
    sim_dir = tmp_path / "sim_images" / "mp-cu_Cu"
    sim_dir.mkdir(parents=True)
    img_path = sim_dir / "mp-cu_001_HAADF.png"
    Image.fromarray(img).save(str(img_path))

    candidates = {
        "query": {"elements": ["Cu"], "timestamp": "2026-06-08T14:00:00"},
        "candidates": [{
            "rank": 1,
            "material_id": "mp-cu",
            "formula_pretty": "Cu",
            "formation_energy_per_atom": -1.0,
            "energy_above_hull": 0.0,
            "band_gap": 0.0,
            "space_group": "Fm-3m",
            "crystal_system": "cubic",
            "n_sites": 1,
        }],
    }
    sim_manifest = {"simulations": [{
        "material_id": "mp-cu",
        "miller_index": [0, 0, 1],
        "image_path": str(img_path),
    }]}
    return candidates, sim_manifest


def test_generate_html(tmp_path):
    """Report contains key content: elements, material id, DOCTYPE."""
    candidates, sim_manifest = make_test_data(tmp_path)
    reporter = Reporter()
    out = tmp_path / "report.html"

    result = reporter.generate(candidates, sim_manifest, out)
    html = out.read_text(encoding="utf-8")

    assert result == str(out)
    assert "<!DOCTYPE html>" in html
    assert "mp-cu" in html
    assert "Cu" in html


def test_report_embeds_images_as_base64(tmp_path):
    """Generated HTML contains base64-encoded PNG images."""
    candidates, sim_manifest = make_test_data(tmp_path)
    reporter = Reporter()
    out = tmp_path / "report.html"

    reporter.generate(candidates, sim_manifest, out)
    html = out.read_text(encoding="utf-8")

    assert "data:image/png;base64," in html


def test_handles_missing_image(tmp_path):
    """Candidate with no matching sim image still produces valid HTML."""
    candidates = {
        "query": {"elements": ["Au"], "timestamp": "2026-06-08T14:00:00"},
        "candidates": [{
            "rank": 1,
            "material_id": "mp-au",
            "formula_pretty": "Au",
            "formation_energy_per_atom": -1.0,
            "energy_above_hull": 0.0,
            "band_gap": 0.0,
            "space_group": "Fm-3m",
            "crystal_system": "cubic",
            "n_sites": 1,
        }],
    }
    sim_manifest = {"simulations": []}  # no matching images

    reporter = Reporter()
    out = tmp_path / "report_missing.html"

    reporter.generate(candidates, sim_manifest, out)
    html = out.read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in html
    assert "mp-au" in html
    assert "Au" in html
