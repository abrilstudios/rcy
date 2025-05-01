"""
Examples of how to use the standardized test fixtures from conftest.py.

This file demonstrates best practices for writing tests using the shared fixtures.
"""
import os
import sys
import pathlib
import pytest
import numpy as np

# Add the src directory to Python path
src_dir = pathlib.Path(__file__).parent.parent / "src" / "python"
sys.path.append(str(src_dir))

# Import the module being tested
from config_manager import ConfigManager


class TestConfigFixtureExamples:
    """Examples of using configuration fixtures."""
    
    def test_with_test_config_manager(self, test_config_manager):
        """Example using the test_config_manager fixture.
        
        This demonstrates using a real ConfigManager with test configuration files.
        """
        # Access configuration values
        assert test_config_manager.colors["waveform"] == "#1E88E5"
        assert test_config_manager.strings["app"]["name"] == "RCY Test"
        
        # Test functionality
        result = test_config_manager.get_string("app", "name")
        assert result == "RCY Test"
        
        # This approach uses actual JSON files behind the scenes
        # Good for integration testing where you need real file loading
    
    def test_with_mock_config_manager(self, mock_config_manager):
        """Example using the mock_config_manager fixture.
        
        This demonstrates using a fully mocked ConfigManager.
        """
        # Access pre-configured mock values
        assert mock_config_manager.colors["waveform"] == "#1E88E5"
        
        # We can also configure method return values
        mock_config_manager.get_string.return_value = "Custom Value"
        result = mock_config_manager.get_string("any", "key")
        assert result == "Custom Value"
        
        # We can verify method calls
        mock_config_manager.get_string("app", "name")
        mock_config_manager.get_string.assert_called_with("app", "name")
        
        # This approach is faster and doesn't require file operations
        # Good for unit testing components that use ConfigManager


class TestAudioFixtureExamples:
    """Examples of using audio data fixtures."""
    
    def test_with_sample_audio_data(self, sample_audio_data):
        """Example using the basic sample_audio_data fixture."""
        # Access audio data
        assert sample_audio_data['sample_rate'] == 44100
        assert len(sample_audio_data['data_left']) == 44100  # 1 second @ 44.1kHz
        
        # Perform calculations
        max_amplitude = np.max(np.abs(sample_audio_data['data_left']))
        assert 0.4 < max_amplitude < 0.6  # Should be close to 0.5
        
        # Perform frequency analysis
        from scipy import signal
        freq, power = signal.periodogram(
            sample_audio_data['data_left'], 
            sample_audio_data['sample_rate']
        )
        
        # Find the frequency with the highest power
        peak_freq = freq[np.argmax(power)]
        assert 430 < peak_freq < 450  # Should be close to 440Hz
    
    def test_with_complex_audio_data(self, complex_audio_data):
        """Example using the complex_audio_data fixture."""
        # This fixture contains multiple frequencies and transient points
        assert complex_audio_data['duration'] == 2.0  # 2 seconds long
        
        # Check transient points
        assert len(complex_audio_data['transient_points']) == 3
        
        # The fixture is ideal for testing transient detection
        # For example, if you were testing a function that detects transients:
        #
        # detected_transients = my_transient_detector(complex_audio_data['data_left'])
        # for transient in complex_audio_data['transient_points']:
        #     assert transient in detected_transients
    
    def test_with_temp_wav_file(self, temp_wav_file):
        """Example using the temp_wav_file fixture."""
        # The fixture creates an actual WAV file we can use for testing
        assert os.path.exists(temp_wav_file['path'])
        
        # We could load this using WavAudioProcessor
        # processor = WavAudioProcessor()
        # processor.load_file(str(temp_wav_file['path']))
        # assert processor.sample_rate == temp_wav_file['sample_rate']


class TestGUIFixtureExamples:
    """Examples of using GUI testing fixtures."""
    
    def test_with_qt_app(self, qt_app):
        """Example using the qt_app fixture."""
        # The qt_app fixture provides a QApplication instance necessary for GUI tests
        from PyQt6.QtWidgets import QLabel
        
        # Create a simple QLabel
        label = QLabel("Test")
        assert label.text() == "Test"
        
        # We can test GUI components properly with a QApplication instance
    
    def test_with_mock_waveform_view(self, mock_waveform_view):
        """Example using the mock_waveform_view fixture."""
        # Call methods on the mock
        mock_waveform_view.add_segment(100)
        mock_waveform_view.update()
        
        # Verify method calls
        mock_waveform_view.add_segment.assert_called_with(100)
        assert mock_waveform_view.update.called
        
        # This allows testing controller logic without a real view


class TestPathFixtureExamples:
    """Examples of using path fixtures."""
    
    def test_with_rcy_paths(self, rcy_paths):
        """Example using the rcy_paths fixture."""
        # Access standard paths
        assert rcy_paths['root'].name == 'rcy'
        assert rcy_paths['config'].name == 'config'
        
        # Check that paths exist
        assert rcy_paths['src'].exists()
        assert rcy_paths['python'].exists()
        
        # Use paths to load files
        config_path = rcy_paths['config'] / 'config.json'
        assert config_path.exists()
        
        # This helps tests use consistent path references


if __name__ == "__main__":
    pytest.main(["-v", __file__])