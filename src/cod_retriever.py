"""COD (Crystallography Open Database) retriever.

Uses the COD REST API to search for experimental crystal structures
by formula or elements, then downloads CIF files and parses them
into the standard MSBatch candidate format.

COD REST API specification (from wiki.crystallography.net/RESTful_API/):
-----------------------------------------------------------------------
Search endpoint:  GET/POST https://www.crystallography.net/cod/result

Key parameters:
  formula          Hill notation, space-separated (e.g. "O5 V2")
  el1..el8         Elements that MUST appear
  nel1..nel4       Elements that must NOT appear
  strictmin/max    Min/max number of distinct elements
  amin/amax etc.   Cell parameter ranges (a, b, c, alpha, beta, gamma)
  vmin/vmax        Cell volume range
  spacegroup       Space group symbol
  year             Publication year
  journal          Journal name
  has_fobs         Only entries with diffraction data
  format           html | csv | json | lst | urls | zip | count

Entry access:  https://www.crystallography.net/cod/{id}.cif
               https://www.crystallography.net/cod/{id}.hkl
               https://www.crystallography.net/cod/{id}.html

No authentication required for search/access.
Deposition requires username/password (not used here).
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pymatgen.core.structure import Structure
from pymatgen.io.cif import CifParser
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def _hill_sort_formula(formula: str) -> str:
    """Convert a chemical formula to Hill notation with spaces.

    Hill notation rules (per COD spec):
    - For organic (contains C): C first, then H, then alphabetical
    - For inorganic (no C): strictly alphabetical by element symbol
    - Elements separated by a single space

    "V2O5" -> "O5 V2"
    """
    from pymatgen.core.composition import Composition
    comp = Composition(formula)
    if "C" not in comp and "H" not in comp:
        parts = sorted(comp.items(), key=lambda x: x[0].symbol)
        return " ".join(
            f"{el.symbol}{int(n) if n != 1 else ''}".replace(".0", "")
            for el, n in parts
        )
    return comp.hill_formula


def _clean_cod_formula(raw: str) -> str:
    """Clean COD formula string like '- O5 V2 -' -> 'V2O5'."""
    return raw.replace("-", "").replace(" ", "").strip()


class CODRetriever:
    """Query the Crystallography Open Database for experimental structures.

    All COD entries are experimentally determined (X-ray, neutron, or
    electron diffraction).  This complements Materials Project which
    contains DFT-computed structures.
    """

    BASE_URL = "https://www.crystallography.net/cod"
    REQUEST_TIMEOUT = 30  # seconds per request

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve_formula(
        self, formula: str, max_candidates: int = 50
    ) -> dict:
        """Search COD by exact chemical formula.

        Uses Hill notation with ``strictmin`` / ``strictmax`` to match
        only entries with the exact number of elements.
        """
        hill = _hill_sort_formula(formula)
        nel = hill.count(" ") + 1  # number of element tokens
        params = {
            "formula": hill,
            "strictmin": str(nel),
            "strictmax": str(nel),
            "format": "json",
        }
        qs = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/result?{qs}"
        entries = self._fetch_json(url)

        if not entries:
            return self._empty_result(formula=formula)

        candidates = []
        for i, entry in enumerate(entries[:max_candidates]):
            cand = self._entry_to_candidate(entry, rank=i + 1)
            if cand:
                candidates.append(cand)

        return {
            "query": {
                "formula": formula, "database": "COD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "candidates": candidates,
        }

    def retrieve_elements(
        self,
        elements: list[str],
        stoichiometry: Optional[dict[str, tuple[float, float]]] = None,
        max_candidates: int = 50,
    ) -> dict:
        """Search COD by constituent elements.

        Uses ``el1..el8`` parameters to require all specified elements.
        Optionally filters by stoichiometric ratio ranges.
        """
        params: dict[str, str] = {}
        for i, el in enumerate(elements[:8]):
            params[f"el{i + 1}"] = el
        params["format"] = "json"

        qs = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/result?{qs}"
        entries = self._fetch_json(url)

        if not entries:
            return self._empty_result(elements=elements)

        candidates = []
        for i, entry in enumerate(entries):
            if len(candidates) >= max_candidates:
                break
            cand = self._entry_to_candidate(entry, rank=i + 1)
            if not cand:
                continue
            if stoichiometry and not self._check_stoichiometry(cand, stoichiometry):
                continue
            candidates.append(cand)

        for i, c in enumerate(candidates):
            c["rank"] = i + 1

        return {
            "query": {
                "elements": elements,
                "stoichiometry": stoichiometry,
                "database": "COD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "candidates": candidates,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _empty_result(self, **query) -> dict:
        return {
            "query": {**query, "database": "COD",
                      "timestamp": datetime.now(timezone.utc).isoformat()},
            "candidates": [],
        }

    def _fetch_json(self, url: str) -> list[dict]:
        """Fetch JSON array from COD API.  Returns [] on any error."""
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "MSBatch/1.0"}
            )
            with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT) as resp:
                raw = resp.read()
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            print(f"  [COD] API request failed: {e}")
            return []

    def _entry_to_candidate(self, entry: dict, rank: int) -> dict | None:
        """Convert a COD search result entry into a standard candidate dict.

        Downloads the CIF file to get full structure_data.  If the CIF
        cannot be fetched or parsed, the candidate is still returned
        with ``structure_data=None`` (slab/simulation stages will skip it).
        """
        cod_id = entry.get("file", "")
        if not cod_id:
            return None

        # Clean formula: COD returns "- O5 V2 -"
        formula = _clean_cod_formula(entry.get("formula", ""))
        sg = entry.get("sg", "")
        sg_number = entry.get("sgNumber", "")

        a = float(entry.get("a") or 1)
        b = float(entry.get("b") or 1)
        c = float(entry.get("c") or 1)
        alpha = float(entry.get("alpha") or 90)
        beta = float(entry.get("beta") or 90)
        gamma = float(entry.get("gamma") or 90)

        crystal_system = self._guess_crystal_system(a, b, c, alpha, beta, gamma)

        # Quality indicators
        r_all = entry.get("Rall")
        has_coords = "has coordinates" in (entry.get("flags") or "")

        # Publication info
        journal = entry.get("journal", "")
        year = entry.get("year", "")

        # Download CIF for structure_data
        structure_data = None
        n_sites = None
        if has_coords:
            try:
                cif_url = f"{self.BASE_URL}/{cod_id}.cif"
                req = urllib.request.Request(
                    cif_url, headers={"User-Agent": "MSBatch/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT) as resp:
                    cif_text = resp.read().decode("utf-8", errors="replace")
                structure = self._parse_cif_text(cif_text)
                if structure is not None:
                    structure_data = structure.as_dict()
                    n_sites = len(structure)
                    try:
                        sa = SpacegroupAnalyzer(structure)
                        sg = sa.get_space_group_symbol() or sg
                        crystal_system = str(sa.get_crystal_system()) or crystal_system
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [COD] CIF download failed for {cod_id}: {e}")

        return {
            "material_id": f"cod-{cod_id}",
            "formula_pretty": formula,
            "formation_energy_per_atom": None,
            "energy_above_hull": None,
            "band_gap": None,
            "space_group": sg,
            "space_group_number": sg_number,
            "crystal_system": crystal_system,
            "n_sites": n_sites,
            "structure_data": structure_data,
            "rank": rank,
            "source": "COD",
            # COD-specific metadata
            "cod_r_factor": float(r_all) if r_all else None,
            "cod_journal": journal,
            "cod_year": int(year) if year else None,
        }

    @staticmethod
    def _parse_cif_text(cif_text: str) -> Structure | None:
        """Parse CIF text into a pymatgen Structure."""
        try:
            parser = CifParser.from_str(cif_text)
            structures = parser.get_structures(primitive=False)
            if structures:
                return structures[0]
        except Exception:
            pass

        try:
            from ase.io import read
            from io import StringIO
            atoms = read(StringIO(cif_text), format="cif")
            if atoms is not None and len(atoms) > 0:
                from pymatgen.io.ase import AseAtomsAdaptor
                return AseAtomsAdaptor.get_structure(atoms)
        except Exception:
            pass

        return None

    @staticmethod
    def _guess_crystal_system(a, b, c, alpha, beta, gamma) -> str:
        """Guess crystal system from cell parameters (tolerance 0.1°)."""
        eps = 0.1
        # Hexagonal: a=b, alpha=beta=90, gamma=120
        if abs(alpha - 90) < eps and abs(beta - 90) < eps and abs(gamma - 120) < eps:
            return "hexagonal"
        # Cubic, tetragonal, orthorhombic: all angles 90
        if abs(alpha - 90) < eps and abs(beta - 90) < eps and abs(gamma - 90) < eps:
            if abs(a - b) < eps and abs(b - c) < eps:
                return "cubic"
            if abs(a - b) < eps:
                return "tetragonal"
            return "orthorhombic"
        # Monoclinic: alpha=gamma=90
        if abs(alpha - 90) < eps and abs(gamma - 90) < eps:
            return "monoclinic"
        return "triclinic"

    @staticmethod
    def _check_stoichiometry(
        cand: dict, stoichiometry: dict[str, tuple[float, float]]
    ) -> bool:
        """Check if candidate matches stoichiometric ratio ranges."""
        if cand.get("structure_data") is None:
            return True
        try:
            struct = Structure.from_dict(cand["structure_data"])
            comp = struct.composition
            total = sum(comp.get(el, 0) for el in stoichiometry)
            if total == 0:
                return False
            for el, (lo, hi) in stoichiometry.items():
                ratio = comp.get(el, 0) / total
                if ratio < lo or ratio > hi:
                    return False
            return True
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def save(result: dict, output_dir: str | Path) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "candidates.json"
        out_path.write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
        return out_path

    @staticmethod
    def load(path: str | Path) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))
