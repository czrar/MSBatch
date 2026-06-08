"""Tests for MPRetriever (Stage 1)."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from pymatgen.core.structure import Structure
from pymatgen.core.lattice import Lattice

from src.retriever import MPRetriever


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_licoo2_structure():
    """Build a minimal LiCoO2 R-3m structure."""
    lattice = Lattice.from_parameters(2.815, 2.815, 14.05, 90, 90, 120)
    struct = Structure(
        lattice,
        ["Li", "Co", "O", "O"],
        [
            [0.0, 0.0, 0.5],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.26],
            [0.0, 0.0, 0.74],
        ],
    )
    return struct


LICOO2_STRUCT = make_licoo2_structure()
LICOO2_STRUCT_DICT = LICOO2_STRUCT.as_dict()


def make_mock_doc(material_id, formula, energy_above_hull, structure_dict):
    """Create a MagicMock that mimics a Materials Summary doc."""
    doc = MagicMock()
    doc.material_id = material_id
    doc.formula_pretty = formula
    doc.formation_energy_per_atom = -1.85
    doc.energy_above_hull = energy_above_hull
    doc.band_gap = 3.2
    doc.space_group = "R-3m"
    doc.crystal_system = "trigonal"
    doc.nsites = 4
    doc.structure.as_dict.return_value = structure_dict
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDocsToCandidates:
    """Verify conversion of MPRester docs to candidate dicts."""

    def test_docs_to_candidates(self):
        doc1 = make_mock_doc("mp-1", "LiCoO2", 0.0, LICOO2_STRUCT_DICT)
        doc2 = make_mock_doc("mp-2", "LiCoO2", 0.05, LICOO2_STRUCT_DICT)
        doc_no_struct = MagicMock()
        doc_no_struct.structure = None

        candidates = MPRetriever._docs_to_candidates([doc1, doc2, doc_no_struct])

        assert len(candidates) == 2  # None-structure doc skipped
        cand = candidates[0]
        assert cand["material_id"] == "mp-1"
        assert cand["formula_pretty"] == "LiCoO2"
        assert cand["formation_energy_per_atom"] == -1.85
        assert cand["energy_above_hull"] == 0.0
        assert cand["band_gap"] == 3.2
        assert cand["space_group"] == "R-3m"
        assert cand["crystal_system"] == "trigonal"
        assert cand["n_sites"] == 4
        assert cand["structure_data"] == LICOO2_STRUCT_DICT

    def test_candidates_not_deduplicated(self):
        """Two candidates with same formula but different mp-id are both kept."""
        doc_a = make_mock_doc("mp-111", "LiCoO2", 0.0, LICOO2_STRUCT_DICT)
        doc_b = make_mock_doc("mp-222", "LiCoO2", 0.1, LICOO2_STRUCT_DICT)

        candidates = MPRetriever._docs_to_candidates([doc_a, doc_b])

        assert len(candidates) == 2
        ids = {c["material_id"] for c in candidates}
        assert ids == {"mp-111", "mp-222"}


class TestStoichiometryFilter:
    """Verify stoichiometric ratio filtering."""

    def test_stoichiometry_filter_passes(self):
        """LiCoO2 should pass Co 0.15-0.35, O 0.50-0.75."""
        cand = {
            "material_id": "mp-1",
            "structure_data": LICOO2_STRUCT_DICT,
        }
        stoichiometry = {"Co": (0.15, 0.35), "O": (0.50, 0.75)}

        kept = MPRetriever._filter_stoichiometry([cand], stoichiometry)

        assert len(kept) == 1
        assert kept[0]["material_id"] == "mp-1"

    def test_stoichiometry_filter_fails(self):
        """LiCoO2 should fail Co 0.5-0.6 (actual Co ratio is 0.25)."""
        cand = {
            "material_id": "mp-1",
            "structure_data": LICOO2_STRUCT_DICT,
        }
        stoichiometry = {"Co": (0.5, 0.6)}

        kept = MPRetriever._filter_stoichiometry([cand], stoichiometry)

        assert len(kept) == 0


class TestSaveAndLoad:
    """Verify JSON round-trip for save/load."""

    def test_save_and_load(self, tmp_path):
        result = {
            "query": {
                "elements": ["Li", "Co", "O"],
                "timestamp": "2026-06-08T00:00:00",
            },
            "candidates": [
                {
                    "rank": 1,
                    "material_id": "mp-1",
                    "formula_pretty": "LiCoO2",
                    "structure_data": LICOO2_STRUCT_DICT,
                }
            ],
        }

        out_path = MPRetriever.save(result, tmp_path)
        loaded = MPRetriever.load(out_path)

        assert loaded["query"]["elements"] == ["Li", "Co", "O"]
        assert loaded["candidates"][0]["material_id"] == "mp-1"
        # Reconstruct Structures to avoid numpy-vs-float type mismatches
        # from JSON round-trip (np.float64 -> float).
        loaded_struct = Structure.from_dict(loaded["candidates"][0]["structure_data"])
        assert loaded_struct == LICOO2_STRUCT
        assert loaded["candidates"][0]["rank"] == 1
