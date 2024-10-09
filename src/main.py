import sys
from PyQt6.QtWidgets import QApplication
from audio_processor import SinAudioProcessor
from rcy_controller import RcyController
from rcy_view import RcyView

def main():
    app = QApplication(sys.argv)
    
    # Create model, view, and controller
    model = SinAudioProcessor(total_time=100, sample_rate=100)
    controller = RcyController(model)
    view = RcyView(controller)
    controller.set_view(view) 
    
    # Initial update
    controller.update_view()
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
