"""Tests for SlabBuilder (Stage 2)."""
import json
from pathlib import Path

import pytest
from pymatgen.core.structure import Structure
from pymatgen.core.lattice import Lattice

from src.slabber import SlabBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cu_structure():
    """Build a Cu FCC structure (Fm-3m, a=3.615 A)."""
    return Structure.from_spacegroup(
        "Fm-3m", Lattice.cubic(3.615), ["Cu"], [[0, 0, 0]]
    )


CU_STRUCT = make_cu_structure()
CU_STRUCT_DICT = CU_STRUCT.as_dict()


def make_candidate(material_id, formula, rank, structure_dict, e_above_hull=0.0):
    """Create a candidate dict matching the retriever output format."""
    return {
        "rank": rank,
        "material_id": material_id,
        "formula_pretty": formula,
        "energy_above_hull": e_above_hull,
        "space_group": "Fm-3m",
        "structure_data": structure_dict,
    }


def make_candidates_json(candidates):
    """Wrap a list of candidate dicts in the expected JSON structure."""
    return {
        "query": {"elements": ["Cu"]},
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildSlabsBasic:
    """Verify basic slab generation for a single Cu (001) face."""

    def test_build_slabs_basic(self, tmp_path):
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            output_dir=tmp_path,
        )

        assert len(manifest["slabs"]) == 1
        slab = manifest["slabs"][0]
        assert slab["material_id"] == "mp-cu"
        assert slab["formula_pretty"] == "Cu"
        assert slab["miller_index"] == [0, 0, 1]
        # Cu a=3.615 Å, min_xy_size=20 → supercell expands to meet ≥20 Å
        assert isinstance(slab["supercell"], list)
        assert len(slab["supercell"]) == 3
        assert slab["supercell"][0] >= 1
        assert slab["supercell"][1] >= 1
        assert slab["supercell"][2] == 1

        # Verify CIF file exists on disk
        cif_path = Path(slab["cif_path"])
        assert cif_path.exists()
        assert cif_path.suffix == ".cif"

        # Verify required keys are all present
        required = [
            "material_id", "miller_index", "cif_path",
            "slab_thickness_A", "vacuum_A", "supercell"
        ]
        for key in required:
            assert key in slab, f"Missing key: {key}"

        # Verify manifest.json was written
        manifest_path = tmp_path / "slabs_manifest.json"
        assert manifest_path.exists()


class TestBuildMultipleFaces:
    """Verify multiple non-equivalent faces produce multiple slabs."""

    def test_build_multiple_faces(self, tmp_path):
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        # (001) and (110) are not symmetry-equivalent in cubic
        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1), (1, 1, 0)],
            deduplicate_symmetrically=True,
            output_dir=tmp_path,
        )

        assert len(manifest["slabs"]) == 2
        faces = sorted([tuple(s["miller_index"]) for s in manifest["slabs"]])
        assert faces == [(0, 0, 1), (1, 1, 0)]


class TestMaxRankLimits:
    """Verify max_rank limits which candidates are slabbed."""

    def test_max_rank_limits(self, tmp_path):
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
            make_candidate("mp-ag", "Ag", 2, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            max_rank=1,
            output_dir=tmp_path,
        )

        # Only the rank-1 candidate should be slabbed
        assert len(manifest["slabs"]) == 1
        assert manifest["slabs"][0]["material_id"] == "mp-cu"

        # Verify mp-ag directory was NOT created
        ag_dir = tmp_path / "slabs" / "mp-ag_Ag"
        assert not ag_dir.exists()


class TestSymmetryDedup:
    """Verify symmetry-equivalent faces are deduplicated."""

    def test_symmetry_dedup(self, tmp_path):
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        # (100), (010), (001) are all equivalent in cubic Fm-3m
        manifest = builder.build(
            candidates,
            miller_indices=[(1, 0, 0), (0, 1, 0), (0, 0, 1)],
            deduplicate_symmetrically=True,
            output_dir=tmp_path,
        )

        # Should yield only 1 slab after deduplication
        assert len(manifest["slabs"]) == 1

    def test_no_dedup_when_disabled(self, tmp_path):
        """With deduplicate_symmetrically=False, all indices should be kept."""
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(1, 0, 0), (0, 1, 0), (0, 0, 1)],
            deduplicate_symmetrically=False,
            output_dir=tmp_path,
        )

        assert len(manifest["slabs"]) == 3


