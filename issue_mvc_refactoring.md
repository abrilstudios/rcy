# SPEC: Refactor MVC Architecture to Remove Circular Dependencies

## Overview

The current MVC (Model-View-Controller) architecture in RCY has developed circular update patterns and tightly coupled components that make it difficult to implement certain UI interactions cleanly, particularly zoom and scrolling operations. This issue proposes a refactoring of the core architecture to establish clear boundaries between components and implement one-way data flow.

## Problem Statement

The current architecture has several issues:

1. **Circular Dependencies**: Updates flow in a circular pattern (View → Controller → Model → View), leading to potential infinite recursion.
2. **Mixed Responsibilities**: Components have overlapping responsibilities, making it difficult to trace where and why updates happen.
3. **Tightly Coupled Components**: Direct calls between components rather than through well-defined interfaces.
4. **Redundant Updates**: Multiple successive updates triggered for single user actions.
5. **Signal Management**: Inadequate signal blocking mechanisms across component boundaries.

These issues were significantly exposed when attempting to implement enhanced zoom functionality, where PyQtGraph view range changes triggered a cascade of updates that eventually caused recursion errors.

## Proposed Solution

Refactor the architecture to establish:

1. **One-Way Data Flow**: Establish a clear, unidirectional flow of data:
   - User Interaction → View → Controller → Model → View Updates

2. **Clear Component Responsibilities**:
   - **Model**: Data storage, business logic, audio processing
   - **Controller**: Coordination, command handling, state management
   - **View**: UI presentation, user input handling, visual updates

3. **View-State Separation**:
   - Separate "what is displayed" from "what data exists"
   - View changes (zoom, scroll) shouldn't always trigger data reloading

4. **Event-Based Communication**:
   - Use a clean event/signal system for loose coupling
   - Implement proper signal blocking across boundaries

## Technical Details

### New Update Flow

1. **UI Event Handling**:
   ```
   User Interaction → View.on_event() → Controller.handle_command()
   ```

2. **Data Changes**:
   ```
   Controller.handle_command() → Model.update() → Model.signals.data_changed
   ```

3. **UI Updates**:
   ```
   Model.signals.data_changed → Controller.on_data_changed() → View.update()
   ```

### View Rendering Process

Separate the view rendering process:

1. **View Window Calculation**: Calculate visible window parameters (start time, end time, zoom level)
2. **Data Request**: Request only data needed for current view window
3. **View Update**: Update UI components without triggering unnecessary data reloads

### Signal Management

Implement robust signal blocking:

```python
# Example of proper signal management
def update_ui(self):
    try:
        self._updating_ui = True  # Block circular updates
        # Perform UI updates
    finally:
        self._updating_ui = False  # Always unblock

def on_model_changed(self):
    if self._updating_ui:
        return  # Prevent recursion
    # Handle model changes
```

## Implementation Plan

This refactoring should be approached in phases:

1. **Analysis & Documentation**:
   - Document current data flows
   - Map out signal connections
   - Identify circular dependencies

2. **View-State Separation**:
   - Create a ViewState object to track current view parameters
   - Decouple view navigation from data loading

3. **Controller Refactoring**:
   - Restructure controller methods for unidirectional data flow
   - Implement command pattern for user actions

4. **Model Updates**:
   - Simplify model update signals
   - Remove view-specific logic from model

5. **View Simplification**:
   - Reduce direct model access from views
   - Implement clean observer pattern for updates

## Benefits

1. **Maintainability**: Clearer code organization and predictable data flow
2. **Testability**: Easier to test components in isolation
3. **Extensibility**: Simpler to add new features like complex zoom operations
4. **Performance**: Reduced redundant updates
5. **Stability**: Prevention of recursion errors and infinite update loops

## Potential Challenges

1. **Backwards Compatibility**: Ensuring existing functionality works throughout refactoring
2. **Incremental Delivery**: Need to break changes into manageable chunks
3. **Testing Coverage**: Ensuring all edge cases are covered in the new architecture

## Success Criteria

1. Implementation of zoom functionality without circular dependencies
2. Clear documentation of component responsibilities
3. Comprehensive test coverage
4. No regressions in existing functionality

## Related Issues

- #27 Improve Zoom Functionality in RCY Waveform View

## Label

`L2` (This requires system architecture understanding and should be handled by Claude rather than Claude Jr.)