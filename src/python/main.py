import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
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

    try:
        # Create model with default preset 'amen_classic'
        model = WavAudioProcessor(preset_id='amen_classic')
        controller = RcyController(model)
        view = RcyView(controller)
        controller.set_view(view)
    except Exception as e:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Error", f"Failed to initialize application: {e}")
        sys.exit(1)
    
    # Initial update
    controller.update_view()
    
    # Ensure tempo is calculated and displayed
    controller.tempo = controller.model.get_tempo(controller.num_measures)
    view.update_tempo(controller.tempo)
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
