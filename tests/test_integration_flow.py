"""
Integration test to ensure multiple zooms do not cause recursive update loops.
"""
import pytest
import numpy as np
from PyQt6.QtCore import Qt
from audio_processor import WavAudioProcessor
from controllers import ApplicationController
from rcy_view import RcyView

@pytest.fixture
def app_and_controller(qtbot, monkeypatch):
    # Prevent preset loading exit by stubbing load_preset
    monkeypatch.setattr(WavAudioProcessor, 'load_preset', lambda self, pid=None: None)
    # Create model and stub get_data
    model = WavAudioProcessor()
    model.total_time = 10.0
    def fake_get_data(start, end):
        time = np.linspace(start, end, num=5)
        data = np.zeros_like(time)
        return time, data, data
    monkeypatch.setattr(model, 'get_data', fake_get_data)

    # Setup controller and view
    controller = ApplicationController(model)
    view = RcyView(controller)
    controller.set_view(view)
    qtbot.addWidget(view)
    return qtbot, view, controller, model

def test_multiple_zoom_no_recursion(app_and_controller, monkeypatch):
    qtbot, view, controller, model = app_and_controller
    calls = {'get_data': 0, 'update_plot': 0}

    # Spy on model.get_data
    original_get_data = model.get_data
    def spy_get_data(start, end):
        calls['get_data'] += 1
        return original_get_data(start, end)
    monkeypatch.setattr(model, 'get_data', spy_get_data)

    # Spy on waveform_view.update_plot
    orig_update_plot = view.waveform_view.update_plot
    def spy_update_plot(time, left, right):
        calls['update_plot'] += 1
        return orig_update_plot(time, left, right)
    monkeypatch.setattr(view.waveform_view, 'update_plot', spy_update_plot)

    # Perform 10 successive zoom in operations
    for _ in range(10):
        qtbot.mouseClick(view.zoom_in_button, Qt.MouseButton.LeftButton)

    # Check that exactly 10 fetches and 10 renders occurred
    assert calls['get_data'] == 10, f"Expected 10 get_data calls, got {calls['get_data']}"
    assert calls['update_plot'] == 10, f"Expected 10 update_plot calls, got {calls['update_plot']}"

def test_many_zooms_and_pans_no_recursion(app_and_controller, monkeypatch, qtbot):
    qtbot, view, controller, model = app_and_controller
    calls = {'get_data': 0, 'update_plot': 0}

    # Spy on model.get_data and view.update_plot
    original_get_data = model.get_data
    def spy_get_data(start, end):
        calls['get_data'] += 1
        return original_get_data(start, end)
    monkeypatch.setattr(model, 'get_data', spy_get_data)
    original_update_plot = view.waveform_view.update_plot
    def spy_update_plot(time, left, right):
        calls['update_plot'] += 1
        return original_update_plot(time, left, right)
    monkeypatch.setattr(view.waveform_view, 'update_plot', spy_update_plot)

    # Perform 50 zoom in/out and pan cycles
    for _ in range(50):
        qtbot.mouseClick(view.zoom_in_button, Qt.MouseButton.LeftButton)
        qtbot.mouseClick(view.zoom_out_button, Qt.MouseButton.LeftButton)
        controller.execute_command('pan', delta_frac=0.02)

    # Each cycle triggers: zoom_in, zoom_out, and pan → 3 view updates per loop
    total_cycles = 50
    expected_calls = total_cycles * 3
    assert calls['get_data'] == expected_calls, f"Expected {expected_calls} get_data calls, got {calls['get_data']}"
    assert calls['update_plot'] == expected_calls, f"Expected {expected_calls} update_plot calls, got {calls['update_plot']}"