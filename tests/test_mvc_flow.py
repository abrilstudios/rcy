"""
Smoke test for MVC data flow: zoom in should trigger exactly one data fetch and one render.
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
    monkeypatch.setattr(WavAudioProcessor, 'load_preset', lambda self, pid: None)
    # Create model and stub get_data
    model = WavAudioProcessor()
    model.total_time = 10.0
    def fake_get_data(start, end):
        time = np.linspace(start, end, num=5)
        data = np.zeros_like(time)
        return time, data, data
    # Replace get_data with fake implementation
    monkeypatch.setattr(model, 'get_data', fake_get_data)

    # Setup controller and view
    controller = ApplicationController(model)
    view = RcyView(controller)
    controller.set_view(view)
    qtbot.addWidget(view)
    return qtbot, view, controller, model

def test_zoom_triggers_single_data_and_render(app_and_controller, monkeypatch):
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

    # Perform zoom in click
    qtbot.mouseClick(view.zoom_in_button, Qt.MouseButton.LeftButton)

    # Assert that data fetch and render occurred once
    assert calls['get_data'] == 1, "Expected one get_data call"
    assert calls['update_plot'] == 1, "Expected one update_plot call"