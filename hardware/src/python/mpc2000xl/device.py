"""MPC2000XL device communication.

Handles MIDI note triggers and SDS sample transfer to the Akai MPC2000XL.

SDS sample upload flow:
    1. Send SDS Dump Header (F0 7E ch 01 ...) with sample metadata
    2. Wait for ACK from device
    3. Send SDS Data Packets with per-packet ACK/NAK handshaking

Note: The MPC2000XL must have MIDI SysEx receive enabled and be in a
state ready to receive (e.g. load from MIDI in the disk/sample menu).
"""

import logging
import platform
import time

import mido

if platform.system() == "Darwin":
    mido.set_backend("mido.backends.rtmidi/MACOSX_CORE")

from midi.ports import find_ports
from midi.sds import (
    pack_16bit_to_sds,
    build_data_packet,
    wait_for_handshake,
    SDS_SYSEX_ID, SDS_DUMP_HEADER,
    SDS_ACK, SDS_NAK, SDS_CANCEL, SDS_WAIT,
    SDS_PACKET_DATA_BYTES,
    SDS_HANDSHAKE_TIMEOUT, SDS_PACKET_TIMEOUT, SDS_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class MPC2000XLError(Exception):
    pass


def _encode_24bit(value: int) -> list[int]:
    """Encode a 21-bit value as three 7-bit SDS bytes (LSB first)."""
    return [value & 0x7F, (value >> 7) & 0x7F, (value >> 14) & 0x7F]


def build_sds_header(
    sample_number: int,
    num_samples: int,
    sample_rate: int,
    bits_per_sample: int = 16,
    loop_start: int = 0,
    loop_end: int | None = None,
    loop_type: int = 0x7F,
    channel: int = 0x00,
) -> bytes:
    """Build an SDS Dump Header message.

    Format: F0 7E ch 01 numLo numHi bits period[3] length[3]
                loopStart[3] loopEnd[3] loopType F7

    Args:
        sample_number: Target sample slot on device (0-based).
        num_samples: Number of sample words (not bytes).
        sample_rate: Sample rate in Hz (e.g. 44100).
        bits_per_sample: Bit depth (typically 16).
        loop_start: Loop start point in samples.
        loop_end: Loop end point in samples (defaults to num_samples - 1).
        loop_type: 0x7F = no loop, 0x00 = forward loop.
        channel: SDS channel byte.

    Returns:
        Complete SDS Dump Header SysEx bytes.
    """
    if loop_end is None:
        loop_end = num_samples - 1

    period_ns = round(1e9 / sample_rate)

    data = [
        0xF0,
        SDS_SYSEX_ID,
        channel & 0x7F,
        SDS_DUMP_HEADER,
        sample_number & 0x7F,
        (sample_number >> 7) & 0x7F,
        bits_per_sample & 0x7F,
        *_encode_24bit(period_ns),
        *_encode_24bit(num_samples),
        *_encode_24bit(loop_start),
        *_encode_24bit(loop_end),
        loop_type & 0x7F,
        0xF7,
    ]
    return bytes(data)


# Default MPC2000XL pad-to-MIDI-note mapping (GM drum map, pad 1-16).
# Pad numbering: 1 = bottom-left, 16 = top-right (A-bank).
DEFAULT_PAD_NOTES = {
    1: 36,   # Kick
    2: 38,   # Snare
    3: 42,   # Closed HH
    4: 46,   # Open HH
    5: 41,   # Low Floor Tom
    6: 43,   # High Floor Tom
    7: 45,   # Low Tom
    8: 47,   # Low-Mid Tom
    9: 48,   # Hi-Mid Tom
    10: 50,  # High Tom
    11: 39,  # Hand Clap
    12: 49,  # Crash
    13: 51,  # Ride
    14: 55,  # Splash / Ride Bell
    15: 54,  # Tambourine
    16: 56,  # Cowbell
}


class MPC2000XL:
    """Akai MPC2000XL device interface.

    Supports MIDI note triggers and SDS sample upload via any MIDI interface.

    Args:
        port_in: MIDI input port name, or None for auto-detection.
        port_out: MIDI output port name, or None for auto-detection.
        pad_notes: Override pad-to-note mapping dict {pad_num: midi_note}.
    """

    PORT_PATTERNS = ["MPC", "Volt 2", "Volt"]

    def __init__(
        self,
        port_in: str | None = None,
        port_out: str | None = None,
        pad_notes: dict[int, int] | None = None,
    ):
        self._port_in_name = port_in
        self._port_out_name = port_out
        self._pad_notes = pad_notes or DEFAULT_PAD_NOTES
        self._port_in = None
        self._port_out = None

    # --- Connection ---

    @staticmethod
    def find_ports() -> tuple[str | None, str | None]:
        """Auto-detect MIDI ports for the MPC2000XL."""
        return find_ports(MPC2000XL.PORT_PATTERNS)

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
            raise MPC2000XLError(
                "No MIDI ports found. Specify port names manually."
            )

        self._port_in_name = in_name
        self._port_out_name = out_name
        self._port_out = mido.open_output(out_name)
        self._port_in = mido.open_input(in_name)
        logger.info("Connected: in=%s out=%s", in_name, out_name)

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

    # --- MIDI control ---

    def send_note(self, note: int, velocity: int = 100, channel: int = 0,
                  duration: float = 0.05):
        """Send a MIDI note-on then note-off.

        Args:
            note: MIDI note number (0-127).
            velocity: Note velocity (0-127).
            channel: MIDI channel (0-15).
            duration: Seconds between note-on and note-off.
        """
        self._port_out.send(mido.Message('note_on', note=note,
                                         velocity=velocity, channel=channel))
        time.sleep(duration)
        self._port_out.send(mido.Message('note_off', note=note,
                                         velocity=0, channel=channel))

    def trigger_pad(self, pad: int, velocity: int = 100, channel: int = 0):
        """Trigger an MPC pad by number (1-16) using the pad note map."""
        note = self._pad_notes.get(pad)
        if note is None:
            raise MPC2000XLError(f"No note mapped for pad {pad}")
        self.send_note(note, velocity=velocity, channel=channel)

    def program_change(self, program: int, channel: int = 0):
        """Send a MIDI program change.

        Args:
            program: Program number (0-127).
            channel: MIDI channel (0-15).
        """
        self._port_out.send(mido.Message('program_change',
                                          program=program, channel=channel))

    # --- SDS sample upload ---

    def _drain(self):
        for _ in self._port_in.iter_pending():
            pass

    def _wait_for_ack(self, timeout: float = SDS_HANDSHAKE_TIMEOUT) -> dict:
        """Wait for an SDS ACK. Returns the handshake dict or raises."""
        start = time.time()
        while time.time() - start < timeout:
            for m in self._port_in.iter_pending():
                if m.type == 'sysex':
                    raw = bytes([0xF0] + list(m.data) + [0xF7])
                    from midi.sds import parse_handshake
                    hs = parse_handshake(raw)
                    if hs:
                        return hs
            time.sleep(0.01)
        raise MPC2000XLError("Timeout waiting for SDS ACK from MPC2000XL")

    def upload_sample(
        self,
        pcm_data: bytes,
        sample_rate: int,
        slot: int = 0,
        bits_per_sample: int = 16,
        progress=None,
    ):
        """Upload a 16-bit mono PCM sample to the MPC2000XL via SDS.

        The MPC must be ready to receive (MIDI SysEx enabled, sample receive
        screen active or auto-receive configured).

        Args:
            pcm_data: Raw 16-bit signed PCM bytes (little-endian, mono).
            sample_rate: Sample rate in Hz.
            slot: Target sample slot number on the MPC (0-based).
            bits_per_sample: Bit depth (default 16).
            progress: Optional callable(packets_done, total_packets).
        """
        num_samples = len(pcm_data) // 2

        # Send SDS Dump Header
        header = build_sds_header(
            sample_number=slot,
            num_samples=num_samples,
            sample_rate=sample_rate,
            bits_per_sample=bits_per_sample,
        )
        self._drain()
        self._port_out.send(mido.Message('sysex', data=list(header[1:-1])))
        logger.debug("Sent SDS header: slot=%d samples=%d rate=%d",
                     slot, num_samples, sample_rate)

        # Wait for initial ACK
        hs = self._wait_for_ack()
        if hs["type"] == SDS_WAIT:
            hs2 = self._wait_for_ack(timeout=SDS_HANDSHAKE_TIMEOUT)
            hs = hs2
        if hs["type"] != SDS_ACK:
            raise MPC2000XLError(
                f"MPC rejected SDS header: {hs['type_name']}"
            )

        # Encode and send data packets
        sds_data = pack_16bit_to_sds(pcm_data)
        total_packets = (len(sds_data) + SDS_PACKET_DATA_BYTES - 1) // SDS_PACKET_DATA_BYTES

        for pkt_num in range(total_packets):
            offset = pkt_num * SDS_PACKET_DATA_BYTES
            chunk = sds_data[offset:offset + SDS_PACKET_DATA_BYTES]

            retries = 0
            while True:
                packet = build_data_packet(pkt_num % 128, chunk, channel=0x00)
                self._port_out.send(
                    mido.Message('sysex', data=list(packet[1:-1]))
                )

                hs = wait_for_handshake(self._port_in, timeout=SDS_PACKET_TIMEOUT)
                if hs is None:
                    raise MPC2000XLError(f"Timeout at packet {pkt_num}")

                if hs["type"] == SDS_ACK:
                    break
                elif hs["type"] == SDS_WAIT:
                    time.sleep(0.5)
                    hs2 = wait_for_handshake(self._port_in,
                                             timeout=SDS_HANDSHAKE_TIMEOUT)
                    if hs2 and hs2["type"] == SDS_ACK:
                        break
                    raise MPC2000XLError(
                        f"No ACK after WAIT at packet {pkt_num}"
                    )
                elif hs["type"] == SDS_NAK:
                    retries += 1
                    if retries >= SDS_MAX_RETRIES:
                        raise MPC2000XLError(
                            f"Max retries exceeded at packet {pkt_num}"
                        )
                    continue
                elif hs["type"] == SDS_CANCEL:
                    raise MPC2000XLError(
                        f"MPC cancelled transfer at packet {pkt_num}"
                    )

            if progress:
                progress(pkt_num + 1, total_packets)

        logger.info("Upload complete: %d packets, slot %d", total_packets, slot)

    @staticmethod
    def list_ports() -> tuple[list[str], list[str]]:
        """Return (input_names, output_names) for all available MIDI ports."""
        return list(mido.get_input_names()), list(mido.get_output_names())
