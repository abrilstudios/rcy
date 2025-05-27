import os
import soundfile as sf
from audio_processor import WavAudioProcessor
from midiutil import MIDIFile
from math import ceil
from export_utils import ExportUtils
from config_manager import config
from commands import (
    ZoomInCommand, ZoomOutCommand, PanCommand,
    AddSegmentCommand, RemoveSegmentCommand, PlaySegmentCommand, CutAudioCommand,
    SetMeasuresCommand, SetThresholdCommand, SetResolutionCommand,
    SplitAudioCommand, LoadPresetCommand
)

# Map command names to command classes
COMMAND_MAP = {
    'zoom_in': ZoomInCommand,
    'zoom_out': ZoomOutCommand,
    'pan': PanCommand,
    'add_segment': AddSegmentCommand,
    'remove_segment': RemoveSegmentCommand,
    'play_segment': PlaySegmentCommand,
    'cut_audio': CutAudioCommand,
    'set_measures': SetMeasuresCommand,
    'set_threshold': SetThresholdCommand,
    'set_resolution': SetResolutionCommand,
    'split_audio': SplitAudioCommand,
    'load_preset': LoadPresetCommand,
}
from utils.audio_preview import get_downsampled_data

class RcyController:
    def __init__(self, model):
        self.model = model
        # Initialize view state based on model duration and default visible time
        from view_state import ViewState
        self.visible_time = 10  # Initial visible time window
        self.view_state = ViewState(self.model.total_time, self.visible_time)
        self.num_measures = 1
        self.measure_resolution = 4
        self.tempo = 120
        
        # Get transient detection parameters from config
        td_config = config.get_setting("audio", "transientDetection", {})
        self.threshold = td_config.get("threshold", 0.20)
        
        # Get playback tempo parameters from config
        pt_config = config.get_setting("audio", "playbackTempo", {})
        self.playback_tempo_enabled = pt_config.get("enabled", False)
        self.target_bpm = pt_config.get("targetBpm", 120)
        
        # Get playback mode from config
        playback_config = config.get_setting("audio", "playback", {})
        self.playback_mode = playback_config.get("mode", "one-shot")
        
        # Validate playback mode
        valid_modes = ["one-shot", "loop", "loop-reverse"]
        if self.playback_mode not in valid_modes:
            print(f"Warning: Invalid playback mode '{self.playback_mode}', using 'one-shot'")
            self.playback_mode = "one-shot"
        
        # Playback state tracking
        self.is_playing_reverse = False
        self.current_segment = (None, None)
        
        print(f"Playback mode initialized to: {self.playback_mode}")
        
        self.view = None
        
        # Setup timer to check playback status periodically
        from PyQt6.QtCore import QTimer
        self.playback_check_timer = QTimer()
        self.playback_check_timer.timeout.connect(self.check_playback_status)
        self.playback_check_timer.start(100)  # Check every 100ms
        
    def execute_command(self, name: str, **kwargs):
        """
        Instantiate and execute a Command by name, passing kwargs to its constructor.
        """
        cmd_cls = COMMAND_MAP.get(name)
        if not cmd_cls:
            raise KeyError(f"Unknown command: {name}")
        cmd = cmd_cls(self, **kwargs)
        return cmd.execute()

    def set_view(self, view):
        self.view = view
        self.view.measures_changed.connect(self.on_measures_changed)
        self.view.threshold_changed.connect(self.on_threshold_changed)
        # Route segment manipulation through command dispatcher
        self.view.remove_segment.connect(
            lambda pos: self.execute_command('remove_segment', position=pos)
        )
        self.view.add_segment.connect(
            lambda pos: self.execute_command('add_segment', position=pos)
        )
        self.view.play_segment.connect(
            lambda pos: self.execute_command('play_segment', position=pos)
        )
        self.view.start_marker_changed.connect(self.on_start_marker_changed)
        self.view.end_marker_changed.connect(self.on_end_marker_changed)
        # Route cut action through command dispatcher
        self.view.cut_requested.connect(
            lambda start, end: self.execute_command('cut_audio', start=start, end=end)
        )
        
        # Initialize marker positions
        self.start_marker_pos = None
        self.end_marker_pos = None
        
        # Initialize playback tempo UI
        # Update the view with initial playback tempo settings
        self.view.update_playback_tempo_display(
            self.playback_tempo_enabled,
            self.target_bpm,
            1.0  # Initial ratio
        )

        # Set initial playback mode in view
        self.view.update_playback_mode_menu(self.playback_mode)

    def on_threshold_changed(self, threshold):
        self.threshold = threshold
        self.split_audio(method='transients')

    def export_segments(self, directory):
        # Pass marker positions for when there are no segments defined
        return ExportUtils.export_segments(self.model,
                                           self.tempo,
                                           self.num_measures,
                                           directory,
                                           self.start_marker_pos,
                                           self.end_marker_pos)

    def load_audio_file(self, filename):
        """Load an audio file from filename"""
        print(f"\n===== DETAILED AUDIO FILE LOADING AND TEMPO CALCULATION =====")
        print(f"Loading file: {filename}")
        print(f"Initial state:")
        print(f"- Current measure count: {self.num_measures}")
        print(f"- Initial target BPM: {self.target_bpm}")
        print(f"- Initial playback tempo enabled: {self.playback_tempo_enabled}")
        
        # Set the filename in the model
        print("Setting filename in model...")
        self.model.set_filename(filename)
        
        # Get audio information
        print(f"\nAudio file information:")
        print(f"- Total duration: {self.model.total_time:.6f}s")
        print(f"- Sample rate: {self.model.sample_rate} Hz")
        print(f"- Channels: {self.model.channels}")
        
        # Calculate tempo based on current measure count
        print(f"\nCalculating tempo from model.get_tempo({self.num_measures})...")
        old_tempo = getattr(self, 'tempo', None)
        self.tempo = self.model.get_tempo(self.num_measures)
        print(f"model.get_tempo returned: {self.tempo:.2f} BPM")
        if old_tempo is not None:
            print(f"Tempo changed from {old_tempo:.2f} to {self.tempo:.2f} BPM")
        
        # Calculate source BPM for playback tempo adjustment
        print(f"\nCalculating source BPM from model.calculate_source_bpm(measures={self.num_measures})...")
        source_bpm = self.model.calculate_source_bpm(measures=self.num_measures)
        print(f"model.calculate_source_bpm returned: {source_bpm} BPM")
        print(f"model.source_bpm is now: {self.model.source_bpm} BPM")
        
        # Ensure model's source BPM matches the calculated tempo
        self.model.source_bpm = self.tempo
        print(f"Ensuring model.source_bpm equals tempo: {self.model.source_bpm} BPM")
        
        # IMPORTANT FIX: Explicitly set target BPM to match the calculated tempo
        old_target_bpm = self.target_bpm
        self.target_bpm = int(round(self.tempo))
        print(f"\nSetting target BPM: {old_target_bpm} → {self.target_bpm}")
        
        # Ensure model's source_bpm stays consistent with the calculated tempo
        old_source_bpm = self.model.source_bpm
        if old_source_bpm != self.tempo:
            print(f"Synchronizing model.source_bpm from {old_source_bpm:.2f} to {self.tempo:.2f} BPM")
            self.model.source_bpm = self.tempo
        
        # Disable playback tempo adjustment by default for imported files
        self.playback_tempo_enabled = False
        
        # Update the model's playback tempo settings
        print(f"\nUpdating model's playback tempo settings...")
        print(f"Calling model.set_playback_tempo({self.playback_tempo_enabled}, {self.target_bpm})")
        ratio = self.model.set_playback_tempo(self.playback_tempo_enabled, self.target_bpm)
        print(f"Playback ratio: {ratio:.4f}")
        
        # Update view first to get everything initialized
        print(f"\nUpdating view...")
        self.update_view()
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)
        
        # Update the main tempo display
        print(f"Updating main tempo display to {self.tempo:.2f} BPM")
        self.view.update_tempo(self.tempo)
        
        # Update the measures display in the UI without triggering the callback
        print(f"Updating measures input to {self.num_measures}")
        old_state = self.view.measures_input.blockSignals(True)
        self.view.measures_input.setText(str(self.num_measures))
        self.view.measures_input.blockSignals(old_state)
        
        # Update the playback tempo UI elements to match
        print(f"Updating playback tempo UI with enabled={self.playback_tempo_enabled}, target={self.target_bpm}")
        self.view.update_playback_tempo_display(
            self.playback_tempo_enabled,
            self.target_bpm,
            ratio
        )
        
        # Now reset markers after everything is updated
        print(f"Resetting markers to file boundaries")
        self.view.clear_markers()
        
        print(f"\nFINAL STATE:")
        print(f"- Audio file: {filename}")
        print(f"- Duration: {self.model.total_time:.6f}s")
        print(f"- Measures: {self.num_measures}")
        print(f"- Tempo: {self.tempo:.2f} BPM")
        print(f"- Source BPM: {self.model.source_bpm:.2f} BPM")
        print(f"- Target BPM: {self.target_bpm} BPM")
        print(f"- Playback tempo enabled: {self.playback_tempo_enabled}")
        print(f"- Playback ratio: {self.model.get_playback_ratio():.4f}")
        print(f"===== END DETAILED AUDIO FILE LOADING AND TEMPO CALCULATION =====\n")
        
        return True
        
    def load_preset(self, preset_id):
        """Load a preset by its ID"""
        # Get preset info
        preset_info = config.get_preset_info(preset_id)
        if not preset_info:
            print(f"ERROR: Preset '{preset_id}' not found")
            return False
            
        # Load the preset in the model
        try:
            self.model.load_preset(preset_id)
            
            # Update number of measures if specified in the preset
            measures = preset_info.get('measures', 1)
            self.num_measures = measures
            print(f"Preset '{preset_id}' specifies {self.num_measures} measures")
            
            # Update the UI - only block signals if needed
            # Temporarily block signals to avoid recursive updates
            old_state = self.view.measures_input.blockSignals(True)
            self.view.measures_input.setText(str(self.num_measures))
            self.view.measures_input.blockSignals(old_state)
            print(f"Updated measures input to {self.num_measures}")
            
            # Update tempo - This will now be calculated with the correct measure count
            self.tempo = self.model.get_tempo(self.num_measures)
            print(f"Tempo: {self.tempo:.2f} BPM based on {self.num_measures} measures")
            
            # Calculate source BPM for playback tempo adjustment
            self.model.calculate_source_bpm(measures=self.num_measures)
            
            # Update view
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)
            self.view.update_tempo(self.tempo)
            
            # Reset markers to file boundaries after view update
            self.view.clear_markers()
            
            # Update playback tempo display
            self.view.update_playback_tempo_display(
                self.playback_tempo_enabled,
                self.target_bpm,
                self.model.get_playback_ratio()
            )
            
            return True
        except Exception as e:
            print(f"ERROR loading preset: {e}")
            return False
    
    def get_available_presets(self):
        """Get a list of available presets"""
        return config.get_preset_list()

    def update_view(self):
        # Prevent recursive UI updates
        if getattr(self, '_updating_ui', False):
            return
        self._updating_ui = True
        
        # Update view state
        self.view_state.set_total_time(self.model.total_time)
        self.view_state.set_visible_time(self.visible_time)
        scroll_frac = self.view.get_scroll_position() / 100.0
        self.view_state.set_scroll_frac(scroll_frac)
        start_time = self.view_state.start
        end_time = self.view_state.end
        
        # Get raw data
        time, data_left, data_right = self.model.get_data(start_time, end_time)
        
        # Apply downsampling if enabled
        ds_config = config.get_setting("audio", "downsampling", {})
        if ds_config.get("enabled", False) and time is not None:
            always_apply = ds_config.get("alwaysApply", True)
            min_length = ds_config.get("minLength", 1000)
            max_length = ds_config.get("maxLength", 5000)
            method = ds_config.get("method", "envelope")
            ds_method = "max_min" if method == "envelope" else "simple"
            
            width = self.view.width()
            target_length = min(max(width * 2, min_length), max_length)
            
            if always_apply or len(time) > target_length:
                time, data_left, data_right = get_downsampled_data(
                    time, data_left, data_right, target_length, method=ds_method
                )
        
        # Update the plot and segments
        self.view.update_plot(time, data_left, data_right, is_stereo=self.model.is_stereo)
        slices = self.model.segment_manager.get_boundaries()
        self.view.update_slices(slices)
        
        # Release update guard
        self._updating_ui = False

    def zoom_in(self):
        # Zoom in by shrinking visible window to 97%, around center
        self.view_state.zoom(0.97)
        # Update controller's visible_time and refresh view
        self.visible_time = self.view_state.visible_time
        self.update_view()
        # Update scroll bar to reflect new window size
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)

    def zoom_out(self):
        # Zoom out by expanding visible window to 103%, limited by total time
        self.view_state.zoom(1.03)
        self.visible_time = self.view_state.visible_time
        self.update_view()
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)

    def get_tempo(self):
        return self.tempo

    def on_measures_changed(self, num_measures):
        print(f"\n===== (on_measures_changed) DETAILED TEMPO UPDATE FROM MEASURES CHANGE =====")
        
        # Store old values for debugging
        old_measures = self.num_measures
        old_tempo = self.tempo
        old_target_bpm = self.target_bpm
        old_enabled = self.playback_tempo_enabled
        old_source_bpm = self.model.source_bpm
        
        print(f"     Measures changed from {old_measures} to {num_measures}")
        print(f"     Current audio file: {self.model.filename}")
        print(f"     Current total_time: {self.model.total_time:.6f}s")
        
        # Update measures and recalculate tempo
        self.num_measures = num_measures
        print(f"     Recalculating tempo with new measures...")
        print(f"     Calling model.get_tempo({self.num_measures})...")
        self.tempo = self.model.get_tempo(self.num_measures)
        print(f"     After measure change, tempo changed from {old_tempo:.2f} to {self.tempo:.2f} BPM")
        
        # CRITICAL FIX: Update model's source_bpm to match the new tempo
        # This ensures playback tempo adjustment works correctly
        self.model.source_bpm = self.tempo
        print(f"     Updated model.source_bpm from {old_source_bpm:.2f} to {self.model.source_bpm:.2f} BPM")
        
        # Usability Choice: Update target BPM to match the new tempo
        self.target_bpm = int(round(self.tempo))
        print(f"     Target BPM updated from {old_target_bpm} to {self.target_bpm}")
        
        # Update the model's playback tempo settings if enabled
        if self.playback_tempo_enabled:
            print(f"     Updating model's playback tempo settings since playback_tempo_enabled is True...")
            print(f"     Calling model.set_playback_tempo({self.playback_tempo_enabled}, {self.target_bpm})...")
            ratio = self.model.set_playback_tempo(self.playback_tempo_enabled, self.target_bpm)
            print(f"     New playback ratio: {ratio:.4f}")
        else:
            print(f"     Not updating playback tempo settings (playback_tempo_enabled is False)")
            ratio = self.model.get_playback_ratio()
        
        # Update the main tempo display
        print(f"     Updating UI...")
        print(f"     Setting tempo display to {self.tempo:.2f} BPM")
        self.view.update_tempo(self.tempo)
        
        # Update the playback tempo UI with the new settings
        if self.playback_tempo_enabled:
            print(f"     Updating playback tempo UI with enabled={self.playback_tempo_enabled}, target={self.target_bpm}, ratio={ratio:.4f}")
            self.view.update_playback_tempo_display(self.playback_tempo_enabled, self.target_bpm, ratio)
        else:
            print(f"     Not updating playback tempo UI (playback_tempo_enabled is False)")
        
        print(f"\nFINAL STATE AFTER MEASURES CHANGE:")
        print(f"- Measures: {self.num_measures}")
        print(f"- Tempo: {self.tempo:.2f} BPM")
        print(f"- Target BPM: {self.target_bpm}")
        print(f"- Source BPM in model: {self.model.source_bpm:.2f} BPM")
        print(f"- Playback tempo enabled: {self.playback_tempo_enabled}")
        print(f"- Playback ratio: {ratio:.4f}")
        print(f"===== END DETAILED TEMPO UPDATE FROM MEASURES CHANGE =====\n")

    def set_measure_resolution(self, resolution):
        """Set the measure resolution without automatically triggering a split"""
        self.measure_resolution = resolution

    def split_audio(self, method='measures', measure_resolution=None):
        if method == 'measures':
            # Use the provided resolution or fall back to the stored value
            resolution = measure_resolution if measure_resolution is not None else self.measure_resolution
            slices = self.model.split_by_measures(self.num_measures, resolution)
        elif method == 'transients':
            slices = self.model.split_by_transients(threshold=self.threshold)
        else:
            raise ValueError("Invalid split method")
        self.view.update_slices(slices)

    def remove_segment(self, click_time):
        print(f"RcyController.remove_segment({click_time})")
        try:
            self.model.remove_segment(click_time)
            print("Successfully called model.remove_segment")
        except Exception as e:
            print(f"ERROR in model.remove_segment: {e}")
        self.update_view()

    def add_segment(self, click_time):
        self.model.add_segment(click_time)
        self.update_view()

    def set_playback_mode(self, mode):
        """Set the playback mode
        
        Args:
            mode (str): One of 'one-shot', 'loop', or 'loop-reverse'
        
        Returns:
            bool: True if mode was valid and set successfully
        """
        valid_modes = ["one-shot", "loop", "loop-reverse"]
        if mode not in valid_modes:
            print(f"Error: Invalid playback mode '{mode}'")
            return False
            
        # Only update if different
        if mode != self.playback_mode:
            print(f"Playback mode changed from '{self.playback_mode}' to '{mode}'")
            self.playback_mode = mode
            
            # Update playback mode in audio engine
            from high_performance_audio import PlaybackMode
            mode_map = {
                "one-shot": PlaybackMode.ONE_SHOT,
                "loop": PlaybackMode.LOOP,
                "loop-reverse": PlaybackMode.LOOP_REVERSE
            }
            self.model.audio_engine.set_playback_mode(mode_map[mode])
            
            # Update playback mode in view
            self.view.update_playback_mode_menu(mode)
                
        return True
        
    def get_playback_mode(self):
        """Get the current playback mode
        
        Returns:
            str: Current playback mode
        """
        return self.playback_mode
        
    def play_segment(self, click_time):
        """Play or stop a segment based on click location"""
        print(f"### Controller received play_segment with click_time: {click_time}")
        
        # Check both if the model is actively playing and if we're in a loop cycle
        if self.model.is_playing:
            print("### Already playing, stopping playback")
            self.stop_playback()
            # Clear current segment to prevent further looping
            self.current_segment = (None, None)
            return
            
        # If not playing, determine segment boundaries and play
        print(f"### Getting segment boundaries for click_time: {click_time}")
        # Use the controller's get_segment_boundaries method, not the model's
        start, end = self.get_segment_boundaries(click_time)
        print(f"### Segment boundaries returned: {start} to {end}")
        
        if start is not None and end is not None:
            print(f"### Playing segment: {start:.2f}s to {end:.2f}s, mode: {self.playback_mode}")
            
            # Store current segment for looping
            self.current_segment = (start, end)
            self.is_playing_reverse = False
            
            # Highlight the active segment in the view
            self.view.highlight_active_segment(start, end)
                
            # Play the segment
            result = self.model.play_segment(start, end, reverse=False)
            print(f"### Play segment result: {result}")
            
    def stop_playback(self):
        """Stop any currently playing audio"""
        self.model.stop_playback()
        
        # Clear the current_segment to prevent loop continuation
        if self.playback_mode in ["loop", "loop-reverse"]:
            self.current_segment = (None, None)
        
        # Clear the active segment highlight
        self.view.clear_active_segment_highlight()

    def get_segment_boundaries(self, click_time):
        """Get the start and end times for the segment containing the click"""
        # If no slices or empty list, return full audio range
        # 'current_slices' may not be initialized until update_slices is called
        if not getattr(self, 'current_slices', []):
            print("No segments defined, using full audio range")
            return 0, self.model.total_time
        
        # Special case for before the first segment marker
        # We use a special threshold for clicks near the start
        # This allows the start marker to be draggable while still allowing first segment playback
        first_slice = self.current_slices[0]
        if click_time <= first_slice:
            # For clicks very close to start, use first segment
            print(f"### FIRST SEGMENT DETECTED")
            print(f"### Click time ({click_time}) <= first slice ({first_slice})")
            print(f"### Returning first segment: 0 to {first_slice}")
            return 0, first_slice
            
        # Special case for after the last segment marker
        last_slice = self.current_slices[-1]
        if click_time >= last_slice:
            print(f"### LAST SEGMENT DETECTED")
            print(f"### Click time ({click_time}) >= last slice ({last_slice})")
            print(f"### Returning last segment: {last_slice} to {self.model.total_time}")
            return last_slice, self.model.total_time
            
        # Middle segments
        for i, slice_time in enumerate(self.current_slices):
            if click_time < slice_time:
                if i == 0:  # Should not happen given the above check, but just in case
                    print(f"First segment (fallback): 0 to {slice_time}")
                    return 0, slice_time
                else:
                    print(f"Middle segment {i}: {self.current_slices[i-1]} to {slice_time}")
                    return self.current_slices[i-1], slice_time
                    
        # Fallback for safety - should not reach here
        print(f"Fallback: last segment - {last_slice} to {self.model.total_time}")
        return last_slice, self.model.total_time

    def on_start_marker_changed(self, position):
        """Called when the start marker position changes"""
        self.start_marker_pos = position
        print(f"Start marker position updated: {position}")
        
        # Update tempo if both markers are set
        if self.start_marker_pos is not None and self.end_marker_pos is not None:
            self._update_tempo_from_markers()
    
    def on_end_marker_changed(self, position):
        """Called when the end marker position changes"""
        self.end_marker_pos = position
        print(f"End marker position updated: {position}")
        
        # Update tempo if both markers are set
        if self.start_marker_pos is not None and self.end_marker_pos is not None:
            self._update_tempo_from_markers()
            
    def _update_tempo_from_markers(self):
        """Calculate tempo based on the current marker positions"""
        print(f"\n=== UPDATING TEMPO FROM MARKERS ===")
        
        # Skip if markers are invalid
        if self.start_marker_pos >= self.end_marker_pos:
            print("Markers invalid: start position >= end position")
            return
            
        # Calculate duration between markers
        duration = self.end_marker_pos - self.start_marker_pos
        
        # Calculate tempo based on the selected duration
        beats_per_measure = 4  # Assuming 4/4 time
        total_beats = self.num_measures * beats_per_measure
        total_time_minutes = duration / 60
        
        # Calculate tempo if time is valid
        if total_time_minutes > 0:
            # Store the old values for debugging
            old_tempo = self.tempo
            old_target_bpm = self.target_bpm
            old_enabled = self.playback_tempo_enabled
            old_source_bpm = self.model.source_bpm if hasattr(self.model, 'source_bpm') else None
            
            # Calculate the new tempo
            self.tempo = total_beats / total_time_minutes
            
            # Update target BPM to match the new tempo, but only if tempo adjustment is already enabled
            # This preserves the user's choice about whether tempo adjustment is enabled
            if self.playback_tempo_enabled:
                self.target_bpm = int(round(self.tempo))
            
            # Update the model's source BPM
            # This ensures consistent playback when markers are moved
            old_source_bpm = self.model.source_bpm
            self.model.source_bpm = self.tempo
            print(f"DEBUG: Updated model.source_bpm from {old_source_bpm:.2f} to {self.tempo:.2f} BPM")
            
            print(f"DEBUG: Marker-based tempo calculation:")
            print(f"DEBUG: - Duration between markers: {duration:.2f} seconds")
            print(f"DEBUG: - Old tempo: {old_tempo:.2f} BPM")
            print(f"DEBUG: - New tempo: {self.tempo:.2f} BPM")
            print(f"DEBUG: - Old source BPM: {old_source_bpm}")
            print(f"DEBUG: - New source BPM: {self.model.source_bpm}")
            print(f"DEBUG: - Old target BPM: {old_target_bpm}")
            print(f"DEBUG: - New target BPM: {self.target_bpm}")
            print(f"DEBUG: - Playback tempo enabled: {self.playback_tempo_enabled} (preserved user setting)")
            
            # Update the model's playback tempo settings directly
            # This preserves the user's choice about whether tempo adjustment is enabled
            self.model.set_playback_tempo(self.playback_tempo_enabled, self.target_bpm)
            
            # Update the main tempo display
            self.view.update_tempo(self.tempo)
            
            # Update the playback tempo display with the new settings
            ratio = self.model.get_playback_ratio()
            self.view.update_playback_tempo_display(
                self.playback_tempo_enabled,
                self.target_bpm,
                ratio
            )
            
            print(f"=== TEMPO UPDATED: {self.tempo:.2f} BPM, Target={self.target_bpm}, Enabled={self.playback_tempo_enabled} ===\n")
    
    def play_selected_region(self):
        """Play or stop the audio between start and end markers"""
        # If already playing, stop playback
        if self.model.is_playing:
            self.stop_playback()
            return
            
        # If not playing, play the selected region
        if self.start_marker_pos is not None and self.end_marker_pos is not None:
            # Store current segment for looping
            self.current_segment = (self.start_marker_pos, self.end_marker_pos)
            self.is_playing_reverse = False
            
            print(f"### Playing selected region: {self.start_marker_pos:.2f}s to {self.end_marker_pos:.2f}s, mode: {self.playback_mode}")
            
            # Highlight the active segment in the view
            self.view.highlight_active_segment(self.start_marker_pos, self.end_marker_pos)
                
            self.model.play_segment(self.start_marker_pos, self.end_marker_pos)
    
    def cut_audio(self, start_time, end_time):
        """Trim the audio to the selected region"""
        # Convert time positions to sample positions
        start_sample = self.model.get_sample_at_time(start_time)
        end_sample = self.model.get_sample_at_time(end_time)
        
        # Perform the cut operation in the model
        success = self.model.cut_audio(start_sample, end_sample)
        if not success:
            print("Failed to trim audio")
            return
        
        # Update tempo and clear segments
        self.tempo = self.model.get_tempo(self.num_measures)
        self.view.update_tempo(self.tempo)
        self.model.segments = []
        
        # Update the view with the new trimmed audio
        self.update_view()
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)
        
        # Ensure markers are within bounds after cut
        if hasattr(self.view.waveform_view, '_clamp_markers_to_data_bounds'):
            self.view.waveform_view._clamp_markers_to_data_bounds()
        
        print("Audio successfully trimmed")
    
    def handle_plot_click(self, click_time):
        print(f"### Handle plot click with time: {click_time}")
        # We'll use the real click time here, not the forced one
        # The force test is now in test_first_segment() below
        
        start_time, end_time = self.get_segment_boundaries(click_time)
        print(f"### Handle plot click determined segment: {start_time} to {end_time}")
        if start_time is not None and end_time is not None:
            # Use the click_time for determining the segment via play_segment
            self.play_segment(click_time)
            
    def handle_loop_playback(self):
        """Handle looping of the current segment according to playback mode"""
        start, end = self.current_segment
        
        if start is None or end is None:
            print("### No current segment to loop")
            return False
            
        if self.playback_mode == "loop":
            # Simple loop - play the same segment again
            print(f"### Loop playback: {start:.2f}s to {end:.2f}s")
            self.model.play_segment(start, end)
            return True
            
        elif self.playback_mode == "loop-reverse":
            # Loop with direction change
            if self.is_playing_reverse:
                # Just finished reverse playback, now play forward
                print(f"### Loop-reverse: Forward playback {start:.2f}s to {end:.2f}s")
                self.is_playing_reverse = False
                self.model.play_segment(start, end, reverse=False)
            else:
                # Just finished forward playback, now play reverse
                print(f"### Loop-reverse: Reverse playback {end:.2f}s to {start:.2f}s")
                self.is_playing_reverse = True
                # Use reverse=True to properly play the segment in reverse
                self.model.play_segment(start, end, reverse=True)
            return True
            
        # Not a looping mode
        return False
            
    def check_playback_status(self):
        """Periodically check if playback has ended"""
        if self.model.playback_just_ended:
            print("### Controller detected playback just ended")
            
            # Reset the flag
            self.model.playback_just_ended = False
            
            # Handle looping if needed
            if self.playback_mode in ["loop", "loop-reverse"]:
                if self.handle_loop_playback():
                    return
            
            # If not looping or loop handling failed, clear highlight
            self.view.clear_active_segment_highlight()
    
    def set_playback_tempo(self, enabled, target_bpm=None):
        """Configure playback tempo settings
        
        Args:
            enabled (bool): Whether tempo adjustment is enabled
            target_bpm (int, optional): Target tempo in BPM
        
        Returns:
            float: The adjustment factor (ratio of target to source tempo)
        """
        # Update controller state
        self.playback_tempo_enabled = enabled
        
        if target_bpm is not None:
            self.target_bpm = int(target_bpm)
            
        # Update model with settings
        playback_ratio = self.model.set_playback_tempo(
            enabled, 
            self.target_bpm
        )
        
        # Update view with new playback tempo settings
        self.view.update_playback_tempo_display(
            enabled,
            self.target_bpm,
            playback_ratio
        )
            
        return playback_ratio
