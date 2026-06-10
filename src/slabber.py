"""Stage 2: Surface slab builder."""
import json
from pathlib import Path
from typing import Optional

import numpy as np
from pymatgen.core.structure import Structure
from pymatgen.core.surface import SlabGenerator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.io.cif import CifWriter

from config.defaults import (
    DEFAULT_MIN_SLAB_THICKNESS, DEFAULT_MIN_VACUUM,
    DEFAULT_MILLER_INDICES, DEFAULT_MAX_SLAB_RANK,
    DEFAULT_MIN_XY_SIZE,
)


class SlabBuilder:
    """Generate surface slab models for candidate structures."""

    def __init__(
        self,
        min_slab_thickness: float = DEFAULT_MIN_SLAB_THICKNESS,
        min_vacuum: float = DEFAULT_MIN_VACUUM,
        min_xy_size: float = DEFAULT_MIN_XY_SIZE,
    ):
        self.min_slab_thickness = min_slab_thickness
        self.min_vacuum = min_vacuum
        self.min_xy_size = min_xy_size

    def build(
        self,
        candidates_json: dict,
        miller_indices: Optional[list[tuple[int, int, int]]] = None,
        user_indices: Optional[list[tuple[int, int, int]]] = None,
        max_rank: int = DEFAULT_MAX_SLAB_RANK,
        deduplicate_symmetrically: bool = True,
        output_dir: str | Path = ".",
    ) -> dict:
        """Generate slabs and return manifest dict."""
        if miller_indices is None:
            miller_indices = list(DEFAULT_MILLER_INDICES)
        if user_indices:
            miller_indices = list(user_indices)

        output_dir = Path(output_dir)
        slabs_dir = output_dir / "slabs"
        slabs_dir.mkdir(parents=True, exist_ok=True)

        slabs = []
        candidates = candidates_json["candidates"]

        for cand in candidates:
            if cand["rank"] > max_rank:
                break

            structure = Structure.from_dict(cand["structure_data"])
            formula = cand["formula_pretty"]
            mat_id = cand["material_id"]

            subdir = slabs_dir / f"{mat_id}_{formula}"
            subdir.mkdir(parents=True, exist_ok=True)

            indices = self._get_unique_indices(
                structure, miller_indices, deduplicate_symmetrically
            )

            for hkl in indices:
                try:
                    slab_gen = SlabGenerator(
                        initial_structure=structure,
                        miller_index=hkl,
                        min_slab_size=self.min_slab_thickness,
                        min_vacuum_size=self.min_vacuum,
                        lll_reduce=False,
                        center_slab=True,
                    )
                    # get_slab() returns first termination (fast).
                    # get_slabs() enumerates ALL possible terminations (slow).
                    slab = slab_gen.get_slab()
                    if slab is None:
                        print(f"  [WARN] No slab for {mat_id} {hkl}")
                        continue

                    # 扩展xy超胞使视场 ≥ min_xy_size
                    a_len = np.linalg.norm(slab.lattice.matrix[0])
                    b_len = np.linalg.norm(slab.lattice.matrix[1])
                    rep_a = max(1, int(np.ceil(self.min_xy_size / a_len))) if a_len > 0 else 1
                    rep_b = max(1, int(np.ceil(self.min_xy_size / b_len))) if b_len > 0 else 1
                    slab.make_supercell([rep_a, rep_b, 1])
                    new_a = np.linalg.norm(slab.lattice.matrix[0])
                    new_b = np.linalg.norm(slab.lattice.matrix[1])
                    heavy = sum(1 for s in slab if s.specie.Z > 8)
                    print(f"  [SLAB] {mat_id} ({hkl_str}): {a_len:.1f}x{b_len:.1f} -> {new_a:.1f}x{new_b:.1f} A, {heavy} heavy atoms")

                    hkl_str = "".join(str(i) for i in hkl)
                    cif_path = subdir / f"{mat_id}_{hkl_str}.cif"
                    CifWriter(slab).write_file(str(cif_path))

                    z_coords = [s.frac_coords[2] for s in slab]
                    slab_height = (
                        (max(z_coords) - min(z_coords)) * slab.lattice.c
                        if z_coords else 0.0
                    )

                    slabs.append({
                        "material_id": mat_id,
                        "formula_pretty": formula,
                        "miller_index": list(hkl),
                        "cif_path": str(cif_path),
                        "slab_thickness_A": round(slab.lattice.c, 2),
                        "vacuum_A": round(slab.lattice.c - slab_height, 2),
                        "supercell": [rep_a, rep_b, 1],
                    })
                except Exception as e:
                    print(f"  [WARN] Failed to slab {mat_id} {hkl}: {e}")
                    continue

        manifest = {"slabs": slabs}
        manifest_path = output_dir / "slabs_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    @staticmethod
    def _get_unique_indices(
        structure: Structure,
        miller_indices: list[tuple[int, int, int]],
        deduplicate: bool,
    ) -> list[tuple[int, int, int]]:
        """Remove symmetry-equivalent Miller indices."""
        if not deduplicate:
            return miller_indices

        sa = SpacegroupAnalyzer(structure)
        sym_ops = sa.get_symmetry_operations()

        unique = []
        for hkl in miller_indices:
            is_equiv = False
            for existing in unique:
                for op in sym_ops:
                    transformed = tuple(
                        abs(int(round(x))) for x in op.apply_rotation_only(hkl)
                    )
                    if transformed == tuple(
                        abs(int(round(x))) for x in existing
                    ):
                        is_equiv = True
                        break
                if is_equiv:
                    break
            if not is_equiv:
                unique.append(hkl)
        return unique
