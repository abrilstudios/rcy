"""
Test waveform view module imports.
This test just ensures the waveform view modules can be imported correctly.
"""
import pytest


def test_waveform_view_import():
    """Test that waveform_view module can be imported"""
    try:
        from waveform_view import create_waveform_view
        assert callable(create_waveform_view)
    except ImportError as e:
        pytest.fail(f"Failed to import waveform_view: {e}")


def test_waveform_classes_import():
    """Test that waveform view classes can be imported"""
    try:
        from waveform_view import BaseWaveformView, PyQtGraphWaveformView
        assert issubclass(PyQtGraphWaveformView, BaseWaveformView)
    except ImportError as e:
        pytest.fail(f"Failed to import waveform view classes: {e}")


def test_pyqtgraph_availability():
    """Test PyQtGraph availability"""
    try:
        import pyqtgraph as pg
        # PyQtGraph is now a required dependency
        print(f"PyQtGraph version: {pg.__version__}")
    except ImportError as e:
        pytest.fail(f"PyQtGraph not available: {e}")