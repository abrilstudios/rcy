"""Command input widget with history and search for Textual TUI."""

from textual.widgets import Input
from textual.message import Message
from typing import Optional


class CommandHistory:
    """Manages command history with navigation and search."""

    def __init__(self, max_size: int = 100):
        self.history: list[str] = []
        self.max_size = max_size
        self.position = 0
        self.search_mode = False
        self.search_query = ""
        self.search_results: list[int] = []
        self.search_index = 0

    def add(self, command: str) -> None:
        """Add a command to history."""
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
            if len(self.history) > self.max_size:
                self.history.pop(0)
        self.reset_position()

    def reset_position(self) -> None:
        """Reset navigation position to end of history."""
        self.position = len(self.history)
        self.search_mode = False
        self.search_query = ""
        self.search_results = []
        self.search_index = 0

    def navigate_up(self) -> Optional[str]:
        """Navigate to previous (older) command."""
        if not self.history:
            return None
        if self.position > 0:
            self.position -= 1
        return self.history[self.position] if self.position < len(self.history) else None

    def navigate_down(self) -> Optional[str]:
        """Navigate to next (newer) command."""
        if not self.history:
            return None
        if self.position < len(self.history):
            self.position += 1
        if self.position >= len(self.history):
            return ""
        return self.history[self.position]

    def start_search(self) -> None:
        """Enter search mode."""
        self.search_mode = True
        self.search_query = ""
        self.search_results = []
        self.search_index = 0

    def update_search(self, query: str) -> Optional[str]:
        """Update search query and return first match."""
        self.search_query = query
        if not query:
            self.search_results = []
            return None

        self.search_results = [
            i for i in range(len(self.history) - 1, -1, -1)
            if query.lower() in self.history[i].lower()
        ]
        self.search_index = 0

        if self.search_results:
            return self.history[self.search_results[0]]
        return None

    def search_next(self) -> Optional[str]:
        """Get next search result (older match)."""
        if not self.search_results:
            return None
        if self.search_index < len(self.search_results) - 1:
            self.search_index += 1
        return self.history[self.search_results[self.search_index]]

    def search_prev(self) -> Optional[str]:
        """Get previous search result (newer match)."""
        if not self.search_results:
            return None
        if self.search_index > 0:
            self.search_index -= 1
        return self.history[self.search_results[self.search_index]]

    def accept_search(self) -> Optional[str]:
        """Accept current search result and exit search mode."""
        result = None
        if self.search_results:
            result = self.history[self.search_results[self.search_index]]
        self.search_mode = False
        return result

    def cancel_search(self) -> None:
        """Cancel search mode."""
        self.search_mode = False
        self.search_query = ""
        self.search_results = []


class CommandInput(Input):
    """Command input with history navigation and reverse search.

    Supports:
    - Up/Down arrow for history navigation
    - Ctrl-R for reverse-i-search
    - Enter to submit command
    - Escape to cancel
    """

    DEFAULT_CSS = """
    CommandInput {
        dock: bottom;
        height: 1;
        border: none;
        padding: 0 1;
    }
    """

    class CommandSubmitted(Message):
        """Posted when a command is submitted."""
        def __init__(self, command: str) -> None:
            self.command = command
            super().__init__()

    class CommandCancelled(Message):
        """Posted when command input is cancelled."""
        pass

    def __init__(
        self,
        placeholder: str = "Type / for commands, 1-0/q-p to play segments",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(placeholder=placeholder, name=name, id=id, classes=classes)
        self.history = CommandHistory()
        self._in_search_mode = False
        self._search_query = ""
        self._search_match = ""

    # Keys that trigger segment playback (1-0, q-p)
    SEGMENT_KEYS = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                    'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'}

    class SegmentKeyPressed(Message):
        """Posted when a segment key is pressed with empty input."""
        def __init__(self, key: str) -> None:
            self.key = key
            super().__init__()

    def on_key(self, event) -> None:
        """Handle special keys for history and search."""
        key = event.key

        if self._in_search_mode:
            self._handle_search_key(event)
            return

        # Post segment keys to app when input is empty
        if key in self.SEGMENT_KEYS and not self.value:
            self.post_message(self.SegmentKeyPressed(key))
            event.stop()
            event.prevent_default()
            return

        if key == "up":
            # Navigate history up
            cmd = self.history.navigate_up()
            if cmd is not None:
                self.value = cmd
                self.cursor_position = len(cmd)
            event.prevent_default()

        elif key == "down":
            # Navigate history down
            cmd = self.history.navigate_down()
            if cmd is not None:
                self.value = cmd
                self.cursor_position = len(cmd)
            event.prevent_default()

        elif key == "ctrl+r":
            # Enter reverse search mode
            self._in_search_mode = True
            self._search_query = ""
            self._search_match = ""
            self.history.start_search()
            self._update_search_placeholder()
            event.prevent_default()

        elif key == "escape":
            # Cancel input
            self.value = ""
            self.history.reset_position()
            event.prevent_default()

        elif key == "enter":
            # Add to history before Input clears it
            cmd = self.value.strip()
            if cmd:
                self.history.add(cmd)
            self.history.reset_position()
            # Let parent Input handle the submit (don't prevent default)

    def _handle_search_key(self, event) -> None:
        """Handle keys in search mode."""
        key = event.key

        if key == "escape":
            # Cancel search
            self._in_search_mode = False
            self.history.cancel_search()
            self.placeholder = "Type / for commands, 1-0/q-p to play segments"
            event.prevent_default()

        elif key == "enter":
            # Accept search result
            result = self.history.accept_search()
            self._in_search_mode = False
            if result:
                self.value = result
                self.cursor_position = len(result)
            self.placeholder = "Type / for commands, 1-0/q-p to play segments"
            event.prevent_default()

        elif key == "ctrl+r":
            # Next search result (older)
            match = self.history.search_next()
            if match:
                self._search_match = match
                self._update_search_placeholder()
            event.prevent_default()

        elif key == "ctrl+s":
            # Previous search result (newer)
            match = self.history.search_prev()
            if match:
                self._search_match = match
                self._update_search_placeholder()
            event.prevent_default()

        elif key == "backspace":
            # Remove last char from search query
            if self._search_query:
                self._search_query = self._search_query[:-1]
                match = self.history.update_search(self._search_query)
                self._search_match = match or ""
                self._update_search_placeholder()
            event.prevent_default()

        elif len(key) == 1 and key.isprintable():
            # Add char to search query
            self._search_query += key
            match = self.history.update_search(self._search_query)
            self._search_match = match or ""
            self._update_search_placeholder()
            event.prevent_default()

    def _update_search_placeholder(self) -> None:
        """Update placeholder to show search state."""
        if self._search_match:
            self.placeholder = f"(reverse-i-search)`{self._search_query}': {self._search_match}"
        else:
            self.placeholder = f"(reverse-i-search)`{self._search_query}':"
