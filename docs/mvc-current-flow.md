<!--
  docs/mvc-current-flow.md
  Phase 1: Current-State MVC Mapping
  Outline of existing signal/slot flow between View, Controller, and Model
-->
# Current-State MVC Flow in RCY

## Overview

This document captures the existing interactions in the RCY application between:

- **View** components (UI elements, PyQtGraph widgets)
- **Controller** (rcy_controller.py)
- **Model** (data storage, audio processing, config_manager)

The goal is to map: View → Controller → Model → View signal/slot pathways, identify circular patterns, and create a baseline smoke test for zoom.

---

## 1. Signal/Slot Connections

Below are the key signal and slot connections currently in use.

| Source (Signal)                | Target (Slot)                     | Description                               |
| ------------------------------ | --------------------------------- | ----------------------------------------- |
| `View.rangeChanged`           | `Controller.on_range_change()`    | Trigger data reload on zoom/pan events    |
| `Controller.load_data()`       | `Model.update_data()`             | Update audio buffer and waveform data     |
| `Model.data_changed`           | `View.render_waveform()`          | Redraw waveform when model updates        |
| …                              | …                                 | …                                         |

> **TODO:** Fill in missing signal/slot pairs by examining `waveform_view.py`, `rcy_controller.py`, and `audio_processor.py`.

---

## 2. Sequence Diagram

```sequence
participant User
participant RcyView
participant RcyController
participant AudioModel
participant WaveformView

User->RcyView: click zoom-in button
RcyView->RcyController: zoom_in()
RcyController->RcyController: visible_time *= 0.97
RcyController->RcyController: update_view()
RcyController->AudioModel: get_data(start_time, end_time)
AudioModel-->RcyController: (time, data_left, data_right)
RcyController->RcyView: update_plot(time, data_left, data_right)
RcyController->RcyView: update_slices(segments)
RcyView->WaveformView: waveform_left.setData(); setXRange(); setYRange()
WaveformView-->User: redraw waveform
```

> **TODO:** Refine this diagram with actual method names and include any intermediate notifications.

---

## 3. Smoke Test: Zoom End-to-End

**Test Scenario**: Verify that a zoom operation triggers exactly one data load and one redraw, without recursion errors.

```python
import pytest
import numpy as np
from PyQt6.QtCore import Qt
from rcy_controller import RcyController
from rcy_view import RcyView
from src.python.audio_processor import AudioModel

@pytest.fixture
def app_and_controller(qtbot, monkeypatch):
    # Setup model with known total_time and stub get_data
    model = AudioModel()
    model.total_time = 10.0
    def fake_get_data(start, end):
        time = np.linspace(start, end, num=5)
        data = np.zeros_like(time)
        return time, data, data
    monkeypatch.setattr(model, 'get_data', fake_get_data)

    controller = RcyController(model)
    view = RcyView(controller)
    controller.set_view(view)
    qtbot.addWidget(view)
    return qtbot, view, controller, model

def test_zoom_triggers_single_data_and_render(app_and_controller, monkeypatch):
    qtbot, view, controller, model = app_and_controller
    calls = {'get_data': 0, 'update_plot': 0}

    # Spy on model.get_data
    def spy_get_data(start, end):
        calls['get_data'] += 1
        return model.get_data.__wrapped__(start, end)
    monkeypatch.setattr(model, 'get_data', spy_get_data)

    # Spy on waveform update_plot
    original_update_plot = view.waveform_view.update_plot
    def spy_update_plot(time, left, right):
        calls['update_plot'] += 1
        return original_update_plot(time, left, right)
    monkeypatch.setattr(view.waveform_view, 'update_plot', spy_update_plot)

    # Perform zoom in click
    qtbot.mouseClick(view.zoom_in_button, Qt.MouseButton.LeftButton)

    # Expect exactly one data fetch and one render
    assert calls['get_data'] == 1, "model.get_data should be called once"
    assert calls['update_plot'] == 1, "view.update_plot should be called once"
```

> **TODO:** Implement spies/mocks and complete assertions.

---

## 4. Next Steps

1. Populate the signal/slot table by diving into code.
2. Update sequence diagram with real method names.
3. Flesh out the smoke test with proper fixtures and assertions.
4. Run pytest and ensure this test passes under current architecture.

Once complete, we’ll have a clear picture of the existing circular dependencies and a baseline for our refactoring.