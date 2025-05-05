# Key Concepts for One-Way Data Flow Architecture

## CORE PRINCIPLES

1. **Single Source of Truth**: All application state lives in one centralized store
2. **Read-Only State**: State can only be read directly, never modified directly
3. **Pure Functions**: State changes occur through pure action handlers
4. **Unidirectional Flow**: Data flows in one direction only
5. **Explicit Updates**: All state changes are explicit and traceable

## ARCHITECTURAL COMPONENTS

### Store
- **Purpose**: Central repository for all application state
- **Properties**: Maintains nested state object
- **Methods**: 
  - `get_state()`: Gets a copy of the entire state
  - `get_value(path)`: Gets a specific value by path
  - `update(path, value)`: Updates a specific value
  - `batch_update(updates)`: Updates multiple values at once
  - `subscribe(listener)`: Registers a state change listener
- **Design Pattern**: Observer pattern with subscription system

### Actions
- **Purpose**: Describe state changes without implementing them
- **Structure**: Simple objects with type and payload
- **Examples**:
  ```python
  {
    "type": "ZOOM_IN",
    "payload": {"center": 2.5}
  }
  ```
- **Design Pattern**: Command pattern for encapsulating operations

### Dispatcher
- **Purpose**: Process actions and update store
- **Methods**: 
  - `dispatch(action_type, payload)`: Dispatch an action
  - Handlers for each action type (`_handle_zoom_in`, etc.)
- **Design Pattern**: Mediator pattern for coordinating updates

### Controller
- **Purpose**: Connect view signals to actions, update view from state
- **Responsibilities**:
  - Subscribe to store changes
  - Connect view signals to action dispatches
  - Update view based on state changes
- **Design Pattern**: Adapter pattern between View and Store/Dispatcher

### View
- **Purpose**: Present UI and emit user interaction signals
- **Responsibilities**:
  - Render UI based on provided data
  - Emit signals for user interactions
  - Never directly modify model or state
- **Design Pattern**: Passive View pattern (from MVP)

## SIGNAL FLOW EXAMPLES

### Zoom Operation
1. User scrolls mouse wheel on waveform
2. WaveformView emits `mouse_wheel_zoom` signal
3. RcyView processes signal and emits `zoom_in_requested` signal
4. Controller handles signal and dispatches `ZOOM_IN` action
5. Dispatcher processes action in `_handle_zoom_in`
6. Store updates `view.visible_time` and `view.scroll_position`
7. Store notifies listeners of state change
8. Controller updates view with new visible range

### Marker Movement
1. User drags a marker
2. WaveformView emits `marker_dragged` signal
3. RcyView emits `marker_changed` signal
4. Controller dispatches `SET_MARKER_POSITION` action
5. Dispatcher updates marker position in store
6. Dispatcher calculates derived state (tempo)
7. Store notifies listeners of state changes
8. Controller updates view with new marker positions and tempo

## PYTHON IMPLEMENTATION PATTERNS

### Signal Blocking
```python
# Block signals during state-driven updates
old_state = view_element.blockSignals(True)
view_element.setValue(state_value)
view_element.blockSignals(old_state)
```

### Path-Based State Access
```python
def get_value(self, path):
    parts = path.split('.')
    current = self._state
    for part in parts:
        if part not in current:
            return None
        current = current[part]
    return copy.deepcopy(current)
```

### Batch Updates
```python
def batch_update(self, updates):
    # Update multiple paths at once
    for path, value in updates.items():
        # ... update logic
    
    # Notify only once
    self._notify_listeners("batch_update")
```

### Signal-Action Mapping
```python
# In controller's set_view method
view.zoom_in_requested.connect(
    lambda center: self.dispatcher.dispatch('ZOOM_IN', {'center': center})
)
```

## BEST PRACTICES

1. **Always Copy State**: Always return copies of state objects to prevent direct mutation
2. **Immutable Updates**: Treat state as immutable, create new objects when updating
3. **Block Signals**: Always block signals when updating UI from state
4. **Keep Actions Simple**: Actions should be simple data carriers, not contain logic
5. **Single Responsibility**: Each component should have clear, limited responsibilities
6. **Explicit Dependencies**: Make dependencies clear and explicit