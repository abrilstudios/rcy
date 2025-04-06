import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from audio_processor import WavAudioProcessor
from rcy_controller import RcyController
from rcy_view import RcyView
from config_manager import config
  
def main():
    # Set application name using string resources
    QApplication.setApplicationName(config.get_string("ui", "applicationName"))
    QApplication.setApplicationDisplayName(config.get_string("ui", "applicationName"))
    QApplication.setOrganizationName(config.get_string("ui", "organizationName"))
    QApplication.setOrganizationDomain(config.get_string("ui", "organizationDomain"))
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
