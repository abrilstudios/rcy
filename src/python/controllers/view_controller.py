"""View controller for RCY application."""

from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from view_state import ViewState
from config_manager import config
from utils.audio_preview import get_downsampled_data
import logging

logger = logging.getLogger(__name__)


class ViewController(QObject):
    """Handles view updates, zooming, and visualization state management."""

    view_updated = pyqtSignal()
    zoom_changed = pyqtSignal(float)

    def __init__(self, model: Any, view: Any, view_state: ViewState) -> None:
        """Initialize ViewController.

        Args:
            model: The audio processor model
            view: The view instance for rendering
            view_state: ViewState instance managing scroll and zoom state
        """
        super().__init__()
        self.model = model
        self.view = view
        self.view_state = view_state
        self.visible_time: float = 10.0
        self._updating_ui: bool = False

    def update_view(self) -> None:
        """Update the view with current audio data and segment information.

        This method:
        - Prevents recursive UI updates
        - Updates view state based on current scroll position
        - Retrieves audio data for the visible time range
        - Applies downsampling if configured
        - Updates plot and segment markers

        The downsampling process:
        - Is controlled by config audio.downsampling settings
        - Can be always applied or applied only when data exceeds target length
        - Supports both 'envelope' (max_min) and 'simple' methods
        """
        # Prevent recursive UI updates
        if getattr(self, '_updating_ui', False):
            return
        self._updating_ui = True

        try:
            # Update view state
            self.view_state.set_total_time(self.model.total_time)
            self.view_state.set_visible_time(self.visible_time)
            scroll_frac = self.view.get_scroll_position() / 100.0
            self.view_state.set_scroll_frac(scroll_frac)
            start_time = self.view_state.start
            end_time = self.view_state.end

            # Get raw data
            time, data_left, data_right = self.model.get_data(start_time, end_time)

            # Apply downsampling if enabled
            ds_config = config.get_setting("audio", "downsampling", {})
            if ds_config.get("enabled", False) and time is not None:
                always_apply = ds_config.get("alwaysApply", True)
                min_length = ds_config.get("minLength", 1000)
                max_length = ds_config.get("maxLength", 5000)
                method = ds_config.get("method", "envelope")
                ds_method = "max_min" if method == "envelope" else "simple"

                width = self.view.width()
                target_length = min(max(width * 2, min_length), max_length)

                if always_apply or len(time) > target_length:
                    time, data_left, data_right = get_downsampled_data(
                        time, data_left, data_right, target_length, method=ds_method
                    )

            # Update the plot and segments
            self.view.update_plot(time, data_left, data_right, is_stereo=self.model.is_stereo)
            slices = self.model.segment_manager.get_boundaries()
            self.view.update_slices(slices)

            self.view_updated.emit()
        finally:
            # Release update guard
            self._updating_ui = False

    def zoom_in(self) -> None:
        """Zoom in on the waveform by shrinking the visible time window.

        Reduces the visible time window to 97% of its current size, zooming in
        around the center of the current view. Updates the scroll bar to reflect
        the new window size.
        """
        logger.debug("Zooming in (shrinking window to 97%%)")
        # Zoom in by shrinking visible window to 97%, around center
        self.view_state.zoom(0.97)
        # Update controller's visible_time and refresh view
        self.visible_time = self.view_state.visible_time
        self.update_view()
        # Update scroll bar to reflect new window size
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)
        self.zoom_changed.emit(self.visible_time)

    def zoom_out(self) -> None:
        """Zoom out from the waveform by expanding the visible time window.

        Expands the visible time window to 103% of its current size (limited by
        total audio duration), zooming out around the center of the current view.
        Updates the scroll bar to reflect the new window size.
        """
        logger.debug("Zooming out (expanding window to 103%%)")
        # Zoom out by expanding visible window to 103%, limited by total time
        self.view_state.zoom(1.03)
        self.visible_time = self.view_state.visible_time
        self.update_view()
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)
        self.zoom_changed.emit(self.visible_time)

    def set_visible_time(self, visible_time: float) -> None:
        """Set the visible time window for the waveform view.

        Args:
            visible_time: Duration in seconds to display in the waveform view
        """
        self.visible_time = visible_time
        self.view_state.set_visible_time(visible_time)
        self.update_view()

    def get_visible_time(self) -> float:
        """Get the current visible time window duration.

        Returns:
            float: Current visible time window in seconds
        """
        return self.visible_time
