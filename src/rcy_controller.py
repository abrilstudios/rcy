from audio_processor import WavAudioProcessor


class RcyController:
    def __init__(self, model):
        self.model = model
        self.visible_time = 10  # Initial visible time window
        self.num_bars = 1

    def set_view(self, view):
        self.view = view
        self.view.bars_input.setText(str(self.num_bars))

    def load_audio_file(self, filename):
        try:
            self.model = WavAudioProcessor(filename)
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)
            self.view.update_tempo()
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

    def set_num_bars(self, num_bars):
        self.num_bars = num_bars
        if self.view:
            self.view.update_tempo()
