"""Command input widget with history and search for Textual TUI."""

from textual.widgets import Input
from textual.suggester import Suggester
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

    # Mode constants
    MODE_INSERT = "insert"    # Normal text input mode
    MODE_SEGMENT = "segment"  # Segment playback mode (vim-like normal mode)

    def __init__(
        self,
        placeholder: str = "[INSERT] Type for AI, /cmd direct | ESC for segment mode",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        suggester: Suggester | None = None,
    ) -> None:
        super().__init__(
            placeholder=placeholder,
            name=name,
            id=id,
            classes=classes,
            suggester=suggester,
        )
        self.history = CommandHistory()
        self._in_search_mode = False
        self._search_query = ""
        self._search_match = ""
        self._mode = self.MODE_INSERT  # Start in insert mode
        # Tab completion cycling state
        self._tab_matches: list[str] = []
        self._tab_index: int = 0
        self._tab_prefix: str = ""

    # Keys that trigger segment playback (1-0, q-p except 'i' which is reserved for insert mode)
    SEGMENT_KEYS = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                    'q', 'w', 'e', 'r', 't', 'y', 'u', 'o', 'p'}

    class SegmentKeyPressed(Message):
        """Posted when a segment key is pressed with empty input."""
        def __init__(self, key: str) -> None:
            self.key = key
            super().__init__()

    def _set_mode(self, mode: str) -> None:
        """Switch between insert and segment modes."""
        self._mode = mode
        if mode == self.MODE_SEGMENT:
            self.placeholder = "[SEGMENT] 1-0/qwertyuop play | i=insert mode"
        else:
            self.placeholder = "[INSERT] Type for AI, /cmd direct | ESC for segment mode"

    def on_key(self, event) -> None:
        """Handle special keys for history and search."""
        key = event.key
        char = event.character if hasattr(event, 'character') else None

        if self._in_search_mode:
            self._handle_search_key(event)
            return

        # SEGMENT MODE: keys trigger segment playback
        if self._mode == self.MODE_SEGMENT:
            check_key = char if char and len(char) == 1 else key

            if check_key in self.SEGMENT_KEYS:
                self.post_message(self.SegmentKeyPressed(check_key))
                event.stop()
                event.prevent_default()
                return

            # 'i' or Escape exits segment mode back to insert
            if key == "escape" or check_key == "i":
                self._set_mode(self.MODE_INSERT)
                event.stop()
                event.prevent_default()
                return

            # Block all other keys in segment mode
            event.stop()
            event.prevent_default()
            return

        # INSERT MODE: normal text input
        # Escape switches to segment mode (clears input first)
        if key == "escape":
            self.value = ""
            self.history.reset_position()
            self._set_mode(self.MODE_SEGMENT)
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

        elif key == "enter":
            # Add to history before Input clears it
            cmd = self.value.strip()
            if cmd:
                self.history.add(cmd)
            self.history.reset_position()
            # Let parent Input handle the submit (don't prevent default)

        elif key == "tab":
            # Tab cycles through completion matches
            self._handle_tab_completion()
            event.prevent_default()

    def _handle_tab_completion(self) -> None:
        """Handle Tab key for cycling through completions."""
        from tui.widgets.command_suggester import CommandSuggester

        # Get the suggester if it exists and is a CommandSuggester
        suggester = getattr(self, '_suggester', None)
        if not isinstance(suggester, CommandSuggester):
            # Fall back to accepting inline suggestion if available
            if self._suggestion:
                self.value = self._suggestion
                self.cursor_position = len(self.value)
            return

        current_value = self.value

        # Check if we're continuing from a previous Tab cycle
        # We're cycling if the current value is one of our matches
        if self._tab_matches and current_value in self._tab_matches:
            # Cycle to next match
            self._tab_index = (self._tab_index + 1) % len(self._tab_matches)
            self.value = self._tab_matches[self._tab_index]
            self.cursor_position = len(self.value)
        else:
            # Get new matches for current input
            self._tab_matches = suggester.get_all_matches(current_value)
            if self._tab_matches:
                self._tab_index = 0
                self._tab_prefix = current_value
                self.value = self._tab_matches[0]
                self.cursor_position = len(self.value)
            elif self._suggestion:
                # Fall back to inline suggestion
                self.value = self._suggestion
                self.cursor_position = len(self.value)

    def _handle_search_key(self, event) -> None:
        """Handle keys in search mode."""
        key = event.key

        if key == "escape":
            # Cancel search - return to insert mode
            self._in_search_mode = False
            self.history.cancel_search()
            self._set_mode(self.MODE_INSERT)
            event.prevent_default()

        elif key == "enter":
            # Accept search result - stay in insert mode
            result = self.history.accept_search()
            self._in_search_mode = False
            if result:
                self.value = result
                self.cursor_position = len(result)
            self._set_mode(self.MODE_INSERT)
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
