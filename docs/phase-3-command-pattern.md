# Phase 3: Command Pattern in Controller

## Goal
Channel all user-driven actions through command objects handled by the Controller. This encapsulates each action’s logic, makes it testable in isolation, and decouples UI wiring from business logic.

## Command List

- **ZoomInCommand**(factor: float = 0.97, anchor_frac: float = 0.5)
- **ZoomOutCommand**(factor: float = 1.03, anchor_frac: float = 0.5)
- **PanCommand**(delta_frac: float)
- **LoadDataCommand**(start_time: float, end_time: float)
- **AddSegmentCommand**(position: float)
- **RemoveSegmentCommand**(position: float)
- **PlaySegmentCommand**(position: float)
- **CutAudioCommand**(start: float, end: float)

Each command implements a common interface:
```python
from abc import ABC, abstractmethod

class Command(ABC):
    def __init__(self, controller, **kwargs):
        self.controller = controller

    @abstractmethod
    def execute(self) -> any:
        pass
```

## Dispatcher API

The Controller maintains a mapping:
```python
COMMAND_MAP = {
    'zoom_in': ZoomInCommand,
    'zoom_out': ZoomOutCommand,
    'pan': PanCommand,
    # ...
}
```

And exposes:
```python
def execute_command(self, name: str, **kwargs):
    """
    Instantiate and execute the command by name, passing kwargs to its constructor.
    """
    cmd_cls = COMMAND_MAP.get(name)
    if not cmd_cls:
        raise KeyError(f"Unknown command: {name}")
    cmd = cmd_cls(self, **kwargs)
    return cmd.execute()
```

## Next Steps
1. Implement `src/python/commands.py` with the `Command` hierarchy.
2. Wire Controller to use `execute_command` (and optionally deprecate direct method calls).
3. Update View event handlers to call `controller.execute_command(...)` instead of `controller.zoom_in` etc.
4. Write unit tests for at least `ZoomInCommand` and `ZoomOutCommand` in `tests/test_commands.py`.