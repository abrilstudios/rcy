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
        self.setGeometry(100, 100, 1000, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.figure, self.ax = plt.subplots(figsize=(10, 4))
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        self.sliders_layout = QHBoxLayout()
        self.sliders = {}
        self.create_slider("pre_max", "Pre Max", 1, 100, 25)
        self.create_slider("post_max", "Post Max", 1, 100, 25)
        self.create_slider("pre_avg", "Pre Avg", 1, 200, 50)
        self.create_slider("post_avg", "Post Avg", 1, 200, 50)
        self.create_slider("delta", "Delta", 1, 100, 50)  # 0.01 to 1.0
        self.create_slider("wait", "Wait", 1, 100, 30)
        self.layout.addLayout(self.sliders_layout)

        self.button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Audio")
        self.play_all_button = QPushButton("Play All")
        self.save_button = QPushButton("Save Splits")
        self.button_layout.addWidget(self.load_button)
        self.button_layout.addWidget(self.play_all_button)
        self.button_layout.addWidget(self.save_button)
        self.layout.addLayout(self.button_layout)

        self.load_button.clicked.connect(self.load_audio)
        self.play_all_button.clicked.connect(self.play_all)
        self.save_button.clicked.connect(self.save_splits)

        self.y = None
        self.sr = None
        self.onset_samples = None
        self.file_path = None

        self.canvas.mpl_connect('button_press_event', self.on_click)

    def create_slider(self, name, label, min_val, max_val, default):
        slider_layout = QVBoxLayout()
        slider_label = QLabel(label)
        slider = QSlider(Qt.Orientation.Vertical)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.valueChanged.connect(self.update_splits)
        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(slider)
        self.sliders_layout.addLayout(slider_layout)
        self.sliders[name] = slider

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
            pre_max = self.sliders["pre_max"].value()
            post_max = self.sliders["post_max"].value()
            pre_avg = self.sliders["pre_avg"].value()
            post_avg = self.sliders["post_avg"].value()
            delta = self.sliders["delta"].value() / 100.0  # Convert to 0.01-1.0 range
            wait = self.sliders["wait"].value()

            onset_env = librosa.onset.onset_strength(y=self.y, sr=self.sr, hop_length=512)
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=self.sr, 
                                                      hop_length=512, backtrack=True,
                                                      pre_max=pre_max, post_max=post_max,
                                                      pre_avg=pre_avg, post_avg=post_avg,
                                                      delta=delta, wait=wait)
            
            self.onset_samples = librosa.frames_to_samples(onset_frames)
            self.onset_samples = np.insert(self.onset_samples, 0, 0)
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
                    
                    sfz_content += f"<region>\nsample={slice_filename}\n"
                    sfz_content += f"key={60 + i}\npitch_keycenter={60 + i}\n\n"
                
                sfz_filename = os.path.join(output_dir, f"{base_filename}.sfz")
                with open(sfz_filename, 'w') as sfz_file:
                    sfz_file.write(sfz_content)
                
                print(f"Splits saved as WAV files and SFZ in {output_dir}")

    def on_click(self, event):
        if self.onset_samples is not None and event.xdata is not None:
            click_sample = int(event.xdata)
            print(event.button)
            print(event.modifiers)
            print('ctrl' in event.modifiers)
            print('alt' in event.modifiers)
            if event.button == 3 and 'ctrl' in event.modifiers: 
                self.remove_split(click_sample)
            elif event.button == 1 and 'alt' in event.modifiers: 
                self.add_split(click_sample)
            else:
                for i, (start, end) in enumerate(zip(self.onset_samples[:-1], self.onset_samples[1:])):
                    if start <= click_sample < end:
                        self.play_segment(start, end)
                        break

    def remove_split(self, click_sample):
        if len(self.onset_samples) > 2:  # Ensure we have at least one split to remove
            closest_split = min(self.onset_samples, key=lambda x: abs(x - click_sample))
            if closest_split != 0 and closest_split != len(self.y):  # Don't remove start and end
                self.onset_samples = self.onset_samples[self.onset_samples != closest_split]
                self.plot_waveform()
                for sample in self.onset_samples:
                    self.ax.axvline(x=sample, color='r', linestyle='--')
                self.canvas.draw()

    def add_split(self, click_sample):
        if self.onset_samples is not None:
            # Insert the new split point
            print("Insert the new split point")
            self.onset_samples = np.sort(np.append(self.onset_samples, click_sample))
        
            # Redraw the waveform and split lines
            self.plot_waveform()
            for sample in self.onset_samples:
                self.ax.axvline(x=sample, color='r', linestyle='--')
            self.canvas.draw()

    def play_segment(self, start, end):
        segment = self.y[start:end]
        sd.play(segment, self.sr)
        sd.wait()

    def play_all(self):
        if self.y is not None and self.sr is not None:
            sd.play(self.y, self.sr)
            sd.wait()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AudioSplitterGUI()
    window.show()
    sys.exit(app.exec())
