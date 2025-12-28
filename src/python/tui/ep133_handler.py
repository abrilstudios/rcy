"""EP-133 device handler for RCY TUI.

Provides tool handlers for EP-133 operations, managing device connection
and audio upload from RCY segments.
"""

import logging
import struct
from typing import TYPE_CHECKING, Optional

import numpy as np

from audio_utils import process_segment_for_output

if TYPE_CHECKING:
    from tui.app import RCYApp

logger = logging.getLogger(__name__)

# Singleton device instance
_device: Optional['EP133Device'] = None

# Current project (1-9), sticky across commands
_current_project: int = 1


def _get_device():
    """Get the EP133Device class, importing lazily."""
    try:
        from ep133 import EP133Device
        return EP133Device
    except ImportError as e:
        logger.warning(f"EP-133 module not available: {e}")
        return None


def _get_errors():
    """Get EP133 error classes."""
    try:
        from ep133 import EP133Error, EP133NotFound, EP133Timeout
        return EP133Error, EP133NotFound, EP133Timeout
    except ImportError:
        return Exception, Exception, Exception


def ep133_connect(args) -> str:
    """Connect to EP-133 device."""
    global _device

    EP133Device = _get_device()
    if EP133Device is None:
        return "EP-133 module not available. Install mido and python-rtmidi."

    EP133Error, EP133NotFound, _ = _get_errors()

    if _device is not None and _device.is_connected:
        return "Already connected to EP-133"

    try:
        _device = EP133Device()
        _device.connect()
        in_port, out_port = _device.port_names
        return f"Connected to EP-133 (in: {in_port}, out: {out_port})"
    except EP133NotFound:
        _device = None
        return "EP-133 not found. Make sure it's connected and powered on."
    except EP133Error as e:
        _device = None
        return f"Connection failed: {e}"


def ep133_disconnect(args) -> str:
    """Disconnect from EP-133 device."""
    global _device

    if _device is None:
        return "Not connected to EP-133"

    _device.disconnect()
    _device = None
    return "Disconnected from EP-133"


def ep133_status(args) -> str:
    """Get EP-133 connection status."""
    EP133Device = _get_device()
    if EP133Device is None:
        return "EP-133 module not available"

    if _device is None:
        # Check if device is available
        in_port, out_port = EP133Device.find_ports()
        if in_port and out_port:
            return f"Not connected. EP-133 detected at: {in_port}"
        return "Not connected. No EP-133 detected."

    if _device.is_connected:
        in_port, out_port = _device.port_names
        return f"Connected to EP-133 (in: {in_port}, out: {out_port})"
    return "EP-133 device instance exists but not connected"


def ep133_list_sounds(args) -> str:
    """List sounds on EP-133."""
    if _device is None or not _device.is_connected:
        return "Not connected to EP-133. Use ep133_connect first."

    EP133Error, _, EP133Timeout = _get_errors()

    try:
        # Node 1000 is the /sounds/ directory
        entries = _device.list_directory(1000)
        if not entries:
            return "No sounds found on EP-133"

        lines = [f"EP-133 sounds ({len(entries)} found):"]
        for entry in entries[:20]:  # Limit output
            name = entry.get('name', '?')
            node_id = entry.get('node_id', 0)
            size = entry.get('size', 0)
            lines.append(f"  Slot {name}: node={node_id}, size={size}")

        if len(entries) > 20:
            lines.append(f"  ... and {len(entries) - 20} more")

        return "\n".join(lines)
    except EP133Timeout:
        return "Timeout reading sounds from EP-133"
    except EP133Error as e:
        return f"Error listing sounds: {e}"


