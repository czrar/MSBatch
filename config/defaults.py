"""MSBatch default configuration."""

# Materials Project API
MP_API_KEY = "3sDGIETDr7oH5nrQ1UP4aSczKFXJHQcC"

# MP retrieval defaults
DEFAULT_MAX_CANDIDATES = 20
DEFAULT_FIELDS = [
    "material_id", "formula_pretty", "formation_energy_per_atom",
    "energy_above_hull", "band_gap", "structure",
    "symmetry", "nsites"
]

# Slab generation defaults
DEFAULT_MIN_SLAB_THICKNESS = 12.0   # Angstrom
DEFAULT_MIN_VACUUM = 15.0           # Angstrom
DEFAULT_MILLER_INDICES = [
    (0, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)
]
DEFAULT_MIN_XY_SIZE = 12.0   # minimum slab xy supercell extent (Å)

DEFAULT_MAX_SLAB_RANK = 10

# STEM simulation parameters (abTEM)
# pixel_size_A and frozen_phonon_configs dominate time.
# pixel is increased adaptively for large cells (target ~120 points/dim).
# Low values for fast preview; increase in Advanced Settings for publication quality.
SIM_CONFIG = {
    "accelerating_voltage_kV": 200,
    "semi_angle_mrad": 22,
    "HAADF_inner_mrad": 60,
    "HAADF_outer_mrad": 180,
    "probe_defocus_nm": 0.0,
    "spherical_aberration_mm": 0.001,
    "pixel_size_A": 0.10,
    "frozen_phonon_configs": 5,
    "thermal_sigma_A": 0.075,
    "seed": 42,
    "slice_thickness_A": 0.5,
    "gpts": 512,
    "min_atomic_number": 0,
}
