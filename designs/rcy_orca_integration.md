# RCY + Orca OSC Integration Guide

A guide for integrating RCY with Orca (and other OSC clients) based on the new OSC-based architecture.

---

## 1. Introduction

This guide outlines how to use Orca as a client for the new OSC-based RCY architecture:

- Demonstrates the comprehensive OSC protocol for RCY's client-server architecture
- Shows how to connect Orca as a test client to the RCY core engine
- Provides examples of live-coding amen-break performances with Orca
- Serves as a practical example of RCY's new extensible architecture

> **Note:** This implementation is part of the larger architectural shift described in [osc-based-architecture.md](./osc-based-architecture.md), where RCY's core audio engine functions as an OSC server and all interfaces (including the main UI) are OSC clients.

---

## 2. OSC Protocol

The full RCY OSC protocol enables all operations, but here are the key messages for Orca integration:

### Basic Segment Control
| Address                     | Arguments                 | Description                                |
|-----------------------------|---------------------------|--------------------------------------------|
| `/audio/segment/play`       | `<segment_id>`            | Plays a specific segment                   |
| `/audio/segment/play/batch` | `<id1,id2,id3,...>`       | Queue multiple segments for playback       |
| `/audio/stop`               | _none_                    | Stops all playback                         |

### Playback Parameters
| Address                     | Arguments                 | Description                                |
|-----------------------------|---------------------------|--------------------------------------------|
| `/playback/tempo`           | `<bpm>`                   | Sets playback tempo in BPM                 |
| `/playback/volume`          | `<level>` (0.0-1.0)       | Sets master volume                         |
| `/playback/mode`            | `<mode>` (0=one-shot, 1=loop) | Sets playback mode                     |

### Extended Control
| Address                     | Arguments                 | Description                                |
|-----------------------------|---------------------------|--------------------------------------------|
| `/segment/parameter`        | `<id> <param> <value>`    | Adjust parameters for a segment            |
| `/sequence/play`            | `<sequence_id>`           | Trigger saved sequence                     |
| `/state/request`            | _none_                    | Request full state information             |

---

## 3. Architecture Overview

```
┌─────────────────┐      OSC       ┌───────────────────┐
│                 │ ◄───Messages───┤                   │
│  RCY Core       │                │  Orca             │
│  (OSC Server)   │ ───Messages──► │  (OSC Client)     │
│                 │                │                   │
└─────────────────┘                └───────────────────┘
        ▲                                  
        │                                  
  OSC Messages                       
        │                                  
        ▼                                  
┌─────────────────┐                
│  Other Clients  │                
│  (UI, MPC, etc.)│                
└─────────────────┘                
```

---

## 4. RCY Core Server Implementation

The RCY Core Engine functions as a standalone OSC server:

```python
from pythonosc import dispatcher, osc_server
import threading
import json

class RCYCoreEngine:
    def __init__(self, audio_processor, port=57120):
        self.audio_processor = audio_processor
        self.port = port
        self.clients = set()  # Connected clients for broadcasting
        
    def start(self):
        """Start the RCY core engine OSC server"""
        # Configure the OSC dispatcher
        self.dispatcher = dispatcher.Dispatcher()
        
        # Register OSC message handlers
        self._register_handlers()
        
        # Create and start the OSC server
        self.server = osc_server.ThreadingOSCUDPServer(
            ("0.0.0.0", self.port), self.dispatcher
        )
        
        print(f"RCY Core Engine OSC server listening on port {self.port}")
        
        # Start server in background thread
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True
        )
        self.server_thread.start()
        
    def _register_handlers(self):
        """Register all OSC message handlers"""
        # Basic segment control
        self.dispatcher.map("/audio/segment/play", self._handle_segment_play)
        self.dispatcher.map("/audio/segment/play/batch", self._handle_batch_play)
        self.dispatcher.map("/audio/stop", self._handle_stop)
        
        # Playback parameters
        self.dispatcher.map("/playback/tempo", self._handle_tempo)
        self.dispatcher.map("/playback/volume", self._handle_volume)
        self.dispatcher.map("/playback/mode", self._handle_mode)
        
        # State management
        self.dispatcher.map("/state/request", self._handle_state_request)
        
    def _handle_segment_play(self, address, *args):
        """Play a segment by ID"""
        if not args:
            return
            
        segment_id = int(args[0])
        print(f"Playing segment {segment_id}")
        
        # Get segment boundaries
        start, end = self.audio_processor.get_segment_boundaries(segment_id)
        
        # Play the segment
        self.audio_processor.play_segment(start, end)
        
    def _handle_batch_play(self, address, *args):
        """Queue multiple segments for playback"""
        if not args:
            return
            
        # Parse comma-separated segment IDs
        segment_ids = [int(id) for id in args[0].split(',')]
        print(f"Queuing segments: {segment_ids}")
        
        # Queue segments for playback
        for segment_id in segment_ids:
            start, end = self.audio_processor.get_segment_boundaries(segment_id)
            self.audio_processor.queue_segment(start, end)
            
    def _handle_stop(self, address, *args):
        """Stop all playback"""
        print("Stopping playback")
        self.audio_processor.stop_playback()
        
    def _handle_tempo(self, address, *args):
        """Set playback tempo"""
        if not args:
            return
            
        tempo = float(args[0])
        print(f"Setting tempo to {tempo} BPM")
        self.audio_processor.set_playback_tempo(True, tempo)
        
    def _handle_volume(self, address, *args):
        """Set master volume"""
        if not args:
            return
            
        volume = float(args[0])
        print(f"Setting volume to {volume}")
        self.audio_processor.set_volume(volume)
        
    def _handle_mode(self, address, *args):
        """Set playback mode"""
        if not args:
            return
            
        mode = int(args[0])
        mode_name = "one-shot" if mode == 0 else "loop"
        print(f"Setting playback mode to {mode_name}")
        self.audio_processor.set_playback_mode(mode_name)
        
    def _handle_state_request(self, address, *args):
        """Handle request for state information"""
        print("State information requested")
        
        # Get current state
        state = {
            "segments": len(self.audio_processor.get_segments()),
            "is_playing": self.audio_processor.is_playing,
            "tempo": self.audio_processor.get_tempo(),
            "playback_mode": self.audio_processor.get_playback_mode()
        }
        
        # Send state information to the requesting client
        client_address = self.server.get_client_address()
        if client_address:
            self._send_to_client(client_address, "/state/update", json.dumps(state))

    def _send_to_client(self, client_address, address, *args):
        """Send OSC message to a specific client"""
        from pythonosc import udp_client
        ip, port = client_address
        client = udp_client.SimpleUDPClient(ip, port)
        client.send_message(address, args)
```

