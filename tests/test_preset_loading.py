"""
Integration tests for preset loading to verify correct marker initialization.

These tests ensure that:
1. Markers are initialized at correct positions (0.0 and total_time)
2. Marker handles are visible after preset load
3. The initialization order is correct (update_view before clear_markers)
4. All presets load correctly with proper tempo calculation
"""
import pytest
import numpy as np
from PyQt6.QtWidgets import QApplication
from audio_processor import WavAudioProcessor
from controllers import ApplicationController
from rcy_view import RcyView


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def app_with_preset(qtbot, qt_app):
    """Create application with a real preset loaded."""
    def _create_app(preset_id='amen_classic'):
        # Create model with preset
        model = WavAudioProcessor(preset_id=preset_id)

        # Setup controller and view
        controller = ApplicationController(model)

        # Set measures from preset info
        from config_manager import config
        preset_info = config.get_preset_info(preset_id)
        controller.num_measures = preset_info.get('measures', 1)

        view = RcyView(controller)
        controller.set_view(view)
        qtbot.addWidget(view)

        # Initial update
        controller.update_view()

        return qtbot, view, controller, model

    return _create_app


@pytest.mark.parametrize("preset_id,expected_measures", [
    ("amen_classic", 4),
    ("think_break", 1),
    ("apache_break", 2),
])
def test_preset_markers_initialized_correctly(app_with_preset, preset_id, expected_measures):
    """Test that markers are initialized at file boundaries for each preset."""
    qtbot, view, controller, model = app_with_preset(preset_id)

    # Get marker positions
    start_pos, end_pos = view.get_marker_positions()

    # Verify markers exist
    assert start_pos is not None, f"{preset_id}: Start marker should be visible"
    assert end_pos is not None, f"{preset_id}: End marker should be visible"

    # Verify start marker is at beginning
    assert start_pos == 0.0, f"{preset_id}: Start marker should be at 0.0, got {start_pos}"

    # Verify end marker is at total_time (allow 20ms tolerance for downsampling)
    assert abs(end_pos - model.total_time) < 0.02, \
        f"{preset_id}: End marker should be at {model.total_time}, got {end_pos}"

    # Verify measures are correct
    assert controller.num_measures == expected_measures, \
        f"{preset_id}: Expected {expected_measures} measures, got {controller.num_measures}"


@pytest.mark.parametrize("preset_id", ["amen_classic", "think_break", "apache_break"])
def test_preset_marker_handles_visible(app_with_preset, preset_id):
    """Test that marker handles are actually visible (not None) after preset load."""
    qtbot, view, controller, model = app_with_preset(preset_id)

    # Access the waveform view directly (it IS the widget)
    waveform_view = view.waveform_view

    # Check that marker lines exist
    assert hasattr(waveform_view, 'start_marker_left'), f"{preset_id}: Should have start_marker_left"
    assert hasattr(waveform_view, 'end_marker_left'), f"{preset_id}: Should have end_marker_left"

    # Check that marker positions are within valid range
    start_pos = waveform_view.start_marker_left.value()
    end_pos = waveform_view.end_marker_left.value()

    assert start_pos >= 0.0, f"{preset_id}: Start marker position should be non-negative"
    assert end_pos <= model.total_time + 0.02, f"{preset_id}: End marker should not exceed total_time (with tolerance)"

    # Check that time_data exists (crucial for marker handle rendering)
    assert hasattr(waveform_view, 'time_data'), f"{preset_id}: Should have time_data"
    assert waveform_view.time_data is not None, f"{preset_id}: time_data should not be None after preset load"
    assert len(waveform_view.time_data) > 0, f"{preset_id}: time_data should not be empty"


def test_think_break_specific_issues(app_with_preset):
    """
    Specific test for think_break which had issues with:
    - Invisible left (start) marker
    - Incorrect tempo display (228 BPM instead of ~114 BPM)
    """
    qtbot, view, controller, model = app_with_preset('think_break')

    # Verify start marker is visible
    start_pos, end_pos = view.get_marker_positions()
    assert start_pos is not None, "think_break: Start marker must be visible"
    assert start_pos == 0.0, f"think_break: Start marker should be at 0.0, got {start_pos}"

    # Verify tempo is reasonable for 1 measure over ~2.1s
    # Actual calculation: 4 beats / (2.105/60) = ~114 BPM
    # Allow wider range for rounding differences
    assert 100.0 < controller.tempo < 130.0, \
        f"think_break: Tempo should be ~100-130 BPM, got {controller.tempo}"

    # Verify duration
    assert 2.0 < model.total_time < 2.2, \
        f"think_break: Duration should be ~2.1s, got {model.total_time}"


