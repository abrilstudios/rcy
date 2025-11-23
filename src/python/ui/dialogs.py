"""Dialog classes for RCY application."""

import os
from typing import Any
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextBrowser,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import QSize, QUrl
from PyQt6.QtGui import QDesktopServices
from config_manager import config


class KeyboardShortcutsDialog(QDialog):
    """Dialog showing keyboard shortcuts information."""

    def __init__(self, parent: Any = None) -> None:
        """Initialize the keyboard shortcuts dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(config.get_string("dialogs", "shortcutsTitle"))
        self.setMinimumSize(QSize(500, 400))
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        # Apply styling to dialog
        self.setStyleSheet(
            f"background-color: {config.get_qt_color('background')}; "
            f"color: {config.get_qt_color('textColor')};"
        )

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create text browser for shortcuts
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(
            f"background-color: {config.get_qt_color('background')}; "
            f"color: {config.get_qt_color('textColor')};"
        )

        # Set font
        text_browser.setFont(config.get_font('primary'))

        # Get marker colors for accurate documentation
        start_marker_color = config.get_qt_color('startMarker')
        end_marker_color = config.get_qt_color('endMarker')

        # Prepare HTML content
        shortcuts_html = f"""
        <h2>{config.get_string("dialogs", "shortcutsTitle")}</h2>

        <h3>{config.get_string("shortcuts", "markersSection")}</h3>
        <ul>
            <li><b>Click+Drag</b> on marker: {config.get_string("shortcuts", "repositionMarker")}</li>
        </ul>

        <h3>{config.get_string("shortcuts", "playbackSection")}</h3>
        <ul>
            <li><b>Click</b> on waveform: {config.get_string("shortcuts", "playSegment")}</li>
            <li><b>Shift+Click</b>: Play first segment (useful if first segment is difficult to click)</li>
            <li><b>Spacebar</b>: Toggle playback (play/stop)</li>
            <li><b>Click</b> again during playback: Stop playback</li>
        </ul>

        <h3>{config.get_string("shortcuts", "segmentsSection")}</h3>
        <ul>
            <li><b>Alt+Click</b> or <b>Ctrl+Click</b>: {config.get_string("shortcuts", "addSegment")}</li>
            <li><b>Alt+Cmd+Click</b> (Alt+Meta on macOS) or <b>Ctrl+Alt+Click</b>: {config.get_string("shortcuts", "removeSegment")}</li>
        </ul>

        <h3>{config.get_string("shortcuts", "fileOperationsSection")}</h3>
        <ul>
            <li><b>Ctrl+O</b>: {config.get_string("shortcuts", "openFile")}</li>
            <li><b>Ctrl+E</b>: {config.get_string("shortcuts", "exportSegments")}</li>
        </ul>
        """

        text_browser.setHtml(shortcuts_html)
        layout.addWidget(text_browser)

        # Add close button
        close_button = QPushButton(config.get_string("buttons", "close"))
        close_button.setFont(config.get_font('primary'))
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        # Set modal
        self.setModal(True)


class AboutDialog(QDialog):
    """Dialog showing information about the application."""

    def __init__(self, parent: Any = None) -> None:
        """Initialize the about dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(config.get_string("dialogs", "aboutTitle"))
        self.setMinimumSize(QSize(400, 300))
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setStyleSheet(
            f"background-color: {config.get_qt_color('background')}; "
            f"color: {config.get_qt_color('textColor')};"
        )

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create text browser for about content
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(
            f"background-color: {config.get_qt_color('background')}; "
            f"color: {config.get_qt_color('textColor')};"
        )
        text_browser.setFont(config.get_font('primary'))

        about_html = f"""
        <h1>{config.get_string("about", "title")}</h1>
        <p>{config.get_string("about", "description")}</p>
        <p>{config.get_string("about", "details")}</p>
        <p><a href="{config.get_string("about", "repositoryUrl")}">{config.get_string("about", "repository")}</a></p>

        <p>{config.get_string("about", "design")}</p>
        """

        text_browser.setHtml(about_html)
        layout.addWidget(text_browser)

        # Add close button
        close_button = QPushButton(config.get_string("buttons", "close"))
        close_button.setFont(config.get_font('primary'))
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        # Set modal
        self.setModal(True)


class ExportCompletionDialog(QDialog):
    """Dialog showing export completion information."""

    def __init__(self, export_stats: dict[str, Any], parent: Any = None) -> None:
        """Initialize the export completion dialog.

        Args:
            export_stats: Dictionary with export statistics
            parent: Parent widget
        """
        super().__init__(parent)
        self.export_stats = export_stats
        self.setWindowTitle("Export Complete")
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        if not self.export_stats:
            return

        # Format time signature for display
        time_sig = (
            f"{self.export_stats['time_signature'][0]}/{self.export_stats['time_signature'][1]}"
            if self.export_stats.get('time_signature')
            else "4/4"
        )

        # Create completion dialog with export statistics
        msg_box = QMessageBox(self.parent())
        msg_box.setWindowTitle("Export Complete")
        msg_box.setIcon(QMessageBox.Icon.Information)

        # Build the message text
        message = f"Successfully exported {self.export_stats['segment_count']} segments.\n\n"
        message += f"SFZ Instrument: {os.path.basename(self.export_stats['sfz_path'])}\n"
        message += f"MIDI Sequence: {os.path.basename(self.export_stats['midi_path'])}\n\n"
        message += f"Time Signature: {time_sig}\n"

        # Show tempo information, accounting for tempo adjustment
        if self.export_stats.get('playback_tempo_enabled', False):
            message += f"Source Tempo: {self.export_stats['source_bpm']:.1f} BPM\n"
            message += f"Adjusted Tempo (MIDI): {self.export_stats['tempo']:.1f} BPM\n"
        else:
            message += f"Tempo: {self.export_stats['tempo']:.1f} BPM\n"

        message += f"Duration: {self.export_stats['duration']:.2f} seconds\n"
        message += f"\nFiles saved to:\n{self.export_stats['directory']}"

        msg_box.setText(message)

        # Add a button to open the export directory
        open_dir_button = msg_box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        close_button = msg_box.addButton(QMessageBox.StandardButton.Close)

        # Show the dialog
        msg_box.exec()

        # Check if the user clicked "Open Folder"
        if msg_box.clickedButton() == open_dir_button:
            # Open the directory using the platform's file manager
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.export_stats['directory']))

    @classmethod
    def show_dialog(cls, export_stats: dict[str, Any] | None, parent: Any = None) -> None:
        """Show the export completion dialog.

        Args:
            export_stats: Dictionary with export statistics
            parent: Parent widget
        """
        if not export_stats:
            return
        dialog = cls(export_stats, parent)
