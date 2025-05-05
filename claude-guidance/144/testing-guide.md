# Testing Guide for One-Way Data Flow Architecture

## TESTING PRINCIPLES

1. **Test One Data Flow Path**: Focus on testing complete flow paths from user action to view update
2. **Component Isolation**: Test components in isolation using mocks for dependencies
3. **State Change Verification**: Verify state changes propagate correctly to the view
4. **Regression Prevention**: Ensure existing functionality continues to work
5. **Signal Handling**: Test signal blocking and signal emission

## TEST CATEGORIES

### Unit Tests

#### Store Tests
- Test initialization with default state
- Test getting state and individual values
- Test updating single and nested state values
- Test batch updates
- Test subscription and notification
- Test path-based access

```python
def test_store_update_notifies_listeners():
    # Setup
    store = RcyStore()
    mock_listener = Mock()
    store.subscribe(mock_listener)
    
    # Action
    store.update('audio.filename', 'test.wav')
    
    # Assert
    mock_listener.assert_called_once()
    assert mock_listener.call_args[0][0] == 'audio.filename'
```

#### Action Tests
- Test action creation with various types and payloads

#### Dispatcher Tests
- Test dispatching actions triggers correct handlers
- Test each action handler updates the store correctly
- Test derived state calculations (e.g., tempo from markers)

```python
def test_zoom_in_handler():
    # Setup
    store = RcyStore()
    dispatcher = RcyDispatcher(store, mock_model)
    initial_visible_time = store.get_value('view.visible_time')
    
    # Action
    dispatcher.dispatch('ZOOM_IN', {})
    
    # Assert
    assert store.get_value('view.visible_time') < initial_visible_time
```

#### Controller Tests
- Test controller subscribes to store changes
- Test controller passes correct actions to dispatcher
- Test controller updates view correctly based on state changes

```python
def test_controller_updates_view_on_state_change():
    # Setup
    store = RcyStore()
    dispatcher = RcyDispatcher(store, mock_model)
    mock_view = Mock()
    controller = RcyController(mock_model, store, dispatcher)
    controller.set_view(mock_view)
    
    # Action
    store.update('view.markers.start', 1.5)
    
    # Assert
    mock_view.update_markers.assert_called_once()
```

### Integration Tests

#### View-Controller Integration
- Test view signals trigger correct controller methods
- Test controller updates view correctly

#### Full Flow Tests
- Test complete flow paths from user action to view update
- Test complex interactions like zoom with center point preservation

```python
def test_zoom_wheel_full_flow():
    # Setup app with real components
    store = RcyStore()
    dispatcher = RcyDispatcher(store, model)
    controller = RcyController(model, store, dispatcher)
    view = RcyView(controller)
    controller.set_view(view)
    
    # Capture initial state
    initial_visible_time = store.get_value('view.visible_time')
    
    # Simulate wheel event
    event = create_mock_wheel_event(delta=120, position=QPoint(100, 100))
    view.waveform_view.wheelEvent(event)
    
    # Assert
    assert store.get_value('view.visible_time') < initial_visible_time
    # Check view was updated correctly
    # ...
```

### Regression Tests

#### Feature Tests
- Test all existing features continue to work
- Test specific bug fixes don't regress

## TEST SCENARIOS FOR KEY FEATURES

### Zoom Functionality

1. **Zoom In**:
   - Test zoom in preserves center point
   - Test zoom in respects minimum zoom bound
   - Test zoom in updates view range correctly

2. **Zoom Out**:
   - Test zoom out preserves center point
   - Test zoom out respects maximum zoom bound
   - Test zoom out updates view range correctly

3. **Mouse Wheel Zoom**:
   - Test mouse wheel events trigger correct zoom actions
   - Test zoom center is based on mouse position
   - Test wheel direction maps to correct zoom direction

### Marker Functionality

1. **Marker Dragging**:
   - Test marker drag events update store correctly
   - Test derived state (tempo) is calculated when markers change
   - Test markers respect bounds (start < end, etc.)

2. **Marker-Based Tempo**:
   - Test tempo calculation based on marker positions
   - Test tempo updates propagate to UI

### Playback Functionality

1. **Playback Controls**:
   - Test play/pause actions update store correctly
   - Test play segment actions with different modes

## TESTING TOOLS AND UTILITIES

### Mock Factory for Testing

```python
def create_mock_audio_state():
    return {
        'filename': 'test.wav',
        'total_time': 10.0,
        'sample_rate': 44100,
        'channels': 1,
        'is_playing': False
    }

def create_mock_wheel_event(delta, position):
    # Create a mock wheel event for testing zoom
    event = QWheelEvent(
        position,
        QPointF(0, 0),
        QPoint(0, delta),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )
    return event
```

### Signal Testing Helpers

```python
class SignalCatcher(QObject):
    def __init__(self, signal):
        super().__init__()
        self.caught = False
        self.args = None
        signal.connect(self.slot)
        
    def slot(self, *args):
        self.caught = True
        self.args = args
```

## COMMON TESTING PATTERNS

### State Before/After Pattern

```python
# Capture state before action
before_state = store.get_state()
before_value = store.get_value('some.path')

# Perform action
dispatcher.dispatch('SOME_ACTION', payload)

# Verify state after action
after_state = store.get_state()
after_value = store.get_value('some.path')

# Assert expected changes
assert after_value != before_value
assert after_state['unchanged_part'] == before_state['unchanged_part']
```

### Action-State-View Verification

```python
# 1. Dispatch action
dispatcher.dispatch('ZOOM_IN', {'center': 2.5})

# 2. Verify state was updated correctly
assert store.get_value('view.visible_time') == expected_visible_time

# 3. Verify view was updated properly
mock_view.update_visible_range.assert_called_with(expected_start, expected_end)
```

### Signal Blocking Verification

```python
# Mock the blockSignals method to verify it's called correctly
mock_widget.blockSignals = Mock(return_value=False)

# Perform state update
controller._update_view_from_state(test_state)

# Check signal blocking was used properly
assert mock_widget.blockSignals.call_args_list == [
    call(True),   # Block signals
    call(False)   # Restore previous state
]
```

## DEBUGGING TIPS FOR TESTS

1. **Circular Dependencies**: If tests hang or cause recursion errors, look for circular update paths

2. **Signal Connection**: Use `print_signal_connections(object)` to verify signal connections:
   ```python
   def print_signal_connections(obj):
       for signal in [attr for attr in dir(obj) if isinstance(getattr(obj, attr), pyqtSignal)]:
           print(f"Signal: {signal}, Connections: {getattr(obj, signal).receivers()}")
   ```

3. **State Updates**: Use state diff helpers to debug state changes:
   ```python
   def diff_states(before, after):
       return {k: after[k] for k in after if k not in before or before[k] != after[k]}
   ```