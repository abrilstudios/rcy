"""
Tests for Command classes and Controller dispatch.
"""
import pytest
from commands import ZoomInCommand, ZoomOutCommand, PanCommand
from view_state import ViewState

class DummyController:
    def __init__(self):
        # Use a real ViewState to track changes
        self.view_state = ViewState(total_time=100.0, visible_time=20.0, scroll_frac=0.2)
        self.visible_time = self.view_state.visible_time
        # Fake model and view
        self.model = type('M', (), {'total_time': 100.0})()
        class View:
            def __init__(self):
                self.scroll_bar = None
            def update_scroll_bar(self, vis, tot):
                self.last_scroll = (vis, tot)
        self.view = View()
        self.update_view_called = False
    def update_view(self):
        self.update_view_called = True

@pytest.mark.parametrize("factor,anchor,expected_vis", [
    (0.5, 0.5, 10.0),
    (2.0, 0.0, 40.0),
    (1.5, 1.0, 30.0),
])
def test_zoom_in_command(factor, anchor, expected_vis):
    ctrl = DummyController()
    cmd = ZoomInCommand(ctrl, factor=factor, anchor_frac=anchor)
    cmd.execute()
    # visible_time updated
    assert ctrl.visible_time == pytest.approx(expected_vis)
    # update_view called
    assert ctrl.update_view_called
    # scroll bar updated
    assert ctrl.view.last_scroll == (ctrl.visible_time, ctrl.model.total_time)

@pytest.mark.parametrize("factor,anchor,initial_vis,expected_vis", [
    (2.0, 0.5, 20.0, 40.0),
    (0.5, 1.0, 20.0, 10.0),
])
def test_zoom_out_command(factor, anchor, initial_vis, expected_vis):
    ctrl = DummyController()
    ctrl.view_state.visible_time = initial_vis
    ctrl.visible_time = initial_vis
    cmd = ZoomOutCommand(ctrl, factor=factor, anchor_frac=anchor)
    cmd.execute()
    assert ctrl.visible_time == pytest.approx(expected_vis)
    assert ctrl.update_view_called
    assert ctrl.view.last_scroll == (ctrl.visible_time, ctrl.model.total_time)

@pytest.mark.parametrize("delta,initial_frac,expected_frac", [
    (0.1, 0.2, 0.3),
    (-0.5, 0.4, 0.0),
    (1.0, 0.2, 1.0),
])
def test_pan_command(delta, initial_frac, expected_frac):
    ctrl = DummyController()
    ctrl.view_state.scroll_frac = initial_frac
    cmd = PanCommand(ctrl, delta_frac=delta)
    cmd.execute()
    assert ctrl.view_state.scroll_frac == pytest.approx(expected_frac)
    # visible_time unchanged by pan
    assert ctrl.visible_time == ctrl.view_state.visible_time
    assert ctrl.update_view_called
    assert ctrl.view.last_scroll == (ctrl.visible_time, ctrl.model.total_time)