"""Transport controls for split, playback, and export operations.

This module provides a horizontal button panel containing:
- Split by Measures button
- Split by Transients button
- Cut Selection button (styled prominently)
- Zoom In/Out buttons

The panel uses Qt signals for button clicks to enable clean integration
with the main controller.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal
import logging
from config_manager import config

logger = logging.getLogger(__name__)


class TransportControls(QWidget):
    """Transport controls for split operations.

    Signals:
        split_measures_requested: Emitted when Split by Measures is clicked (checked)
        split_transients_requested: Emitted when Split by Transients is clicked (checked)
        clear_segments_requested: Emitted when a split button is unchecked
    """

    # Signals
    split_measures_requested = pyqtSignal()
    split_transients_requested = pyqtSignal()
    clear_segments_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the transport controls.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        # Use horizontal layout for single row of split buttons
        button_layout = QHBoxLayout()
        self.setLayout(button_layout)

        # Split buttons
        self._create_split_buttons(button_layout)

    def _create_split_buttons(self, layout: QHBoxLayout) -> None:
        """Create the split operation buttons.

        Args:
            layout: Layout to add buttons to
        """
        # Split by Measures button (checkable for toggle behavior)
        self.split_measures_button = QPushButton(
            config.get_string("buttons", "splitMeasures")
        )
        self.split_measures_button.setCheckable(True)
        self.split_measures_button.clicked.connect(self._on_split_measures_clicked)
        layout.addWidget(self.split_measures_button)

        # Split by Transients button (checkable for toggle behavior)
        self.split_transients_button = QPushButton(
            config.get_string("buttons", "splitTransients")
        )
        self.split_transients_button.setCheckable(True)
        self.split_transients_button.clicked.connect(self._on_split_transients_clicked)
        layout.addWidget(self.split_transients_button)


    # Signal handlers

    def _on_split_measures_clicked(self) -> None:
        """Handle Split by Measures button click (toggle mode)."""
        if self.split_measures_button.isChecked():
            # Activate measures mode, deactivate transients
            self.split_transients_button.setChecked(False)
            logger.debug("Split by Measures mode activated")
            self.split_measures_requested.emit()
        else:
            logger.debug("Split by Measures mode deactivated - clearing segments")
            self.clear_segments_requested.emit()

    def _on_split_transients_clicked(self) -> None:
        """Handle Split by Transients button click (toggle mode)."""
        if self.split_transients_button.isChecked():
            # Activate transients mode, deactivate measures
            self.split_measures_button.setChecked(False)
            logger.debug("Split by Transients mode activated")
            self.split_transients_requested.emit()
        else:
            logger.debug("Split by Transients mode deactivated - clearing segments")
            self.clear_segments_requested.emit()


    # Public API methods

    def set_split_measures_enabled(self, enabled: bool) -> None:
        """Enable or disable the Split by Measures button.

        Args:
            enabled: Whether the button should be enabled
        """
        self.split_measures_button.setEnabled(enabled)

    def set_split_transients_enabled(self, enabled: bool) -> None:
        """Enable or disable the Split by Transients button.

        Args:
            enabled: Whether the button should be enabled
        """
        self.split_transients_button.setEnabled(enabled)


    def update_split_measures_text(self, text: str) -> None:
        """Update the text on the Split by Measures button.

        Args:
            text: New button text
        """
        self.split_measures_button.setText(text)

    def update_split_transients_text(self, text: str) -> None:
        """Update the text on the Split by Transients button.

        Args:
            text: New button text
        """
        self.split_transients_button.setText(text)

    def is_split_measures_active(self) -> bool:
        """Check if Split by Measures mode is currently active.

        Returns:
            True if measures mode is active (button is checked)
        """
        return self.split_measures_button.isChecked()

    def is_split_transients_active(self) -> bool:
        """Check if Split by Transients mode is currently active.

        Returns:
            True if transients mode is active (button is checked)
        """
        return self.split_transients_button.isChecked()

    def reset_to_default_state(self) -> None:
        """Reset all transport controls to their default state.

        This should be called when loading a new audio file to ensure
        UI state doesn't persist from previous file. Blocks signals
        to prevent unintended side effects during reset.
        """
        logger.debug("Resetting transport controls to default state")

        # Block signals to prevent triggering clear_segments_requested
        old_measures_state = self.split_measures_button.blockSignals(True)
        old_transients_state = self.split_transients_button.blockSignals(True)

        try:
            self.split_measures_button.setChecked(False)
            self.split_transients_button.setChecked(False)
        finally:
            self.split_measures_button.blockSignals(old_measures_state)
            self.split_transients_button.blockSignals(old_transients_state)
