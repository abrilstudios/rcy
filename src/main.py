import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from audio_processor import WavAudioProcessor
from rcy_controller import RcyController
from rcy_view import RcyView
  
def main():
    # Set application name
    QApplication.setApplicationName("RCY")
    QApplication.setApplicationDisplayName("RCY")
    QApplication.setOrganizationName("Abril Audio Labs")
    QApplication.setOrganizationDomain("abrilaudio.com")
    app = QApplication([''])

    # Create model, view, and controller
    model = WavAudioProcessor()
    controller = RcyController(model)
    view = RcyView(controller)
    controller.set_view(view) 
    
    # Initial update
    controller.update_view()
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
