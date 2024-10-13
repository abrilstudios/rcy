import os
import soundfile as sf
from audio_processor import WavAudioProcessor


class RcyController:
    def __init__(self, model):
        self.model = model
        self.visible_time = 10  # Initial visible time window
        self.num_bars = 1
        self.bar_resolution = 4
        self.threshold = 0.20
        self.view = None

    def set_view(self, view):
        self.view = view
        self.view.bars_changed.connect(self.on_bars_changed)
        self.view.threshold_changed.connect(self.on_threshold_changed)
        self.view.remove_segment.connect(self.remove_segment)
        self.view.add_segment.connect(self.add_segment)
        self.view.play_segment.connect(self.play_segment)

    def on_threshold_changed(self, threshold):
        self.threshold = threshold
        self.split_audio(method='transients')

    def load_audio_file(self, filename):
        try:
            self.model.set_filename(filename)
            tempo = self.model.get_tempo(self.num_bars)
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)
            self.view.update_tempo(tempo)
            return True
        except Exception as e:
            print(f"Error loading audio file : {e}")
            return False

    def export_segments(self, directory):
        if not isinstance(self.model, WavAudioProcessor):
            return

        segments = self.model.get_segments()
        audio_data = self.model.data
        sample_rate = self.model.sample_rate

        sfz_content = []

        for i, (start, end) in enumerate(zip([0] + segments, segments + [len(audio_data)])):
            # Export audio segment
            segment_data = audio_data[start:end]
            segment_filename = f"segment_{i+1}.wav"
            segment_path = os.path.join(directory, segment_filename)
            sf.write(segment_path, segment_data, sample_rate)

            # Add to SFZ content
            sfz_content.append(f"""
<region>
sample={segment_filename}
pitch_keycenter={60 + i}  // Adjust as needed
lokey={60 + i}
hikey={60 + i}
""")

        # Write SFZ file
        sfz_path = os.path.join(directory, "instrument.sfz")
        with open(sfz_path, 'w') as sfz_file:
            sfz_file.write("\n".join(sfz_content))

        print(f"Exported {len(segments)} segments and SFZ file to {directory}")

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
        if isinstance(self.model, WavAudioProcessor):
            return self.model.get_tempo(self.num_bars)
        return None

    def on_bars_changed(self, num_bars):
        self.num_bars = num_bars
        tempo = self.model.get_tempo(self.num_bars)
        self.update_tempo()

    def update_tempo(self):
        tempo = self.model.get_tempo(self.num_bars)
        self.view.update_tempo(tempo)

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

    def handle_plot_click(self, click_time):
        start_time, end_time = self.get_segment_boundaries(click_time)
        print(f"handle plot click {start_time} {end_time}")
        if start_time is not None and end_time is not None:
            self.play_segment(start_time, end_time)
