"""Control panel with input widgets and playback tempo controls.

This module provides a unified control panel containing:
- Measures input
- Threshold slider for transient detection
- Split method dropdown
- Resolution dropdown for measure splits
- Playback tempo control with enable checkbox and BPM input

The panel uses Qt signals for value changes to enable clean integration
with the main controller.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSlider, QComboBox, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIntValidator, QValidator
import logging
from typing import Any
from config_manager import config

logger = logging.getLogger(__name__)


class ControlPanel(QWidget):
    """Control panel with input widgets and playback tempo controls.

    Signals:
        measures_changed: Emitted when number of measures changes (int)
        threshold_changed: Emitted when threshold slider changes (float 0.0-1.0)
        split_method_changed: Emitted when split method dropdown changes (str)
        resolution_changed: Emitted when measure resolution changes (int)
        playback_tempo_toggled: Emitted when tempo adjustment is enabled/disabled (bool)
        target_bpm_changed: Emitted when target BPM is changed (int)
    """

    # Signals
    measures_changed = pyqtSignal(int)
    threshold_changed = pyqtSignal(float)
    threshold_slider_released = pyqtSignal(float)  # Emitted when slider is released
    split_method_changed = pyqtSignal(str)
    resolution_changed = pyqtSignal(int)
    playback_tempo_toggled = pyqtSignal(bool)
    target_bpm_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the control panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create top row with measures, tempo display, and playback tempo
        info_layout = QHBoxLayout()

        # Measures input
        self._create_measures_input(info_layout)

        # Tempo display (read-only)
        self._create_tempo_display(info_layout)

        # Playback tempo controls
        self._create_playback_tempo_controls(info_layout)

        main_layout.addLayout(info_layout)

        # Threshold slider
        self._create_threshold_slider(main_layout)

        # Resolution dropdown
        self._create_resolution_dropdown(main_layout)

    def _create_measures_input(self, layout: QHBoxLayout) -> None:
        """Create the measures input field.

        Args:
            layout: Layout to add widgets to
        """
        self.measures_label = QLabel(config.get_string("labels", "numMeasures"))
        self.measures_input = QLineEdit("1")
        self.measures_input.setValidator(QIntValidator(1, 1000))
        self.measures_input.editingFinished.connect(self._on_measures_changed)

        layout.addWidget(self.measures_label)
        layout.addWidget(self.measures_input)

    def _create_tempo_display(self, layout: QHBoxLayout) -> None:
        """Create the tempo display field.

        Args:
            layout: Layout to add widgets to
        """
        self.tempo_label = QLabel(config.get_string("labels", "tempo"))
        self.tempo_display = QLineEdit("N/A")
        self.tempo_display.setReadOnly(True)

        layout.addWidget(self.tempo_label)
        layout.addWidget(self.tempo_display)

    def _create_playback_tempo_controls(self, layout: QHBoxLayout) -> None:
        """Create the playback tempo controls.

        Args:
            layout: Layout to add widgets to
        """
        playback_tempo_layout = QHBoxLayout()

        # Checkbox for enabling/disabling
        self.playback_tempo_checkbox = QCheckBox("Tempo Adjust:")
        self.playback_tempo_checkbox.setChecked(False)
        self.playback_tempo_checkbox.toggled.connect(self._on_tempo_toggled)
        playback_tempo_layout.addWidget(self.playback_tempo_checkbox)

        # BPM input field
        self.target_bpm_input = QLineEdit()
        self.target_bpm_input.setValidator(QIntValidator(40, 300))
        self.target_bpm_input.setPlaceholderText("BPM")
        self.target_bpm_input.editingFinished.connect(self._on_target_bpm_changed)
        self.target_bpm_input.setMaximumWidth(80)
        playback_tempo_layout.addWidget(self.target_bpm_input)

        layout.addLayout(playback_tempo_layout)

    def _create_threshold_slider(self, layout: QVBoxLayout) -> None:
        """Create the threshold slider for transient detection.

        Args:
            layout: Layout to add widgets to
        """
        threshold_layout = QHBoxLayout()

        # Label
        threshold_label = QLabel(config.get_string("labels", "onsetThreshold"))
        threshold_layout.addWidget(threshold_label)

        # Get default threshold from config
        td_config = config.get_setting("audio", "transientDetection", {})
        default_threshold = td_config.get("threshold", 0.2)
        # Convert threshold to sensitivity (inverted: threshold 0.2 → sensitivity 80)
        default_slider_value = int((1.0 - default_threshold) * 100)

        # Slider (0-99 range to match ReCycle)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 99)
        self.threshold_slider.setValue(default_slider_value)
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(10)
        self.threshold_slider.valueChanged.connect(self._on_threshold_slider_changed)
        self.threshold_slider.sliderReleased.connect(self._on_threshold_slider_released)
        threshold_layout.addWidget(self.threshold_slider)

        # Value display label - shows sensitivity value (0-99), not internal threshold
        self.threshold_value_label = QLabel(f"{default_slider_value}")
        threshold_layout.addWidget(self.threshold_value_label)

        layout.addLayout(threshold_layout)

    def _create_resolution_dropdown(self, layout: QVBoxLayout) -> None:
        """Create the measure resolution dropdown.

        Args:
            layout: Layout to add widgets to
        """
        resolution_layout = QHBoxLayout()

        self.measure_resolution_combo = QComboBox()
        self.measure_resolutions = config.get_string("labels", "measureResolutions")

        # Add each resolution option to the dropdown
        for resolution in self.measure_resolutions:
            self.measure_resolution_combo.addItem(resolution["label"])

        # Set default selection to Quarter Note (4)
        default_index = next(
            (i for i, res in enumerate(self.measure_resolutions) if res["value"] == 4),
            2
        )
        self.measure_resolution_combo.setCurrentIndex(default_index)
        self.measure_resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)

        resolution_layout.addWidget(self.measure_resolution_combo)
        layout.addLayout(resolution_layout)

    # Signal handlers

    def _on_measures_changed(self) -> None:
        """Handle measures input changes."""
        text = self.measures_input.text()
        validator = self.measures_input.validator()
        if validator is None:
            return

        state, _, _ = validator.validate(text, 0)

        if state == QValidator.State.Acceptable:
            num_measures = int(text)
            logger.debug(f"Measures changed to {num_measures}")
            self.measures_changed.emit(num_measures)
        else:
            # Reset to 1 if invalid
            self.measures_input.setText("1")
            logger.debug("Invalid measures value, reset to 1")

    def _on_threshold_slider_changed(self, value: int) -> None:
        """Handle threshold slider changes.

        Args:
            value: Slider value (0-99) representing sensitivity

        Note:
            Uses strong exponential mapping for precise control:
            - Higher slider value = higher sensitivity = lower threshold = more slices
            - Lower slider value = lower sensitivity = higher threshold = fewer slices
            - Power of 5 gives very aggressive curve, most useful range in upper values
        """
        # Convert sensitivity (0-99) to normalized value (0.0-1.0)
        normalized = value / 99.0

        # Apply strong exponential curve: threshold = (1 - sensitivity)^5
        # This maps:
        #   sensitivity 0  → threshold 1.0 (no slices)
        #   sensitivity 50 → threshold ~0.03
        #   sensitivity 70 → threshold ~0.0024
        #   sensitivity 90 → threshold ~0.00001 (extremely sensitive)
        #   sensitivity 99 → threshold ~0.0 (maximum)
        threshold = (1.0 - normalized) ** 5

        # Display the sensitivity value (0-99), not the internal threshold
        self.threshold_value_label.setText(f"{value}")
        logger.debug(f"Sensitivity {value} → threshold {threshold:.6f}")
        self.threshold_changed.emit(threshold)

    def _on_threshold_slider_released(self) -> None:
        """Handle threshold slider release (mouse button released).

        Emits the threshold_slider_released signal which can trigger
        auto-update if transients mode is active.
        """
        value = self.threshold_slider.value()
        # Use same exponential mapping as _on_threshold_slider_changed
        normalized = value / 99.0
        threshold = (1.0 - normalized) ** 5
        logger.debug(f"Sensitivity slider released at {value} (threshold {threshold:.6f})")
        self.threshold_slider_released.emit(threshold)

    def _on_resolution_changed(self, index: int) -> None:
        """Handle resolution dropdown changes.

        Args:
            index: Selected index in dropdown
        """
        if 0 <= index < len(self.measure_resolutions):
            resolution_value = self.measure_resolutions[index]["value"]
            logger.debug(f"Resolution changed to {resolution_value}")
            self.resolution_changed.emit(resolution_value)

    def _on_tempo_toggled(self, enabled: bool) -> None:
        """Handle playback tempo checkbox toggle.

        Args:
            enabled: Whether tempo adjustment is enabled
        """
        logger.debug(f"Playback tempo toggled: {enabled}")
        self.playback_tempo_toggled.emit(enabled)

    def _on_target_bpm_changed(self) -> None:
        """Handle target BPM input changes."""
        text = self.target_bpm_input.text()
        if not text:
            return

        validator = self.target_bpm_input.validator()
        if validator is None:
            return

        state, _, _ = validator.validate(text, 0)

        if state == QValidator.State.Acceptable:
            bpm = int(text)
            logger.debug(f"Target BPM changed to {bpm}")

            # Auto-enable checkbox if user enters BPM
            if not self.playback_tempo_checkbox.isChecked():
                logger.debug("Auto-enabling tempo adjustment")
                # Block signals to prevent recursion
                old_state = self.playback_tempo_checkbox.blockSignals(True)
                self.playback_tempo_checkbox.setChecked(True)
                self.playback_tempo_checkbox.blockSignals(old_state)
                # Emit the toggle signal manually
                self.playback_tempo_toggled.emit(True)

            self.target_bpm_changed.emit(bpm)
        else:
            # Reset to default
            logger.debug("Invalid BPM value, resetting to 120")
            old_state = self.target_bpm_input.blockSignals(True)
            self.target_bpm_input.setText("120")
            self.target_bpm_input.blockSignals(old_state)

    # Public API methods

    def set_measures(self, num: int) -> None:
        """Set the number of measures.

        Args:
            num: Number of measures
        """
        self.measures_input.setText(str(num))

    def get_measures(self) -> int:
        """Get the current number of measures.

        Returns:
            Number of measures
        """
        text = self.measures_input.text()
        try:
            return int(text)
        except ValueError:
            return 1

    def set_threshold(self, value: float) -> None:
        """Set the threshold value.

        Args:
            value: Threshold value (0.0-1.0)

        Note:
            Converts threshold to sensitivity using inverse exponential mapping:
            threshold 0.0 (very sensitive) → sensitivity 99
            threshold 1.0 (not sensitive) → sensitivity 0
        """
        # Inverse of exponential mapping: threshold = (1 - normalized)^5
        # Solve for normalized: normalized = 1 - threshold^(1/5)
        normalized = 1.0 - (value ** (1.0/5.0))
        sensitivity = int(normalized * 99)
        self.threshold_slider.setValue(sensitivity)

    def get_threshold(self) -> float:
        """Get the current threshold value.

        Returns:
            Threshold value (0.0-1.0)
        """
        value = self.threshold_slider.value()
        normalized = value / 99.0
        threshold = (1.0 - normalized) ** 5
        return threshold

    def set_resolution(self, value: int) -> None:
        """Set the measure resolution.

        Args:
            value: Resolution value (1, 2, 4, 8, or 16)
        """
        index = next(
            (i for i, res in enumerate(self.measure_resolutions) if res["value"] == value),
            2  # Default to quarter note
        )
        self.measure_resolution_combo.setCurrentIndex(index)

    def get_resolution(self) -> int:
        """Get the current measure resolution.

        Returns:
            Resolution value
        """
        index = self.measure_resolution_combo.currentIndex()
        if 0 <= index < len(self.measure_resolutions):
            return self.measure_resolutions[index]["value"]
        return 4  # Default to quarter note

    def set_playback_tempo(self, enabled: bool, target_bpm: int | None = None) -> None:
        """Set the playback tempo settings.

        Args:
            enabled: Whether tempo adjustment is enabled
            target_bpm: Target BPM value (optional)
        """
        # Block signals to prevent recursion
        old_checkbox_state = self.playback_tempo_checkbox.blockSignals(True)
        self.playback_tempo_checkbox.setChecked(enabled)
        self.playback_tempo_checkbox.blockSignals(old_checkbox_state)

        if target_bpm is not None:
            old_input_state = self.target_bpm_input.blockSignals(True)
            self.target_bpm_input.setText(str(target_bpm))
            self.target_bpm_input.blockSignals(old_input_state)

    def get_playback_tempo_enabled(self) -> bool:
        """Get whether playback tempo adjustment is enabled.

        Returns:
            True if enabled
        """
        return self.playback_tempo_checkbox.isChecked()

    def get_target_bpm(self) -> int | None:
        """Get the target BPM value.

        Returns:
            Target BPM or None if not set
        """
        text = self.target_bpm_input.text()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def update_tempo_display(self, tempo: float) -> None:
        """Update the tempo display.

        Args:
            tempo: Tempo in BPM
        """
        self.tempo_display.setText(f"{tempo:.2f} BPM")

    def increment_sensitivity(self) -> None:
        """Increment sensitivity slider by 1 (matches ReCycle + key behavior)."""
        current = self.threshold_slider.value()
        if current < 99:  # Max value
            self.threshold_slider.setValue(current + 1)
            logger.debug("Incremented sensitivity to %s", current + 1)

    def decrement_sensitivity(self) -> None:
        """Decrement sensitivity slider by 1 (matches ReCycle - key behavior)."""
        current = self.threshold_slider.value()
        if current > 0:  # Min value
            self.threshold_slider.setValue(current - 1)
            logger.debug("Decremented sensitivity to %s", current - 1)
