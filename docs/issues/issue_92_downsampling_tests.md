# Issue 92: Create Proper Tests for Downsampling Functionality

## Description
We need to create proper tests for the audio waveform downsampling functionality. Previous testing approaches became overly complex with mocking issues and import conflicts. 

A simpler, more focused testing approach is needed that verifies:
1. Downsampling functions work correctly with different input parameters
2. Controller correctly applies downsampling based on config
3. The view receives appropriately sized data

## Approach
1. Add unit tests for the individual downsampling functions
2. Create focused controller tests that verify downsampling decisions
3. Ensure tests follow CLAUDE.md guidelines for imports and structure

## Technical Details
The downsampling functionality is located in:
- `src/python/utils/audio_preview.py`: Core downsampling functions
- `src/python/rcy_controller.py`: Integration with configuration and UI

The controller imports the downsampling functions and uses them based on configuration settings.

## Acceptance Criteria
- Tests should verify all downsampling functions work correctly
- Tests should verify controller applies downsampling based on configuration
- Tests must follow CLAUDE.md guidelines for imports and code structure
- All tests should pass without patching imports or complex mocking