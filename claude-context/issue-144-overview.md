# Issue #144: Refactor MVC Architecture to Remove Circular Dependencies

## BACKGROUND AND CONTEXT

RCY is an audio processing and waveform visualization application using PyQt6 and PyQtGraph. The current MVC architecture has bidirectional data flow causing circular dependency issues - particularly when implementing zoom/scroll functionality.

## PROBLEM SUMMARY

1. **Core Issue**: Updates flow in circular patterns (View → Controller → Model → View) causing infinite recursion
2. **Primary Example**: When implementing PyQtGraph-based zoom functionality, view range changes trigger controller updates, which modify the model, which updates the view again
3. **Design Flaw**: Mixed responsibilities and tight coupling between components

## SOLUTION APPROACH

We've designed a unidirectional data flow architecture inspired by Flux/Redux patterns:

1. **Key Components**:
   - Store: Centralized state repository
   - Actions: Plain objects describing state changes
   - Dispatcher: Processes actions and updates store
   - Controller: Subscribes to store changes and updates view
   - View: UI components that emit signals for user events

2. **Data Flow**:
   - User → View signals → Controller → Actions → Dispatcher → Store → Controller → View updates

3. **Documentation Created**:
   - [/designs/one-way-data-flow.md](/designs/one-way-data-flow.md): Detailed technical specification
   - [/designs/one-way-data-flow-diagram.md](/designs/one-way-data-flow-diagram.md): Architecture diagrams

## IMPLEMENTATION PLAN

### Phase 1: Initial Architecture Setup
- Create `RcyStore` class for centralized state management
- Implement `RcyAction` and action type constants
- Create `RcyDispatcher` for processing actions
- Modify `RcyController` to use store/dispatcher
- Update main application initialization

### Phase 2: View Refactoring
- Add new signals to the `RcyView` class
- Update view methods with consistent signal blocking
- Modify `WaveformView` to emit signals for user interactions
- Connect view signals to controller methods

### Phase 3: Zoom Functionality Refactoring
- Implement zoom-specific action handlers
- Update waveform view to emit signals for wheel events
- Connect zoom signals to dispatcher
- Test zoom functionality

### Phase 4: Progressive Component Migration
- Migrate playback functionality
- Migrate marker functionality
- Migrate segment management
- Migrate audio analysis

### Phase 5: Testing and Validation
- Create tests for refactored architecture
- Validate zoom functionality
- Ensure no regressions

## KEY FILES TO MODIFY

1. **Controller**: `/src/python/rcy_controller.py`
2. **View**: `/src/python/rcy_view.py`
3. **Waveform View**: `/src/python/waveform_view.py`
4. **New Files**:
   - `/src/python/rcy_store.py`
   - `/src/python/rcy_actions.py`
   - `/src/python/rcy_dispatcher.py`

## SUCCESS CRITERIA

1. Zoom functionality works without circular dependencies or recursion errors
2. Code architecture follows one-way data flow patterns
3. Components have clear, separated responsibilities
4. All existing functionality works without regression

## STATUS (INCOMPLETE)

Implementation has not yet begun. Next step is to create the `RcyStore` class according to the design document.