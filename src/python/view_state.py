"""
ViewState: encapsulate view window parameters (zoom and scroll) for MVC refactor.
"""

class ViewState:
    """Manage view window (start/end times) based on total duration, zoom, and scroll."""
    def __init__(self, total_time: float, visible_time: float, scroll_frac: float = 0.0):
        self.total_time = float(total_time)
        self.visible_time = float(visible_time)
        self.scroll_frac = float(scroll_frac)
        self._clamp()

    def _clamp(self):
        # Clamp visible_time to [0, total_time]
        if self.visible_time < 0.0:
            self.visible_time = 0.0
        if self.visible_time > self.total_time:
            self.visible_time = self.total_time
        # Clamp scroll_frac to valid range
        if self.total_time <= self.visible_time:
            # Window covers or exceeds data: start always at 0
            self.scroll_frac = 0.0
        else:
            self.scroll_frac = min(max(self.scroll_frac, 0.0), 1.0)

    @property
    def start(self) -> float:
        """Absolute start time of the window."""
        return (self.total_time - self.visible_time) * self.scroll_frac

    @property
    def end(self) -> float:
        """Absolute end time of the window."""
        return self.start + self.visible_time

    def set_total_time(self, total_time: float) -> None:
        """Update total duration and clamp state."""
        self.total_time = float(total_time)
        self._clamp()

    def set_visible_time(self, visible_time: float) -> None:
        """Update window length (zoom level) and clamp state."""
        self.visible_time = float(visible_time)
        self._clamp()

    def set_scroll_frac(self, scroll_frac: float) -> None:
        """Update scroll position fraction and clamp state."""
        self.scroll_frac = float(scroll_frac)
        self._clamp()

    def zoom(self, factor: float, anchor_frac: float = 0.5) -> None:
        """Zoom the window by `factor` around `anchor_frac` (0.0 to 1.0) of the window."""
        # Compute anchor time
        anchor_time = self.start + anchor_frac * self.visible_time
        # Adjust visible_time
        self.visible_time *= factor
        # Clamp visible_time
        if self.visible_time < 0.0:
            self.visible_time = 0.0
        if self.visible_time > self.total_time:
            self.visible_time = self.total_time
        # Recompute scroll_frac so that anchor_time stays at same relative position
        if self.total_time > self.visible_time:
            new_start = anchor_time - anchor_frac * self.visible_time
            self.scroll_frac = new_start / (self.total_time - self.visible_time)
        else:
            self.scroll_frac = 0.0
        self._clamp()

    def pan(self, delta_frac: float) -> None:
        """Pan by shifting scroll_frac by `delta_frac` (can be negative)."""
        self.scroll_frac += float(delta_frac)
        self._clamp()