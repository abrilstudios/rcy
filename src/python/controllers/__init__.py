"""Controllers package for RCY application.

This package provides a modular controller architecture with domain-specific
controllers orchestrated by the ApplicationController.

Main Components:
    ApplicationController: Main orchestrator that integrates all controllers
    AudioController: Audio file loading and preset management
    TempoController: BPM calculations and measure management
    PlaybackController: Playback control and looping
    SegmentController: Segment manipulation and splitting
    ExportController: Audio segment export operations
    ViewController: View updates, zooming, and visualization

Usage:
    from controllers import ApplicationController

    # Create the main controller
    controller = ApplicationController(model)
    controller.set_view(view)

    # All operations are delegated to appropriate sub-controllers
    controller.load_audio_file("path/to/file.wav")
    controller.play_segment(2.5)
"""

from controllers.application_controller import ApplicationController
from controllers.audio_controller import AudioController
from controllers.tempo_controller import TempoController
from controllers.playback_controller import PlaybackController
from controllers.segment_controller import SegmentController
from controllers.export_controller import ExportController
from controllers.view_controller import ViewController

# Only export the main ApplicationController
# Internal controllers are implementation details
__all__ = ['ApplicationController']
