"""
Test suite for ConfigManager with dependency injection.
"""
import json
import os
import pathlib
import pytest
import sys
from unittest.mock import patch

# Add the src/python directory to the Python path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src" / "python"))

from config_manager import ConfigManager


class TestConfigManager:
    """Tests for the ConfigManager with dependency injection."""

    @pytest.fixture
    def test_config_data(self):
        """Create test configuration data."""
        return {
            "colors": {
                "palette": {
                    "waveform": "#1E88E5",
                    "background": "#121212",
                    "segments": "#4CAF50",
                    "text": "#FFFFFF"
                },
                "fonts": {
                    "primary": "Arial"
                }
            },
            "strings": {
                "app": {
                    "name": "RCY Test"
                },
                "ui": {
                    "buttons": {
                        "play": "Play",
                        "stop": "Stop"
                    }
                }
            },
            "ui": {
                "markers": {
                    "width": 2,
                    "style": "solid"
                },
                "waveform": {
                    "resolution": 1000
                }
            },
            "audio": {
                "tailFade": {
                    "enabled": True,
                    "durationMs": 10,
                    "curve": "linear"
                }
            }
        }

    @pytest.fixture
    def test_presets_data(self):
        """Create test presets data."""
        return {
            "test_preset": {
                "name": "Test Preset",
                "path": "test/path.wav",
                "bpm": 120
            }
        }

    @pytest.fixture
    def test_config_files(self, tmp_path, test_config_data, test_presets_data):
        """Create temporary config and preset files for testing."""
        # Create test config files
        config_file = tmp_path / "test_config.json"
        presets_file = tmp_path / "test_presets.json"
        
        # Write test data to files
        with open(config_file, 'w') as f:
            json.dump(test_config_data, f)
        
        with open(presets_file, 'w') as f:
            json.dump(test_presets_data, f)
        
        return {
            "config_path": config_file,
            "presets_path": presets_file
        }

    def test_config_with_custom_paths(self, test_config_files, test_config_data, test_presets_data):
        """Test ConfigManager initialization with custom paths."""
        # Create a ConfigManager with custom paths
        config_mgr = ConfigManager(
            cfg_path=test_config_files["config_path"],
            presets_path=test_config_files["presets_path"],
            exit_on_error=False
        )
        
        # Verify configuration was loaded correctly
        assert config_mgr.colors["waveform"] == test_config_data["colors"]["palette"]["waveform"]
        assert config_mgr.strings["app"]["name"] == test_config_data["strings"]["app"]["name"]
        assert config_mgr.ui["markers"]["width"] == test_config_data["ui"]["markers"]["width"]
        assert config_mgr.audio["tailFade"]["enabled"] == test_config_data["audio"]["tailFade"]["enabled"]
        assert config_mgr.presets["test_preset"]["name"] == test_presets_data["test_preset"]["name"]

    def test_default_paths(self):
        """Test default path resolution logic."""
        config_mgr = ConfigManager(exit_on_error=False)  # Don't exit on error for testing
        
        # Since we're not mocking file operations, this will likely raise an exception
        # in test environments without actual config files. But we can still test the path resolution.
        expected_config_path = pathlib.Path(__file__).parent.parent / "config" / "config.json"
        expected_presets_path = pathlib.Path(__file__).parent.parent / "presets" / "presets.json"
        
        assert str(config_mgr.cfg_path) == str(expected_config_path)
        assert str(config_mgr.presets_path) == str(expected_presets_path)

    def test_config_missing_key(self, tmp_path):
        """Test handling of missing configuration keys."""
        # Create incomplete config
        config_file = tmp_path / "incomplete_config.json"
        with open(config_file, 'w') as f:
            json.dump({"colors": {}}, f)  # Missing palette key
        
        # Empty presets file
        presets_file = tmp_path / "empty_presets.json"
        with open(presets_file, 'w') as f:
            json.dump({}, f)
        
        # This should raise a KeyError in test mode
        with pytest.raises(KeyError):
            ConfigManager(
                cfg_path=config_file, 
                presets_path=presets_file,
                exit_on_error=False
            )

    def test_config_file_not_found(self, tmp_path):
        """Test handling of missing configuration files."""
        non_existent_file = tmp_path / "does_not_exist.json"
        
        # This should raise a RuntimeError in test mode
        with pytest.raises(RuntimeError):
            ConfigManager(
                cfg_path=non_existent_file,
                exit_on_error=False
            )

    def test_get_string(self, test_config_files):
        """Test the get_string method."""
        config_mgr = ConfigManager(
            cfg_path=test_config_files["config_path"],
            presets_path=test_config_files["presets_path"],
            exit_on_error=False
        )
        
        # Test existing string
        assert config_mgr.get_string("app", "name") == "RCY Test"
        
        # Test non-existent string with default
        assert config_mgr.get_string("app", "nonexistent", "Default") == "Default"
        
        # Test non-existent string without default
        assert config_mgr.get_string("app", "nonexistent") == "nonexistent"

    def test_get_nested_string(self, test_config_files):
        """Test the get_nested_string method."""
        config_mgr = ConfigManager(
            cfg_path=test_config_files["config_path"],
            presets_path=test_config_files["presets_path"],
            exit_on_error=False
        )
        
        # Test existing nested string
        assert config_mgr.get_nested_string("app.name") == "RCY Test"
        assert config_mgr.get_nested_string("ui.buttons.play") == "Play"
        
        # Test non-existent nested string with default
        assert config_mgr.get_nested_string("app.nonexistent", "Default") == "Default"
        
        # Test non-existent nested string without default
        assert config_mgr.get_nested_string("app.nonexistent") == "app.nonexistent"

if __name__ == "__main__":
    pytest.main(["-v", __file__])