import os
import soundfile as sf
from audio_processor import WavAudioProcessor
from midiutil import MIDIFile
from math import ceil
from export_utils import ExportUtils
from config_manager import config
from utils.audio_preview import get_downsampled_data

class RcyController:
    def __init__(self, model):
        self.model = model
        self.visible_time = 10  # Initial visible time window
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

    def set_view(self, view):
        self.view = view
        self.view.measures_changed.connect(self.on_measures_changed)
        self.view.threshold_changed.connect(self.on_threshold_changed)
        self.view.remove_segment.connect(self.remove_segment)
        self.view.add_segment.connect(self.add_segment)
        self.view.play_segment.connect(self.play_segment)
        self.view.start_marker_changed.connect(self.on_start_marker_changed)
        self.view.end_marker_changed.connect(self.on_end_marker_changed)
        self.view.cut_requested.connect(self.cut_audio)
        
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
        
        # IMPORTANT FIX: Explicitly set target BPM to match the calculated tempo
        old_target_bpm = self.target_bpm
        self.target_bpm = int(round(self.tempo))
        print(f"\nSetting target BPM: {old_target_bpm} → {self.target_bpm}")
        
        # IMPORTANT FIX: Enable playback tempo adjustment by default for imported files
        old_enabled = self.playback_tempo_enabled
        self.playback_tempo_enabled = True
        print(f"Setting playback tempo enabled: {old_enabled} → {self.playback_tempo_enabled}")
        
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
        
        # Update the playback tempo UI elements to match
        print(f"Updating playback tempo UI with enabled={self.playback_tempo_enabled}, target={self.target_bpm}")
        self.view.update_playback_tempo_display(
            self.playback_tempo_enabled,
            self.target_bpm,
            self.model.get_playback_ratio()
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
            if measures != self.num_measures:
                # Only update if different to avoid unnecessary recalculations
                self.num_measures = measures
                print(f"Preset '{preset_id}' specifies {self.num_measures} measures")
                
                # Update the UI - only block signals if needed
                # Temporarily block signals to avoid recursive updates
                old_state = self.view.measures_input.blockSignals(True)
                self.view.measures_input.setText(str(self.num_measures))
                self.view.measures_input.blockSignals(old_state)
                print(f"Updated measures input to {self.num_measures}")
            else:
                print(f"Preset '{preset_id}' has same measure count ({measures}), no update needed")
            
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
        print(f"\n==== CONTROLLER UPDATE_VIEW ====")
        
        # Get data window
        start_time = self.view.get_scroll_position() * (self.model.total_time - self.visible_time) / 100
        end_time = start_time + self.visible_time
        print(f"DEBUG: View window: start_time={start_time:.6f}, end_time={end_time:.6f}, visible_time={self.visible_time}")
        print(f"DEBUG: Model total_time: {self.model.total_time}")
        
        # Track marker positions before update
        pre_markers = self.view.waveform_view.get_marker_positions()
        print(f"DEBUG: Pre-update marker positions: start={pre_markers[0]}, end={pre_markers[1]}")
        
        # Check data bounds
        try:
            if self.view.waveform_view.time_data is not None and len(self.view.waveform_view.time_data) > 0:
                pre_data_max = self.view.waveform_view.time_data[-1]
                print(f"DEBUG: Pre-update data bounds: max={pre_data_max}")
        except TypeError:
            print("DEBUG: TypeError in controller update_view when accessing time_data length")
        
        # Get raw data with left and right channels if stereo
        time, data_left, data_right = self.model.get_data(start_time, end_time)
        try:
            if time is not None and len(time) > 0:
                print(f"DEBUG: Got data: time_length={len(time)}, time_range=[{time[0]}, {time[-1]}]")
            else:
                print("DEBUG: Got data: time is None or empty")
        except TypeError:
            print("DEBUG: TypeError in update_view when accessing time length")
        
        # Get downsampling configuration from config file
        ds_config = config.get_setting("audio", "downsampling", {})
        
        # Check if downsampling is enabled
        if ds_config.get("enabled", False):
            # Get configuration values with defaults
            always_apply = ds_config.get("alwaysApply", True)
            default_target = ds_config.get("targetLength", 2000)
            min_length = ds_config.get("minLength", 1000)
            max_length = ds_config.get("maxLength", 5000)
            method = ds_config.get("method", "envelope")
            
            # Convert method name to method parameter for downsampling function
            ds_method = "max_min" if method == "envelope" else "simple"
            
            # Calculate appropriate target length based on view size
            width = self.view.width()
            target_length = min(max(width * 2, min_length), max_length)
            
            print(f"DEBUG: Downsampling settings: enabled={ds_config.get('enabled')}, method={method}, target_length={target_length}")
            
            # Apply downsampling if configured to always apply or if we have enough data to benefit
            try:
                if always_apply or (time is not None and len(time) > target_length):
                    print(f"DEBUG: Applying downsampling - original length={len(time)}")
                    # Use get_downsampled_data imported at the top of the file
                    time, data_left, data_right = get_downsampled_data(
                        time, data_left, data_right, target_length, method=ds_method
                    )
                if time is not None and len(time) > 0:
                    print(f"DEBUG: After downsampling - length={len(time)}, time_range=[{time[0]}, {time[-1]}]")
                else:
                    print("DEBUG: After downsampling - time data is None or empty")
            except TypeError:
                print("DEBUG: TypeError in downsampling check when accessing time length")
        
        # Pre-update check - see if markers would fall outside bounds
        try:
            if pre_markers[0] is not None and pre_markers[1] is not None and time is not None and len(time) > 0:
                if pre_markers[1] > time[-1]:
                    print(f"DEBUG: ⚠️ End marker ({pre_markers[1]}) will be outside new time bounds ([{time[0]}, {time[-1]}])")
        except TypeError:
            print("DEBUG: TypeError in pre-update bounds check when accessing time data")
        
        try:
            if time is not None and len(time) > 0:
                print(f"DEBUG: About to call view.update_plot with time_range=[{time[0]}, {time[-1]}]")
            else:
                print("DEBUG: About to call view.update_plot with empty or None time data")
        except TypeError:
            print("DEBUG: TypeError when trying to log time data range for update_plot")
        # Update the plot with data (downsampled or raw)
        self.view.update_plot(time, data_left, data_right)
        
        slices = self.model.get_segments()
        try:
            if slices is not None:
                print(f"DEBUG: About to call view.update_slices with {len(slices)} segments")
            else:
                print("DEBUG: About to call view.update_slices with None slices")
        except TypeError:
            print("DEBUG: TypeError when trying to access segments length")
        self.view.update_slices(slices)
        
        # Post-update check: verify marker bounds and handle existence
        post_markers = self.view.waveform_view.get_marker_positions()
        print(f"DEBUG: Post-update marker positions: start={post_markers[0]}, end={post_markers[1]}")

        # Check data bounds
        try:
            if self.view.waveform_view.time_data is not None and len(self.view.waveform_view.time_data) > 0:
                post_data_max = self.view.waveform_view.time_data[-1]
                print(f"DEBUG: Post-update data bounds: max={post_data_max}")
        except TypeError:
            print("DEBUG: TypeError in post-update check when accessing time_data length")

        # Check if end marker is beyond data bounds
        if post_markers[1] is not None and post_markers[1] > post_data_max:
            print(f"DEBUG: ⚠️ End marker ({post_markers[1]}) is still beyond data bounds ({post_data_max})")

            # Current handle positions
            end_handle = self.view.waveform_view.marker_handles.get('end_handle')
            if end_handle is None:
                print("DEBUG: End marker handle is None")
            else:
                print("DEBUG: End marker handle exists in plot")

        print(f"==== END CONTROLLER UPDATE_VIEW ====\n")

    def zoom_in(self):
        self.visible_time *= 0.97
        self.update_view()
        self.view.update_scroll_bar(self.visible_time,
                                    self.model.total_time)

    def zoom_out(self):
        self.visible_time = min(self.visible_time * 1.03,
                                self.model.total_time)
        self.update_view()
        self.view.update_scroll_bar(self.visible_time,
                                    self.model.total_time)

    def get_tempo(self):
        return self.tempo

    def on_measures_changed(self, num_measures):
        print(f"\n===== DETAILED TEMPO UPDATE FROM MEASURES CHANGE =====")
        
        # Store old values for debugging
        old_measures = self.num_measures
        old_tempo = self.tempo
        old_target_bpm = self.target_bpm
        old_enabled = self.playback_tempo_enabled
        
        print(f"Measures changed from {old_measures} to {num_measures}")
        print(f"Current audio file: {getattr(self.model, 'filename', 'None')}")
        print(f"Current total_time: {self.model.total_time:.6f}s")
        
        # Update measures and recalculate tempo
        self.num_measures = num_measures
        print(f"\nRecalculating tempo with new measures...")
        print(f"Calling model.get_tempo({self.num_measures})...")
        self.tempo = self.model.get_tempo(self.num_measures)
        print(f"Tempo changed from {old_tempo:.2f} to {self.tempo:.2f} BPM")
        
        # IMPORTANT FIX: Update target BPM to match the new tempo
        self.target_bpm = int(round(self.tempo))
        print(f"Target BPM updated from {old_target_bpm} to {self.target_bpm}")
        
        # IMPORTANT FIX: Always enable playback tempo when measures change
        # self.playback_tempo_enabled = True
        # print(f"Playback tempo enabled changed from {old_enabled} to {self.playback_tempo_enabled}")
        
        # IMPORTANT FIX: Update the model's playback tempo settings directly
        print(f"\nUpdating model's playback tempo settings...")
        print(f"Calling model.set_playback_tempo({self.playback_tempo_enabled}, {self.target_bpm})...")
        ratio = self.model.set_playback_tempo(self.playback_tempo_enabled, self.target_bpm)
        print(f"New playback ratio: {ratio:.4f}")
        
        # Update the main tempo display
        print(f"\nUpdating UI...")
        print(f"Setting tempo display to {self.tempo:.2f} BPM")
        self.view.update_tempo(self.tempo)
        
        # Update the playback tempo UI with the new settings
        print(f"Updating playback tempo UI with enabled={self.playback_tempo_enabled}, target={self.target_bpm}")
        self.view.update_playback_tempo_display(
            self.playback_tempo_enabled,
            self.target_bpm,
            ratio
        )
        
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
            self.model.source_bpm = self.tempo
            
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
        print(f"\n==== CONTROLLER CUT OPERATION ====")
        print(f"Cutting audio between {start_time:.6f}s and {end_time:.6f}s")
        
        # Get marker positions before cut for tracking
        pre_markers = self.view.waveform_view.get_marker_positions()
        print(f"DEBUG: Pre-cut marker positions: start={pre_markers[0]}, end={pre_markers[1]}")
        
        # Get current model state before cut
        pre_total_time = self.model.total_time
        try:
            pre_time_max = self.model.time[-1] if (self.model.time is not None and len(self.model.time) > 0) else None
        except TypeError:
            print("DEBUG: TypeError in cut_audio when accessing model.time length")
            pre_time_max = None
        print(f"DEBUG: Pre-cut model state: total_time={pre_total_time}, time_max={pre_time_max}")
        
        # Convert time positions to sample positions
        start_sample = self.model.get_sample_at_time(start_time)
        end_sample = self.model.get_sample_at_time(end_time)
        print(f"DEBUG: Converting to samples: start_sample={start_sample}, end_sample={end_sample}")
        
        # Perform the cut operation in the model
        success = self.model.cut_audio(start_sample, end_sample)
        
        if not success:
            print("Failed to trim audio")
            return
        
        # Get model state after cut
        post_total_time = self.model.total_time
        try:
            post_time_max = self.model.time[-1] if (self.model.time is not None and len(self.model.time) > 0) else None
        except TypeError:
            print("DEBUG: TypeError in cut_audio when accessing post-cut model.time length")
            post_time_max = None
        print(f"DEBUG: Post-cut model state: total_time={post_total_time}, time_max={post_time_max}")
        
        # Reset tempo to initial values
        old_tempo = self.tempo
        self.tempo = self.model.get_tempo(self.num_measures)
        self.view.update_tempo(self.tempo)
        print(f"DEBUG: Tempo updated from {old_tempo} to {self.tempo}")
        
        # Clear segments
        self.model.segments = []
        
        print("DEBUG: About to call update_view()")
        # Update the view with the new trimmed audio
        self.update_view()
        print("DEBUG: About to call update_scroll_bar()")
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)
        
        # Get marker positions after update
        post_markers = self.view.waveform_view.get_marker_positions()
        print(f"DEBUG: Post-update marker positions: start={post_markers[0]}, end={post_markers[1]}")

        # Check if end marker is still beyond data bounds
        try:
            if self.view.waveform_view.time_data is not None and len(self.view.waveform_view.time_data) > 0:
                data_max = self.view.waveform_view.time_data[-1]
                print(f"DEBUG: Data bounds check: end_marker={post_markers[1]}, data_max={data_max}")
                if post_markers[1] > data_max:
                    print("DEBUG: **** END MARKER IS STILL BEYOND DATA BOUNDS ****")
                    # Force a final bounds check
                    print("DEBUG: Forcing a final bounds check on waveform_view")
                    try:
                        # First try clamping
                        self.view.waveform_view._clamp_markers_to_data_bounds()
                        check_markers = self.view.waveform_view.get_marker_positions()
                        print(f"DEBUG: Marker positions after clamping: start={check_markers[0]}, end={check_markers[1]}")
                        
                        # If still beyond bounds, try direct set_end_marker call
                        if check_markers[1] is not None and check_markers[1] > data_max:
                            print("DEBUG: Direct end marker correction needed")
                            # Call set_end_marker directly with the max value
                            self.view.waveform_view.set_end_marker(data_max)
                            
                            # Verify the correction
                            final_markers = self.view.waveform_view.get_marker_positions()
                            print(f"DEBUG: Final marker positions after direct correction: start={final_markers[0]}, end={final_markers[1]}")
                        else:
                            print("DEBUG: Clamping successful, no direct correction needed")
                    except Exception as e:
                        print(f"DEBUG: Exception during marker correction: {e}")
        except TypeError:
            print("DEBUG: TypeError in cut_audio when checking time_data bounds")
        
        print("DEBUG: Audio cut operation completed - markers should now be correct")
        print(f"==== END CONTROLLER CUT OPERATION ====\n")
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
    
    def test_first_segment(self):
        """Special test method to debug first segment playback
        
        This can be manually called for debugging purposes.
        It's not used in normal application flow.
        """
        print("\n\n### TESTING FIRST SEGMENT PLAYBACK ###")
        
        # Force a click in the first segment
        test_click_time = 0.1  # This should be within the first segment
        
        print(f"### Test click time: {test_click_time}")
        
        # Get segment boundaries for the test click
        start, end = self.get_segment_boundaries(test_click_time)
        print(f"### First segment boundaries: {start} to {end}")
        
        # Try to play the segment
        print(f"### Attempting to play first segment")
        result = self.model.play_segment(start, end)
        print(f"### First segment play result: {result}")
        
        # Wait for playback to complete
        import time
        time.sleep(0.5)
        print("### First segment test complete")
        
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
