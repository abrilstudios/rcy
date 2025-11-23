# RCY Architecture

This document describes the system architecture of RCY, including its Model-View-Controller (MVC) pattern, component responsibilities, and modernization phases.

## Overview

RCY follows a **Model-View-Controller** pattern with a focus on clean separation of concerns and unidirectional data flow. The system is organized into three main layers:

- **Model**: Data storage, audio processing, and business logic
- **View**: User interface presentation and input handling
- **Controller**: Coordination between Model and View, command handling

## Core Components

### Model (`rcy_model.py`)

Responsibilities:
- Store and manage audio data (samples, duration, sample rate, channels)
- Maintain audio processing state (segments, markers, slicing information)
- Perform audio analysis and processing operations
- Emit signals when data changes

Key classes:
- `RcyModel`: Main model class encapsulating all audio state
- Audio processors and analyzers for transient detection, downsampling, etc.

### View (`rcy_view.py`)

Responsibilities:
- Display the user interface using PyQt6
- Render waveforms using PyQtGraph
- Capture user input events (clicks, drags, key presses)
- Update visual elements based on model state

Key components:
- Waveform display using PyQtGraph
- Marker visualization (start/end trim markers, segment points)
- Control panels and menus
- Audio playback controls

### Controller (`rcy_controller.py`)

Responsibilities:
- Coordinate between Model and View
- Handle user commands and events
- Apply transformations to model state
- Manage application state consistency

Key methods:
- Event handlers (clicks, drags, parameter changes)
- State update methods
- Command execution via dispatcher pattern

## Data Flow

### User Interaction Flow

```
User Input (UI Event)
    ↓
View Event Handler
    ↓
Controller Command Handler
    ↓
Model State Update
    ↓
Controller Updates View
    ↓
View Renders Changes
```

### Signal Blocking & Guards

To prevent circular updates and infinite recursion:

1. **Controller Guard**: The `_updating_ui` flag in the Controller prevents reentrant view updates
2. **View Signal Blocking**: PyQt signals are blocked during programmatic UI updates
3. **Clear Boundaries**: View-to-Model communication only happens through the Controller

## Modernization Phases

RCY is undergoing a multi-phase modernization to improve architecture clarity and maintainability.

### Phase 2: View-State Extraction

**Goal**: Separate UI window parameters (zoom, scroll) from data state

**Components**:
- `ViewState` class: Encapsulates visible window calculations
- Tracks: total duration, visible window length, scroll position
- Provides: zoom, pan, and boundary calculations

**Benefit**: UI changes (zoom, scroll) don't require data reloading

### Phase 3: Command Pattern

**Goal**: Channel user actions through command objects

**Components**:
- `Command` abstract base class
- Concrete command classes:
  - `ZoomInCommand` / `ZoomOutCommand`
  - `PanCommand`
  - `LoadDataCommand`
  - `AddSegmentCommand` / `RemoveSegmentCommand`
  - `PlaySegmentCommand`
  - `CutAudioCommand`

**Benefit**: Commands are testable in isolation and decouple UI from business logic

### Phase 4: One-Way Data Flow

**Goal**: Establish strict unidirectional data flow

**Flow**:
```
User Interaction → View → Controller → Model → Controller → View
```

**Mechanisms**:
- Model doesn't directly update View
- View doesn't directly update Model
- All communication through Controller
- Signal blocking prevents circular updates
- Guard flags prevent reentrant calls

**Benefit**: Predictable, testable state transitions

## Key Design Principles

1. **Single Responsibility**: Each component has one clear reason to exist
2. **Explicit Over Implicit**: Code failures are explicit rather than silent
3. **No Circular Dependencies**: Clear unidirectional data flow
4. **Signal Management**: Proper use of PyQt signal blocking
5. **Testability**: Components are designed for unit testing

## Configuration

Configuration is managed through:
- `config/` directory containing JSON configuration files
- `config_manager.py` module for accessing configuration
- Sensible defaults for all configuration parameters

Configuration should NOT be hardcoded in application code.

## Testing

Tests are organized by component:
- `tests/model/` - Model unit tests
- `tests/view/` - View tests
- `tests/controller/` - Controller tests
- `tests/integration/` - End-to-end integration tests

Key testing principles:
- Mock external dependencies
- Test one concern per test
- Use pytest fixtures for setup
- Include integration tests for critical workflows

## Future Considerations

- Further refinement of command pattern implementation
- Event-based communication for loose coupling
- Additional view state abstractions
- Performance optimizations for large audio files
- Accessibility improvements

## References

For detailed phase specifications, see:
- [Phase 2: View-State Extraction](docs/phase-2-view-state.md)
- [Phase 3: Command Pattern](docs/phase-3-command-pattern.md)
- [Phase 4: One-Way Data Flow](docs/phase-4-one-way-data-flow.md)
- [MVC Current Flow](docs/mvc-current-flow.md)

For related component designs, see:
- [Playback and Export Pipelines](designs/playback-export-pipelines.md)
- [Downsampling Strategy](designs/downsampling-strategy.md)
- [Zoom and Scroll](designs/zoom-and-scroll.md)
