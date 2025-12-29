"""
Ring Buffer Audio Engine for RCY

A simpler, more robust audio engine aligned with "feels good for auditioning",
not DAW-grade transport. Designed for EP-133 oriented workflows.

Architecture:
- StereoRingBuffer: Lock-free circular buffer of (N, 2) float32 frames
- Producer Thread: Preprocesses audio and fills the ring buffer
- Audio Callback: Minimal, allocation-free, reads from ring buffer only

Key features:
- Responsive one-shot playback (keypress → sound)
- Hard-cut semantics with configurable fade-in (anti-click)
- Gapless looping
- Fixed engine format: 44.1kHz, stereo, float32
- Graceful underruns (silence, continue)

See issues #175 and #176 for design spec and test plan.
"""

import numpy as np
import sounddevice as sd
import threading
import queue
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class EngineState(Enum):
    """Engine playback state"""
    STOPPED = auto()   # Engine not running
    IDLE = auto()      # Engine running, not playing
    ARMED = auto()     # Engine running, ready for trigger (autostop=False)
    PLAYING = auto()   # Engine running, outputting audio


@dataclass
class EngineConfig:
    """Configuration for the ring buffer audio engine"""
    sample_rate: int = 44100
    channels: int = 2
    blocksize: int = 256
    ring_buffer_ms: int = 250
    low_watermark_ms: int = 50
    high_watermark_ms: int = 150
    fade_in_ms: float = 3.0
    tail_fade_ms: float = 3.0
    fade_curve: str = "exponential"
    autostop_one_shot: bool = True

    @property
    def ring_buffer_frames(self) -> int:
        return int(self.sample_rate * self.ring_buffer_ms / 1000)

    @property
    def low_watermark_frames(self) -> int:
        return int(self.sample_rate * self.low_watermark_ms / 1000)

    @property
    def high_watermark_frames(self) -> int:
        return int(self.sample_rate * self.high_watermark_ms / 1000)

    @property
    def fade_in_frames(self) -> int:
        return int(self.sample_rate * self.fade_in_ms / 1000)

    @property
    def tail_fade_frames(self) -> int:
        return int(self.sample_rate * self.tail_fade_ms / 1000)


def mono_to_stereo(mono_data: np.ndarray) -> np.ndarray:
    """
    Convert mono audio to stereo by duplicating to both channels.

    IMPORTANT: No amplitude scaling is applied. The mono signal is
    duplicated exactly to both channels to preserve loudness.

    Args:
        mono_data: 1D array of mono samples (float32)

    Returns:
        2D array of shape (N, 2) with identical left and right channels
    """
    mono_data = np.asarray(mono_data, dtype=np.float32)
    return np.column_stack([mono_data, mono_data])


def apply_fade_in(audio: np.ndarray, fade_frames: int, curve: str = "exponential") -> np.ndarray:
    """
    Apply fade-in to the beginning of audio.

    Args:
        audio: Stereo audio array (N, 2)
        fade_frames: Number of frames to fade
        curve: "linear" or "exponential"

    Returns:
        Audio with fade-in applied (modifies in place and returns)
    """
    if fade_frames <= 0 or len(audio) == 0:
        return audio

    fade_frames = min(fade_frames, len(audio))

    if curve == "exponential":
        # Attempt a different exponential ramp that starts closer to 0
        # Using a simple power curve: (x)^3 gives a nice ease-in
        t = np.linspace(0, 1, fade_frames, dtype=np.float32)
        ramp = t ** 3  # Starts slow, accelerates
    else:
        # Linear ramp
        ramp = np.linspace(0, 1, fade_frames, dtype=np.float32)

    audio[:fade_frames, 0] *= ramp
    audio[:fade_frames, 1] *= ramp

    return audio


def apply_tail_fade(audio: np.ndarray, fade_frames: int, curve: str = "exponential") -> np.ndarray:
    """
    Apply fade-out to the end of audio.

    Args:
        audio: Stereo audio array (N, 2)
        fade_frames: Number of frames to fade
        curve: "linear" or "exponential"

    Returns:
        Audio with fade-out applied (modifies in place and returns)
    """
    if fade_frames <= 0 or len(audio) == 0:
        return audio

    fade_frames = min(fade_frames, len(audio))

    if curve == "exponential":
        t = np.linspace(1, 0, fade_frames, dtype=np.float32)
        ramp = t ** 3
    else:
        ramp = np.linspace(1, 0, fade_frames, dtype=np.float32)

    audio[-fade_frames:, 0] *= ramp
    audio[-fade_frames:, 1] *= ramp

    return audio


