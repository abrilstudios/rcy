# Phase 2: View-State Extraction

## Goal
Extract a pure Python `ViewState` class to encapsulate view window parameters (zoom and scroll), decoupling UI widgets from data flow logic.

## Requirements
1. Track the total duration (`total_time`) of the data.
2. Track the visible window length (`visible_time`) within `[0, total_time]`.
3. Track the scroll position as a fraction between `0.0` (start aligned) and `1.0` (end aligned).
4. Compute the absolute start and end times of the window: 
   - `start = scroll_frac * (total_time - visible_time)`
   - `end = start + visible_time`
5. Clamp values so that:
   - `visible_time` never exceeds `total_time`
   - `scroll_frac` is always in `[0.0, 1.0]`
6. Support programmatic zooming and panning:
   - `zoom(factor, anchor_frac=0.5)`: scale `visible_time` by `factor` around an anchor point in the window.
   - `pan(delta_frac)`: shift `scroll_frac` by `delta_frac`.

## API Design
```python
class ViewState:
    def __init__(self, total_time: float, visible_time: float, scroll_frac: float = 0.0):
        ...

    @property
    def start(self) -> float:
        """Absolute start time of current window"""

    @property
    def end(self) -> float:
        """Absolute end time of current window"""

    def set_total_time(self, total_time: float) -> None:
        """Update total_time and clamp state"""

    def set_visible_time(self, visible_time: float) -> None:
        """Update zoom level (window length) and clamp state"""

    def set_scroll_frac(self, scroll_frac: float) -> None:
        """Update scroll position fraction and clamp state"""

    def zoom(self, factor: float, anchor_frac: float = 0.5) -> None:
        """Zoom by a factor around `anchor_frac` in [0,1] of the window"""

    def pan(self, delta_frac: float) -> None:
        """Pan by adjusting `scroll_frac` by `delta_frac`"""
```

## Next Steps
1. Implement `ViewState` in `src/python/view_state.py`.
2. Write unit tests in `tests/test_view_state.py` covering all methods.
3. Refactor controller and view to use `ViewState` for window calculations.