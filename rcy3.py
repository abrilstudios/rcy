import sys
import numpy as np
import librosa
import soundfile as sf
import matplotlib.pyplot as plt
import sounddevice as sd
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class Config:
    def __init__(self):
        self.window_title = "Audio Splitter"
        self.window_geometry = (100, 100, 800, 600)
        self.figure_size = (8, 4)
        self.slider_range = (0, 100)
        self.slider_default = 50

class AudioProcessor:
    def __init__(self):
        self.y = None
        self.sr = None
        self.onset_samples = None

    def load_audio(self, file_path):
        self.y, self.sr = librosa.load(file_path)
        return self.y, self.sr

    def detect_onsets(self, delta):
        onset_frames = librosa.onset.onset_detect(y=self.y, sr=self.sr, delta=delta)
        self.onset_samples = librosa.frames_to_samples(onset_frames)
        self.onset_samples = np.append(self.onset_samples, len(self.y))
        return self.onset_samples

    def save_splits(self, output_dir, base_filename):
        sfz_content = "<group>\nampeg_release=0.5\n\n"
        for i, (start, end) in enumerate(zip(self.onset_samples[:-1], self.onset_samples[1:])):
            audio_slice = self.y[start:end]
            slice_filename = f"{base_filename}_slice_{i}.wav"
            sf.write(os.path.join(output_dir, slice_filename), audio_slice, self.sr)
            sfz_content += f"<region>\nsample={slice_filename}\n"
            sfz_content += f"key={60 + i}\npitch_keycenter={60 + i}\n\n"
        
        sfz_filename = os.path.join(output_dir, f"{base_filename}.sfz")
        with open(sfz_filename, 'w') as sfz_file:
            sfz_file.write(sfz_content)

    def play_segment(self, start, end):
        segment = self.y[start:end]
        sd.play(segment, self.sr)
        sd.wait()

class AudioSplitterView(QMainWindow):
    load_audio_signal = pyqtSignal(str)
    save_splits_signal = pyqtSignal()
    update_splits_signal = pyqtSignal(float)
    play_segment_signal = pyqtSignal(int, int)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(self.config.window_title)
        self.setGeometry(*self.config.window_geometry)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.figure, self.ax = plt.subplots(figsize=self.config.figure_size)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        self.slider_layout = QHBoxLayout()
        self.slider_label = QLabel("Delta:")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(*self.config.slider_range)
        self.slider.setValue(self.config.slider_default)
        self.slider_layout.addWidget(self.slider_label)
        self.slider_layout.addWidget(self.slider)
        self.layout.addLayout(self.slider_layout)

        self.button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Audio")
        self.save_button = QPushButton("Save Splits")
        self.button_layout.addWidget(self.load_button)
        self.button_layout.addWidget(self.save_button)
        self.layout.addLayout(self.button_layout)

        self.load_button.clicked.connect(self.load_audio)
        self.save_button.clicked.connect(self.save_splits_signal.emit)
        self.slider.sliderReleased.connect(self.update_splits)

        self.canvas.mpl_connect('button_press_event', self.on_click)

    def load_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "Audio Files (*.wav *.mp3)")
        if file_path:
            self.load_audio_signal.emit(file_path)

    def update_splits(self):
        delta = self.slider.value() / 100.0
        self.update_splits_signal.emit(delta)

    def on_click(self, event):
        if event.xdata is not None:
            click_sample = int(event.xdata)
            self.play_segment_signal.emit(click_sample, click_sample + 1)  # Controller will handle finding the correct segment

    def plot_waveform(self, y, onset_samples=None):
        self.ax.clear()
        self.ax.plot(y)
        self.ax.set_xlabel('Sample')
        self.ax.set_ylabel('Amplitude')
        if onset_samples is not None:
            for sample in onset_samples:
                self.ax.axvline(x=sample, color='r', linestyle='--')
        self.canvas.draw()

class AudioSplitterController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.file_path = None
        self.connect_signals()

    def connect_signals(self):
        self.view.load_audio_signal.connect(self.load_audio)
        self.view.save_splits_signal.connect(self.save_splits)
        self.view.update_splits_signal.connect(self.update_splits)
        self.view.play_segment_signal.connect(self.play_segment)

    def load_audio(self, file_path):
        self.file_path = file_path
        y, sr = self.model.load_audio(file_path)
        self.view.plot_waveform(y)
        self.update_splits(self.view.slider.value() / 100.0)

    def update_splits(self, delta):
        onset_samples = self.model.detect_onsets(delta)
        self.view.plot_waveform(self.model.y, onset_samples)

    def save_splits(self):
        if self.file_path:
            output_dir = QFileDialog.getExistingDirectory(self.view, "Select Output Directory")
            if output_dir:
                base_filename = os.path.splitext(os.path.basename(self.file_path))[0]
                self.model.save_splits(output_dir, base_filename)
                print(f"Splits saved as WAV files and SFZ in {output_dir}")

    def play_segment(self, click_sample, _):
        for start, end in zip(self.model.onset_samples[:-1], self.model.onset_samples[1:]):
            if start <= click_sample < end:
                self.model.play_segment(start, end)
                break

if __name__ == '__main__':
    app = QApplication(sys.argv)
    config = Config()
    model = AudioProcessor()
    view = AudioSplitterView(config)
    controller = AudioSplitterController(model, view)
    view.show()
    sys.exit(app.exec())