---

## 5. Standalone Runner

Run the RCY core engine as a standalone server:

```python
import argparse
from rcy.audio_processor import WavAudioProcessor
from rcy.core_engine import RCYCoreEngine

def main():
    parser = argparse.ArgumentParser(description="RCY Core Engine OSC Server")
    parser.add_argument("--port", type=int, default=57120,
                      help="OSC server port (default: 57120)")
    parser.add_argument("--audio", type=str, required=True,
                      help="Path to audio file")
    args = parser.parse_args()

    # Initialize the audio processor with the specified file
    processor = WavAudioProcessor()
    processor.set_filename(args.audio)
    
    # Create and start the core engine
    engine = RCYCoreEngine(processor, port=args.port)
    engine.start()
    
    # Keep the main thread alive
    try:
        print("RCY Core Engine running. Press Ctrl+C to exit.")
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
```

Run with:
```bash
python -m rcy.server --audio path/to/amen.wav --port 57120
```

---

## 6. Connecting Orca to RCY

### Orca Configuration

1. Set Orca's OSC output to `127.0.0.1:57120` (or matching RCY server port)
2. Configure OSC address patterns in Orca's settings
3. Use the `;` operator to send OSC messages from Orca

### Example Configuration:

Configure Orca to map keys to specific OSC addresses:

| Key | OSC Address           | Argument Type |
|-----|------------------------|--------------|
| `0-9` | `/audio/segment/play` | Integer     |
| `a`   | `/audio/stop`        | Bang        |
| `t`   | `/playback/tempo`    | Integer     |
| `m`   | `/playback/mode`     | Integer     |

---

## 7. Orca Examples

Point Orca's OSC output to `127.0.0.1:57120`.

**Basic 8-slice sequencer:**
```
D4
|
t   0   1   2   3   4   5   6   7
> ; ; ; ; ; ; ; ;
```

**16-step pattern with stop:**
```
D4
|
t   0   1   2   3   4   5   a   7   0   3   6   2   5   a   3   4
> ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ;
```

**Tempo modulation:**
```
t   140 160 120 180
> > > > > ; ; ; ;
            |
            V
            /playback/tempo
```

**Dynamic pattern generator:**
```
R   8
| 
V
X   0   1   2   3   4   5   6   7
> > > > > > > > > ;
```
Here the `R` operator generates a value 0-7, and `X` translates it into a segment index.

**Multi-segment batch playback:**
```
;0,1,4
```
Sends a single message that queues segments 0, 1, and 4 in sequence.

---

## 8. Two-Way Communication

For more advanced integrations, you can set up Orca to receive messages from RCY as well:

1. Configure Orca's OSC input to listen for messages
2. RCY can send state updates to Orca (tempo changes, active segment, etc.)
3. Use Orca's `:` operator to listen for incoming OSC messages

This enables features like:
- Visual feedback of current segment in Orca
- Automatic tempo synchronization
- Monitoring of playback state
- Interactive visualization of RCY's internal state

---

## 9. Conclusion

Using Orca with RCY demonstrates the power of the new OSC-based architecture:

1. **Modular Design**: RCY core functions independently from its UI
2. **Multiple Clients**: Use RCY's UI, Orca, or other OSC clients simultaneously
3. **Creative Workflow**: Live-code beats instead of export/import cycles
4. **Extensibility**: Add new clients or controllers without modifying the core

As we continue developing the full OSC-based architecture, Orca provides an excellent testing platform and creative tool for RCY's new capabilities.