def ep133_upload(args, app: 'RCYApp') -> str:
    """Upload segment(s) to EP-133."""
    if _device is None or not _device.is_connected:
        return "Not connected to EP-133. Use ep133_connect first."

    if not app.model:
        return "No audio loaded"

    EP133Error, _, EP133Timeout = _get_errors()

    slot = args.slot
    segment_index = args.segment

    boundaries = app.segment_manager.get_boundaries()
    num_segments = len(boundaries) - 1

    if num_segments < 1:
        return "No segments defined. Use /slice first."

    # Determine which segments to upload
    if segment_index is not None:
        if segment_index < 1 or segment_index > num_segments:
            return f"Invalid segment {segment_index}. Valid range: 1-{num_segments}"
        segment_indices = [segment_index]
    else:
        segment_indices = list(range(1, num_segments + 1))

    # Check slot range
    if slot + len(segment_indices) - 1 > 999:
        return f"Not enough slots. Starting at {slot} with {len(segment_indices)} segments exceeds 999."

    uploaded = 0
    sample_rate = app.model.sample_rate
    data_left = app.model.data_left
    data_right = app.model.data_right if hasattr(app.model, 'data_right') else data_left

    for i, seg_idx in enumerate(segment_indices):
        target_slot = slot + i
        start_sample = boundaries[seg_idx - 1]
        end_sample = boundaries[seg_idx]

        # Extract segment audio
        segment_left = data_left[start_sample:end_sample]
        segment_right = data_right[start_sample:end_sample]

        # Convert to mono if stereo (EP-133 prefers mono for samples)
        if np.array_equal(segment_left, segment_right):
            segment_data = segment_left
            channels = 1
        else:
            # Mix to mono
            segment_data = (segment_left + segment_right) / 2
            channels = 1

        # Convert float32 [-1, 1] to int16 PCM
        pcm_data = _float_to_pcm_s16le(segment_data)

        # Resample if needed (EP-133 requires 44100 Hz)
        if sample_rate != 44100:
            # Simple resampling - for better quality, use librosa.resample
            pcm_data = _resample_pcm(pcm_data, sample_rate, 44100)

        try:
            _device.upload_sample(
                slot=target_slot,
                audio_data=pcm_data,
                channels=channels,
                samplerate=44100
            )
            uploaded += 1
            logger.info(f"Uploaded segment {seg_idx} to slot {target_slot}")
        except EP133Timeout:
            return f"Timeout uploading segment {seg_idx}. {uploaded} segments uploaded."
        except EP133Error as e:
            return f"Error uploading segment {seg_idx}: {e}. {uploaded} segments uploaded."

    if len(segment_indices) == 1:
        return f"Uploaded segment {segment_indices[0]} to EP-133 slot {slot}"
    return f"Uploaded {uploaded} segments to EP-133 slots {slot}-{slot + uploaded - 1}"


def ep133_assign(args) -> str:
    """Assign a sound to an EP-133 pad."""
    if _device is None or not _device.is_connected:
        return "Not connected to EP-133. Use ep133_connect first."

    from ep133.pad_mapping import pad_to_node_id, format_pad_address

    EP133Error, _, EP133Timeout = _get_errors()

    project = args.project
    group = args.group.upper()
    pad = args.pad
    sound_number = args.sound_number

    try:
        node_id = pad_to_node_id(project, group, pad)
        _device.assign_sound(node_id, sound_number)
        addr = format_pad_address(project, group, pad)
        return f"Assigned sound {sound_number} to pad {addr} (node {node_id})"

    except ValueError as e:
        return f"Invalid pad address: {e}"
    except EP133Timeout:
        return "Timeout communicating with EP-133"
    except EP133Error as e:
        return f"Error: {e}"


