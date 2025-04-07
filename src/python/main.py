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
        
        # Get preset info to initialize controller with correct measure count
        preset_info = config.get_preset_info('amen_classic')
        initial_measures = preset_info.get('measures', 1) if preset_info else 1
        print(f"Initializing with preset amen_classic, measures={initial_measures}")
        
        # Create controller with correct initial measures
        controller = RcyController(model)
        controller.num_measures = initial_measures  # Set before view creation
        
        # Create and connect view
        view = RcyView(controller)
        controller.set_view(view)
        
        # Ensure view has correct number of measures
        if hasattr(view, 'measures_input'):
            view.measures_input.setText(str(initial_measures))
    except Exception as e:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Error", f"Failed to initialize application: {e}")
        sys.exit(1)
    
    # Initial update
    controller.update_view()
    
    # Ensure tempo is calculated and displayed with correct measure count
    controller.tempo = controller.model.get_tempo(controller.num_measures)
    view.update_tempo(controller.tempo)
    print(f"Initial tempo: {controller.tempo:.2f} BPM based on {controller.num_measures} measures")
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
