"""
Tests for downsampling integration in RCY controller
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# Use relative imports correctly for pytest
from src.python.rcy_controller import RcyController


class TestDownsamplingIntegration:
    """Tests for ensuring downsampling is properly integrated at controller level"""

    @pytest.fixture
    def mock_model(self):
        """Create a mock audio processor model"""
        model = MagicMock()
        
        # Mock data generation
        sample_rate = 44100
        duration = 5.0  # seconds
        model.sample_rate = sample_rate
        model.total_time = duration
        
        # Create test data
        num_samples = int(sample_rate * duration)
        time = np.linspace(0, duration, num_samples)
        data_left = np.sin(2 * np.pi * 440 * time)  # 440 Hz sine wave
        data_right = np.sin(2 * np.pi * 440 * time)
        
        # Mock get_data to return raw data without downsampling
        def mock_get_data(start_time, end_time):
            start_idx = int(start_time * sample_rate)
            end_idx = int(end_time * sample_rate)
            return (time[start_idx:end_idx], 
                    data_left[start_idx:end_idx], 
                    data_right[start_idx:end_idx])
            
        model.get_data.side_effect = mock_get_data
        return model
    
    @pytest.fixture
    def mock_view(self):
        """Create a mock view"""
        view = MagicMock()
        view.width.return_value = 800
        view.get_scroll_position.return_value = 0
        return view
    
    @pytest.fixture
    def controller(self, mock_model, mock_view):
        """Create a controller with mock model and view"""
        controller = RcyController(mock_model)
        controller.set_view(mock_view)
        return controller
    
    @patch('src.python.utils.audio_preview.get_downsampled_data')
    def test_controller_applies_downsampling(self, mock_get_downsampled, controller, mock_view):
        """Test that controller applies downsampling based on config"""
        # Set up the test
        controller.visible_time = 2.0  # 2 seconds of visible audio
        
        # Override config to ensure downsampling is enabled
        with patch('src.python.config_manager.config.get_value_from_json_file') as mock_config:
            mock_config.return_value = {
                "enabled": True,
                "method": "envelope",
                "alwaysApply": True,
                "targetLength": 2000,
                "minLength": 1000,
                "maxLength": 5000
            }
            
            # Mock the downsampling function
            mock_time = np.linspace(0, 2.0, 2000)
            mock_left = np.zeros(2000)
            mock_right = np.zeros(2000)
            mock_get_downsampled.return_value = (mock_time, mock_left, mock_right)
            
            # Call the method under test
            controller.update_view()
            
            # Assertions
            # 1. View's update_plot should be called with downsampled data
            mock_view.update_plot.assert_called_once()
            
            # 2. Downsampling function should be called
            mock_get_downsampled.assert_called_once()
            
            # 3. Model's get_data should be called for raw data
            mock_model = controller.model
            mock_model.get_data.assert_called_once()
    
    @patch('src.python.utils.audio_preview.get_downsampled_data')
    def test_controller_respects_config_disabled(self, mock_get_downsampled, controller, mock_view):
        """Test that controller respects disabled downsampling in config"""
        # Set up the test
        controller.visible_time = 2.0
        
        # Override config to disable downsampling
        with patch('src.python.config_manager.config.get_value_from_json_file') as mock_config:
            mock_config.return_value = {
                "enabled": False  # Downsampling disabled
            }
            
            # Call the method under test
            controller.update_view()
            
            # Assertions
            # Downsampling function should not be called
            mock_get_downsampled.assert_not_called()
    
    @patch('src.python.utils.audio_preview.get_downsampled_data')
    def test_controller_calculates_target_length_from_view_size(self, mock_get_downsampled, controller, mock_view):
        """Test that controller calculates target length based on view size and config limits"""
        # Set up the test with a wider view
        mock_view.width.return_value = 1500
        controller.visible_time = 2.0
        
        # Override config
        with patch('src.python.config_manager.config.get_value_from_json_file') as mock_config:
            mock_config.return_value = {
                "enabled": True,
                "method": "envelope",
                "alwaysApply": True,
                "targetLength": 2000,
                "minLength": 1000,
                "maxLength": 5000
            }
            
            # Mock for downsampling function
            mock_get_downsampled.return_value = (np.zeros(3000), np.zeros(3000), np.zeros(3000))
            
            # Call the method under test
            controller.update_view()
            
            # Assertions
            # Check that target_length is calculated based on view width
            # It should be width * 2 = 1500 * 2 = 3000 (between min and max)
            _, args, _ = mock_get_downsampled.mock_calls[0]
            target_length = args[3]  # Assuming target_length is the 4th parameter
            assert target_length == 3000