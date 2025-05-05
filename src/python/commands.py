"""
Command pattern for RCY controller actions.
"""
from abc import ABC, abstractmethod

class Command(ABC):
    """Base class for controller commands."""
    def __init__(self, controller):
        self.controller = controller

    @abstractmethod
    def execute(self):
        """Execute the command against the controller."""
        pass

class ZoomInCommand(Command):
    """Zoom in by a given factor around an anchor point."""
    def __init__(self, controller, factor=0.97, anchor_frac=0.5):
        super().__init__(controller)
        self.factor = factor
        self.anchor_frac = anchor_frac

    def execute(self):
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
    def __init__(self, controller, factor=1.03, anchor_frac=0.5):
        super().__init__(controller)
        self.factor = factor
        self.anchor_frac = anchor_frac

    def execute(self):
        self.controller.view_state.zoom(self.factor, self.anchor_frac)
        self.controller.visible_time = self.controller.view_state.visible_time
        self.controller.update_view()
        self.controller.view.update_scroll_bar(
            self.controller.visible_time,
            self.controller.model.total_time,
        )

class PanCommand(Command):
    """Pan the view window by a fractional amount."""
    def __init__(self, controller, delta_frac):
        super().__init__(controller)
        self.delta_frac = delta_frac

    def execute(self):
        self.controller.view_state.pan(self.delta_frac)
        self.controller.visible_time = self.controller.view_state.visible_time
        self.controller.update_view()
        self.controller.view.update_scroll_bar(
            self.controller.visible_time,
            self.controller.model.total_time,
        )
        return None

class AddSegmentCommand(Command):
    """Command to add a new segment at a given position."""
    def __init__(self, controller, position):
        super().__init__(controller)
        self.position = position

    def execute(self):
        self.controller.add_segment(self.position)
        return None

class RemoveSegmentCommand(Command):
    """Command to remove a segment at a given position."""
    def __init__(self, controller, position):
        super().__init__(controller)
        self.position = position

    def execute(self):
        self.controller.remove_segment(self.position)
        return None

class PlaySegmentCommand(Command):
    """Command to play or stop a segment at a given position."""
    def __init__(self, controller, position):
        super().__init__(controller)
        self.position = position

    def execute(self):
        self.controller.play_segment(self.position)
        return None

class CutAudioCommand(Command):
    """Command to cut audio between two marker positions."""
    def __init__(self, controller, start, end):
        super().__init__(controller)
        self.start = start
        self.end = end

    def execute(self):
        self.controller.cut_audio(self.start, self.end)
        return None
        
class SetMeasuresCommand(Command):
    """Command to update number of measures and recalculate tempo."""
    def __init__(self, controller, num_measures):
        super().__init__(controller)
        self.num_measures = num_measures

    def execute(self):
        # Update controller's measures and trigger logic
        self.controller.on_measures_changed(self.num_measures)
        return None

class SetThresholdCommand(Command):
    """Command to update onset detection threshold."""
    def __init__(self, controller, threshold):
        super().__init__(controller)
        self.threshold = threshold

    def execute(self):
        # Update UI label and controller behavior
        self.controller.threshold = self.threshold
        self.controller.on_threshold_changed(self.threshold)
        return None

class SetResolutionCommand(Command):
    """Command to update measure resolution for splitting."""
    def __init__(self, controller, resolution):
        super().__init__(controller)
        self.resolution = resolution

    def execute(self):
        self.controller.set_measure_resolution(self.resolution)
        return None

class SplitAudioCommand(Command):
    """Command to split audio by measures or transients."""
    def __init__(self, controller, method, measure_resolution=None):
        super().__init__(controller)
        self.method = method
        self.measure_resolution = measure_resolution

    def execute(self):
        if self.method == 'measures':
            self.controller.split_audio(method='measures', measure_resolution=self.measure_resolution)
        else:
            self.controller.split_audio(method=self.method)
        return None

class LoadPresetCommand(Command):
    """Command to load a preset by ID."""
    def __init__(self, controller, preset_id):
        super().__init__(controller)
        self.preset_id = preset_id

    def execute(self):
        self.controller.load_preset(self.preset_id)
        return None

# Additional commands (LoadData, AddSegment, etc.) can follow the same pattern.