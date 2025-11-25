"""Keyboard shortcut handling for RCY application."""

from typing import Any, Callable
from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtGui import QKeyEvent
import logging

logger = logging.getLogger(__name__)


class KeyboardShortcutHandler(QObject):
    """Handles keyboard shortcuts and events for the RCY application.

    This class encapsulates all keyboard shortcut logic including:
    - Spacebar for play/pause toggle
    - Number keys (1-9, 0) and letter keys (Q-P) for segment selection
    - Event filtering at the application level
    """

    # Ultra-fast segment shortcut mapping (class attribute for performance)
    # Maps Qt Key enums to 1-based segment indices
    SEGMENT_KEY_MAP = {
        Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3, Qt.Key.Key_4: 4, Qt.Key.Key_5: 5,
        Qt.Key.Key_6: 6, Qt.Key.Key_7: 7, Qt.Key.Key_8: 8, Qt.Key.Key_9: 9, Qt.Key.Key_0: 10,
        Qt.Key.Key_Q: 11, Qt.Key.Key_W: 12, Qt.Key.Key_E: 13, Qt.Key.Key_R: 14, Qt.Key.Key_T: 15,
        Qt.Key.Key_Y: 16, Qt.Key.Key_U: 17, Qt.Key.Key_I: 18, Qt.Key.Key_O: 19, Qt.Key.Key_P: 20
    }

    def __init__(
        self,
        on_play_pause: Callable[[], None],
        on_segment_selected: Callable[[int], None],
        on_sensitivity_increment: Callable[[], None] | None = None,
        on_sensitivity_decrement: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the keyboard shortcut handler.

        Args:
            on_play_pause: Callback for spacebar/play-pause toggle
            on_segment_selected: Callback for segment selection by number key
                                 Receives 1-based segment index (1-20)
            on_sensitivity_increment: Callback for + key to increment sensitivity
            on_sensitivity_decrement: Callback for - key to decrement sensitivity
        """
        super().__init__()
        self.on_play_pause = on_play_pause
        self.on_segment_selected = on_segment_selected
        self.on_sensitivity_increment = on_sensitivity_increment
        self.on_sensitivity_decrement = on_sensitivity_decrement

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Application-wide event filter to catch key events.

        Handles spacebar detection at the application level to ensure
        it's captured even when other widgets have focus.

        Args:
            obj: The object that the event is being filtered for
            event: The event to filter

        Returns:
            True if the event was handled, False otherwise
        """
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                logger.debug("Spacebar detected via event filter! Toggling playback...")
                self.on_play_pause()
                return True
        return super().eventFilter(obj, event)

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key press events for the window.

        Processes keyboard shortcuts:
        - Spacebar: Toggle playback
        - Number keys (1-9, 0): Select segments 1-10
        - Letter keys (Q-P): Select segments 11-20
        - Plus (+/=): Increment sensitivity
        - Minus (-/_): Decrement sensitivity

        Args:
            event: The key press event

        Returns:
            True if the event was handled, False otherwise
        """
        key = event.key()

        # Spacebar - toggle playback
        if key == Qt.Key.Key_Space:
            self.on_play_pause()
            return True

        # Plus key - increment sensitivity
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            if self.on_sensitivity_increment:
                self.on_sensitivity_increment()
                return True

        # Minus key - decrement sensitivity
        if key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            if self.on_sensitivity_decrement:
                self.on_sensitivity_decrement()
                return True

        # Segment shortcuts - ultra-fast lookup
        segment_index = self._get_segment_index_from_key(key)
        if segment_index is not None:
            self.on_segment_selected(segment_index)
            return True

        # Key not handled by shortcuts
        return False

    def _get_segment_index_from_key(self, key: Qt.Key) -> int | None:
        """Ultra-fast key to segment index mapping.

        Args:
            key: The Qt Key enum value

        Returns:
            1-based segment index (1-20) or None if key doesn't map to a segment
        """
        return self.SEGMENT_KEY_MAP.get(key)
