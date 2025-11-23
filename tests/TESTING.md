# RCY Testing Guide

This document provides guidance on testing the RCY codebase using our standardized testing infrastructure.

## Test Structure

### Test File Organization

All test files are consolidated in the `tests/` directory, organized as follows:

- **Main test files**: Root level of `tests/` directory for primary test modules
- **Utility tests**: `tests/utils/` for tests related to utility modules
- **Waveform tests**: `tests/waveform/` for tests related to waveform-specific functionality

Example test files:
- `test_audio_processing_pipeline.py` - Tests for audio processing pipeline
- `test_config_manager.py` - Tests for configuration management
- `test_waveform_backends.py` - Tests for waveform backend implementations
- `test_pyqtgraph_minimal.py` - Minimal PyQtGraph visualization tests
- `utils/test_audio_preview.py` - Tests for audio preview utilities
- `waveform/test_waveform_imports.py` - Tests for waveform module imports

## Test Environment Setup

### PYTHONPATH Configuration

The pytest configuration in `pytest.ini` automatically handles PYTHONPATH setup. When running tests from the project root, pytest will:

1. Include the project root (`.`) in the Python path
2. Include `src/python` directory for module imports

```bash
# Run tests from the project root (pytest.ini handles PYTHONPATH)
pytest

# Run all tests with collection display
pytest --collect-only

# Or manually specify PYTHONPATH (for direct Python execution)
PYTHONPATH=./src/python pytest
```

### Running Specific Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_audio_processor.py

# Run a specific test class
pytest tests/test_audio_processor.py::TestAudioProcessor

# Run a specific test method
pytest tests/test_audio_processor.py::TestAudioProcessor::test_load_file
```

## Standardized Test Fixtures

RCY provides a comprehensive set of test fixtures in `conftest.py` to make testing easier and more consistent. These fixtures provide standardized test data, mock objects, and environment setup.

### Configuration Fixtures

| Fixture | Description |
|---------|-------------|
| `test_config_data` | Dictionary with standard test configuration |
| `test_presets_data` | Dictionary with test preset definitions |
| `test_config_files` | Temporary config and preset JSON files |
| `test_config_manager` | ConfigManager instance with test configuration |
| `mock_config_manager` | Mocked ConfigManager for unit testing |

Example usage:

```python
def test_with_config(test_config_manager):
    # Use the test ConfigManager
    assert test_config_manager.get_string("app", "name") == "RCY Test"
```

### Audio Data Fixtures

| Fixture | Description |
|---------|-------------|
| `sample_audio_data` | Basic 1-second sine wave audio data |
| `complex_audio_data` | More complex audio with multiple frequencies and transients |
| `temp_wav_file` | Temporary WAV file for testing file operations |

Example usage:

```python
def test_audio_processing(sample_audio_data):
    # Process audio data
    result = my_audio_processor(sample_audio_data['data_left'])
    assert len(result) == sample_audio_data['sample_rate']
```

### GUI Testing Fixtures

| Fixture | Description |
|---------|-------------|
| `qt_app` | QApplication instance for GUI tests (session scope) |
| `mock_waveform_view` | Mock of waveform view for testing controllers |

Example usage:

```python
def test_gui_component(qt_app):
    # Create and test a PyQt widget
    from PyQt6.QtWidgets import QPushButton
    button = QPushButton("Test")
    assert button.text() == "Test"
```

### Path and Environment Fixtures

| Fixture | Description |
|---------|-------------|
| `rcy_paths` | Dictionary with standard RCY paths |

Example usage:

```python
def test_with_paths(rcy_paths):
    config_file = rcy_paths['config'] / 'config.json'
    assert config_file.exists()
```

## Testing Best Practices

### Use the Standardized Fixtures

Always prefer the standardized fixtures over creating your own test data. This ensures consistency across tests and makes them more maintainable.

### Test Organization

1. Group related tests in classes
2. Name test methods clearly (start with `test_`)
3. Use descriptive docstrings for test methods

### Mocking vs. Real Objects

- Use `mock_config_manager` for fast unit tests
- Use `test_config_manager` for tests that need real file loading behavior
- Use mocks for external dependencies and services

### Test Independence

Each test should be independent and not rely on the state from other tests. Use fixtures to set up the required state for each test.

### Testing Core Components

#### Audio Processing

Use `sample_audio_data` or `complex_audio_data` fixtures to test audio processing functions:

```python
def test_transient_detection(complex_audio_data):
    transients = detect_transients(complex_audio_data['data_left'])
    assert len(transients) > 0
```

#### Configuration

Use `test_config_manager` or `mock_config_manager` to test components that use configuration:

```python
def test_component_with_config(mock_config_manager):
    # Configure the mock for this test
    mock_config_manager.get_ui_setting.return_value = 42
    
    # Test your component that uses config
    component = MyComponent(config=mock_config_manager)
    result = component.do_something()
    assert result == 42
```

#### GUI Components

Use `qt_app` for testing GUI components and `mock_waveform_view` for testing controllers:

```python
def test_controller(mock_waveform_view):
    controller = Controller(view=mock_waveform_view)
    controller.add_segment(100)
    mock_waveform_view.add_segment.assert_called_with(100)
```

## Example Tests

See `test_fixture_usage_examples.py` for detailed examples of how to use the standardized fixtures in different testing scenarios.