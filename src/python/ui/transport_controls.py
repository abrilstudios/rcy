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
    """Transport controls for split, playback, and export operations.

    Signals:
        split_measures_requested: Emitted when Split by Measures is clicked
        split_transients_requested: Emitted when Split by Transients is clicked
        cut_requested: Emitted when Cut Selection is clicked
        zoom_in_requested: Emitted when Zoom In is clicked
        zoom_out_requested: Emitted when Zoom Out is clicked
    """

    # Signals
    split_measures_requested = pyqtSignal()
    split_transients_requested = pyqtSignal()
    cut_requested = pyqtSignal()
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the transport controls.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        # Create horizontal layout for buttons
        button_layout = QHBoxLayout()
        self.setLayout(button_layout)

        # Split buttons row
        self._create_split_buttons(button_layout)

        # Zoom and cut buttons row (separate layout)
        control_layout = QHBoxLayout()
        self._create_control_buttons(control_layout)

        # Note: In the original implementation, these were in separate rows
        # We'll create a vertical layout to maintain that structure
        from PyQt6.QtWidgets import QVBoxLayout

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # First row: Split buttons
        split_row = QHBoxLayout()
        self._create_split_buttons(split_row)
        main_layout.addLayout(split_row)

        # Second row: Control buttons (zoom, cut)
        control_row = QHBoxLayout()
        self._create_control_buttons(control_row)
        main_layout.addLayout(control_row)

    def _create_split_buttons(self, layout: QHBoxLayout) -> None:
        """Create the split operation buttons.

        Args:
            layout: Layout to add buttons to
        """
        # Split by Measures button
        self.split_measures_button = QPushButton(
            config.get_string("buttons", "splitMeasures")
        )
        self.split_measures_button.clicked.connect(self._on_split_measures_clicked)
        layout.addWidget(self.split_measures_button)

        # Split by Transients button
        self.split_transients_button = QPushButton(
            config.get_string("buttons", "splitTransients")
        )
        self.split_transients_button.clicked.connect(self._on_split_transients_clicked)
        layout.addWidget(self.split_transients_button)

    def _create_control_buttons(self, layout: QHBoxLayout) -> None:
        """Create the control buttons (zoom, cut).

        Args:
            layout: Layout to add buttons to
        """
        # Zoom In button
        self.zoom_in_button = QPushButton(config.get_string("buttons", "zoomIn"))
        self.zoom_in_button.clicked.connect(self._on_zoom_in_clicked)
        layout.addWidget(self.zoom_in_button)

        # Zoom Out button
        self.zoom_out_button = QPushButton(config.get_string("buttons", "zoomOut"))
        self.zoom_out_button.clicked.connect(self._on_zoom_out_clicked)
        layout.addWidget(self.zoom_out_button)

        # Cut button (styled prominently)
        self.cut_button = QPushButton(config.get_string("buttons", "cut"))
        self.cut_button.setStyleSheet(
            f"background-color: {config.get_qt_color('cutButton')}; "
            "color: white; "
            "font-weight: bold;"
        )
        self.cut_button.clicked.connect(self._on_cut_clicked)
        layout.addWidget(self.cut_button)

    # Signal handlers

    def _on_split_measures_clicked(self) -> None:
        """Handle Split by Measures button click."""
        logger.debug("Split by Measures button clicked")
        self.split_measures_requested.emit()

    def _on_split_transients_clicked(self) -> None:
        """Handle Split by Transients button click."""
        logger.debug("Split by Transients button clicked")
        self.split_transients_requested.emit()

    def _on_cut_clicked(self) -> None:
        """Handle Cut Selection button click."""
        logger.debug("Cut Selection button clicked")
        self.cut_requested.emit()

    def _on_zoom_in_clicked(self) -> None:
        """Handle Zoom In button click."""
        logger.debug("Zoom In button clicked")
        self.zoom_in_requested.emit()

    def _on_zoom_out_clicked(self) -> None:
        """Handle Zoom Out button click."""
        logger.debug("Zoom Out button clicked")
        self.zoom_out_requested.emit()

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

    def set_cut_enabled(self, enabled: bool) -> None:
        """Enable or disable the Cut Selection button.

        Args:
            enabled: Whether the button should be enabled
        """
        self.cut_button.setEnabled(enabled)

    def set_zoom_in_enabled(self, enabled: bool) -> None:
        """Enable or disable the Zoom In button.

        Args:
            enabled: Whether the button should be enabled
        """
        self.zoom_in_button.setEnabled(enabled)

    def set_zoom_out_enabled(self, enabled: bool) -> None:
        """Enable or disable the Zoom Out button.

        Args:
            enabled: Whether the button should be enabled
        """
        self.zoom_out_button.setEnabled(enabled)

    def update_cut_button_text(self, text: str) -> None:
        """Update the text on the Cut Selection button.

        Args:
            text: New button text
        """
        self.cut_button.setText(text)

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
