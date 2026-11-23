"""EP-133 device communication layer.

Provides high-level access to the EP-133 over MIDI SysEx.
"""

import json
import logging
import time
from typing import Iterator

logger = logging.getLogger(__name__)

try:
    import mido
except ImportError:
    mido = None

from ep133.protocol import (
    TE_MANUFACTURER,
    UPLOAD_CHUNK_SIZE,
    PATTERN_STEPS,
    PATTERN_PADS,
    PATTERN_PAD_BYTES,
    build_te_message,
    build_file_init_request,
    build_file_list_request,
    build_metadata_get_request,
    build_metadata_set_request,
    build_upload_init_request,
    build_upload_chunk_request,
    build_upload_end_request,
    build_pattern_get_request,
    build_pattern_put_request,
    parse_te_response,
    parse_file_list_response,
    parse_pattern_response,
    unpack_7bit,
)


class EP133Error(Exception):
    """Base exception for EP-133 errors."""
    pass


class EP133NotFound(EP133Error):
    """EP-133 device not found."""
    pass


class EP133Timeout(EP133Error):
    """Timeout waiting for response."""
    pass


class EP133Device:
    """High-level interface to EP-133 device."""

    def __init__(self, in_port: str | None = None, out_port: str | None = None):
        """Initialize EP-133 device connection.

        Args:
            in_port: MIDI input port name (auto-detect if None)
            out_port: MIDI output port name (auto-detect if None)
        """
        if mido is None:
            raise EP133Error("mido not installed. Run: pip install mido python-rtmidi")

        self._in_port_name = in_port
        self._out_port_name = out_port
        self._in_port = None
        self._out_port = None
        self._seq = 0
        self._timeout = 2.0

    def _next_seq(self) -> int:
        """Get next sequence number."""
        seq = self._seq
        self._seq = (self._seq + 1) & 0x7F
        return seq

    @staticmethod
    def find_ports() -> tuple[str | None, str | None]:
        """Find EP-133 MIDI ports.

        Returns:
            Tuple of (input_port, output_port) names, or None if not found
        """
        if mido is None:
            return None, None

        inputs = mido.get_input_names()
        outputs = mido.get_output_names()

        in_port = next((n for n in inputs if "EP-133" in n), None)
        out_port = next((n for n in outputs if "EP-133" in n), None)

        return in_port, out_port

    def connect(self) -> None:
        """Open MIDI ports to device."""
        if self._in_port_name is None or self._out_port_name is None:
            found_in, found_out = self.find_ports()
            if self._in_port_name is None:
                self._in_port_name = found_in
            if self._out_port_name is None:
                self._out_port_name = found_out

        if self._in_port_name is None or self._out_port_name is None:
            raise EP133NotFound("EP-133 MIDI ports not found")

        self._in_port = mido.open_input(self._in_port_name)
        self._out_port = mido.open_output(self._out_port_name)

        # Initialize file protocol
        self._init_file_protocol()

    def _init_file_protocol(self) -> None:
        """Initialize the file protocol.

        Must be called after connecting before any file operations.
        """
        req = build_file_init_request(self._next_seq())
        resp = self.send_and_receive(req)
        # We don't fail if init doesn't respond - device may already be initialized

    def sync(self) -> bool:
        """Re-initialize file protocol to sync device state.

        Call this after bulk operations to ensure the device's internal
        state is refreshed and external tools (like EP-133 Sample Tool)
        see the updated state.

        Returns:
            True if sync succeeded
        """
        req = build_file_init_request(self._next_seq())
        resp = self.send_and_receive(req)
        return resp is not None and resp.get("status", 1) == 0

    def disconnect(self) -> None:
        """Close MIDI ports."""
        if self._in_port:
            self._in_port.close()
            self._in_port = None
        if self._out_port:
            self._out_port.close()
            self._out_port = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._in_port is not None and self._out_port is not None

    @property
    def port_names(self) -> tuple[str | None, str | None]:
        """Get current port names."""
        return self._in_port_name, self._out_port_name

    def _send_raw(self, data: bytes) -> None:
        """Send raw SysEx message."""
        if not self._out_port:
            raise EP133Error("Not connected")
        # Strip F0/F7 for mido
        self._out_port.send(mido.Message('sysex', data=list(data[1:-1])))

    def _recv_raw(self, timeout: float | None = None) -> bytes | None:
        """Receive raw SysEx message."""
        if not self._in_port:
            raise EP133Error("Not connected")

        timeout = timeout or self._timeout
        start = time.time()

        while time.time() - start < timeout:
            for msg in self._in_port.iter_pending():
                if msg.type == 'sysex':
                    # Add F0/F7 back
                    return bytes([0xF0] + list(msg.data) + [0xF7])
            time.sleep(0.01)

        return None

    def drain_pending(self) -> int:
        """Drain all pending messages from the receive buffer.

        Returns:
            Number of messages drained
        """
        drained = 0
        while True:
            raw = self._recv_raw(timeout=0.01)
            if raw is None:
                break
            drained += 1
            logger.debug(f"Drained pending message: {raw.hex()[:40]}...")
        return drained

    def send_and_receive(self, data: bytes, timeout: float | None = None) -> dict | None:
        """Send message and wait for response.

        The EP-133 sends async notifications (cmd not in 0x2x range) that we skip.
        We wait for the first actual response (is_response=True).

        Args:
            data: Complete SysEx message
            timeout: Response timeout in seconds

        Returns:
            Parsed response dict, or None on timeout
        """
        # Drain any pending messages before sending
        self.drain_pending()

        self._send_raw(data)

        timeout = timeout or self._timeout
        start = time.time()

        while time.time() - start < timeout:
            raw_response = self._recv_raw(timeout=0.1)
            if raw_response is None:
                continue

            parsed = parse_te_response(raw_response)
            if parsed is None:
                logger.warning(f"Invalid response format: {raw_response.hex()}")
                continue

            # Skip non-response messages (notifications from device)
            # Responses have cmd in 0x2x range (is_response=True)
            if not parsed.get("is_response", False):
                logger.debug(f"Skipping non-response: cmd=0x{parsed.get('cmd', 0):02x}")
                continue

            return parsed

        return None

    def list_directory(self, node_id: int) -> list[dict]:
        """List contents of a directory node.

        Args:
            node_id: Directory node ID (0 for root)

        Returns:
            List of file/directory entries
        """
        all_entries = []
        page = 0

        while True:
            req = build_file_list_request(self._next_seq(), node_id, page)
            resp = self.send_and_receive(req)

            if resp is None:
                raise EP133Timeout(f"Timeout listing node {node_id}")

            if resp.get("status", 0) != 0:
                break

            payload = resp.get("payload", b"")
            entries = parse_file_list_response(payload)

            if not entries:
                break

            all_entries.extend(entries)
            page += 1

            # Safety limit
            if page > 100:
                break

        return all_entries

    def get_metadata(self, node_id: int) -> dict | None:
        """Get metadata for a node.

        Metadata may span multiple pages. This method fetches all pages
        and concatenates the JSON.

        Args:
            node_id: Node ID

        Returns:
            Parsed JSON metadata, or None if not found
        """
        all_json_bytes = bytearray()
        page = 0

        while True:
            req = build_metadata_get_request(self._next_seq(), node_id, page)
            resp = self.send_and_receive(req)

            if resp is None:
                break

            if resp.get("status", 1) != 0:
                break

            payload = resp.get("payload", b"")
            if len(payload) < 2:
                break

            # First 2 bytes are header, rest is JSON fragment
            json_fragment = payload[2:]
            if not json_fragment or json_fragment == b'\x00':
                break

            all_json_bytes.extend(json_fragment.rstrip(b'\x00'))
            page += 1

            # Safety limit
            if page > 20:
                break

        if not all_json_bytes:
            return None

        try:
            json_str = bytes(all_json_bytes).decode('utf-8')
            return json.loads(json_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def set_metadata(self, node_id: int, metadata: dict) -> bool:
        """Set metadata for a node.

        Args:
            node_id: Node ID
            metadata: Metadata dict to set

        Returns:
            True if successful
        """
        json_str = json.dumps(metadata, separators=(',', ':'))
        logger.debug(f"set_metadata: node_id={node_id}, metadata={json_str}")

        req = build_metadata_set_request(self._next_seq(), node_id, json_str)
        resp = self.send_and_receive(req)

        if resp is None:
            logger.warning(f"set_metadata: no response for node_id={node_id}")
            return False

        status = resp.get("status", 1)
        success = status == 0
        if not success:
            logger.warning(f"set_metadata: failed for node_id={node_id}, status={status}, resp={resp}")
        else:
            logger.debug(f"set_metadata: success for node_id={node_id}")

        return success

    def assign_sound(self, pad_node_id: int, sound_number: int) -> bool:
        """Assign a sound to a pad.

        Args:
            pad_node_id: Pad's node ID
            sound_number: Sound number to assign

        Returns:
            True if successful
        """
        return self.set_metadata(pad_node_id, {"sym": sound_number})

    def verify_pad_assignment(self, pad_node_id: int, expected_sound: int) -> bool:
        """Verify a pad is assigned to the expected sound.

        Args:
            pad_node_id: Pad's node ID
            expected_sound: Expected sound number

        Returns:
            True if assignment matches
        """
        metadata = self.get_metadata(pad_node_id)
        if metadata is None:
            logger.warning(f"verify_pad_assignment: no metadata for node {pad_node_id}")
            return False

        actual = metadata.get("sym")
        if actual != expected_sound:
            logger.warning(f"verify_pad_assignment: node {pad_node_id} has sym={actual}, expected {expected_sound}")
            return False

        logger.debug(f"verify_pad_assignment: node {pad_node_id} correctly has sym={expected_sound}")
        return True

    def walk_filesystem(self, node_id: int = 0, path: str = "/") -> Iterator[tuple[str, dict]]:
        """Walk the filesystem tree.

        Args:
            node_id: Starting node ID (0 for root)
            path: Current path prefix

        Yields:
            Tuples of (path, entry_dict)
        """
        entries = self.list_directory(node_id)
        for entry in entries:
            entry_path = f"{path}{entry['name']}"
            yield entry_path, entry
            if entry["is_dir"]:
                yield from self.walk_filesystem(entry["node_id"], f"{entry_path}/")

    def upload_sample(
        self,
        slot: int,
        audio_data: bytes,
        channels: int = 1,
        samplerate: int = 44100,
        name: str | None = None,
        progress_callback=None
    ) -> bool:
        """Upload raw PCM audio to a sound slot.

        Args:
            slot: Sound slot number (1-999)
            audio_data: Raw s16 PCM bytes (16-bit signed, little-endian)
            channels: Number of channels (1 or 2)
            samplerate: Sample rate (must be 44100)
            name: Optional display name for the sample
            progress_callback: Optional callback(chunks_sent, total_chunks)

        Returns:
            True if upload succeeded

        Raises:
            EP133Error: If upload fails
            EP133Timeout: If device doesn't respond
        """
        if not 1 <= slot <= 999:
            raise EP133Error(f"Slot must be 1-999, got {slot}")

        if samplerate != 44100:
            raise EP133Error(f"Sample rate must be 44100 Hz, got {samplerate}")

        if channels not in (1, 2):
            raise EP133Error(f"Channels must be 1 or 2, got {channels}")

        file_size = len(audio_data)
        total_chunks = (file_size + UPLOAD_CHUNK_SIZE - 1) // UPLOAD_CHUNK_SIZE

        # Send init message
        init_req = build_upload_init_request(
            self._next_seq(),
            slot,
            file_size,
            channels,
            samplerate,
            name
        )
        init_resp = self.send_and_receive(init_req, timeout=5.0)
        if init_resp is None:
            raise EP133Timeout("No response to upload init")
        if init_resp.get("status", 1) != 0:
            raise EP133Error(f"Upload init failed: status={init_resp.get('status')}")

        # Send data chunks
        chunk_index = 0
        offset = 0

        while offset < file_size:
            chunk_data = audio_data[offset:offset + UPLOAD_CHUNK_SIZE]
            chunk_req = build_upload_chunk_request(
                self._next_seq(),
                chunk_index,
                chunk_data
            )

            chunk_resp = self.send_and_receive(chunk_req, timeout=2.0)
            if chunk_resp is None:
                raise EP133Timeout(f"No response to chunk {chunk_index}")
            if chunk_resp.get("status", 1) != 0:
                raise EP133Error(f"Chunk {chunk_index} failed: status={chunk_resp.get('status')}")

            offset += UPLOAD_CHUNK_SIZE
            chunk_index += 1

            if progress_callback:
                progress_callback(chunk_index, total_chunks)

        # Send end marker
        end_req = build_upload_end_request(self._next_seq(), chunk_index)
        end_resp = self.send_and_receive(end_req, timeout=5.0)
        if end_resp is None:
            raise EP133Timeout("No response to upload end")

        return True

    def read_pattern_step(self, layer: int, step_index: int) -> dict | None:
        """Read a single step of pattern data.

        Args:
            layer: Data layer (0=audio, 1=triggers/notes, 2=FX)
            step_index: Step index (0-127)

        Returns:
            Parsed pattern data dict, or None on error
        """
        req = build_pattern_get_request(self._next_seq(), layer, step_index)
        resp = self.send_and_receive(req)

        if resp is None:
            return None

        payload = resp.get("payload", b"")
        if not payload:
            return None

        return parse_pattern_response(payload)

    def read_pattern(self, layer: int = 1, progress_callback=None) -> list[dict]:
        """Read all 128 steps of pattern data for a layer.

        Args:
            layer: Data layer (0=audio, 1=triggers/notes, 2=FX)
            progress_callback: Optional callback(step, total)

        Returns:
            List of 128 parsed step dicts
        """
        steps = []
        for step in range(PATTERN_STEPS):
            step_data = self.read_pattern_step(layer, step)
            if step_data:
                steps.append(step_data)
            else:
                # Create empty step on error
                steps.append({
                    "flags": 0,
                    "layer": layer,
                    "step_index": step,
                    "step_data": b"\x00" * (PATTERN_PADS * PATTERN_PAD_BYTES),
                    "pads": [],
                })

            if progress_callback:
                progress_callback(step + 1, PATTERN_STEPS)

        return steps

    def write_pattern_step(self, layer: int, step_index: int, step_data: bytes) -> bool:
        """Write a single step of pattern data.

        WARNING: This is experimental and may not work correctly.
        The PUT protocol for patterns has not been fully verified.

        Args:
            layer: Data layer (0=audio, 1=triggers/notes, 2=FX)
            step_index: Step index (0-127)
            step_data: Step data (324 bytes = 12 pads × 27 bytes)

        Returns:
            True if device acknowledged, False otherwise
        """
        req = build_pattern_put_request(self._next_seq(), layer, step_index, step_data)
        resp = self.send_and_receive(req)

        if resp is None:
            return False

        # Check for success status
        return resp.get("status", 1) == 0

    def write_pattern(
        self,
        steps: list[dict],
        layer: int = 1,
        progress_callback=None
    ) -> bool:
        """Write all 128 steps of pattern data for a layer.

        WARNING: This is experimental and may not work correctly.

        Args:
            steps: List of 128 step dicts (from read_pattern or constructed)
            layer: Data layer (0=audio, 1=triggers/notes, 2=FX)
            progress_callback: Optional callback(step, total)

        Returns:
            True if all steps written successfully
        """
        if len(steps) != PATTERN_STEPS:
            raise EP133Error(f"Pattern must have {PATTERN_STEPS} steps, got {len(steps)}")

        for i, step in enumerate(steps):
            step_data = step.get("step_data", b"")
            if len(step_data) != PATTERN_PADS * PATTERN_PAD_BYTES:
                # Pad with zeros if needed
                step_data = step_data.ljust(PATTERN_PADS * PATTERN_PAD_BYTES, b"\x00")

            if not self.write_pattern_step(layer, i, step_data):
                return False

            if progress_callback:
                progress_callback(i + 1, PATTERN_STEPS)

        return True
