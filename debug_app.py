import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/rcy_debug_full.log'
)

# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s: %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

logger = logging.getLogger('debug_app')

# Import application modules - these should be found through PYTHONPATH
from config_manager import config
from audio_processor import WavAudioProcessor
from rcy_controller import RcyController
from rcy_view import RcyView

def print_transient_detection_config():
    """Print the current transient detection configuration"""
    td_config = config.get_value_from_json_file("audio.json", "transientDetection", {})
    logger.info("Current Transient Detection Configuration:")
    logger.info(f"  threshold:   {td_config.get('threshold', 0.2)}")
    logger.info(f"  waitTime:    {td_config.get('waitTime', 1)}")
    logger.info(f"  preMax:      {td_config.get('preMax', 1)}")
    logger.info(f"  postMax:     {td_config.get('postMax', 1)}")
    logger.info(f"  deltaFactor: {td_config.get('deltaFactor', 0.1)}")

def run_app():
    try:
        logger.info("Starting application")
        
        # Print current transient detection config
        print_transient_detection_config()
        
        # Set up a Qt application
        app = QApplication(sys.argv)
        
        logger.info("Imports successful")
        
        # Create model with default preset
        model = WavAudioProcessor(preset_id='amen_classic')
        logger.info("Model created")
        
        # Get preset info
        preset_info = config.get_preset_info('amen_classic')
        initial_measures = preset_info.get('measures', 1) if preset_info else 1
        logger.info(f"Initial measures: {initial_measures}")
        
        # Create controller
        controller = RcyController(model)
        controller.num_measures = initial_measures
        logger.info("Controller created")
        
        # Create view
        backend = config.get_value_from_json_file("audio.json", "backend", "matplotlib")
        use_pyqtgraph = (backend == "pyqtgraph")
        logger.info(f"Using backend: {backend}")
        
        view = RcyView(controller, use_pyqtgraph=use_pyqtgraph)
        logger.info("View created")
        controller.set_view(view)
        
        # Set measures
        if hasattr(view, 'measures_input'):
            view.measures_input.setText(str(initial_measures))
        
        # Initial update
        controller.update_view()
        
        # Update tempo
        controller.tempo = controller.model.get_tempo(controller.num_measures)
        view.update_tempo(controller.tempo)
        
        # Automatically split by transients to show current settings
        controller.split_audio(method='transients')
        logger.info("Split by transients with configured parameters")
        
        # Show the view
        view.show()
        
        # Start the application event loop
        logger.info("Starting event loop")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.exception(f"Error: {e}")
        return 1

if __name__ == "__main__":
    run_app()