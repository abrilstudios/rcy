"""
Unit tests for ViewState class.
"""
import pytest

from view_state import ViewState

def test_init_and_properties():
    vs = ViewState(total_time=10, visible_time=5, scroll_frac=0.0)
    assert vs.total_time == 10.0
    assert vs.visible_time == 5.0
    assert vs.scroll_frac == 0.0
    assert vs.start == pytest.approx(0.0)
    assert vs.end == pytest.approx(5.0)

def test_scroll_frac_half():
    vs = ViewState(total_time=10, visible_time=4, scroll_frac=0.5)
    assert vs.start == pytest.approx((10.0 - 4.0) * 0.5)
    assert vs.end == pytest.approx(vs.start + 4.0)

def test_visible_time_clamp():
    # visible_time > total_time should clamp
    vs = ViewState(total_time=8, visible_time=10, scroll_frac=0.5)
    assert vs.visible_time == pytest.approx(8.0)
    # scroll_frac reset to 0 when window covers all
    assert vs.scroll_frac == pytest.approx(0.0)
    assert vs.start == pytest.approx(0.0)
    assert vs.end == pytest.approx(8.0)

def test_setters_and_clamp():
    vs = ViewState(total_time=10, visible_time=2, scroll_frac=0)
    vs.set_visible_time(12)
    assert vs.visible_time == pytest.approx(10.0)
    vs.set_total_time(5)
    assert vs.total_time == pytest.approx(5.0)
    # now total_time <= visible_time, scroll_frac reset
    vs.set_visible_time(5)
    vs.set_scroll_frac(1.0)
    assert vs.scroll_frac == pytest.approx(0.0)
    assert vs.start == pytest.approx(0.0)
    assert vs.end == pytest.approx(5.0)

def test_zoom_center_anchor():
    # Setup a state and zoom in by factor 0.5 around center
    vs = ViewState(total_time=10, visible_time=4, scroll_frac=0.25)
    # initial positions
    start0 = vs.start
    end0 = vs.end
    # perform zoom
    vs.zoom(0.5, anchor_frac=0.5)
    # after zoom, visible_time halved
    assert vs.visible_time == pytest.approx(2.0)
    # anchor at old center stays same
    old_center = (start0 + end0) / 2
    new_center = (vs.start + vs.end) / 2
    assert new_center == pytest.approx(old_center)
    # check window length
    assert vs.end - vs.start == pytest.approx(vs.visible_time)

@pytest.mark.parametrize("delta,exp_frac,exp_start,exp_end", [
    (0.1, 0.35, (10-2)*0.35, (10-2)*0.35 + 2),
    (-0.5, 0.0, 0.0, 2.0),
    (1.0, 1.0, (10-2)*1.0, 10.0)
])
def test_pan(delta, exp_frac, exp_start, exp_end):
    vs = ViewState(total_time=10, visible_time=2, scroll_frac=0.25)
    vs.pan(delta)
    assert vs.scroll_frac == pytest.approx(exp_frac)
    assert vs.start == pytest.approx(exp_start)
    assert vs.end == pytest.approx(exp_end)