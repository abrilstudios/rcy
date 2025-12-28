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
        result = _run(suggester.get_suggestion("/pre"))
        assert result == "/preset"

    def test_complete_slice_command(self, suggester):
        """Test completing /sl to /slice."""
        result = _run(suggester.get_suggestion("/sl"))
        assert result == "/slice"

    def test_complete_export(self, suggester):
        """Test completing /exp to /export."""
        result = _run(suggester.get_suggestion("/exp"))
        assert result == "/export"

    def test_no_completion_for_unknown(self, suggester):
        """Test no completion for unknown prefix."""
        result = _run(suggester.get_suggestion("/xyz"))
        assert result is None

    def test_no_completion_without_slash(self, suggester):
        """Test no completion for input not starting with /."""
        result = _run(suggester.get_suggestion("preset"))
        assert result is None

    def test_no_completion_for_just_slash(self, suggester):
        """Test no completion for just /."""
        result = _run(suggester.get_suggestion("/"))
        assert result is None

    def test_alias_completion(self, suggester):
        """Test that aliases are also completed."""
        # Check that some aliases exist in TOOL_ALIASES
        assert "p" in TOOL_ALIASES  # p -> preset
        result = _run(suggester.get_suggestion("/p"))
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
        result = _run(suggester.get_suggestion("/preset rl_"))
        assert result is not None
        assert result.startswith("/preset rl_")

    def test_complete_preset_empty_prefix(self, suggester):
        """Test completing preset with empty prefix."""
        result = _run(suggester.get_suggestion("/preset "))
        assert result is not None
        # Should suggest first preset alphabetically
        assert result.startswith("/preset ")

    def test_complete_preset_no_match(self, suggester):
        """Test no completion when no presets match."""
        result = _run(suggester.get_suggestion("/preset xyz"))
        assert result is None

    def test_complete_preset_amen(self, suggester):
        """Test completing /preset amen."""
        result = _run(suggester.get_suggestion("/preset amen"))
        assert result == "/preset amen_classic"

    def test_no_preset_completion_without_config(self):
        """Test no preset completion when config is None."""
        suggester = CommandSuggester(config_manager=None)
        result = _run(suggester.get_suggestion("/preset rl_"))
        assert result is None


class TestEP133Completion:
    """Tests for EP-133 subcommand and bank completion."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=None)

    def test_complete_subcommand_empty(self, suggester):
        """Test completing subcommand with empty prefix."""
        result = _run(suggester.get_suggestion("/ep133 "))
        # Returns first subcommand in workflow order: 'connect'
        assert result == "/ep133 connect"

    def test_complete_subcommand_partial(self, suggester):
        """Test completing partial subcommand."""
        result = _run(suggester.get_suggestion("/ep133 up"))
        assert result == "/ep133 upload"

    def test_complete_subcommand_connect(self, suggester):
        """Test completing /ep133 co to /ep133 connect."""
        result = _run(suggester.get_suggestion("/ep133 co"))
        assert result == "/ep133 connect"

    def test_complete_upload_bank_empty(self, suggester):
        """Test completing bank after upload with empty prefix."""
        result = _run(suggester.get_suggestion("/ep133 upload "))
        assert result == "/ep133 upload A"

    def test_complete_upload_bank_b(self, suggester):
        """Test completing bank B after upload."""
        result = _run(suggester.get_suggestion("/ep133 upload B"))
        assert result == "/ep133 upload B"

    def test_complete_clear_bank_lowercase(self, suggester):
        """Test completing bank with lowercase input after clear."""
        result = _run(suggester.get_suggestion("/ep133 clear c"))
        assert result == "/ep133 clear C"

    def test_complete_bank_invalid(self, suggester):
        """Test no completion for invalid bank letter."""
        result = _run(suggester.get_suggestion("/ep133 upload X"))
        assert result is None

    def test_no_bank_for_connect(self, suggester):
        """Test no bank completion for connect subcommand."""
        result = _run(suggester.get_suggestion("/ep133 connect "))
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
        result = _run(suggester.get_suggestion("/preset  rl"))
        assert result is not None
        assert result.startswith("/preset rl_")

    def test_unknown_command_with_argument(self, suggester):
        """Test no completion for unknown command with argument."""
        result = _run(suggester.get_suggestion("/unknown arg"))
        assert result is None

    def test_empty_string(self, suggester):
        """Test handling empty string."""
        result = _run(suggester.get_suggestion(""))
        assert result is None


class TestGetAllMatches:
    """Tests for get_all_matches method used for Tab cycling."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=MockConfigManager())

    def test_all_preset_matches(self, suggester):
        """Test getting all preset matches."""
        matches = suggester.get_all_matches("/preset rl_")
        assert len(matches) == 3  # rl_hot_pants, rl_shack_up, rl_walk_this_way
        assert all(m.startswith("/preset rl_") for m in matches)

    def test_all_command_matches(self, suggester):
        """Test getting all command matches."""
        matches = suggester.get_all_matches("/pre")
        # Should include 'preset' and 'presets'
        assert "/preset" in matches
        assert "/presets" in matches

    def test_no_matches(self, suggester):
        """Test getting no matches."""
        matches = suggester.get_all_matches("/xyz")
        assert matches == []

    def test_all_ep133_subcommand_matches(self, suggester):
        """Test getting all EP-133 subcommand matches."""
        matches = suggester.get_all_matches("/ep133 ")
        # Order matches workflow: connect, disconnect, status, set, list, upload, clear
        expected = [
            "/ep133 connect",
            "/ep133 disconnect",
            "/ep133 status",
            "/ep133 set",
            "/ep133 list",
            "/ep133 upload",
            "/ep133 clear",
        ]
        assert matches == expected

    def test_all_ep133_bank_matches(self, suggester):
        """Test getting all EP-133 bank matches for upload."""
        matches = suggester.get_all_matches("/ep133 upload ")
        assert matches == [
            "/ep133 upload A",
            "/ep133 upload B",
            "/ep133 upload C",
            "/ep133 upload D",
        ]
