import os
import soundfile as sf
from audio_processor import WavAudioProcessor
from midiutil import MIDIFile
from math import ceil
from export_utils import ExportUtils
from config_manager import config

class RcyController:
    def __init__(self, model):
        self.model = model
        self.visible_time = 10  # Initial visible time window
        self.num_bars = 1
        self.bar_resolution = 4
        self.tempo = 120
        self.threshold = 0.20
        self.view = None

    def set_view(self, view):
        self.view = view
        self.view.bars_changed.connect(self.on_bars_changed)
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

    def on_threshold_changed(self, threshold):
        self.threshold = threshold
        self.split_audio(method='transients')

    def export_segments(self, directory):
        return ExportUtils.export_segments(self.model,
                                           self.tempo,
                                           self.num_bars,
                                           directory)

    def load_audio_file(self, filename):
        self.model.set_filename(filename)
        self.tempo = self.model.get_tempo(self.num_bars)
        self.update_view()
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)
        self.view.update_tempo(self.tempo)
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
            
            # Update number of bars if specified in the preset
            if 'measures' in preset_info:
                self.num_bars = preset_info['measures']
                if hasattr(self.view, 'bars_input'):
                    self.view.bars_input.setText(str(self.num_bars))
            
            # Update tempo
            self.tempo = self.model.get_tempo(self.num_bars)
            
            # Update view
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)
            self.view.update_tempo(self.tempo)
            
            return True
        except Exception as e:
            print(f"ERROR loading preset: {e}")
            return False
    
    def get_available_presets(self):
        """Get a list of available presets"""
        return config.get_preset_list()

    def update_view(self):
        start_time = self.view.get_scroll_position() * (self.model.total_time - self.visible_time) / 100
        end_time = start_time + self.visible_time
        time, data = self.model.get_data(start_time, end_time)
        self.view.update_plot(time, data)
        slices = self.model.get_segments()
        self.view.update_slices(slices)

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

    def on_bars_changed(self, num_bars):
        self.num_bars = num_bars
        self.tempo = self.model.get_tempo(self.num_bars)
        self.view.update_tempo(self.tempo)

    def set_bar_resolution(self, resolution):
        self.bar_resolution = resolution
        self.split_audio(method='bars', bar_resolution=resolution)

    def split_audio(self, method='bars', bar_resolution=4):
        if method == 'bars':
            slices = self.model.split_by_bars(self.num_bars, bar_resolution)
        elif method == 'transients':
            slices = self.model.split_by_transients(threshold=self.threshold)
        else:
            raise ValueError("Invalid split method")
        self.view.update_slices(slices)

    def remove_segment(self, click_time):
        self.model.remove_segment(click_time)
        self.update_view()

    def add_segment(self, click_time):
        self.model.add_segment(click_time)
        self.update_view()

    def play_segment(self, click_time):
        start, end = self.model.get_segment_boundaries(click_time)
        if start is not None and end is not None:
            self.model.play_segment(start, end)

    def get_segment_boundaries(self, click_time):
        if not hasattr(self, 'current_slices'):
            return None, None
        for i, slice_time in enumerate(self.current_slices):
            if click_time < slice_time:
                if i == 0:
                    return 0, slice_time
                else:
                    return self.current_slices[i-1], slice_time
        return self.current_slices[-1], self.model.total_time

    def on_start_marker_changed(self, position):
        """Called when the start marker position changes"""
        self.start_marker_pos = position
        print(f"Start marker position updated: {position}")
    
    def on_end_marker_changed(self, position):
        """Called when the end marker position changes"""
        self.end_marker_pos = position
        print(f"End marker position updated: {position}")
    
    def play_selected_region(self):
        """Play the audio between start and end markers"""
        if self.start_marker_pos is not None and self.end_marker_pos is not None:
            self.model.play_segment(self.start_marker_pos, self.end_marker_pos)
    
    def cut_audio(self, start_time, end_time):
        """Trim the audio to the selected region"""
        print(f"Cutting audio between {start_time:.2f}s and {end_time:.2f}s")
        
        # Convert time positions to sample positions
        start_sample = self.model.get_sample_at_time(start_time)
        end_sample = self.model.get_sample_at_time(end_time)
        
        # Perform the cut operation in the model
        success = self.model.cut_audio(start_sample, end_sample)
        
        if success:
            # Reset tempo to initial values
            self.tempo = self.model.get_tempo(self.num_bars)
            self.view.update_tempo(self.tempo)
            
            # Clear segments
            self.model.segments = []
            
            # Update the view with the new trimmed audio
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)
            print("Audio successfully trimmed")
        else:
            print("Failed to trim audio")
    
    def handle_plot_click(self, click_time):
        start_time, end_time = self.get_segment_boundaries(click_time)
        print(f"handle plot click {start_time} {end_time}")
        if start_time is not None and end_time is not None:
            self.play_segment(start_time, end_time)
