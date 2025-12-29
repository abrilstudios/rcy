"""Tests for CommandSuggester tab completion."""

import asyncio
import os
import tempfile
import pytest
from pathlib import Path

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


class TestImportPathCompletion:
    """Tests for file path completion in /import command."""

    @pytest.fixture
    def suggester(self):
        return CommandSuggester(config_manager=None)

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some WAV files
            Path(tmpdir, "beat1.wav").touch()
            Path(tmpdir, "beat2.wav").touch()
            Path(tmpdir, "drums.wav").touch()
            # Create a non-WAV file (should be excluded)
            Path(tmpdir, "notes.txt").touch()
            # Create a subdirectory
            subdir = Path(tmpdir, "samples")
            subdir.mkdir()
            Path(subdir, "kick.wav").touch()
            # Create a hidden file (should be excluded)
            Path(tmpdir, ".hidden.wav").touch()
            yield tmpdir

    def test_complete_import_in_directory(self, suggester, temp_dir):
        """Test completing files in a directory."""
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/"))
        assert result is not None
        # Should suggest first match alphabetically (beat1.wav or samples/)
        assert result.startswith(f"/import {temp_dir}/")

    def test_complete_import_partial_filename(self, suggester, temp_dir):
        """Test completing a partial filename."""
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/beat"))
        assert result is not None
        assert "beat1.wav" in result or "beat2.wav" in result

    def test_complete_import_exact_prefix(self, suggester, temp_dir):
        """Test completing with exact prefix."""
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/drum"))
        assert result == f"/import {temp_dir}/drums.wav"

    def test_complete_import_excludes_non_wav(self, suggester, temp_dir):
        """Test that non-WAV files are excluded."""
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/note"))
        # notes.txt should not match
        assert result is None

    def test_complete_import_excludes_hidden(self, suggester, temp_dir):
        """Test that hidden files are excluded."""
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/.hid"))
        assert result is None

    def test_complete_import_includes_directories(self, suggester, temp_dir):
        """Test that directories are included with trailing slash."""
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/sam"))
        assert result == f"/import {temp_dir}/samples/"

    def test_complete_import_nonexistent_dir(self, suggester):
        """Test completing in nonexistent directory."""
        result = _run(suggester.get_suggestion("/import /nonexistent/path/"))
        assert result is None

    def test_get_all_import_matches(self, suggester, temp_dir):
        """Test getting all import matches for Tab cycling."""
        matches = suggester.get_all_matches(f"/import {temp_dir}/beat")
        assert len(matches) == 2
        assert f"/import {temp_dir}/beat1.wav" in matches
        assert f"/import {temp_dir}/beat2.wav" in matches

    def test_get_all_import_matches_empty_dir(self, suggester):
        """Test getting matches in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            matches = suggester.get_all_matches(f"/import {tmpdir}/")
            assert matches == []

    def test_complete_import_case_insensitive(self, suggester, temp_dir):
        """Test that filename matching is case-insensitive."""
        # Create a file with different case
        Path(temp_dir, "LOUD.wav").touch()
        result = _run(suggester.get_suggestion(f"/import {temp_dir}/lou"))
        assert result is not None
        assert "LOUD.wav" in result