def ep133_upload_bank(args, app: 'RCYApp') -> str:
    """Upload segments to an EP-133 bank and assign to pads.

    This is the high-level command for loading a sliced break onto the EP-133.
    Uploads segments to consecutive sound slots and assigns them to pads 1-12.
    """
    if _device is None or not _device.is_connected:
        return "Not connected to EP-133. Use ep133_connect first."

    if not app.model:
        return "No audio loaded"

    from ep133.pad_mapping import pad_to_node_id, format_pad_address

    EP133Error, _, EP133Timeout = _get_errors()

    project = args.project
    bank = args.bank.upper()
    slot_start = args.slot_start
    seg_start = args.segment_start
    seg_count = args.segment_count

    boundaries = app.segment_manager.get_boundaries()
    num_segments = len(boundaries) - 1

    if num_segments < 1:
        return "No segments defined. Use /slice first."

    # Calculate how many segments to upload (max 12 for one bank)
    available = num_segments - seg_start + 1
    if seg_count is None:
        seg_count = min(available, 12)
    else:
        seg_count = min(seg_count, 12, available)

    if seg_count < 1:
        return f"No segments available starting from {seg_start}"

    # Check slot range
    if slot_start + seg_count - 1 > 999:
        return f"Not enough slots. Starting at {slot_start} with {seg_count} segments exceeds 999."

    sample_rate = app.model.sample_rate
    data_left = app.model.data_left
    data_right = app.model.data_right if hasattr(app.model, 'data_right') else data_left

    # Get preset name for sample naming
    preset_name = getattr(app, 'preset_id', None) or 'sample'

    # Get tempo settings from model
    tempo_enabled = app.model.playback_tempo_enabled
    source_bpm = app.model.source_bpm if tempo_enabled else None
    target_bpm = app.model.target_bpm if tempo_enabled else None

    if tempo_enabled:
        logger.info(f"Tempo adjustment enabled: {source_bpm:.1f} -> {target_bpm} BPM")

    uploaded = 0
    assigned = 0
    assign_failures = 0

    for i in range(seg_count):
        seg_idx = seg_start + i
        target_slot = slot_start + i
        pad_num = i + 1  # Pads 1-12

        start_sample = boundaries[seg_idx - 1]
        end_sample = boundaries[seg_idx]

        # Process segment with tempo adjustment (resamples to apply tempo)
        segment_data, output_rate = process_segment_for_output(
            data_left,
            data_right,
            start_sample,
            end_sample,
            sample_rate,
            is_stereo=False,  # EP-133 prefers mono
            reverse=False,
            playback_tempo_enabled=tempo_enabled,
            source_bpm=source_bpm,
            target_bpm=target_bpm,
            for_export=True,
            resample_on_export=True,
        )

        # Convert float32 [-1, 1] to int16 PCM
        pcm_data = _float_to_pcm_s16le(segment_data)

        # Resample if output isn't 44100 Hz (EP-133 requires 44100 Hz)
        if output_rate != 44100:
            pcm_data = _resample_pcm(pcm_data, output_rate, 44100)

        # Generate sample name: preset_001, preset_002, etc.
        sample_name = f"{preset_name}_{seg_idx:03d}"

        try:
            # Upload audio to slot with name
            _device.upload_sample(
                slot=target_slot,
                audio_data=pcm_data,
                channels=1,
                samplerate=44100,
                name=sample_name
            )
            uploaded += 1
            logger.info(f"Uploaded segment {seg_idx} to slot {target_slot}")

            # Assign slot to pad
            # Note: We trust success=True from assign_sound; verification via get_metadata
            # doesn't work reliably after set_metadata due to EP-133 protocol quirks
            node_id = pad_to_node_id(project, bank, pad_num)
            success = _device.assign_sound(node_id, target_slot)
            if success:
                assigned += 1
                logger.info(f"Assigned slot {target_slot} to pad {project}/{bank}/{pad_num}")
            else:
                assign_failures += 1
                logger.warning(f"Failed to assign slot {target_slot} to pad {project}/{bank}/{pad_num}")

        except EP133Timeout:
            return f"Timeout. Uploaded {uploaded}, assigned {assigned} segments to {project}/{bank}."
        except EP133Error as e:
            return f"Error at segment {seg_idx}: {e}. Uploaded {uploaded}, assigned {assigned}."

    addr = format_pad_address(project, bank, 1)
    slot_end = slot_start + seg_count - 1

    # Sync device state after bulk operation
    _device.sync()

    # Build result message
    tempo_note = ""
    if tempo_enabled:
        ratio = target_bpm / source_bpm if source_bpm > 0 else 1.0
        tempo_note = f" @ {target_bpm}BPM ({ratio:.2f}x)"

    if assign_failures > 0:
        return f"Uploaded {uploaded} segments to slots {slot_start}-{slot_end}{tempo_note}. WARNING: {assign_failures} pad assignments failed!"

    return f"Uploaded {uploaded} segments to {project}/{bank} (slots {slot_start}-{slot_end}, pads 1-{seg_count}){tempo_note}"


def ep133_clear_bank(args) -> str:
    """Clear all pad assignments in an EP-133 bank.

    Resets pads 1-12 by assigning sound 0 (no sound) to each pad.
    """
    if _device is None or not _device.is_connected:
        return "Not connected to EP-133. Use ep133_connect first."

    from ep133.pad_mapping import pad_to_node_id, format_pad_address

    EP133Error, _, EP133Timeout = _get_errors()

    project = args.project
    bank = args.bank.upper()

    cleared = 0
    for pad_num in range(1, 13):
        try:
            node_id = pad_to_node_id(project, bank, pad_num)
            # Assign sound 0 to clear the pad
            _device.assign_sound(node_id, 0)
            cleared += 1
            logger.info(f"Cleared pad {project}/{bank}/{pad_num}")
        except EP133Timeout:
            return f"Timeout. Cleared {cleared}/12 pads in {project}/{bank}."
        except EP133Error as e:
            return f"Error at pad {pad_num}: {e}. Cleared {cleared}/12 pads."

    # Sync device state after bulk operation
    _device.sync()

    return f"Cleared all 12 pads in {project}/{bank}"