class StereoRingBuffer:
    """
    Thread-safe circular buffer for stereo audio frames.

    Fixed format: float32 stereo (N, 2)

    The buffer uses a lock for thread safety between producer and consumer.
    For real-time audio, the lock contention is minimal since:
    - Writes happen in bursts from producer thread
    - Reads happen from audio callback (very fast, small blocks)
    """

    def __init__(self, capacity_frames: int):
        """
        Initialize ring buffer.

        Args:
            capacity_frames: Maximum number of stereo frames to hold
        """
        self._capacity = capacity_frames
        self._buffer = np.zeros((capacity_frames, 2), dtype=np.float32)
        self._read_pos = 0
        self._write_pos = 0
        self._count = 0  # Number of frames currently in buffer
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        """Total capacity in frames"""
        return self._capacity

    def available_read(self) -> int:
        """Number of frames available to read"""
        with self._lock:
            return self._count

    def available_write(self) -> int:
        """Number of frames that can be written"""
        with self._lock:
            return self._capacity - self._count

    def write(self, frames: np.ndarray) -> int:
        """
        Write frames to the buffer.

        Args:
            frames: Stereo audio data, shape (N, 2), float32

        Returns:
            Number of frames actually written (may be less if buffer full)
        """
        frames = np.asarray(frames, dtype=np.float32)
        if frames.ndim == 1:
            frames = frames.reshape(-1, 2)

        num_frames = len(frames)
        if num_frames == 0:
            return 0

        with self._lock:
            available = self._capacity - self._count
            to_write = min(num_frames, available)

            if to_write == 0:
                return 0

            # Handle wraparound
            first_part = min(to_write, self._capacity - self._write_pos)
            second_part = to_write - first_part

            self._buffer[self._write_pos:self._write_pos + first_part] = frames[:first_part]
            if second_part > 0:
                self._buffer[:second_part] = frames[first_part:first_part + second_part]

            self._write_pos = (self._write_pos + to_write) % self._capacity
            self._count += to_write

            return to_write

    def read(self, out: np.ndarray) -> int:
        """
        Read frames from the buffer into output array.

        Args:
            out: Output array, shape (N, 2), float32. Will be filled with data.

        Returns:
            Number of frames actually read (may be less if buffer doesn't have enough)
        """
        num_frames = len(out)
        if num_frames == 0:
            return 0

        with self._lock:
            to_read = min(num_frames, self._count)

            if to_read == 0:
                return 0

            # Handle wraparound
            first_part = min(to_read, self._capacity - self._read_pos)
            second_part = to_read - first_part

            out[:first_part] = self._buffer[self._read_pos:self._read_pos + first_part]
            if second_part > 0:
                out[first_part:first_part + second_part] = self._buffer[:second_part]

            self._read_pos = (self._read_pos + to_read) % self._capacity
            self._count -= to_read

            return to_read

    def clear(self) -> None:
        """Clear the buffer, resetting read/write positions"""
        with self._lock:
            self._read_pos = 0
            self._write_pos = 0
            self._count = 0


# Producer command types
class _ProducerCommand:
    """Base class for producer commands"""
    pass


@dataclass
class _PlayOneShotCommand(_ProducerCommand):
    """Play a one-shot audio clip"""
    audio: np.ndarray  # Already stereo, float32


@dataclass
class _StartLoopCommand(_ProducerCommand):
    """Start looping a sequence of audio clips"""
    slices: list  # List of stereo audio arrays


@dataclass
class _StopCommand(_ProducerCommand):
    """Stop playback"""
    pass


@dataclass
class _SetTempoCommand(_ProducerCommand):
    """Set tempo (only when stopped)"""
    bpm: float
    source_bpm: float


