# Issue 93: Implement PyQt-Based GUI Testing

## Description
We need to implement proper unit testing for our PyQt6/PyQtGraph GUI components that can run in headless environments. The previous approach in `tests/waveform/test_pyqtgraph_basic.py` was removed because it crashed when run without a display server.

## Recommended Approach: PyQt's QTest Framework
PyQt provides a dedicated testing framework called QTest that's specifically designed for testing Qt applications without requiring a display server:

1. Use `QTest` for simulating user interaction
   ```python
   from PyQt6.QtTest import QTest
   from PyQt6.QtCore import Qt
   
   # Test button click
   QTest.mouseClick(button, Qt.LeftButton)
   
   # Test keyboard input
   QTest.keyClicks(line_edit, "test input")
   ```

2. Use `QSignalSpy` for testing signals
   ```python
   from PyQt6.QtTest import QSignalSpy
   
   # Test that a signal was emitted
   spy = QSignalSpy(waveform_view.start_marker_changed)
   waveform_view.set_start_marker(1.0)
   assert len(spy) == 1
   assert spy[0][0] == 1.0
   ```

## Technical Implementation
1. Create separate test classes for each widget component
2. Focus on testing functionality rather than rendering
3. Use mock objects for any dependencies
4. Validate signal emissions and state changes

## Acceptance Criteria
- Tests for WaveformView validate:
  - Setting marker positions
  - Signal emissions for marker changes
  - Slice point management
  - Highlight segment functionality
- All tests run in headless environments
- Tests are added to CI pipeline
- Documentation explains how to run GUI tests