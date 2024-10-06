import sys
import numpy as np
import librosa
import soundfile as sf
import matplotlib.pyplot as plt
import sounddevice as sd
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class AudioSplitterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Splitter")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.figure, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        self.slider_layout = QHBoxLayout()
        self.slider_label = QLabel("Delta:")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
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
        self.save_button.clicked.connect(self.save_splits)
        self.slider.sliderReleased.connect(self.update_splits)

        self.y = None
        self.sr = None
        self.onset_samples = None
        self.file_path = None

        self.canvas.mpl_connect('button_press_event', self.on_click)

    def load_audio(self):
        self.file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "Audio Files (*.wav *.mp3)")
        if self.file_path:
            self.y, self.sr = librosa.load(self.file_path)
            self.plot_waveform()
            self.update_splits()

    def plot_waveform(self):
        self.ax.clear()
        self.ax.plot(self.y)
        self.ax.set_xlabel('Sample')
        self.ax.set_ylabel('Amplitude')
        self.canvas.draw()

    def update_splits(self):
        if self.y is not None and self.sr is not None:
            delta = self.slider.value() / 100.0
            onset_frames = librosa.onset.onset_detect(y=self.y, sr=self.sr, delta=delta)
            self.onset_samples = librosa.frames_to_samples(onset_frames)
            self.onset_samples = np.append(self.onset_samples, len(self.y))
            
            self.plot_waveform()
            for sample in self.onset_samples:
                self.ax.axvline(x=sample, color='r', linestyle='--')
            self.canvas.draw()

    def save_splits(self):
        if self.onset_samples is not None and self.file_path is not None:
            output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if output_dir:
                base_filename = os.path.splitext(os.path.basename(self.file_path))[0]
                sfz_content = "<group>\nampeg_release=0.5\n\n"
                
                for i, (start, end) in enumerate(zip(self.onset_samples[:-1], self.onset_samples[1:])):
                    audio_slice = self.y[start:end]
                    slice_filename = f"{base_filename}_slice_{i}.wav"
                    sf.write(os.path.join(output_dir, slice_filename), audio_slice, self.sr)
                    
                    # Add region to SFZ content
                    sfz_content += f"<region>\nsample={slice_filename}\n"
                    sfz_content += f"key={60 + i}\npitch_keycenter={60 + i}\n\n"
                
                # Write SFZ file
                sfz_filename = os.path.join(output_dir, f"{base_filename}.sfz")
                with open(sfz_filename, 'w') as sfz_file:
                    sfz_file.write(sfz_content)
                
                print(f"Splits saved as WAV files and SFZ in {output_dir}")

    def on_click(self, event):
        if self.onset_samples is not None and event.xdata is not None:
            click_sample = int(event.xdata)
            for i, (start, end) in enumerate(zip(self.onset_samples[:-1], self.onset_samples[1:])):
                if start <= click_sample < end:
                    self.play_segment(start, end)
                    break

    def play_segment(self, start, end):
        segment = self.y[start:end]
        sd.play(segment, self.sr)
        sd.wait()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AudioSplitterGUI()
    window.show()
    sys.exit(app.exec())
