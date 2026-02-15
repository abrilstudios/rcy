"""S2800 sampler device communication.

Single class, single code path per operation. Talks to the Akai S2800
over MIDI using S1000-family SysEx protocol and MIDI SDS for audio data.
"""

import logging
import platform
import time

import mido

if platform.system() == "Darwin":
    mido.set_backend("mido.backends.rtmidi/MACOSX_CORE")

from s2800.protocol import (
    AKAI_MFR, S1000_MODEL,
    FUNC_RPLIST, FUNC_PLIST,
    FUNC_RPDATA,
    FUNC_RSLIST, FUNC_SLIST,
    FUNC_SDATA,
    FUNC_PDATA, FUNC_KDATA,
    FUNC_RKDATA,
    FUNC_DELP,
    FUNC_S3K_PDATA, FUNC_S3K_KDATA,
    FUNC_S3K_RPDATA, FUNC_S3K_RKDATA,
    FUNC_DELS,
    FUNC_REPLY,
    REPLY_OK,
    build_message,
    nibble_encode, nibble_decode,
    decode_akai_name,
)
from s2800.headers import build_sample_header, build_program_header, build_keygroup
from s2800.sds import (
    pack_16bit_to_sds,
    build_data_packet,
    parse_handshake, wait_for_handshake,
    SDS_ACK, SDS_NAK, SDS_CANCEL, SDS_WAIT,
    SDS_PACKET_DATA_BYTES,
    SDS_HANDSHAKE_TIMEOUT, SDS_PACKET_TIMEOUT,
    SDS_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class S2800Error(Exception):
    """Base exception for S2800 errors."""
    pass


class S2800:
    """Akai S2800 sampler interface over MIDI SysEx.

    Args:
        port_in: MIDI input port name, or None for auto-detection
        port_out: MIDI output port name, or None for auto-detection
        channel: S1000 exclusive channel (default 0x00)
    """

    # Port name patterns for auto-detection (Volt 2 first, then generic)
    PORT_PATTERNS = ["Volt 2", "Volt", "S2800", "Akai", "AKAI"]

    def __init__(self, port_in: str | None = None, port_out: str | None = None,
                 channel: int = 0x00):
        self._port_in_name = port_in
        self._port_out_name = port_out
        self._channel = channel
        self._port_in = None
        self._port_out = None

    # --- Connection ---

    @staticmethod
    def find_ports() -> tuple[str | None, str | None]:
        """Auto-detect MIDI ports for the S2800.

        Searches for ports matching known patterns (Volt 2, Akai, etc).

        Returns:
            Tuple of (input_port_name, output_port_name), either may be None
        """
        inputs = mido.get_input_names()
        outputs = mido.get_output_names()

        in_port = None
        out_port = None

        for pattern in S2800.PORT_PATTERNS:
            if in_port is None:
                in_port = next((n for n in inputs if pattern in n), None)
            if out_port is None:
                out_port = next((n for n in outputs if pattern in n), None)

        return in_port, out_port

    def open(self):
        """Open MIDI ports. Auto-detects if port names were not provided."""
        in_name = self._port_in_name
        out_name = self._port_out_name

        if in_name is None or out_name is None:
            auto_in, auto_out = self.find_ports()
            if in_name is None:
                in_name = auto_in
            if out_name is None:
                out_name = auto_out

        if not in_name or not out_name:
            raise S2800Error(
                "No MIDI ports found. Use --in/--out to specify ports, "
                "or run 's2800 ports' to list available ports."
            )

        self._port_in_name = in_name
        self._port_out_name = out_name
        self._port_out = mido.open_output(out_name)
        self._port_in = mido.open_input(in_name)

    def close(self):
        """Close MIDI ports."""
        if self._port_in:
            self._port_in.close()
            self._port_in = None
        if self._port_out:
            self._port_out.close()
            self._port_out = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # --- Internal helpers ---

    def _send(self, function: int, data: bytes = b""):
        """Send an S1000-family SysEx message."""
        msg = build_message(self._channel, function, data)
        self._port_out.send(mido.Message('sysex', data=list(msg[1:-1])))

    def _recv(self, timeout: float = 5.0) -> tuple[int, bytes] | None:
        """Wait for an S1000-family SysEx reply.

        Returns:
            Tuple of (function_code, payload) or None on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            for m in self._port_in.iter_pending():
                if m.type == 'sysex' and len(m.data) >= 4:
                    data = list(m.data)
                    if data[0] == AKAI_MFR and data[3] == S1000_MODEL:
                        function = data[2]
                        payload = bytes(data[4:])
                        return function, payload
            time.sleep(0.01)
        return None

    def _drain(self):
        """Drain all pending MIDI messages from the input buffer."""
        for _ in self._port_in.iter_pending():
            pass

    def _wait_for_sdata_response(self, timeout: float = SDS_HANDSHAKE_TIMEOUT):
        """Wait for SDATA response: WAIT+ACK, direct ACK, or REPLY error.

        Returns:
            True if device acknowledged and is ready for SDS data.

        Raises:
            S2800Error: On rejection, error, or timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            for m in self._port_in.iter_pending():
                if m.type != 'sysex':
                    continue

                raw = bytes([0xF0] + list(m.data) + [0xF7])
                data = list(m.data)

                # Check for SDS handshake
                hs = parse_handshake(raw)
                if hs:
                    if hs["type"] == SDS_ACK:
                        return True
                    if hs["type"] == SDS_WAIT:
                        # Wait for follow-up ACK
                        hs2 = wait_for_handshake(self._port_in, timeout=SDS_HANDSHAKE_TIMEOUT)
                        if hs2 and hs2["type"] == SDS_ACK:
                            return True
                        raise S2800Error("No ACK after WAIT")
                    if hs["type"] in (SDS_NAK, SDS_CANCEL):
                        raise S2800Error(f"Device rejected: {hs['type_name']}")

                # Check for Akai REPLY error
                if data[0] == AKAI_MFR and len(data) >= 5:
                    if data[2] == FUNC_REPLY and data[3] == S1000_MODEL:
                        code = data[4] if len(data) > 4 else 0
                        if code != REPLY_OK:
                            raise S2800Error(f"Device error (code={code})")
                        return True

            time.sleep(0.01)

        raise S2800Error("Timeout waiting for SDATA response")

    # --- Samples ---

    def list_samples(self) -> list[str]:
        """List all sample names on the device.

        Returns:
            List of sample names decoded to ASCII.
        """
        self._drain()
        self._send(FUNC_RSLIST)

        result = self._recv(timeout=5.0)
        if result is None:
            return []

        function, payload = result
        if function != FUNC_SLIST:
            return []
        if len(payload) < 2:
            return []

        count = payload[0] | (payload[1] << 8)
        names = []
        offset = 2
        for _ in range(count):
            if offset + 12 > len(payload):
                break
            name_bytes = payload[offset:offset + 12]
            names.append(decode_akai_name(name_bytes))
            offset += 12
        return names

    def upload_sample(self, pcm_data: bytes, sample_rate: int, name: str,
                      original_pitch: int = 60, progress=None) -> int:
        """Upload a single sample to the device.

        Flow:
            1. list_samples() to get current count
            2. SDATA with 192-byte header (nibble-encoded)
            3. Wait for WAIT+ACK
            4. Send SDS data packets with per-packet handshaking
            5. Return new sample index

        Args:
            pcm_data: 16-bit signed PCM bytes (little-endian, mono).
                      Will be converted to unsigned offset binary.
            sample_rate: Sample rate in Hz
            name: Sample name (max 12 chars)
            original_pitch: MIDI note number for the sample's natural pitch (default 60=C3)
            progress: Optional callback(packets_sent, total_packets)

        Returns:
            Index of the newly created sample
        """
        import numpy as np

        # Convert signed PCM to unsigned offset binary (S2800 format)
        samples = np.frombuffer(pcm_data, dtype=np.int16).copy()
        samples = (samples.astype(np.int32) + 32768).astype(np.uint16).view(np.int16)
        unsigned_pcm = samples.tobytes()

        sample_count = len(pcm_data) // 2
        existing = self.list_samples()
        sample_number = len(existing)

        # Build and send SDATA with 192-byte header
        header = build_sample_header(
            name=name,
            sample_length=sample_count,
            sample_rate=sample_rate,
            original_pitch=original_pitch,
        )
        nibbled = nibble_encode(header)

        sdata_payload = bytearray([
            sample_number & 0x7F,
            (sample_number >> 7) & 0x7F,
        ])
        sdata_payload.extend(nibbled)
        self._send(FUNC_SDATA, bytes(sdata_payload))

        # Wait for device acknowledgment
        self._wait_for_sdata_response()

        # Send SDS data packets
        sds_data = pack_16bit_to_sds(unsigned_pcm)
        total_packets = (len(sds_data) + SDS_PACKET_DATA_BYTES - 1) // SDS_PACKET_DATA_BYTES

        for pkt_num in range(total_packets):
            offset = pkt_num * SDS_PACKET_DATA_BYTES
            chunk = sds_data[offset:offset + SDS_PACKET_DATA_BYTES]

            retries = 0
            while True:
                packet = build_data_packet(pkt_num % 128, chunk, channel=0x00)
                self._port_out.send(mido.Message('sysex', data=list(packet[1:-1])))

                hs = wait_for_handshake(self._port_in, timeout=SDS_PACKET_TIMEOUT)
                if hs is None:
                    raise S2800Error(f"Timeout at packet {pkt_num}")

                if hs["type"] == SDS_ACK:
                    break
                elif hs["type"] == SDS_WAIT:
                    time.sleep(0.5)
                    hs2 = wait_for_handshake(self._port_in, timeout=SDS_HANDSHAKE_TIMEOUT)
                    if hs2 and hs2["type"] == SDS_ACK:
                        break
                    raise S2800Error(f"No ACK after WAIT at packet {pkt_num}")
                elif hs["type"] == SDS_NAK:
                    retries += 1
                    if retries >= SDS_MAX_RETRIES:
                        raise S2800Error(f"Max retries at packet {pkt_num}")
                    continue
                elif hs["type"] == SDS_CANCEL:
                    raise S2800Error(f"Device cancelled at packet {pkt_num}")

            if progress:
                progress(pkt_num + 1, total_packets)

        return sample_number

    def delete_sample(self, index: int):
        """Delete a sample by index.

        Args:
            index: Sample index (0-based)
        """
        data = bytes([index & 0x7F, (index >> 7) & 0x7F])
        self._send(FUNC_DELS, data)
        time.sleep(0.3)

    def delete_all_samples(self):
        """Delete all samples by iterating in reverse order."""
        names = self.list_samples()
        for i in range(len(names) - 1, -1, -1):
            self.delete_sample(i)
            time.sleep(0.2)

    # --- Programs ---

    def list_programs(self) -> list[str]:
        """List all program names on the device.

        Uses RPLIST/PLIST -- same pattern as list_samples.

        Returns:
            List of program names decoded to ASCII.
        """
        self._drain()
        self._send(FUNC_RPLIST)

        result = self._recv(timeout=5.0)
        if result is None:
            return []

        function, payload = result
        if function != FUNC_PLIST:
            return []
        if len(payload) < 2:
            return []

        count = payload[0] | (payload[1] << 8)
        names = []
        offset = 2
        for _ in range(count):
            if offset + 12 > len(payload):
                break
            name_bytes = payload[offset:offset + 12]
            names.append(decode_akai_name(name_bytes))
            offset += 12
        return names

    def delete_program(self, index: int):
        """Delete a program by index.

        Args:
            index: Program index (0-based)
        """
        data = bytes([index & 0x7F, (index >> 7) & 0x7F])
        self._send(FUNC_DELP, data)
        time.sleep(0.3)

    def delete_all_programs(self):
        """Delete all programs by iterating in reverse order."""
        names = self.list_programs()
        for i in range(len(names) - 1, -1, -1):
            self.delete_program(i)
            time.sleep(0.2)

    def create_program(self, name: str, keygroups: list[dict],
                       midi_channel: int = 0, program_number: int = 0):
        """Create a program with keygroup assignments.

        Uses S1000 function codes (PDATA 0x07 + KDATA 0x09) which are
        supported on S2800/S3000. All headers are 192 bytes, nibble-encoded.

        S1000 PDATA format: [pp, PP, nibbled_192_byte_program_header]
        S1000 KDATA format: [pp, PP, kk, nibbled_192_byte_keygroup]
        (pp PP = program number 14-bit, kk = keygroup number 7-bit)

        Args:
            name: Program name (max 12 chars)
            keygroups: List of dicts with keys:
                low_note: MIDI note number
                high_note: MIDI note number
                sample_name: Name of sample to assign
            midi_channel: MIDI channel (0-15)
            program_number: Program number (0-127)
        """
        # Drain any stale messages before program creation
        self._drain()

        # Step 1: Send 192-byte program header via PDATA (0x07)
        prog_hdr = build_program_header(
            name=name,
            num_keygroups=len(keygroups),
            midi_channel=midi_channel,
            program_number=program_number,
        )
        nibbled_hdr = nibble_encode(prog_hdr)

        pdata_payload = bytearray([
            program_number & 0x7F,
            (program_number >> 7) & 0x7F,
        ])
        pdata_payload.extend(nibbled_hdr)
        self._send(FUNC_PDATA, bytes(pdata_payload))

        result = self._recv(timeout=5.0)
        if result is not None:
            function, resp_payload = result
            logger.info("PDATA response: func=0x%02X payload=%d bytes",
                        function, len(resp_payload))
            if function == FUNC_REPLY:
                code = resp_payload[0] if len(resp_payload) > 0 else 0
                if code != REPLY_OK:
                    raise S2800Error(f"PDATA rejected (code={code})")
        time.sleep(0.5)

        # Step 2: Send each 192-byte keygroup via KDATA (0x09)
        for kg_idx, kg in enumerate(keygroups):
            self._drain()

            kg_hdr = build_keygroup(
                low_note=kg["low_note"],
                high_note=kg["high_note"],
                sample_name=kg["sample_name"],
            )
            nibbled_kg = nibble_encode(kg_hdr)

            # S1000 KDATA: pp PP kk [nibbled_data]
            kdata_payload = bytearray([
                program_number & 0x7F,
                (program_number >> 7) & 0x7F,
                kg_idx & 0x7F,
            ])
            kdata_payload.extend(nibbled_kg)
            self._send(FUNC_KDATA, bytes(kdata_payload))

            result = self._recv(timeout=5.0)
            if result is not None:
                function, resp_payload = result
                logger.info("KDATA %d response: func=0x%02X payload=%d bytes",
                            kg_idx, function, len(resp_payload))
                if function == FUNC_REPLY:
                    code = resp_payload[0] if len(resp_payload) > 0 else 0
                    if code != REPLY_OK:
                        raise S2800Error(
                            f"KDATA rejected for keygroup {kg_idx} (code={code})"
                        )
            time.sleep(0.3)

    def modify_program(self, program_number: int, name: str | None = None,
                       num_keygroups: int | None = None):
        """Modify fields of an existing program via S3000 partial write (0x28).

        Only writes the fields that are specified. The program must already
        exist on the device (created from the front panel).

        Args:
            program_number: Program index (0-based)
            name: New program name (12 chars max), or None to keep existing
            num_keygroups: New keygroup count, or None to keep existing
        """
        from s2800.protocol import encode_akai_name

        # Write name at offset 3 (12 bytes)
        if name is not None:
            name_bytes = encode_akai_name(name)
            nibbled_name = nibble_encode(name_bytes)
            payload = bytearray([
                program_number & 0x7F, (program_number >> 7) & 0x7F,
                0x00,        # reserved
                3, 0x00,     # offset = 3
                12, 0x00,    # count = 12
            ])
            payload.extend(nibbled_name)
            self._send(FUNC_S3K_PDATA, bytes(payload))
            result = self._recv(timeout=3.0)
            if result and result[0] == FUNC_REPLY:
                code = result[1][0] if result[1] else 0
                if code != REPLY_OK:
                    raise S2800Error(f"modify_program name rejected (code={code})")
            time.sleep(0.1)

        # Write GROUPS at offset 42 (1 byte)
        # Note: docs say read-only, but worth trying for modification
        if num_keygroups is not None:
            kg_byte = bytes([min(num_keygroups, 99)])
            nibbled_kg = nibble_encode(kg_byte)
            payload = bytearray([
                program_number & 0x7F, (program_number >> 7) & 0x7F,
                0x00,        # reserved
                42, 0x00,    # offset = 42
                1, 0x00,     # count = 1
            ])
            payload.extend(nibbled_kg)
            self._send(FUNC_S3K_PDATA, bytes(payload))
            self._recv(timeout=3.0)  # may be silently ignored
            time.sleep(0.1)

    def modify_keygroup(self, program_number: int, keygroup_number: int,
                        low_note: int | None = None, high_note: int | None = None,
                        sample_name: str | None = None):
        """Modify fields of an existing keygroup via S3000 partial write (0x2A).

        Args:
            program_number: Program index (0-based)
            keygroup_number: Keygroup index (0-based)
            low_note: New lower key range (21-127)
            high_note: New upper key range (21-127)
            sample_name: New sample name for zone 1
        """
        from s2800.protocol import encode_akai_name

        # Write LONOTE + HINOTE at offsets 3-4 (2 bytes)
        if low_note is not None or high_note is not None:
            lo = (low_note if low_note is not None else 21) & 0x7F
            hi = (high_note if high_note is not None else 127) & 0x7F
            note_bytes = bytes([lo, hi])
            nibbled = nibble_encode(note_bytes)
            payload = bytearray([
                program_number & 0x7F, (program_number >> 7) & 0x7F,
                keygroup_number & 0x7F,  # kk
                3, 0x00,     # offset = 3
                2, 0x00,     # count = 2
            ])
            payload.extend(nibbled)
            self._send(FUNC_S3K_KDATA, bytes(payload))
            result = self._recv(timeout=3.0)
            if result and result[0] == FUNC_REPLY:
                code = result[1][0] if result[1] else 0
                if code != REPLY_OK:
                    raise S2800Error(
                        f"modify_keygroup notes rejected kg={keygroup_number} "
                        f"(code={code})"
                    )
            time.sleep(0.1)

        # Write SNAME1 at offset 34 (12 bytes) -- zone 1 sample name
        if sample_name is not None:
            name_bytes = encode_akai_name(sample_name)
            nibbled = nibble_encode(name_bytes)
            payload = bytearray([
                program_number & 0x7F, (program_number >> 7) & 0x7F,
                keygroup_number & 0x7F,  # kk
                34, 0x00,    # offset = 34 (0x22)
                12, 0x00,    # count = 12
            ])
            payload.extend(nibbled)
            self._send(FUNC_S3K_KDATA, bytes(payload))
            result = self._recv(timeout=3.0)
            if result and result[0] == FUNC_REPLY:
                code = result[1][0] if result[1] else 0
                if code != REPLY_OK:
                    raise S2800Error(
                        f"modify_keygroup sample rejected kg={keygroup_number} "
                        f"(code={code})"
                    )
            time.sleep(0.1)

    def read_program_header(self, program_number: int = 0) -> bytes | None:
        """Read back a program header from the device.

        Uses S3000 extended code (0x27) with offset/count format:
            F0 47 cc 27 48 [pp PP] 00 [oo oo] [nn nn] F7

        Args:
            program_number: Program index (0-based)

        Returns:
            Raw (nibble-decoded) program header bytes, or None on timeout.
        """
        # Request full 192-byte program header
        data = bytes([
            program_number & 0x7F,        # pp
            (program_number >> 7) & 0x7F, # PP
            0x00,                          # reserved
            0x00, 0x00,                    # offset = 0
            192 & 0x7F,                   # count low (0x40)
            (192 >> 7) & 0x7F,            # count high (0x01)
        ])
        self._send(FUNC_S3K_RPDATA, data)

        result = self._recv(timeout=5.0)
        if result is None:
            return None

        function, payload = result
        if function == FUNC_S3K_PDATA:
            # S3000 response: [pp, PP, 0x00, oo_lo, oo_hi, nn_lo, nn_hi, nibbled...]
            nibbled = payload[7:]
            return nibble_decode(nibbled)
        if function == FUNC_PDATA:
            # S1000 fallback response: [pp, PP, nibbled...]
            nibbled = payload[2:]
            return nibble_decode(nibbled)
        if function == FUNC_REPLY:
            code = payload[0] if len(payload) > 0 else 0
            logger.warning("RPDATA reply code=%d", code)
            return None
        return None

    def read_keygroup(self, program_number: int = 0,
                      keygroup_number: int = 0) -> bytes | None:
        """Read back a keygroup header from the device.

        Uses S3000 extended code (0x29) with offset/count format:
            F0 47 cc 29 48 [pp PP] kk [oo oo] [nn nn] F7

        Args:
            program_number: Program index (0-based)
            keygroup_number: Keygroup index (0-based)

        Returns:
            Raw (nibble-decoded) keygroup header bytes, or None on timeout.
        """
        # Request full 191-byte keygroup header
        data = bytes([
            program_number & 0x7F,        # pp
            (program_number >> 7) & 0x7F, # PP
            keygroup_number & 0x7F,        # kk
            0x00, 0x00,                    # offset = 0
            191 & 0x7F,                   # count low (0x3F)
            (191 >> 7) & 0x7F,            # count high (0x01)
        ])
        self._send(FUNC_S3K_RKDATA, data)

        result = self._recv(timeout=5.0)
        if result is None:
            return None

        function, payload = result
        if function == FUNC_S3K_KDATA:
            # S3000 response: [pp, PP, kk, oo_lo, oo_hi, nn_lo, nn_hi, nibbled...]
            nibbled = payload[7:]
            return nibble_decode(nibbled)
        if function == FUNC_KDATA:
            # S1000 fallback response: [pp, PP, kk, KK, nibbled...]
            nibbled = payload[4:]
            return nibble_decode(nibbled)
        if function == FUNC_REPLY:
            code = payload[0] if len(payload) > 0 else 0
            logger.warning("RKDATA reply code=%d", code)
            return None
        return None

    # --- MIDI playback ---

    def play_note(self, note: int, velocity: int = 100,
                  duration: float = 0.3, channel: int = 0):
        """Send a MIDI note-on, wait, then note-off.

        Args:
            note: MIDI note number (0-127)
            velocity: Note velocity (0-127)
            duration: Note duration in seconds
            channel: MIDI channel (0-15)
        """
        self._port_out.send(mido.Message(
            'note_on', note=note, velocity=velocity, channel=channel
        ))
        time.sleep(duration)
        self._port_out.send(mido.Message(
            'note_off', note=note, velocity=0, channel=channel
        ))

    @staticmethod
    def list_ports() -> tuple[list[str], list[str]]:
        """List all available MIDI ports.

        Returns:
            Tuple of (input_names, output_names)
        """
        return list(mido.get_input_names()), list(mido.get_output_names())