def test_apache_preset_start_marker_at_zero(app_with_preset):
    """
    Test that apache preset start marker is exactly at 0.0 (not offset).
    This was the original bug - start marker was offset and missed the kick drum.
    """
    qtbot, view, controller, model = app_with_preset('apache_break')

    # Get start marker position
    start_pos, _ = view.get_marker_positions()

    # Verify start marker is EXACTLY at 0.0
    assert start_pos == 0.0, \
        f"apache_break: Start marker must be exactly 0.0 to capture kick drum, got {start_pos}"

    # Verify waveform time_data starts at 0.0
    waveform_view = view.waveform_view
    assert waveform_view.time_data is not None, "apache_break: time_data should exist"
    assert waveform_view.time_data[0] == 0.0, \
        f"apache_break: time_data should start at 0.0, got {waveform_view.time_data[0]}"


def test_preset_reload_resets_markers(app_with_preset):
    """
    Test that loading a new preset correctly resets markers.
    This verifies the fix for state persistence between preset loads.
    """
    qtbot, view, controller, model = app_with_preset('amen_classic')

    # Get initial markers
    start_1, end_1 = view.get_marker_positions()
    duration_1 = model.total_time

    # Load different preset
    success = controller.load_preset('think_break')
    assert success, "think_break should load successfully"

    # Get new markers
    start_2, end_2 = view.get_marker_positions()
    duration_2 = model.total_time

    # Verify markers are different (different audio duration)
    assert duration_1 != duration_2, "Presets should have different durations"
    assert end_1 != end_2, "End markers should be different after preset change"

    # Verify new markers are correct
    assert start_2 == 0.0, "Start marker should be at 0.0 after preset change"
    assert abs(end_2 - duration_2) < 0.02, \
        f"End marker should be at {duration_2} after preset change, got {end_2}"


def test_markers_set_after_time_data_available(app_with_preset, monkeypatch):
    """
    Test that markers are only set AFTER time_data is available in the view.
    This is the core fix for the race condition.
    """
    qtbot, view, controller, model = app_with_preset('amen_classic')

    # Track the order of operations
    operations = []

    # Spy on update_plot (which sets time_data)
    original_update_plot = view.update_plot
    def spy_update_plot(*args, **kwargs):
        operations.append('update_plot')
        return original_update_plot(*args, **kwargs)
    monkeypatch.setattr(view, 'update_plot', spy_update_plot)

    # Spy on clear_markers
    original_clear_markers = view.clear_markers
    def spy_clear_markers(*args, **kwargs):
        operations.append('clear_markers')
        # Verify time_data is set when clear_markers is called
        waveform_view = view.waveform_view
        assert hasattr(waveform_view, 'time_data'), "Waveform view should have time_data attribute"
        assert waveform_view.time_data is not None, \
            "CRITICAL: time_data must be set before clear_markers is called!"
        return original_clear_markers(*args, **kwargs)
    monkeypatch.setattr(view, 'clear_markers', spy_clear_markers)

    # Load a new preset to trigger the operation sequence
    operations.clear()
    controller.load_preset('think_break')

    # Verify correct order: update_plot BEFORE clear_markers
    assert 'update_plot' in operations, "update_plot should have been called"
    assert 'clear_markers' in operations, "clear_markers should have been called"

    update_plot_idx = operations.index('update_plot')
    clear_markers_idx = operations.index('clear_markers')

    assert update_plot_idx < clear_markers_idx, \
        "update_plot must be called BEFORE clear_markers to ensure time_data is available"


def test_all_presets_load_without_errors(app_with_preset):
    """
    Smoke test: verify all presets can be loaded without errors.
    """
    preset_ids = ["amen_classic", "think_break", "apache_break", "apache_L", "apache_R"]

    for preset_id in preset_ids:
        qtbot, view, controller, model = app_with_preset(preset_id)

        # Basic assertions
        assert model.total_time > 0, f"{preset_id}: Should have valid duration"
        assert controller.tempo > 0, f"{preset_id}: Should have valid tempo"

        # Markers should be visible
        start_pos, end_pos = view.get_marker_positions()
        assert start_pos is not None, f"{preset_id}: Start marker should be visible"
        assert end_pos is not None, f"{preset_id}: End marker should be visible"
        assert start_pos == 0.0, f"{preset_id}: Start marker should be at 0.0"


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_preset_loading.py -v
    pytest.main([__file__, "-v"])
