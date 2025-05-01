"""
conftest.py - Shared pytest fixtures for RCY tests

This module provides standardized test fixtures for use across all RCY tests.
It includes fixtures for:
- Path setup and Python path configuration
- Configuration management
- Sample audio data generation
- GUI testing support
- Temporary test directories with predefined files
"""
import os
import sys
import json
import pathlib
import tempfile
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# Add the src/python directory to the Python path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src" / "python"))

# Imports from RCY modules (now that path is configured)
from config_manager import ConfigManager


# Path and Environment Fixtures
# ----------------------------

@pytest.fixture
def rcy_paths():
    """Provide standard paths to key RCY directories."""
    root_dir = pathlib.Path(__file__).parent.parent
    return {
        'root': root_dir,
        'src': root_dir / 'src',
        'python': root_dir / 'src' / 'python',
        'config': root_dir / 'config',
        'presets': root_dir / 'presets',
        'audio': root_dir / 'audio',
        'tests': root_dir / 'tests'
    }


# Configuration Fixtures
# ---------------------

@pytest.fixture
def test_config_data():
    """Create minimal test configuration data."""
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
def test_presets_data():
    """Create test presets data."""
    return {
        "test_preset": {
            "name": "Test Preset",
            "path": "test/path.wav",
            "bpm": 120
        }
    }


@pytest.fixture
def test_config_files(tmp_path, test_config_data, test_presets_data):
    """Create temporary config and preset files."""
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
        "presets_path": presets_file,
        "tmp_path": tmp_path
    }


@pytest.fixture
def test_config_manager(test_config_files):
    """Create a ConfigManager instance with test configuration."""
    return ConfigManager(
        cfg_path=test_config_files["config_path"],
        presets_path=test_config_files["presets_path"],
        exit_on_error=False
    )


@pytest.fixture
def mock_config_manager():
    """Create a mocked ConfigManager for lightweight tests."""
    mock_manager = MagicMock(spec=ConfigManager)
    
    # Set up common attributes
    mock_manager.colors = {
        "waveform": "#1E88E5",
        "background": "#121212",
        "segments": "#4CAF50",
        "text": "#FFFFFF"
    }
    mock_manager.fonts = {"primary": "Arial"}
    mock_manager.strings = {
        "app": {"name": "RCY Test"},
        "ui": {"buttons": {"play": "Play", "stop": "Stop"}}
    }
    mock_manager.ui = {
        "markers": {"width": 2, "style": "solid"},
        "waveform": {"resolution": 1000}
    }
    mock_manager.audio = {
        "tailFade": {"enabled": True, "durationMs": 10, "curve": "linear"}
    }
    mock_manager.presets = {
        "test_preset": {"name": "Test Preset", "path": "test/path.wav", "bpm": 120}
    }
    
    # Set up common methods
    mock_manager.get_string.return_value = "Test String"
    mock_manager.get_nested_string.return_value = "Test Nested String"
    mock_manager.get_ui_setting.return_value = 42
    mock_manager.get_preset_info.return_value = {"name": "Test Preset"}
    mock_manager.get_setting.return_value = "Test Setting"
    
    return mock_manager


# Audio Data Fixtures
# ------------------

@pytest.fixture
def sample_audio_data():
    """Generate basic sine wave audio data for testing."""
    # Create 1 second of audio at 44.1kHz (44100 samples)
    sample_rate = 44100
    duration = 1.0  # seconds
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Generate a simple sine wave at 440Hz (A4 note)
    frequency = 440
    data_left = 0.5 * np.sin(2 * np.pi * frequency * t)
    data_right = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    return {
        'sample_rate': sample_rate,
        'data_left': data_left,
        'data_right': data_right,
        'duration': duration,
        'time': t,
        'frequency': frequency
    }


@pytest.fixture
def complex_audio_data():
    """Generate more complex audio data with multiple frequencies and features."""
    # Create 2 seconds of audio at 44.1kHz
    sample_rate = 44100
    duration = 2.0  # seconds
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Create a more complex waveform with multiple frequencies
    # Base frequency (A4 = 440Hz) + third harmonic + fifth harmonic
    data_left = 0.5 * np.sin(2 * np.pi * 440 * t) + \
                0.25 * np.sin(2 * np.pi * 660 * t) + \
                0.125 * np.sin(2 * np.pi * 880 * t)
    
    # Add some "transients" at specific points for testing transient detection
    transient_points = [
        int(0.5 * sample_rate),   # At 0.5 seconds
        int(1.0 * sample_rate),   # At 1.0 second
        int(1.5 * sample_rate),   # At 1.5 seconds
    ]
    
    for point in transient_points:
        # Add a short burst at each transient point (50ms window)
        window = 0.05 * sample_rate
        for i in range(int(window)):
            if point + i < len(data_left):
                data_left[point + i] = 0.9 * np.sin(2 * np.pi * 1000 * (i / sample_rate))
    
    # Create right channel with slight variation
    data_right = data_left.copy()
    data_right += 0.1 * np.sin(2 * np.pi * 500 * t)  # Add a different frequency component
    
    # Normalize to avoid clipping
    max_amplitude = max(np.max(np.abs(data_left)), np.max(np.abs(data_right)))
    if max_amplitude > 1.0:
        data_left = data_left / max_amplitude
        data_right = data_right / max_amplitude
    
    return {
        'sample_rate': sample_rate,
        'data_left': data_left,
        'data_right': data_right,
        'duration': duration,
        'time': t,
        'transient_points': transient_points,
        'transient_times': [p / sample_rate for p in transient_points]
    }


@pytest.fixture
def temp_wav_file(tmp_path, sample_audio_data):
    """Create a temporary WAV file for testing."""
    try:
        import soundfile as sf
    except ImportError:
        pytest.skip("soundfile not installed, skipping test")
    
    # Create a temporary WAV file
    wav_path = tmp_path / "test_audio.wav"
    
    # Interleave channels for stereo
    stereo_data = np.column_stack((
        sample_audio_data['data_left'], 
        sample_audio_data['data_right']
    ))
    
    # Write to WAV file
    sf.write(
        str(wav_path), 
        stereo_data, 
        sample_audio_data['sample_rate']
    )
    
    return {
        'path': wav_path,
        'sample_rate': sample_audio_data['sample_rate'],
        'duration': sample_audio_data['duration'],
        'num_channels': 2
    }


# GUI Testing Fixtures
# ------------------

@pytest.fixture(scope="session")
def qt_app():
    """Create a QApplication instance that persists for the test session."""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PyQt6 not installed, skipping test")
    
    # Check if an instance already exists
    app = QApplication.instance()
    if app is None:
        # Create a new application with dummy arguments
        app = QApplication([''])
    
    yield app


@pytest.fixture
def mock_waveform_view(qt_app):
    """Create a mocked waveform view for testing."""
    from unittest.mock import MagicMock
    
    mock_view = MagicMock()
    mock_view.update = MagicMock()
    mock_view.set_data = MagicMock()
    mock_view.add_segment = MagicMock()
    mock_view.clear_segments = MagicMock()
    
    return mock_view