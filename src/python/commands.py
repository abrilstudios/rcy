"""
Command pattern for RCY controller actions.
"""
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from enums import SplitMethod

if TYPE_CHECKING:
    from rcy_controller import RcyController

class Command(ABC):
    """Base class for controller commands."""
    def __init__(self, controller: 'RcyController') -> None:
        self.controller = controller

    @abstractmethod
    def execute(self) -> Any:
        """Execute the command against the controller."""
        pass

class ZoomInCommand(Command):
    """Zoom in by a given factor around an anchor point."""
    def __init__(self, controller: 'RcyController', factor: float = 0.97, anchor_frac: float = 0.5) -> None:
        super().__init__(controller)
        self.factor = factor
        self.anchor_frac = anchor_frac

    def execute(self) -> None:
        # Apply zoom via view_state
        self.controller.view_state.zoom(self.factor, self.anchor_frac)
        # Sync controller visible_time and update view
        self.controller.visible_time = self.controller.view_state.visible_time
        self.controller.update_view()
        self.controller.view.update_scroll_bar(
            self.controller.visible_time,
            self.controller.model.total_time,
        )

class ZoomOutCommand(Command):
    """Zoom out by a given factor around an anchor point."""
    def __init__(self, controller: 'RcyController', factor: float = 1.03, anchor_frac: float = 0.5) -> None:
        super().__init__(controller)
        self.factor = factor
        self.anchor_frac = anchor_frac

    def execute(self) -> None:
        self.controller.view_state.zoom(self.factor, self.anchor_frac)
        self.controller.visible_time = self.controller.view_state.visible_time
        self.controller.update_view()
        self.controller.view.update_scroll_bar(
            self.controller.visible_time,
            self.controller.model.total_time,
        )

class PanCommand(Command):
    """Pan the view window by a fractional amount."""
    def __init__(self, controller: 'RcyController', delta_frac: float) -> None:
        super().__init__(controller)
        self.delta_frac = delta_frac

    def execute(self) -> None:
        self.controller.view_state.pan(self.delta_frac)
        self.controller.visible_time = self.controller.view_state.visible_time
        self.controller.update_view()
        self.controller.view.update_scroll_bar(
            self.controller.visible_time,
            self.controller.model.total_time,
        )

class AddSegmentCommand(Command):
    """Command to add a new segment at a given position."""
    def __init__(self, controller: 'RcyController', position: float) -> None:
        super().__init__(controller)
        self.position = position

    def execute(self) -> None:
        self.controller.add_segment(self.position)

class RemoveSegmentCommand(Command):
    """Command to remove a segment at a given position."""
    def __init__(self, controller: 'RcyController', position: float) -> None:
        super().__init__(controller)
        self.position = position

    def execute(self) -> None:
        self.controller.remove_segment(self.position)

class PlaySegmentCommand(Command):
    """Command to play or stop a segment at a given position."""
    def __init__(self, controller: 'RcyController', position: float) -> None:
        super().__init__(controller)
        self.position = position

    def execute(self) -> None:
        self.controller.play_segment(self.position)

class CutAudioCommand(Command):
    """Command to cut audio between two marker positions."""
    def __init__(self, controller: 'RcyController', start: float, end: float) -> None:
        super().__init__(controller)
        self.start = start
        self.end = end

    def execute(self) -> None:
        self.controller.cut_audio(self.start, self.end)

class SetMeasuresCommand(Command):
    """Command to update number of measures and recalculate tempo."""
    def __init__(self, controller: 'RcyController', num_measures: int) -> None:
        super().__init__(controller)
        self.num_measures = num_measures

    def execute(self) -> None:
        # Update controller's measures and trigger logic
        self.controller.on_measures_changed(self.num_measures)

class SetThresholdCommand(Command):
    """Command to update onset detection threshold."""
    def __init__(self, controller: 'RcyController', threshold: float) -> None:
        super().__init__(controller)
        self.threshold = threshold

    def execute(self) -> None:
        # Update UI label and controller behavior
        self.controller.threshold = self.threshold
        self.controller.on_threshold_changed(self.threshold)

class SetResolutionCommand(Command):
    """Command to update measure resolution for splitting."""
    def __init__(self, controller: 'RcyController', resolution: int) -> None:
        super().__init__(controller)
        self.resolution = resolution

    def execute(self) -> None:
        self.controller.set_measure_resolution(self.resolution)

class SplitAudioCommand(Command):
    """Command to split audio by measures or transients."""
    def __init__(self, controller: 'RcyController', method: str | SplitMethod, measure_resolution: int | None = None) -> None:
        super().__init__(controller)
        # Convert string to enum if necessary
        self.method = SplitMethod(method) if isinstance(method, str) else method
        self.measure_resolution = measure_resolution

    def execute(self) -> None:
        match self.method:
            case SplitMethod.MEASURES:
                self.controller.split_audio(method=SplitMethod.MEASURES, measure_resolution=self.measure_resolution)
            case SplitMethod.TRANSIENTS:
                self.controller.split_audio(method=SplitMethod.TRANSIENTS)
            case _:
                raise ValueError(f"Invalid split method: {self.method}")

class LoadPresetCommand(Command):
    """Command to load a preset by ID."""
    def __init__(self, controller: 'RcyController', preset_id: str) -> None:
        super().__init__(controller)
        self.preset_id = preset_id

    def execute(self) -> None:
        self.controller.load_preset(self.preset_id)

# Additional commands (LoadData, AddSegment, etc.) can follow the same pattern.