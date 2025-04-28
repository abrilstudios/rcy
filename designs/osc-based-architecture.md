# OSC-Based Architecture: UI as Client

## Overview

This design proposes a significant architectural shift for RCY, moving from a tightly coupled application to a service-oriented architecture using Open Sound Control (OSC) as the communication protocol. In this architecture, the core audio processing engine operates as an OSC server, while the UI and external controllers function as OSC clients.

```
┌─────────────────┐      OSC       ┌───────────────────┐
│                 │ ◄───Messages───┤                   │
│  RCY Core       │                │  RCY UI           │
│  (OSC Server)   │ ───Messages──► │  (OSC Client)     │
│                 │                │                   │
└─────────────────┘                └───────────────────┘
        ▲                                  ▲
        │                                  │
  OSC Messages                       OSC Messages
        │                                  │
        ▼                                  ▼
┌─────────────────┐                ┌───────────────────┐
│  External       │                │  Other UI         │
│  Hardware       │                │  Clients          │
│  (MPC, etc.)    │                │  (Web, Mobile)    │
└─────────────────┘                └───────────────────┘
```

## Motivation

The current architecture requires export/import cycles to test segment arrangements, creating friction in the workflow. Additionally, the tight coupling between UI and audio processing makes it difficult to implement advanced features or alternative interfaces.

By adopting an OSC-based architecture, we can:

1. Enable real-time control of segments via hardware like MPC
2. Create a more extensible platform that can evolve independently
3. Support multiple interfaces and remote control
4. Facilitate better integration with other audio tools
5. Implement a high-performance audio engine optimized for real-time playback

## Architecture Components

### 1. Core Engine (OSC Server)

The core engine runs as an OSC server that:
- Handles all audio processing operations
- Manages segments and sample data
- Controls playback with high performance
- Broadcasts state changes to connected clients
- Implements the OSC message protocol

### 2. User Interface (OSC Client)

The UI becomes an OSC client that:
- Sends control messages to the core engine
- Receives and visualizes state updates
- Provides configuration for OSC mappings
- Manages connection to local or remote core engines

### 3. External Controllers

External hardware/software can connect as additional OSC clients:
- Hardware controllers (MPC, Launchpad, etc.)
- DAWs with OSC support
- Custom control applications

### 4. Protocol Definition

A comprehensive OSC address pattern scheme for all operations:

#### Core Operations:
- `/file/open [path]` - Open an audio file
- `/file/save [path]` - Save current project
- `/file/export [path]` - Export processed audio

#### Audio Processing:
- `/audio/segment/add [time]` - Add segment marker
- `/audio/segment/remove [id]` - Remove segment
- `/audio/segment/play [id] [velocity?]` - Play segment
- `/audio/segment/stop` - Stop playback
- `/audio/process/transient [threshold]` - Process transients

#### Waveform View:
- `/waveform/zoom [factor]` - Zoom waveform
- `/waveform/scroll [position]` - Scroll waveform
- `/waveform/marker/start [time]` - Set start marker
- `/waveform/marker/end [time]` - Set end marker

#### State Updates:
- `/state/request` - Request full state update
- `/state/full [json]` - Full state information
- `/state/segment/add [id] [data]` - Segment added
- `/state/segment/remove [id]` - Segment removed
- `/state/playback [playing] [segment_id]` - Playback state

## Implementation

### Core Engine Implementation

```python
class RCYCoreEngine:
    def __init__(self, osc_port=9001):
        # Initialize audio processing components
        self.audio_processor = AudioProcessor()
        self.segment_manager = SegmentManager()
        
        # Initialize OSC server
        self.osc_server = OSCServer(
            ip="0.0.0.0",  # Listen on all interfaces
            port=osc_port,
            callback=self.handle_osc_message
        )
        
        # Register OSC message handlers
        self.register_handlers()
        
    def start(self):
        """Start the core engine and OSC server"""
        self.osc_server.start()
        
    def stop(self):
        """Stop the core engine and OSC server"""
        self.osc_server.stop()
        
    def register_handlers(self):
        """Register all OSC message handlers"""
        # File operations
        self.osc_server.add_handler("/file/open", self.handle_file_open)
        self.osc_server.add_handler("/file/save", self.handle_file_save)
        
        # Audio processing
        self.osc_server.add_handler("/audio/segment/add", self.handle_add_segment)
        self.osc_server.add_handler("/audio/segment/remove", self.handle_remove_segment)
        self.osc_server.add_handler("/audio/segment/play", self.handle_play_segment)
        self.osc_server.add_handler("/audio/segment/stop", self.handle_stop_playback)
        
        # Waveform view
        self.osc_server.add_handler("/waveform/zoom", self.handle_zoom)
        self.osc_server.add_handler("/waveform/scroll", self.handle_scroll)
        
        # State updates (sent to clients)
        self.osc_server.add_handler("/state/request", self.handle_state_request)
        
    def handle_osc_message(self, address, *args):
        """Main OSC message handler that routes to specific handlers"""
        print(f"Received OSC message: {address} {args}")
        # Routing happens in the OSC server based on registered handlers
        
    def handle_file_open(self, address, *args):
        """Handle file open request"""
        if len(args) < 1:
            return
        filename = args[0]
        success = self.audio_processor.load_file(filename)
        # Send notification to all clients about new file
        self.broadcast_update("/file/opened", filename, success)
        
    def handle_play_segment(self, address, *args):
        """Handle segment play request"""
        if len(args) < 1:
            return
        segment_id = int(args[0])
        # Additional parameters can be passed (velocity, etc.)
        success = self.audio_processor.play_segment(segment_id)
        # No need to broadcast - playback is stateless
        
    def broadcast_update(self, address, *args):
        """Send an OSC update to all connected clients"""
        # Implementation depends on how client connections are tracked
        self.osc_server.broadcast(address, *args)
```

