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
        self._current_page = "waveform"  # Current notebook page
        # Tab completion cycling state
        self._tab_matches: list[str] = []
        self._tab_index: int = 0
        self._tab_last: str = ""

    # Keys that trigger segment playback (1-0, q-p except 'i' which is reserved for insert mode)
    SEGMENT_KEYS = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                    'q', 'w', 'e', 'r', 't', 'y', 'u', 'o', 'p'}

    class SegmentKeyPressed(Message):
        """Posted when a segment key is pressed with empty input."""
        def __init__(self, key: str) -> None:
            self.key = key
            super().__init__()

    class MarkerNudge(Message):
        """Posted when marker nudge key is pressed."""
        def __init__(self, direction: str, mode: str = "normal") -> None:
            self.direction = direction  # "left" or "right"
            self.mode = mode  # "normal", "fine", or "coarse"
            super().__init__()

    class MarkerCycleFocus(Message):
        """Posted when marker focus cycle key is pressed."""
        def __init__(self, reverse: bool = False) -> None:
            self.reverse = reverse
            super().__init__()

    class SpacePressed(Message):
        """Posted when space is pressed in segment mode."""
        pass

    class OutputScroll(Message):
        """Posted when up/down arrow is pressed in segment mode to scroll output."""
        def __init__(self, direction: str) -> None:
            self.direction = direction  # "up" or "down"
            super().__init__()

    class PageCycle(Message):
        """Posted when Tab/Shift+Tab is pressed in segment mode to cycle pages."""
        def __init__(self, reverse: bool = False) -> None:
            self.reverse = reverse
            super().__init__()

    # Page-specific placeholders for segment mode
    PAGE_PLACEHOLDERS = {
        "waveform": "[WAVEFORM] 1-0/qw play | ←→ nudge | []=marker | Tab=page | i=insert",
        "bank": "[BANK] 1-0/qw pad | ←→ pad | ↑↓ bank | Space=pick/drop | Tab=page | i=insert",
        "sounds": "[SOUNDS] ←→ sound | ↑↓ category | []=category | Space=pick | Tab=page | i=insert",
    }

    def set_page(self, page: str) -> None:
        """Set the current notebook page and update placeholder if in segment mode."""
        self._current_page = page.lower()
        if self._mode == self.MODE_SEGMENT:
            self._update_placeholder()

    def _update_placeholder(self) -> None:
        """Update placeholder based on current mode and page."""
        if self._mode == self.MODE_SEGMENT:
            self.placeholder = self.PAGE_PLACEHOLDERS.get(
                self._current_page,
                "[SEGMENT] Tab=page | i=insert"
            )
        else:
            self.placeholder = "[INSERT] Type for AI, /cmd direct | ESC for segment mode"

    def _set_mode(self, mode: str) -> None:
        """Switch between insert and segment modes."""
        self._mode = mode
        self._update_placeholder()

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

            # Arrow keys nudge the focused marker (with modifier support)
            if key in ("left", "shift+left", "ctrl+left"):
                mode = "fine" if "shift" in key else ("coarse" if "ctrl" in key else "normal")
                self.post_message(self.MarkerNudge("left", mode))
                event.stop()
                event.prevent_default()
                return
            if key in ("right", "shift+right", "ctrl+right"):
                mode = "fine" if "shift" in key else ("coarse" if "ctrl" in key else "normal")
                self.post_message(self.MarkerNudge("right", mode))
                event.stop()
                event.prevent_default()
                return

            # [ and ] cycle marker focus
            if check_key == "[":
                self.post_message(self.MarkerCycleFocus(reverse=True))
                event.stop()
                event.prevent_default()
                return
            if check_key == "]":
                self.post_message(self.MarkerCycleFocus(reverse=False))
                event.stop()
                event.prevent_default()
                return

            # Space plays/stops full sample
            if key == "space":
                self.post_message(self.SpacePressed())
                event.stop()
                event.prevent_default()
                return

            # Up/Down arrows - route through MarkerNudge (app decides per-page behavior)
            if key == "up":
                self.post_message(self.MarkerNudge("up"))
                event.stop()
                event.prevent_default()
                return
            if key == "down":
                self.post_message(self.MarkerNudge("down"))
                event.stop()
                event.prevent_default()
                return

            # Tab/Shift+Tab cycles notebook pages
            if key == "tab":
                self.post_message(self.PageCycle(reverse=False))
                event.stop()
                event.prevent_default()
                return
            if key == "shift+tab":
                self.post_message(self.PageCycle(reverse=True))
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
            self._handle_tab_completion(reverse=False)
            event.prevent_default()

        elif key == "shift+tab":
            # Shift+Tab cycles backwards through completion matches
            self._handle_tab_completion(reverse=True)
            event.prevent_default()

    def _handle_tab_completion(self, reverse: bool = False) -> None:
        """Handle Tab key for cycling through completions."""
        from tui.widgets.command_suggester import CommandSuggester

        suggester = getattr(self, 'suggester', None)
        if not isinstance(suggester, CommandSuggester):
            if self._suggestion:
                self.value = self._suggestion
                self.cursor_position = len(self.value)
            return

        current_value = self.value

        # Cycling if current value is one of our matches
        if self._tab_matches and current_value in self._tab_matches:
            # Directory + Tab twice (didn't cycle away) = descend
            if current_value.endswith("/") and current_value == self._tab_last:
                new_matches = suggester.get_all_matches(current_value)
                if new_matches:
                    self._tab_matches = new_matches
                    self._tab_index = 0
                    self.value = self._tab_matches[0]
                    self._tab_last = ""
                    self.cursor_position = len(self.value)
                    return
            # Mark current before cycling (so next Tab on same dir descends)
            self._tab_last = current_value
            # Cycle through siblings
            if reverse:
                self._tab_index = (self._tab_index - 1) % len(self._tab_matches)
            else:
                self._tab_index = (self._tab_index + 1) % len(self._tab_matches)
            self.value = self._tab_matches[self._tab_index]
        else:
            # Fresh completion
            self._tab_matches = suggester.get_all_matches(current_value)
            if self._tab_matches:
                self._tab_index = len(self._tab_matches) - 1 if reverse else 0
                self.value = self._tab_matches[self._tab_index]
            elif self._suggestion:
                self.value = self._suggestion
            self._tab_last = ""

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
