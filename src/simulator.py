"""Stage 3: STEM-HAADF image simulator using abTEM."""
import json
import math
import os
import warnings
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image

# Prevent dask "cannot schedule new futures after shutdown"
import dask.config
dask.config.set(scheduler='threads')

# ---- GPU detection ----
# abTEM uses cupy automatically when it's importable.
# If cupy is present, multislice runs on GPU (10-50x faster).
try:
    import warnings as _w
    with _w.catch_warnings():
        _w.filterwarnings("ignore", message="CUDA path could not be detected")
        import cupy  # noqa: F401
    _HAS_GPU = True
except ImportError:
    _HAS_GPU = False

from config.defaults import SIM_CONFIG


class SimulatorNotAvailableError(RuntimeError):
    """Raised when no simulation engine is available."""
    pass


class STEMSimulator:
    """STEM-HAADF simulator using abTEM.

    Uses the multislice algorithm with frozen phonons for thermal
    diffuse scattering (TDS), which provides the Z-contrast signal
    in HAADF-STEM imaging.

    Parameters
    ----------
    config : dict, optional
        Simulation configuration.  Merged with defaults from
        ``config.defaults.SIM_CONFIG``.  Supported keys:
        accelerating_voltage_kV, semi_angle_mrad,
        HAADF_inner_mrad, HAADF_outer_mrad, probe_defocus_nm,
        spherical_aberration_mm, pixel_size_A,
        frozen_phonon_configs, thermal_sigma_A, seed,
        slice_thickness_A, gpts.
    """

    def __init__(self, config: dict | None = None):
        self.config = {**SIM_CONFIG, **(config or {})}
        self._engine = None
        self._try_load_engine()

    # ------------------------------------------------------------------
    # Engine detection
    # ------------------------------------------------------------------

    def _try_load_engine(self):
        """Try to import abTEM.  Fall back to placeholder mode."""
        try:
            import abtem
            if _HAS_GPU:
                abtem.config.set({'device': 'gpu'})
                self._engine = "abtem-gpu"
            else:
                self._engine = "abtem"
        except ImportError:
            self._engine = "placeholder"
            warnings.warn(
                "abTEM not installed. Running in placeholder mode (dummy images). "
                "Install with: pip install abtem"
            )

    @property
    def engine(self) -> str:
        """Return the active simulation engine name."""
        return self._engine

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def simulate(self, manifest: dict, output_dir: str | Path) -> dict:
        """Run HAADF simulation for every slab in *manifest*.

        Parameters
        ----------
        manifest : dict
            Slabs manifest produced by ``SlabBuilder.build()``.
            Must contain a ``"slabs"`` list; each entry must have
            ``"cif_path"``, ``"material_id"``, ``"miller_index"``,
            and ``"formula_pretty"``.
        output_dir : str or Path
            Root output directory.  Images are written to
            ``<output_dir>/sim_images/`` and the result manifest to
            ``<output_dir>/sim_images_manifest.json``.

        Returns
        -------
        dict
            Manifest with a ``"simulations"`` list matching
            slab entries to generated image paths.
        """
        output_dir = Path(output_dir)
        sim_dir = output_dir / "sim_images"
        sim_dir.mkdir(parents=True, exist_ok=True)

        simulations = []
        cfg = self.config

        for slab in manifest["slabs"]:
            cif_path = Path(slab["cif_path"])
            if not cif_path.exists():
                print(f"  [SKIP] CIF not found: {cif_path}")
                continue

            mat_id = slab["material_id"]
            hkl_str = "".join(str(i) for i in slab["miller_index"])
            formula = slab.get("formula_pretty", "")
            out_subdir = sim_dir / f"{mat_id}_{formula}"
            out_subdir.mkdir(parents=True, exist_ok=True)
            out_path = out_subdir / f"{mat_id}_{hkl_str}_HAADF.png"

            try:
                if self._engine in ("abtem", "abtem-gpu"):
                    self._run_abtem(str(cif_path), str(out_path), cfg)
                else:
                    self._run_placeholder(str(out_path), cfg)
            except Exception as e:
                print(f"  [ERR] Simulation failed {mat_id} {hkl_str}: {e}")
                continue

            simulations.append({
                "material_id": mat_id,
                "miller_index": slab["miller_index"],
                "image_path": str(out_path),
            })

        manifest_out = {"simulations": simulations}
        manifest_path = output_dir / "sim_images_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_out, indent=2), encoding="utf-8"
        )
        return manifest_out

    # ------------------------------------------------------------------
    # abTEM engine
    # ------------------------------------------------------------------

    def _run_abtem(self, cif_path: str, out_path: str, cfg: dict):
        """Run abTEM multislice HAADF simulation for a single slab.

        Workflow
        --------
        1. Load CIF via ASE.
        2. Build FrozenPhonons ensemble, convert to AtomsEnsemble.
        3. Create Potential from the ensemble.
        4. Set up electron Probe, annular detector, and GridScan.
        5. Run multislice, compute, normalise, save PNG.
        """
        from ase.io import read
        from abtem import (
            Potential, FrozenPhonons, Probe,
            AnnularDetector, GridScan,
        )

        atoms = read(cif_path)

        # --- Atomic number filter ---
        min_z = cfg.get("min_atomic_number", 0)
        if min_z > 0:
            mask = [atom.number >= min_z for atom in atoms]
            atoms = atoms[mask]
            if len(atoms) == 0:
                raise ValueError(f"all atoms removed by min_atomic_number={min_z}")

        # abTEM requires an orthogonal simulation cell.
        # abTEM 1.0.9's orthogonalize_cell has a bug where the diagonal
        # check passes for cells with off-diagonal elements => we use a
        # custom implementation based on best_orthogonal_cell + cut.
        atoms = self._ensure_orthogonal_cell(atoms)

        # --- Frozen phonons (TDS for Z-contrast) ---
        sigma = cfg["thermal_sigma_A"]
        sigmas = {atom.symbol: sigma for atom in atoms}
        frozen_phonons = FrozenPhonons(
            atoms,
            num_configs=cfg["frozen_phonon_configs"],
            sigmas=sigmas,
            seed=cfg["seed"],
        )
        atoms_ensemble = frozen_phonons.to_atoms_ensemble()

        # --- Adaptive gpts: ensure max scattering angle >= detector outer angle ---
        # max_angle_mrad = gpts * lambda * 1000 / (2 * cell_size)
        # at 200 kV: lambda = 0.02508 Å → gpts = outer_mrad * cell_size / 12.54
        cell = np.array(atoms.cell)
        a_len = np.linalg.norm(cell[0])
        b_len = np.linalg.norm(cell[1])
        cell_size = max(a_len, b_len)
        # 1.1x safety margin on cell size
        min_gpts = int(cell_size * 1.1 * cfg["HAADF_outer_mrad"] / 12.54) + 1
        gpts = max(cfg["gpts"], min_gpts)
        # Round up to next power of 2 for optimal FFT
        gpts = 2 ** math.ceil(math.log2(gpts))

        # --- Adaptive pixel size: target ~60 scan points per dimension ---
        # regardless of slab size, so all slabs take similar time.
        target_points = 60
        auto_pixel = cell_size / target_points
        pixel = max(cfg["pixel_size_A"], auto_pixel)

        # --- Electrostatic potential ---
        potential = Potential(
            atoms_ensemble,
            gpts=gpts,
            slice_thickness=cfg["slice_thickness_A"],
            projection="infinite",
        )

        # --- Electron probe ---
        # Energy: kV -> eV; Cs: mm -> Angstrom (1 mm = 1e7 A)
        probe = Probe(
            energy=cfg["accelerating_voltage_kV"] * 1e3,
            semiangle_cutoff=cfg["semi_angle_mrad"],
            defocus=cfg["probe_defocus_nm"] * 10,  # nm -> A
            Cs=cfg["spherical_aberration_mm"] * 1e7,
        )

        # --- HAADF annular detector ---
        detector = AnnularDetector(
            inner=cfg["HAADF_inner_mrad"],
            outer=cfg["HAADF_outer_mrad"],
        )

        # --- Scan grid ---
        scan = GridScan(sampling=pixel)

        # --- Multislice ---
        measurement = probe.scan(potential, scan, detector)
        result = measurement.compute()
        arr = result.array
        # Explicit GPU→CPU transfer when using cupy
        if _HAS_GPU and hasattr(arr, 'get'):
            arr = arr.get()
        image = np.array(arr)

        # --- Normalize and save ---
        img_normalized = self._normalize_image(image)
        Image.fromarray(img_normalized).save(out_path)

    # ------------------------------------------------------------------
    # Placeholder engine
    # ------------------------------------------------------------------

    def _run_placeholder(self, out_path: str, cfg: dict):
        """Generate a synthetic HAADF-like image for pipeline testing.

        Creates a 256x256 image with random bright spots (atomic
        columns) on a dark background, blurred with a Gaussian to
        approximate a STEM probe, plus shot noise.
        """
        rng = np.random.default_rng(cfg["seed"])
        img = np.zeros((256, 256), dtype=np.float32)
        n_spots = rng.integers(5, 20)
        for _ in range(n_spots):
            x = rng.integers(32, 224)
            y = rng.integers(32, 224)
            img[y, x] = rng.uniform(0.6, 1.0)
        sigma = 256 / 40
        img = gaussian_filter(img, sigma=sigma)
        img += rng.normal(0, 0.02, img.shape)
        img = np.clip(img, 0, 1)
        img = (img / img.max() * 255).astype(np.uint8)
        Image.fromarray(img).save(out_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_orthogonal_cell(atoms, max_repetitions: int = 5):
        """Return *atoms* with an orthogonal cell.

        abTEM requires the simulation cell to be orthogonal.  The
        built-in ``orthogonalize_cell`` in abTEM 1.0.9 has a bug where
        it checks ``np.diag(cell)`` instead of the full cell for
        orthogonality, so it may return a non-orthogonal cell unchanged.
        This helper uses ``best_orthogonal_cell`` from abTEM to compute
        the ideal box and ``ase.build.cut`` to build the orthogonal
        supercell.  After the cut, fractional off-diagonal elements are
        clamped to zero to satisfy abTEM's strict ``tol=1e-12`` check
        in ``is_cell_orthogonal``.
        """
        cell = np.array(atoms.cell)
        # Already orthogonal?
        diag = np.diag(np.diag(cell))
        if np.allclose(cell, diag, atol=1e-12):
            return atoms

        from abtem.atoms import best_orthogonal_cell
        from ase.build import cut

        box = best_orthogonal_cell(cell, max_repetitions=max_repetitions)
        inv = np.linalg.inv(cell)
        vectors = np.dot(np.diag(box), inv)
        vectors = np.round(vectors)
        atoms = cut(atoms, a=vectors[0], b=vectors[1], c=vectors[2])

        # Clamp tiny off-diagonal residues from the cut operation.
        # abTEM's is_cell_orthogonal uses tol=1e-12, but the cut
        # operation may leave residues on the order of 1e-9.
        new_cell = np.array(atoms.cell)
        new_cell[np.abs(new_cell) < 1e-8] = 0.0
        atoms.set_cell(new_cell)

        return atoms

    @staticmethod
    def _normalize_image(img: np.ndarray) -> np.ndarray:
        """Normalise an image array to 0-255 uint8."""
        img = np.array(img, dtype=np.float64)
        img_min, img_max = img.min(), img.max()
        if img_max > img_min:
            img = (img - img_min) / (img_max - img_min)
            img = (img * 255).astype(np.uint8)
        else:
            img = np.zeros_like(img, dtype=np.uint8)
        return img
