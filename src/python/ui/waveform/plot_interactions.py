"""
Plot interaction handlers for waveform visualization.

This module provides low-level handling of mouse and keyboard interactions
on PyQtGraph waveform plots, enabling segment selection and manipulation.
"""

import logging
from typing import Any
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


def on_plot_clicked(
    widget: Any,
    event: Any,
    start_marker: Any,
    end_marker: Any,
    plot_left: Any,
    plot_right: Any | None,
    segment_slices: list[float] | None = None
) -> tuple[str, float] | None:
    """
    Handle plot click events with keyboard modifiers.

    Processes mouse clicks on waveform plots and determines the appropriate
    action based on keyboard modifiers and proximity to existing markers.

    Args:
        widget: The parent widget (used for signal emission context)
        event: PyQtGraph MouseClickEvent containing click position and button
        start_marker: The start marker InfiniteLine object
        end_marker: The end marker InfiniteLine object
        plot_left: The left plot (main plot, always present)
        plot_right: The right plot (stereo only, may be None)
        segment_slices: List of segment boundary positions for add/remove logic

    Returns:
        tuple: (click_type, position) where click_type is one of:
            - 'add_segment': Segment creation requested (Ctrl+Click away from marker)
            - 'remove_segment': Segment removal requested (Ctrl+Click near marker)
            - 'segment_clicked': Regular click on plot area
            Or None if click should be ignored (near start/end marker or non-left-button)

    Keyboard Modifiers:
        - Ctrl+Click: Add segment if not near existing marker, remove if near marker
        - Regular Click: Emit segment_clicked signal

    Marker Proximity:
        If click is within 0.1 units of start or end marker, returns None
        to allow the marker's drag handler to take precedence.

    Raises:
        No exceptions raised; all errors are logged and handled gracefully.
    """

    # Only process left button clicks
    if event.button() != Qt.MouseButton.LeftButton:
        logger.debug("Non-left-button click ignored: %s", event.button())
        return None

    # Get keyboard modifiers
    modifiers = QApplication.keyboardModifiers()
    logger.debug("Click modifiers: %s", modifiers)
    logger.debug("  Alt: %s", bool(modifiers & Qt.KeyboardModifier.AltModifier))
    logger.debug("  Ctrl: %s", bool(modifiers & Qt.KeyboardModifier.ControlModifier))
    logger.debug("  Cmd: %s", bool(modifiers & Qt.KeyboardModifier.MetaModifier))

    # Get mouse position in scene coordinates
    scene_pos = event.scenePos()

    # Check which plot was clicked
    plots_to_check = [(plot_left, "left")]
    if plot_right is not None:
        plots_to_check.append((plot_right, "right"))

    for plot, plot_name in plots_to_check:
        if plot is None:
            continue

        view_box = plot.getViewBox()
        if view_box.sceneBoundingRect().contains(scene_pos):
            # Convert scene position to data coordinates
            data_pos = view_box.mapSceneToView(scene_pos)
            x_pos = data_pos.x()

            logger.debug("Click detected on %s plot at position: %f", plot_name, x_pos)

            # Check if near a marker (high priority)
            start_pos = start_marker.value()
            end_pos = end_marker.value()

            # If near the start marker
            if abs(x_pos - start_pos) < 0.1:
                logger.debug("Click near start marker at %f, delegating to marker handler", start_pos)
                return None  # Let the marker's drag handle this

            # If near the end marker
            if abs(x_pos - end_pos) < 0.1:
                logger.debug("Click near end marker at %f, delegating to marker handler", end_pos)
                return None  # Let the marker's drag handle this

            # Check for keyboard modifiers for segment manipulation
            # On Mac: Ctrl key maps to AltModifier, Cmd key maps to ControlModifier
            # We use AltModifier (Ctrl on Mac) for add/remove segment behavior
            ctrl_or_alt = (modifiers & Qt.KeyboardModifier.ControlModifier) or (modifiers & Qt.KeyboardModifier.AltModifier)

            if ctrl_or_alt:
                # Check if click is near an existing segment slice marker
                tolerance = 0.1  # seconds
                near_slice = False
                if segment_slices:
                    for slice_pos in segment_slices:
                        # Skip start (0) and end boundaries - those are file boundaries
                        if slice_pos <= 0.001:
                            continue
                        if abs(x_pos - slice_pos) < tolerance:
                            near_slice = True
                            logger.debug("Modifier+Click near segment marker at %.3fs (click at %.3fs) - remove_segment", slice_pos, x_pos)
                            break

                if near_slice:
                    return ('remove_segment', x_pos)
                else:
                    logger.debug("Modifier+Click away from any segment marker at %.3fs - add_segment", x_pos)
                    return ('add_segment', x_pos)

            # No modifiers - regular segment click
            logger.debug("Regular click - segment_clicked at %f", x_pos)
            return ('segment_clicked', x_pos)

    logger.debug("Click outside plot areas, ignoring")
    return None
