"""GUI integration smoke tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_main_window_creates(qtbot):
    """Main window creates without crash."""
    from gui.main_window import MSBatchMainWindow
    window = MSBatchMainWindow()
    qtbot.addWidget(window)
    assert "MSBatch" in window.windowTitle()


def test_sidebar_default_state(qtbot):
    """Sidebar simulate button starts disabled."""
    from gui.main_window import MSBatchMainWindow
    window = MSBatchMainWindow()
    qtbot.addWidget(window)
    assert not window.sidebar.simulate_btn.isEnabled()
    assert window.sidebar.retrieve_btn.isEnabled()


def test_sidebar_inputs_exist(qtbot):
    """Sidebar has all required input fields."""
    from gui.main_window import MSBatchMainWindow
    window = MSBatchMainWindow()
    qtbot.addWidget(window)
    assert window.sidebar.elements_input is not None
    assert window.sidebar.stoich_input is not None
    assert window.sidebar.miller_input is not None


def test_three_tabs_exist(qtbot):
    """Main window has 3 tabs with correct names."""
    from gui.main_window import MSBatchMainWindow
    window = MSBatchMainWindow()
    qtbot.addWidget(window)
    assert window.tabs.count() == 3
    assert window.tabs.tabText(0) == "Candidate Structures"
    assert window.tabs.tabText(1) == "Simulated Images"
    assert window.tabs.tabText(2) == "Comparison Report"


def test_advanced_settings_dialog_defaults(qtbot):
    """Advanced settings dialog returns correct default config."""
    from gui.dialogs import AdvancedSettingsDialog
    dialog = AdvancedSettingsDialog()
    qtbot.addWidget(dialog)
    config = dialog.get_config()
    assert config["accelerating_voltage_kV"] == 200
    assert config["HAADF_inner_mrad"] == 60
    assert config["frozen_phonon_configs"] == 3
