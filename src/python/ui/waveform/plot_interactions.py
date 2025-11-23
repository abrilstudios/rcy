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
    plot_right: Any | None
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

    Returns:
        tuple: (click_type, position) where click_type is one of:
            - 'add_segment': Segment creation requested (Ctrl+Click or Alt+Click)
            - 'remove_segment': Segment removal requested (Ctrl+Alt or Alt+Cmd)
            - 'segment_clicked': Regular click on plot area
            Or None if click should be ignored (near marker or non-left-button)

    Keyboard Modifiers:
        - Ctrl+Click or Alt+Click: Add segment at click position
        - Ctrl+Alt+Click or Alt+Cmd+Click: Remove segment at click position
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

            # Check for keyboard modifiers for removal

            # Check for Ctrl+Alt (Option) combination for removing segments
            if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.AltModifier):
                logger.debug("Ctrl+Alt combination detected - remove_segment at %f", x_pos)
                return ('remove_segment', x_pos)

            # Check for Alt+Cmd (Meta) combination for removing segments
            if (modifiers & Qt.KeyboardModifier.AltModifier) and (modifiers & Qt.KeyboardModifier.MetaModifier):
                logger.debug("Alt+Cmd combination detected - remove_segment at %f", x_pos)
                return ('remove_segment', x_pos)

            # Add segment with Ctrl+Click
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                logger.debug("Ctrl detected - add_segment at %f", x_pos)
                return ('add_segment', x_pos)

            # Add segment with Alt+Click
            if modifiers & Qt.KeyboardModifier.AltModifier:
                logger.debug("Alt detected - add_segment at %f", x_pos)
                return ('add_segment', x_pos)

            # No modifiers - regular segment click
            logger.debug("Regular click - segment_clicked at %f", x_pos)
            return ('segment_clicked', x_pos)

    logger.debug("Click outside plot areas, ignoring")
    return None
