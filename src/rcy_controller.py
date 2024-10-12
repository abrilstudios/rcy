from audio_processor import WavAudioProcessor


class RcyController:
    def __init__(self, model):
        self.model = model
        self.visible_time = 10  # Initial visible time window
        self.num_bars = 1
        self.bar_resolution = 4

    def set_view(self, view):
        self.view = view
        self.view.bars_changed.connect(self.on_bars_changed)

    def load_audio_file(self, filename):
        try:
            self.model = WavAudioProcessor(filename)
            tempo = self.model.get_tempo(self.num_bars)
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)
            self.view.update_tempo(tempo)
            return True
        except Exception as e:
            print(f"Error loading audio file : {e}")
            return False

    def update_view(self):
        start_time = self.view.get_scroll_position() * (self.model.total_time - self.visible_time) / 100
        end_time = start_time + self.visible_time
        time, data = self.model.get_data(start_time, end_time)
        self.view.update_plot(time, data)

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
            slices = self.model.split_by_transients()
        else:
            raise ValueError("Invalid split method")
        self.view.update_slices(slices)

    def play_segment(self, start_time, end_time):
        if isinstance(self.model, WavAudioProcessor):
            start_sample = self.model.get_sample_at_time(start_time)
            end_sample = self.model.get_sample_at_time(end_time)
            self.model.play_segment(start_sample, end_sample)

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
