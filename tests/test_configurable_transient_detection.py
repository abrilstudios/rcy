import os
import json
import sys
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# Add the src/python directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "python"))

# Import the modules we want to test
from audio_processor import WavAudioProcessor
from rcy_controller import RcyController
from config_manager import ConfigManager


class TestConfigurableTransientDetection:
    """Tests for configurable transient detection parameters"""
    
    @pytest.fixture
    def mock_audio_config(self):
        """Create a mock audio.json config"""
        return {
            "stereoDisplay": True,
            "transientDetection": {
                "threshold": 0.3,
                "waitTime": 2,
                "preMax": 3,
                "postMax": 4,
                "deltaFactor": 0.2
            }
        }
    
    @pytest.fixture
    def mock_config_manager(self, mock_audio_config):
        """Create a mock config manager that returns our test config"""
        with patch('config_manager.ConfigManager.get_value_from_json_file') as mock_get_value:
            mock_get_value.return_value = mock_audio_config.get("transientDetection", {})
            yield
    
    def test_transient_detection_parameters_from_config(self, mock_config_manager):
        """Test that transient detection parameters are taken from the config file"""
        # Create the needed mocks
        with patch('librosa.onset.onset_strength') as mock_onset_strength:
            # Set up mock return value
            mock_onset_strength.return_value = np.array([0.1, 0.2, 0.3])
            
            with patch('librosa.onset.onset_detect') as mock_onset_detect:
                mock_onset_detect.return_value = np.array([1, 2, 3])
                
                with patch('librosa.frames_to_samples') as mock_frames_to_samples:
                    mock_frames_to_samples.return_value = np.array([100, 200, 300])
                    
                    # Create an instance of WavAudioProcessor directly
                    processor = WavAudioProcessor.__new__(WavAudioProcessor)
                    processor.data_left = np.zeros(1000)  # Mock audio data
                    processor.sample_rate = 44100
                    processor.segments = []
                    
                    # Call the method we're testing
                    processor.split_by_transients()
                    
                    # Check that librosa.onset.onset_detect was called with parameters from config
                    args, kwargs = mock_onset_detect.call_args
                    
                    # Verify parameters
                    assert kwargs['delta'] == 0.3 * 0.2  # threshold * deltaFactor
                    assert kwargs['wait'] == 2
                    assert kwargs['pre_max'] == 3
                    assert kwargs['post_max'] == 4
                    
                    # Verify the segments were set correctly
                    assert processor.segments == [100, 200, 300]
    
    def test_controller_initializes_threshold_from_config(self, mock_config_manager):
        """Test that controller initializes the threshold from config"""
        # Create a mock model
        model = MagicMock()
        
        # Instantiate the controller
        controller = RcyController(model)
        
        # Threshold should be initialized from the config
        assert controller.threshold == 0.3

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])