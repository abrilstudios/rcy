"""
conftest.py - Shared pytest fixtures for RCY tests
"""
import os
import sys
import pytest
import numpy as np

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing"""
    # Create 1 second of audio at 44.1kHz (44100 samples)
    sample_rate = 44100
    duration = 1.0  # seconds
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Generate a simple sine wave at 440Hz
    frequency = 440  # A4 note
    data_left = 0.5 * np.sin(2 * np.pi * frequency * t)
    data_right = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    return {
        'sample_rate': sample_rate,
        'data_left': data_left,
        'data_right': data_right,
        'duration': duration,
        'time': t
    }