### UI Client Implementation

```python
class RCYUI:
    def __init__(self, server_ip="127.0.0.1", server_port=9001, client_port=9002):
        # Initialize UI components (PyQt, etc.)
        self.app = QApplication([])
        self.main_window = QMainWindow()
        
        # Initialize OSC client
        self.osc_client = OSCClient(server_ip, server_port)
        
        # Initialize OSC receiver for updates from server
        self.osc_receiver = OSCReceiver(port=client_port, callback=self.handle_osc_message)
        
        # Set up UI components
        self.setup_ui()
        
    def start(self):
        """Start the UI and connect to core engine"""
        # Start OSC receiver
        self.osc_receiver.start()
        
        # Request initial state from server
        self.osc_client.send("/state/request")
        
        # Start UI event loop
        self.app.exec_()
        
    def setup_ui(self):
        """Set up all UI components"""
        # Create waveform view
        self.waveform_view = WaveformView()
        
        # Connect UI signals to OSC message senders
        self.waveform_view.segment_clicked.connect(self.on_segment_clicked)
        
    def on_segment_clicked(self, segment_id):
        """Handle segment click in UI"""
        # Send OSC message to play segment
        self.osc_client.send("/audio/segment/play", segment_id)
        
    def handle_osc_message(self, address, *args):
        """Handle incoming OSC messages from server"""
        if address == "/state/full":
            # Update UI with full state information
            self.update_ui_state(json.loads(args[0]))
        elif address == "/file/opened":
            # Update UI for newly opened file
            filename, success = args
            if success:
                self.update_file_display(filename)
            else:
                self.show_error(f"Failed to open file: {filename}")
```

## Configuration and Deployment

### Running Modes

1. **Integrated Mode**:
   - Core engine and UI run as separate threads in same process
   - Automatic configuration for local communication
   - Simplified startup for standard use cases

2. **Distributed Mode**:
   - Core engine runs as standalone server
   - UI connects to remote or local server
   - Configuration for network connection parameters

### Discovery and Connection

- Auto-discovery of local or network RCY core engines
- Connection management for multiple clients
- Persistent configuration for connection preferences

## Benefits

1. **Workflow Improvement**:
   - Directly trigger segments in real-time
   - Test arrangements without export/import cycles
   - Control RCY with hardware controllers

2. **Architecture Improvements**:
   - Clear separation of concerns
   - Independent evolution of UI and engine
   - Better testability of components

3. **Extensibility**:
   - Support for multiple simultaneous clients
   - Potential for alternative UIs (web, mobile)
   - Plugin architecture for additional processing

## Challenges and Considerations

1. **Performance**:
   - Ensuring OSC messaging doesn't introduce latency
   - Optimizing state synchronization
   - Handling large audio data efficiently

2. **Complexity**:
   - More complex architecture to maintain
   - Need for comprehensive protocol documentation
   - Additional error handling for network issues

3. **Security**:
   - Network access controls
   - Validation of incoming messages
   - Protection against malformed requests

## Implementation Plan

1. **Phase 1: Core OSC Server** (1-2 weeks)
   - Implement basic OSC server in core engine
   - Define protocol for essential operations
   - Create standalone server mode

2. **Phase 2: UI Client Conversion** (1-2 weeks)
   - Convert UI to OSC client
   - Implement state synchronization
   - Handle connection management

3. **Phase 3: External Control Support** (1 week)
   - Implement MPC/controller mapping
   - Add configuration interface
   - Test with hardware controllers

4. **Phase 4: Advanced Features** (1-2 weeks)
   - Multiple client support
   - Network distribution
   - Performance optimization

## Conclusion

This architectural shift represents a significant evolution for RCY, transforming it from a standalone application into a flexible platform for audio processing and segment manipulation. By decoupling the UI from the core engine via OSC, we create a more extensible system that can adapt to various workflows and integrate more effectively with external hardware and software.

The modular approach also aligns with modern software design principles, making the codebase easier to maintain and extend in the future. While this represents a substantial development effort, the benefits in terms of workflow improvement and future capabilities make it a worthwhile investment.