def _float_to_pcm_s16le(audio: np.ndarray) -> bytes:
    """Convert float32 audio to s16le PCM bytes."""
    # Clip to [-1, 1] and scale to int16 range
    clipped = np.clip(audio, -1.0, 1.0)
    scaled = (clipped * 32767).astype(np.int16)
    return scaled.tobytes()


def _resample_pcm(pcm_data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Simple PCM resampling (linear interpolation)."""
    if src_rate == dst_rate:
        return pcm_data

    # Convert bytes to int16 array
    samples = np.frombuffer(pcm_data, dtype=np.int16)

    # Calculate new length
    ratio = dst_rate / src_rate
    new_len = int(len(samples) * ratio)

    # Simple linear interpolation
    indices = np.linspace(0, len(samples) - 1, new_len)
    resampled = np.interp(indices, np.arange(len(samples)), samples.astype(np.float32))

    return resampled.astype(np.int16).tobytes()


def ep133_handler(args, app: 'RCYApp') -> str:
    """Unified EP-133 command handler.

    Dispatches to subcommand handlers based on args.subcommand.
    """
    global _current_project

    subcommand = args.subcommand.lower()

    if subcommand == "connect":
        return ep133_connect(args)

    elif subcommand == "disconnect":
        return ep133_disconnect(args)

    elif subcommand == "status":
        return ep133_status(args)

    elif subcommand == "list":
        return ep133_list_sounds(args)

    elif subcommand == "set":
        # /ep133 set project <1-9>
        if not args.arg1:
            return f"Usage: /ep133 set project <1-9>\nCurrent project: {_current_project}"
        if args.arg1.lower() == "project":
            if not args.arg2:
                return f"Current target project: {_current_project}\nUsage: /ep133 set project <1-9>"
            try:
                proj = int(args.arg2)
                if not (1 <= proj <= 9):
                    return "Project must be 1-9"
                _current_project = proj
                return f"Target project set to {_current_project} (make sure EP-133 is on project {_current_project})"
            except ValueError:
                return f"Invalid project number: {args.arg2}. Must be 1-9."
        else:
            return f"Unknown setting: {args.arg1}\nAvailable: /ep133 set project <1-9>"

    elif subcommand == "upload":
        bank = args.arg1
        # Allow slot in arg2 or slot field
        slot = args.slot
        if not slot and args.arg2:
            try:
                slot = int(args.arg2)
            except ValueError:
                pass
        if not bank:
            return f"Usage: /ep133 upload <bank> <slot>  (e.g., /ep133 upload A 700)\nCurrent project: {_current_project}"
        if bank.upper() not in ('A', 'B', 'C', 'D'):
            return f"Invalid bank: {bank}. Must be A, B, C, or D."
        if not slot:
            return f"Usage: /ep133 upload <bank> <slot>  (e.g., /ep133 upload A 700)\nSlot is required to avoid accidentally overwriting samples.\nCurrent project: {_current_project}"
        # Create args object compatible with ep133_upload_bank
        class UploadArgs:
            pass
        upload_args = UploadArgs()
        upload_args.project = _current_project
        upload_args.bank = bank
        upload_args.slot_start = slot
        upload_args.segment_start = 1
        upload_args.segment_count = None
        return ep133_upload_bank(upload_args, app)

    elif subcommand == "clear":
        bank = args.arg1
        if not bank:
            return f"Usage: /ep133 clear <bank>  (A, B, C, or D)\nCurrent project: {_current_project}"
        if bank.upper() not in ('A', 'B', 'C', 'D'):
            return f"Invalid bank: {bank}. Must be A, B, C, or D."
        # Create args object compatible with ep133_clear_bank
        class ClearArgs:
            pass
        clear_args = ClearArgs()
        clear_args.project = _current_project
        clear_args.bank = bank
        return ep133_clear_bank(clear_args)

    else:
        return f"""Unknown subcommand: {subcommand}

Usage:
  /ep133 connect              Connect to EP-133
  /ep133 disconnect           Disconnect
  /ep133 status               Show connection status
  /ep133 set project <1-9>    Set target project (match EP-133 selection)
  /ep133 list                 List sounds on device
  /ep133 upload <bank> <slot> Upload segments to bank starting at slot
  /ep133 clear <bank>         Clear pad assignments in bank

Current project: {_current_project}

Examples:
  /ep133 set project 9       Target project 9 on EP-133
  /ep133 upload A 700        Upload to bank A, slots 700+
  /ep133 clear B             Clear bank B assignments"""
