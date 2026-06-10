"""Advanced settings dialog."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDoubleSpinBox, QSpinBox, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt

from config.defaults import SIM_CONFIG, DEFAULT_MIN_SLAB_THICKNESS, DEFAULT_MIN_VACUUM


class AdvancedSettingsDialog(QDialog):
    """Modal dialog for editing simulation and slab parameters."""

    def __init__(self, current_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Simulation Parameters")
        self.setMinimumWidth(420)
        self._config = dict(SIM_CONFIG, **(current_config or {}))
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Slab params
        slab_group = QGroupBox("Slab Parameters")
        slab_form = QFormLayout(slab_group)
        self.slab_thickness = QDoubleSpinBox()
        self.slab_thickness.setRange(5.0, 50.0)
        self.slab_thickness.setSuffix(" A")
        slab_form.addRow("Min Slab Thickness:", self.slab_thickness)

        self.vacuum = QDoubleSpinBox()
        self.vacuum.setRange(5.0, 50.0)
        self.vacuum.setSuffix(" A")
        slab_form.addRow("Vacuum Layer:", self.vacuum)
        layout.addWidget(slab_group)

        # Optics params
        optics_group = QGroupBox("Electron Optics")
        optics_form = QFormLayout(optics_group)
        self.voltage = QSpinBox()
        self.voltage.setRange(60, 300)
        self.voltage.setSuffix(" kV")
        optics_form.addRow("Accelerating Voltage:", self.voltage)

        self.semi_angle = QDoubleSpinBox()
        self.semi_angle.setRange(5.0, 50.0)
        self.semi_angle.setSuffix(" mrad")
        optics_form.addRow("Semi-angle:", self.semi_angle)

        self.cs = QDoubleSpinBox()
        self.cs.setRange(0.0, 5.0)
        self.cs.setDecimals(4)
        self.cs.setSuffix(" mm")
        optics_form.addRow("Cs:", self.cs)

        self.defocus = QDoubleSpinBox()
        self.defocus.setRange(-100.0, 100.0)
        self.defocus.setSuffix(" nm")
        optics_form.addRow("Defocus:", self.defocus)
        layout.addWidget(optics_group)

        # Detector params
        det_group = QGroupBox("HAADF Detector")
        det_form = QFormLayout(det_group)
        self.inner_angle = QDoubleSpinBox()
        self.inner_angle.setRange(10.0, 150.0)
        self.inner_angle.setSuffix(" mrad")
        det_form.addRow("Inner Angle:", self.inner_angle)

        self.outer_angle = QDoubleSpinBox()
        self.outer_angle.setRange(50.0, 300.0)
        self.outer_angle.setSuffix(" mrad")
        det_form.addRow("Outer Angle:", self.outer_angle)

        self.pixel_size = QDoubleSpinBox()
        self.pixel_size.setRange(0.01, 1.0)
        self.pixel_size.setDecimals(3)
        self.pixel_size.setSuffix(" A")
        det_form.addRow("Pixel Size:", self.pixel_size)
        layout.addWidget(det_group)

        # TDS params
        tds_group = QGroupBox("Thermal Diffuse Scattering (TDS)")
        tds_form = QFormLayout(tds_group)
        self.frozen_phonons = QSpinBox()
        self.frozen_phonons.setRange(1, 50)
        tds_form.addRow("Frozen Phonon Configs:", self.frozen_phonons)

        self.thermal_sigma = QDoubleSpinBox()
        self.thermal_sigma.setRange(0.01, 0.5)
        self.thermal_sigma.setDecimals(3)
        self.thermal_sigma.setSuffix(" A")
        tds_form.addRow("Thermal Sigma:", self.thermal_sigma)
        layout.addWidget(tds_group)

        # Atomic filter group
        af_group = QGroupBox("Atomic Number Filter")
        af_layout = QFormLayout(af_group)
        self.min_z = QSpinBox()
        self.min_z.setRange(0, 50)
        self.min_z.setToolTip("Only keep atoms with Z >= this value (0=keep all)")
        af_layout.addRow("Min Atomic Number (Z):", self.min_z)
        layout.addWidget(af_group)

        # Buttons
        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Restore Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _load_values(self):
        c = self._config
        self.slab_thickness.setValue(DEFAULT_MIN_SLAB_THICKNESS)
        self.vacuum.setValue(DEFAULT_MIN_VACUUM)
        self.voltage.setValue(c["accelerating_voltage_kV"])
        self.semi_angle.setValue(c["semi_angle_mrad"])
        self.cs.setValue(c["spherical_aberration_mm"])
        self.defocus.setValue(c["probe_defocus_nm"])
        self.inner_angle.setValue(c["HAADF_inner_mrad"])
        self.outer_angle.setValue(c["HAADF_outer_mrad"])
        self.pixel_size.setValue(c["pixel_size_A"])
        self.frozen_phonons.setValue(c["frozen_phonon_configs"])
        self.thermal_sigma.setValue(c["thermal_sigma_A"])
        self.min_z.setValue(c.get("min_atomic_number", 0))

    def _reset_defaults(self):
        from config.defaults import SIM_CONFIG as D
        self._config = dict(D)
        self._load_values()

    def get_config(self):
        return {
            "accelerating_voltage_kV": self.voltage.value(),
            "semi_angle_mrad": self.semi_angle.value(),
            "HAADF_inner_mrad": self.inner_angle.value(),
            "HAADF_outer_mrad": self.outer_angle.value(),
            "probe_defocus_nm": self.defocus.value(),
            "spherical_aberration_mm": self.cs.value(),
            "pixel_size_A": self.pixel_size.value(),
            "frozen_phonon_configs": self.frozen_phonons.value(),
            "thermal_sigma_A": self.thermal_sigma.value(),
            "gpts": self._config.get("gpts", 512),
            "slice_thickness_A": self._config.get("slice_thickness_A", 0.5),
            "seed": self._config.get("seed", 42),
            "min_atomic_number": self.min_z.value(),
        }

    def get_slab_params(self):
        return {
            "min_slab_thickness": self.slab_thickness.value(),
            "min_vacuum": self.vacuum.value(),
        }