class RingBufferAudioEngine:
    """
    Ring buffer-based audio engine for audition-first workflows.

    Key design principles:
    - Audio callback is DUMB: only reads from ring buffer, writes to output
    - All intelligence (fade, conversion, looping) lives in producer thread
    - Hard-cut semantics: new trigger immediately replaces current audio
    - Graceful underruns: output silence, don't crash
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        channels: int = 2,
        blocksize: int = 256,
        autostop_one_shot: bool = True,
    ):
        """
        Initialize the audio engine.

        Args:
            sample_rate: Sample rate (default 44100)
            channels: Output channels (default 2, stereo)
            blocksize: Audio block size (default 256)
            autostop_one_shot: If True, transition to IDLE when one-shot drains
        """
        self.config = EngineConfig(
            sample_rate=sample_rate,
            channels=channels,
            blocksize=blocksize,
            autostop_one_shot=autostop_one_shot,
        )

        self._ring_buffer = StereoRingBuffer(self.config.ring_buffer_frames)
        self._state = EngineState.STOPPED
        self._state_lock = threading.Lock()

        # Producer thread management
        self._command_queue: queue.Queue = queue.Queue()
        self._producer_thread: threading.Thread | None = None
        self._producer_stop_event = threading.Event()

        # Loop state (managed by producer)
        self._loop_slices: list[np.ndarray] = []
        self._loop_index: int = 0
        self._looping: bool = False

        # Stream
        self._stream: sd.OutputStream | None = None

        # Diagnostics
        self._underrun_count = 0

        # Callbacks
        self._playback_ended_callback: Callable[[], None] | None = None

    @property
    def sample_rate(self) -> int:
        return self.config.sample_rate

    @property
    def state(self) -> EngineState:
        with self._state_lock:
            return self._state

    @property
    def underrun_count(self) -> int:
        return self._underrun_count

    def set_playback_ended_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to fire when playback ends (autostop)"""
        self._playback_ended_callback = callback

    def start(self) -> None:
        """Start the audio engine (stream + producer thread)"""
        if self._state != EngineState.STOPPED:
            return

        # Start producer thread
        self._producer_stop_event.clear()
        self._producer_thread = threading.Thread(target=self._producer_loop, daemon=True)
        self._producer_thread.start()

        # Start audio stream
        self._stream = sd.OutputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            callback=self._audio_callback,
            blocksize=self.config.blocksize,
            dtype=np.float32,
            latency='low',
        )
        self._stream.start()

        with self._state_lock:
            self._state = EngineState.IDLE

        logger.debug("RingBufferAudioEngine started: %dHz, blocksize=%d",
                     self.config.sample_rate, self.config.blocksize)

    def stop(self) -> None:
        """Stop the audio engine completely"""
        if self._state == EngineState.STOPPED:
            return

        # Stop producer
        self._producer_stop_event.set()
        if self._producer_thread:
            self._producer_thread.join(timeout=1.0)
            self._producer_thread = None

        # Stop stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Clear state
        self._ring_buffer.clear()
        self._loop_slices = []
        self._looping = False

        with self._state_lock:
            self._state = EngineState.STOPPED

        logger.debug("RingBufferAudioEngine stopped")

    def play_one_shot(self, audio: np.ndarray) -> None:
        """
        Play a one-shot audio clip with hard-cut semantics.

        This immediately replaces any currently playing audio.

        Args:
            audio: Audio data. Can be mono (N,) or stereo (N, 2), float32.
        """
        # Convert to stereo if needed
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim == 1:
            audio = mono_to_stereo(audio)

        # Send command to producer
        self._command_queue.put(_PlayOneShotCommand(audio=audio))

    def start_loop(self, slices: list[np.ndarray]) -> None:
        """
        Start looping a sequence of audio slices.

        Args:
            slices: List of audio arrays (each can be mono or stereo)
        """
        # Convert all slices to stereo
        stereo_slices = []
        for s in slices:
            s = np.asarray(s, dtype=np.float32)
            if s.ndim == 1:
                s = mono_to_stereo(s)
            stereo_slices.append(s)

        self._command_queue.put(_StartLoopCommand(slices=stereo_slices))

    def stop_playback(self) -> None:
        """Stop current playback but keep engine running"""
        self._command_queue.put(_StopCommand())

    def set_tempo(self, bpm: float, source_bpm: float) -> bool:
        """
        Set playback tempo via sample rate adjustment (S1000 style).

        This is only allowed when stopped or idle.

        Args:
            bpm: Target BPM
            source_bpm: Original BPM of the source material

        Returns:
            True if tempo change was accepted, False if rejected
        """
        with self._state_lock:
            if self._state == EngineState.PLAYING:
                logger.warning("Cannot change tempo while playing")
                return False

        self._command_queue.put(_SetTempoCommand(bpm=bpm, source_bpm=source_bpm))
        return True

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        """
        Audio callback - MUST BE MINIMAL.

        This callback:
        - Reads from ring buffer
        - Writes to output
        - Zero-fills on underrun
        - Nothing else

        NO allocations. NO branching on mono/stereo. NO playback decisions.
        """
        # Read from ring buffer
        read_count = self._ring_buffer.read(outdata)

        # Zero-fill any remaining frames (underrun or end of audio)
        if read_count < frames:
            outdata[read_count:] = 0

            # Track underrun if we were expecting data
            with self._state_lock:
                if self._state == EngineState.PLAYING:
                    self._underrun_count += 1

                    # Check if we should transition state
                    if self._ring_buffer.available_read() == 0 and not self._looping:
                        if self.config.autostop_one_shot:
                            self._state = EngineState.IDLE
                            if self._playback_ended_callback:
                                threading.Thread(
                                    target=self._playback_ended_callback,
                                    daemon=True
                                ).start()
                        else:
                            self._state = EngineState.ARMED

    def _producer_loop(self) -> None:
        """
        Producer thread main loop.

        Handles:
        - Processing commands (play, loop, stop, tempo)
        - Preprocessing audio (fade-in, tail fade)
        - Keeping ring buffer filled during loops
        """
        pending_audio: np.ndarray | None = None
        audio_pos = 0

        while not self._producer_stop_event.is_set():
            # Process any pending commands
            try:
                while True:
                    cmd = self._command_queue.get_nowait()
                    pending_audio, audio_pos = self._process_command(cmd, pending_audio, audio_pos)
            except queue.Empty:
                pass

            # Fill ring buffer if we have audio to write
            if pending_audio is not None and audio_pos < len(pending_audio):
                available = self._ring_buffer.available_write()
                if available > 0:
                    remaining = len(pending_audio) - audio_pos
                    to_write = min(available, remaining)
                    written = self._ring_buffer.write(pending_audio[audio_pos:audio_pos + to_write])
                    audio_pos += written

                    if audio_pos >= len(pending_audio):
                        # Finished writing this audio
                        if self._looping and self._loop_slices:
                            # Move to next loop slice
                            self._loop_index = (self._loop_index + 1) % len(self._loop_slices)
                            pending_audio = self._loop_slices[self._loop_index].copy()
                            audio_pos = 0
                            # No fade for loop continuation (gapless)
                        else:
                            pending_audio = None
                            audio_pos = 0

            # Keep buffer topped up during loops
            elif self._looping and self._loop_slices:
                if self._ring_buffer.available_read() < self.config.low_watermark_frames:
                    pending_audio = self._loop_slices[self._loop_index].copy()
                    audio_pos = 0
                    self._loop_index = (self._loop_index + 1) % len(self._loop_slices)

            # Small sleep to avoid busy-waiting
            self._producer_stop_event.wait(0.001)

    def _process_command(
        self,
        cmd: _ProducerCommand,
        pending_audio: np.ndarray | None,
        audio_pos: int
    ) -> tuple[np.ndarray | None, int]:
        """Process a producer command"""

        if isinstance(cmd, _PlayOneShotCommand):
            # Hard cut: clear buffer and start new audio
            self._ring_buffer.clear()
            self._looping = False
            self._loop_slices = []

            # Apply fades
            audio = cmd.audio.copy()
            apply_fade_in(audio, self.config.fade_in_frames, self.config.fade_curve)
            apply_tail_fade(audio, self.config.tail_fade_frames, self.config.fade_curve)

            with self._state_lock:
                self._state = EngineState.PLAYING

            return audio, 0

        elif isinstance(cmd, _StartLoopCommand):
            # Hard cut: clear buffer and start loop
            self._ring_buffer.clear()
            self._looping = True
            self._loop_slices = cmd.slices
            self._loop_index = 0

            if self._loop_slices:
                # Apply fade-in to first slice only
                audio = self._loop_slices[0].copy()
                apply_fade_in(audio, self.config.fade_in_frames, self.config.fade_curve)

                with self._state_lock:
                    self._state = EngineState.PLAYING

                return audio, 0

            return None, 0

        elif isinstance(cmd, _StopCommand):
            self._ring_buffer.clear()
            self._looping = False
            self._loop_slices = []

            with self._state_lock:
                self._state = EngineState.IDLE

            return None, 0

        elif isinstance(cmd, _SetTempoCommand):
            # Tempo change via sample rate adjustment
            with self._state_lock:
                if self._state == EngineState.PLAYING:
                    return pending_audio, audio_pos  # Ignore while playing

            ratio = cmd.bpm / cmd.source_bpm
            new_sample_rate = int(44100 * ratio)

            # Need to restart the stream with new sample rate
            # This is handled by stopping and starting the engine
            self.config.sample_rate = new_sample_rate
            self._ring_buffer.clear()

            logger.debug("Tempo changed: %s -> %s BPM (sample rate: %d)",
                         cmd.source_bpm, cmd.bpm, new_sample_rate)

            return None, 0

        return pending_audio, audio_pos
