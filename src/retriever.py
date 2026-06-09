"""Stage 1: Materials Project retriever."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mp_api.client import MPRester
from pymatgen.core.structure import Structure

from config.defaults import MP_API_KEY, DEFAULT_MAX_CANDIDATES, DEFAULT_FIELDS


def _safe_hull(val):
    """Sort key: treat None as infinity (unstable/unknown → end of list)."""
    if val is None:
        return float("inf")
    return val


class MPRetriever:
    """Query Materials Project for candidate structures."""

    def __init__(self, api_key: str = MP_API_KEY):
        self.api_key = api_key

    def retrieve_elements(
        self,
        elements: list[str],
        stoichiometry: Optional[dict[str, tuple[float, float]]] = None,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
    ) -> dict:
        """Search by elements with optional stoichiometry filtering.

        Pagination is handled automatically by mp-api's internal chunking
        (default chunk_size=1000), so >1000 results are fully retrieved.
        """
        with MPRester(self.api_key) as mpr:
            docs = mpr.materials.summary.search(
                elements=elements,
                fields=DEFAULT_FIELDS,
            )
        candidates = self._docs_to_candidates(docs)
        if stoichiometry:
            candidates = self._filter_stoichiometry(candidates, stoichiometry)
        candidates.sort(key=lambda c: _safe_hull(c.get("energy_above_hull")))
        candidates = candidates[:max_candidates]
        for i, c in enumerate(candidates):
            c["rank"] = i + 1
        return {
            "query": {
                "elements": elements,
                "stoichiometry": stoichiometry,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "candidates": candidates,
        }

    def retrieve_formula(
        self, formula: str, max_candidates: int = DEFAULT_MAX_CANDIDATES
    ) -> dict:
        """Search by exact formula string.

        Pagination is handled automatically by mp-api's internal chunking
        (default chunk_size=1000), so >1000 results are fully retrieved.
        """
        with MPRester(self.api_key) as mpr:
            docs = mpr.materials.summary.search(
                formula=formula,
                fields=DEFAULT_FIELDS,
            )
        candidates = self._docs_to_candidates(docs)
        # Sort by energy_above_hull ascending (stable phases first).
        # Candidates with same formula but different material_id are all kept
        # (no deduplication) — critical for structure identification.
        candidates.sort(key=lambda c: _safe_hull(c.get("energy_above_hull")))
        candidates = candidates[:max_candidates]
        for i, c in enumerate(candidates):
            c["rank"] = i + 1
        return {
            "query": {
                "formula": formula,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "candidates": candidates,
        }

    @staticmethod
    def _docs_to_candidates(docs) -> list[dict]:
        """Convert MPRester summary docs to candidate dicts.

        Embeds the full pymatgen Structure.as_dict() so downstream stages
        can reconstruct the Structure without re-fetching from MP.
        """
        candidates = []
        for doc in docs:
            if doc.structure is None:
                continue
            candidates.append({
                "material_id": doc.material_id,
                "formula_pretty": doc.formula_pretty,
                "formation_energy_per_atom": doc.formation_energy_per_atom,
                "energy_above_hull": getattr(doc, "energy_above_hull", None),
                "band_gap": doc.band_gap,
                "space_group": getattr(doc.symmetry, "symbol", "") if doc.symmetry else "",
                "crystal_system": str(doc.symmetry.crystal_system) if doc.symmetry else "",
                "n_sites": getattr(doc, "nsites", None),
                "structure_data": doc.structure.as_dict(),
            })
        return candidates

    @staticmethod
    def _filter_stoichiometry(
        candidates: list[dict], stoichiometry: dict[str, tuple[float, float]]
    ) -> list[dict]:
        """Filter candidates by stoichiometric ratio ranges.

        For each element in *stoichiometry*, compute its fraction of the
        total atoms (limited to the elements specified in stoichiometry)
        and check it falls within [lo, hi].
        """
        kept = []
        for cand in candidates:
            struct = Structure.from_dict(cand["structure_data"])
            comp = struct.composition
            total = sum(comp.get(el, 0) for el in stoichiometry)
            if total == 0:
                continue
            ok = True
            for el, (lo, hi) in stoichiometry.items():
                ratio = comp.get(el, 0) / total
                if ratio < lo or ratio > hi:
                    ok = False
                    break
            if ok:
                kept.append(cand)
        return kept

    @staticmethod
    def save(result: dict, output_dir: str | Path) -> Path:
        """Save candidates result to JSON file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "candidates.json"
        out_path.write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
        return out_path

    @staticmethod
    def load(path: str | Path) -> dict:
        """Load candidates result from JSON file."""
        return json.loads(Path(path).read_text(encoding="utf-8"))