class TestSlabManifestStructure:
    """Verify manifest entries have all required keys with correct types."""

    def test_slab_manifest_structure(self, tmp_path):
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            output_dir=tmp_path,
        )

        slab = manifest["slabs"][0]

        assert isinstance(slab["material_id"], str)
        assert isinstance(slab["miller_index"], list)
        assert len(slab["miller_index"]) == 3
        assert isinstance(slab["cif_path"], str)
        assert isinstance(slab["slab_thickness_A"], (int, float))
        assert slab["slab_thickness_A"] > 0
        assert isinstance(slab["vacuum_A"], (int, float))
        assert slab["vacuum_A"] > 0
        assert isinstance(slab["supercell"], list)
        assert len(slab["supercell"]) == 3

    def test_manifest_json_roundtrip(self, tmp_path):
        """Verify the on-disk manifest.json can be loaded back."""
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            output_dir=tmp_path,
        )

        manifest_path = tmp_path / "slabs_manifest.json"
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert "slabs" in loaded
        assert len(loaded["slabs"]) == 1
        assert loaded["slabs"][0]["material_id"] == "mp-cu"


class TestUserIndicesReplaces:
    """Verify user_indices REPLACES default miller_indices, not appended."""

    def test_user_indices_replaces(self, tmp_path):
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        # default miller_indices includes (0,0,1), (1,0,0), (1,1,0), (1,1,1)
        # user provides only (1,1,1) — should NOT also get the defaults
        manifest = builder.build(
            candidates,
            miller_indices=None,
            user_indices=[(1, 1, 1)],
            deduplicate_symmetrically=False,
            output_dir=tmp_path,
        )

        assert len(manifest["slabs"]) == 1
        assert manifest["slabs"][0]["miller_index"] == [1, 1, 1]

    def test_user_indices_replaces_all_defaults(self, tmp_path):
        """Even when user provides many indices, defaults are NOT merged."""
        builder = SlabBuilder(min_slab_thickness=10.0, min_vacuum=10.0)
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=None,
            user_indices=[(0, 0, 1), (1, 1, 0)],
            deduplicate_symmetrically=False,
            output_dir=tmp_path,
        )

        # With dedup on, (0,0,1) and (1,1,0) are not equivalent in cubic
        # Wait, in Fm-3m, (001) and (110) are NOT symmetry-equivalent.
        # So we should get 2 slabs from user_indices, not 2+4=6
        assert len(manifest["slabs"]) == 2
        faces = sorted([tuple(s["miller_index"]) for s in manifest["slabs"]])
        assert faces == [(0, 0, 1), (1, 1, 0)]


class TestSupercellXYExpansion:
    """Verify xy supercell expands to meet min_xy_size."""

    def test_supercell_expansion_small_cell(self, tmp_path):
        """Cu cell is 3.615 A → with min_xy_size=20, need 6x6 supercell."""
        builder = SlabBuilder(
            min_slab_thickness=10.0, min_vacuum=10.0, min_xy_size=20.0
        )
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            output_dir=tmp_path,
        )

        slab = manifest["slabs"][0]
        assert slab["supercell"][0] >= 6
        assert slab["supercell"][1] >= 6
        assert slab["supercell"][2] == 1

    def test_supercell_expansion_large_min_xy(self, tmp_path):
        """Larger min_xy_size → larger supercell."""
        builder = SlabBuilder(
            min_slab_thickness=10.0, min_vacuum=10.0, min_xy_size=40.0
        )
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            output_dir=tmp_path,
        )

        slab = manifest["slabs"][0]
        # Cu a=3.615, ceil(40/3.615)=12
        assert slab["supercell"][0] >= 12
        assert slab["supercell"][1] >= 12

    def test_supercell_always_at_least_one(self, tmp_path):
        """When min_xy_size is small, supercell should be at least [1,1,1]."""
        builder = SlabBuilder(
            min_slab_thickness=10.0, min_vacuum=10.0, min_xy_size=1.0
        )
        candidates = make_candidates_json([
            make_candidate("mp-cu", "Cu", 1, CU_STRUCT_DICT),
        ])

        manifest = builder.build(
            candidates,
            miller_indices=[(0, 0, 1)],
            output_dir=tmp_path,
        )

        slab = manifest["slabs"][0]
        assert slab["supercell"][0] >= 1
        assert slab["supercell"][1] >= 1
        assert slab["supercell"][2] == 1
