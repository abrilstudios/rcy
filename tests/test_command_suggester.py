"""Tests for CommandSuggester tab completion."""

import asyncio
import pytest

from tui.widgets.command_suggester import CommandSuggester
from tui.agents.tools import TOOL_SCHEMAS, TOOL_ALIASES


class MockConfigManager:
    """Mock config manager for testing preset completion."""

    def __init__(self, presets=None):
        self._presets = presets or [
            ("amen_classic", "Amen Break"),
            ("think_break", "Think (About It)"),
            ("apache_break", "Apache"),
            ("rl_hot_pants", "Hot Pants"),
            ("rl_walk_this_way", "Walk This Way"),
            ("rl_shack_up", "Shack Up"),
        ]

    def get_preset_list(self):
        return self._presets


def _run(coro):
    """Helper to run async coroutines in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestCommandCompletion:
    """Tests for command name completion."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=None)

    def test_complete_partial_command(self, suggester):
        """Test completing a partial command name."""
        result = _run(suggester.get_suggestion("/pre", 4))
        assert result == "/preset"

    def test_complete_slice_command(self, suggester):
        """Test completing /sl to /slice."""
        result = _run(suggester.get_suggestion("/sl", 3))
        assert result == "/slice"

    def test_complete_export(self, suggester):
        """Test completing /exp to /export."""
        result = _run(suggester.get_suggestion("/exp", 4))
        assert result == "/export"

    def test_no_completion_for_unknown(self, suggester):
        """Test no completion for unknown prefix."""
        result = _run(suggester.get_suggestion("/xyz", 4))
        assert result is None

    def test_no_completion_without_slash(self, suggester):
        """Test no completion for input not starting with /."""
        result = _run(suggester.get_suggestion("preset", 6))
        assert result is None

    def test_no_completion_for_just_slash(self, suggester):
        """Test no completion for just /."""
        result = _run(suggester.get_suggestion("/", 1))
        assert result is None

    def test_alias_completion(self, suggester):
        """Test that aliases are also completed."""
        # Check that some aliases exist in TOOL_ALIASES
        assert "p" in TOOL_ALIASES  # p -> preset
        result = _run(suggester.get_suggestion("/p", 2))
        # Could complete to 'p' (alias), 'preset', 'play', or 'presets'
        assert result is not None
        assert result.startswith("/p")


class TestPresetCompletion:
    """Tests for preset ID completion."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=MockConfigManager())

    def test_complete_preset_with_prefix(self, suggester):
        """Test completing preset with prefix."""
        result = _run(suggester.get_suggestion("/preset rl_", 11))
        assert result is not None
        assert result.startswith("/preset rl_")

    def test_complete_preset_empty_prefix(self, suggester):
        """Test completing preset with empty prefix."""
        result = _run(suggester.get_suggestion("/preset ", 8))
        assert result is not None
        # Should suggest first preset alphabetically
        assert result.startswith("/preset ")

    def test_complete_preset_no_match(self, suggester):
        """Test no completion when no presets match."""
        result = _run(suggester.get_suggestion("/preset xyz", 11))
        assert result is None

    def test_complete_preset_amen(self, suggester):
        """Test completing /preset amen."""
        result = _run(suggester.get_suggestion("/preset amen", 12))
        assert result == "/preset amen_classic"

    def test_no_preset_completion_without_config(self):
        """Test no preset completion when config is None."""
        suggester = CommandSuggester(config_manager=None)
        result = _run(suggester.get_suggestion("/preset rl_", 11))
        assert result is None


class TestBankCompletion:
    """Tests for EP-133 bank completion."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=None)

    def test_complete_bank_empty(self, suggester):
        """Test completing bank with empty prefix."""
        result = _run(suggester.get_suggestion("/ep133_upload_bank ", 19))
        assert result == "/ep133_upload_bank A"

    def test_complete_bank_b(self, suggester):
        """Test completing bank B."""
        result = _run(suggester.get_suggestion("/ep133_upload_bank B", 20))
        assert result == "/ep133_upload_bank B"

    def test_complete_bank_lowercase(self, suggester):
        """Test completing bank with lowercase input."""
        result = _run(suggester.get_suggestion("/ep133_upload_bank c", 20))
        assert result == "/ep133_upload_bank C"

    def test_complete_bank_invalid(self, suggester):
        """Test no completion for invalid bank letter."""
        result = _run(suggester.get_suggestion("/ep133_upload_bank X", 20))
        assert result is None


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=MockConfigManager())

    def test_command_with_extra_spaces(self, suggester):
        """Test that extra whitespace is normalized."""
        # Python's split() without separator collapses whitespace
        # So "/preset  rl" becomes ["preset", "rl"] and works normally
        result = _run(suggester.get_suggestion("/preset  rl", 11))
        assert result is not None
        assert result.startswith("/preset rl_")

    def test_unknown_command_with_argument(self, suggester):
        """Test no completion for unknown command with argument."""
        result = _run(suggester.get_suggestion("/unknown arg", 12))
        assert result is None

    def test_empty_string(self, suggester):
        """Test handling empty string."""
        result = _run(suggester.get_suggestion("", 0))
        assert result is None
