"""
High Performance Audio Engine for RCY

This module implements a stream-based audio engine designed for low-latency,
real-time audio playback with seamless looping and segment transitions.

Key improvements over the original playback architecture:
1. Continuous stream-based playback instead of discrete sd.play() calls
2. Callback-driven architecture for sample-accurate timing
3. Pre-processing and buffering for seamless transitions
4. Queue-based segment management for gapless playback
5. Real-time loop handling with configurable modes

Architecture Overview:
- ImprovedAudioEngine: Main engine managing the stream and playback state
- Segment preprocessing pipeline with buffering
- Callback-based audio delivery for minimal latency
- Queue management for seamless segment transitions
"""

import numpy as np
import sounddevice as sd
import threading
import collections
from typing import Any, Callable
from dataclasses import dataclass
import time

from audio_utils import process_segment_for_output, process_segment_for_playback
from config_manager import config
from error_handler import ErrorHandler
from enums import PlaybackMode


import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProcessedSegment:
    """Container for a processed audio segment ready for playback"""
    data: np.ndarray
    sample_rate: int
    start_time: float
    end_time: float
    is_stereo: bool
    reverse: bool = False
    
    @property
    def duration(self) -> float:
        """Duration of the segment in seconds"""
        return len(self.data) / self.sample_rate
    
    @property
    def frame_count(self) -> int:
        """Number of frames in the segment"""
        return len(self.data)


class SegmentBuffer:
    """Thread-safe buffer for managing pre-processed audio segments"""
    
    def __init__(self, max_size: int = 3) -> None:
        self.max_size = max_size
        self._buffer: collections.deque[ProcessedSegment] = collections.deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add_segment(self, segment: ProcessedSegment) -> None:
        """Add a processed segment to the buffer"""
        with self._lock:
            self._buffer.append(segment)

    def get_next_segment(self) -> ProcessedSegment | None:
        """Get the next segment from the buffer"""
        with self._lock:
            if self._buffer:
                return self._buffer.popleft()
            return None

    def peek_next_segment(self) -> ProcessedSegment | None:
        """Peek at the next segment without removing it"""
        with self._lock:
            if self._buffer:
                return self._buffer[0]
            return None

    def clear(self) -> None:
        """Clear all buffered segments"""
        with self._lock:
            self._buffer.clear()
            
    def is_empty(self) -> bool:
        """Check if the buffer is empty"""
        with self._lock:
            return len(self._buffer) == 0
            
    def size(self) -> int:
        """Get the current buffer size"""
        with self._lock:
            return len(self._buffer)


class ImprovedAudioEngine:
    """
    High-performance audio engine using sounddevice OutputStream callbacks
    
    This engine provides:
    - Low-latency audio playback through continuous streaming
    - Seamless segment transitions and looping
    - Real-time segment processing and buffering
    - Sample-accurate timing control
    """
    
    def __init__(self, sample_rate: int = 44100, channels: int = 2, blocksize: int = 512) -> None:
        """
        Initialize the audio engine

        Args:
            sample_rate: Audio sample rate (default 44100)
            channels: Number of audio channels (default 2 for stereo)
            blocksize: Audio block size for low latency (default 512)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize

        # Stream and playback state
        self.stream: sd.OutputStream | None = None
        self.is_playing = False
        self.is_streaming = False

        # Segment management
        self.segment_buffer = SegmentBuffer()
        self.current_segment: ProcessedSegment | None = None
        self.current_position = 0  # Position within current segment

        # Playback configuration
        self.playback_mode = PlaybackMode.ONE_SHOT
        self.loop_enabled = False
        self.is_playing_reverse = False

        # Source audio data (reference to the main audio processor data)
        self.source_data_left: np.ndarray | None = None
        self.source_data_right: np.ndarray | None = None
        self.source_sample_rate = 44100
        self.source_is_stereo = False

        # Playback tempo settings
        self.playback_tempo_enabled = False
        self.source_bpm = 120.0
        self.target_bpm = 120

        # Callback state
        self._callback_lock = threading.Lock()
        self._underrun_count = 0

        # Event callbacks
        self.playback_ended_callback: Callable[[], None] | None = None

        # Loop parameters
        self._loop_start_time: float | None = None
        self._loop_end_time: float | None = None
        self._loop_reverse: bool = False

        logger.debug("ImprovedAudioEngine initialized: %sHz, %sch, blocksize=%s", sample_rate, channels, blocksize)
    
    def set_source_audio(self, data_left: np.ndarray, data_right: np.ndarray,
                        sample_rate: int, is_stereo: bool) -> None:
        """Set the source audio data for processing"""
        self.source_data_left = data_left
        self.source_data_right = data_right
        self.source_sample_rate = sample_rate
        self.source_is_stereo = is_stereo
        logger.debug("Set source audio: %s samples at %sHz, stereo=%s", len(data_left), sample_rate, is_stereo)

    def set_playback_tempo(self, enabled: bool, source_bpm: float, target_bpm: int) -> None:
        """Configure playback tempo using engine sample rate adjustment"""
        self.playback_tempo_enabled = enabled
        self.source_bpm = source_bpm
        self.target_bpm = target_bpm

        logger.debug("Playback tempo: enabled=%s, %s -> %s BPM", enabled, source_bpm, target_bpm)

        if enabled and source_bpm > 0:
            tempo_ratio = target_bpm / source_bpm
            new_sample_rate = int(self.source_sample_rate * tempo_ratio)
            logger.debug("Adjusting sample rate from %s to %s Hz (ratio: %s)", self.source_sample_rate, new_sample_rate, tempo_ratio)
            self.restart_with_sample_rate(new_sample_rate)
        else:
            logger.debug("Resetting to original sample rate: %sHz", self.source_sample_rate)
            self.restart_with_sample_rate(self.source_sample_rate)

    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """Set the playback mode"""
        self.playback_mode = mode
        self.loop_enabled = mode == PlaybackMode.LOOP
        logger.debug("Playback mode set to: %s (loop_enabled=%s)", mode.value, self.loop_enabled)

    def set_playback_ended_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when playback ends"""
        self.playback_ended_callback = callback

    def start_stream(self) -> None:
        """Start the audio stream"""
        if self.is_streaming:
            logger.debug("Stream already running")
            return
            
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                blocksize=self.blocksize,
                latency='low'  # Request low latency mode
            )
            self.stream.start()
            self.is_streaming = True
            logger.debug("Audio stream started: %sHz, %sch, blocksize=%s", self.sample_rate, self.channels, self.blocksize)
        except Exception as e:
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine.start_stream")
            raise

    def stop_stream(self) -> None:
        """Stop the audio stream"""
        if not self.is_streaming:
            return

        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.is_streaming = False
            self.is_playing = False
            self.segment_buffer.clear()
            self.current_segment = None
            self.current_position = 0
            logger.debug("Audio stream stopped")
        except Exception as e:
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine.stop_stream")

    def restart_with_sample_rate(self, new_sample_rate: int) -> None:
        """Restart the audio engine with a new sample rate for tempo adjustment"""
        logger.debug("Restarting audio engine: %sHz -> %sHz", self.sample_rate, new_sample_rate)

        self.stop_stream()
        self.sample_rate = new_sample_rate
        self.start_stream()

        logger.debug("Audio engine restarted: %sHz", self.sample_rate)

    def _audio_callback(self, outdata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        """
        Audio callback function called by sounddevice
        
        This is the core of the real-time audio engine. It runs at high priority
        and must complete within the audio block time to avoid dropouts.
        """
        try:
            with self._callback_lock:
                # Initialize output with silence
                outdata.fill(0)
                
                if not self.is_playing:
                    return
                
                # Track how many frames we've filled
                frames_filled = 0
                
                while frames_filled < frames:
                    # Get current segment if we don't have one
                    if self.current_segment is None:
                        self.current_segment = self.segment_buffer.get_next_segment()
                        self.current_position = 0
                        
                        if self.current_segment is None:
                            # No more segments available
                            if self.loop_enabled and self.playback_mode != PlaybackMode.ONE_SHOT:
                                # Handle looping by queuing the same segment again
                                self._handle_loop_continuation()
                                continue
                            else:
                                # End of playback
                                self._end_playback()
                                break
                    
                    # Calculate how much data we can copy from current segment
                    segment_data = self.current_segment.data
                    remaining_in_segment = len(segment_data) - self.current_position
                    remaining_in_output = frames - frames_filled
                    
                    # Copy as much as possible
                    copy_frames = min(remaining_in_segment, remaining_in_output)
                    
                    if copy_frames > 0:
                        # Handle mono vs stereo output
                        if self.channels == 1:
                            # Mono output
                            if self.current_segment.is_stereo:
                                # Convert stereo segment to mono
                                mono_data = np.mean(segment_data[self.current_position:self.current_position + copy_frames], axis=1)
                                outdata[frames_filled:frames_filled + copy_frames, 0] = mono_data
                            else:
                                # Mono segment to mono output
                                outdata[frames_filled:frames_filled + copy_frames, 0] = segment_data[self.current_position:self.current_position + copy_frames]
                        else:
                            # Stereo output
                            if self.current_segment.is_stereo:
                                # Stereo segment to stereo output
                                outdata[frames_filled:frames_filled + copy_frames] = segment_data[self.current_position:self.current_position + copy_frames]
                            else:
                                # Mono segment to stereo output (duplicate to both channels)
                                mono_data = segment_data[self.current_position:self.current_position + copy_frames]
                                outdata[frames_filled:frames_filled + copy_frames, 0] = mono_data
                                outdata[frames_filled:frames_filled + copy_frames, 1] = mono_data
                        
                        self.current_position += copy_frames
                        frames_filled += copy_frames
                    
                    # Check if we've finished the current segment
                    if self.current_position >= len(segment_data):
                        self.current_segment = None
                        self.current_position = 0
                
        except Exception as e:
            # Log callback errors but don't raise (would crash the audio system)
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine._audio_callback")
            self._underrun_count += 1
            if self._underrun_count > 10:
                logger.warning("Multiple audio callback errors detected (%d)", self._underrun_count)

    def _handle_loop_continuation(self) -> None:
        """Handle loop continuation logic"""
        # This would be called from the audio callback to handle looping
        # Re-queue the current loop segment to continue seamless playback
        if self._loop_start_time is not None and self._loop_end_time is not None:
            logger.debug("Re-queuing loop segment for continuous playback")
            self.queue_segment(self._loop_start_time, self._loop_end_time, self._loop_reverse)
        else:
            # Fallback: end playback if we don't have loop parameters
            logger.warning("WARNING: No loop parameters available, ending playback")
            self._end_playback()

    def _end_playback(self) -> None:
        """Handle end of playback"""
        self.is_playing = False
        self.current_segment = None
        self.current_position = 0

        # Notify callback if set
        if self.playback_ended_callback:
            # Call in a separate thread to avoid blocking the audio callback
            threading.Thread(target=self.playback_ended_callback, daemon=True).start()

    def queue_segment(self, start_time: float, end_time: float, reverse: bool = False) -> bool:
        """
        Queue a segment for playback
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds  
            reverse: Whether to play the segment in reverse
        """
        if self.source_data_left is None:
            logger.warning("No source audio data set")
            return False
        
        try:
            # Convert times to sample positions
            logger.debug("queue_segment: start_time=%s, end_time=%s, source_sample_rate=%s, source_data_left length=%s",
                        start_time, end_time, self.source_sample_rate, len(self.source_data_left))
            start_sample = int(start_time * self.source_sample_rate)
            end_sample = int(end_time * self.source_sample_rate)
            logger.debug("queue_segment: start_sample=%s, end_sample=%s", start_sample, end_sample)
            
            # Get tail fade settings from config
            tail_fade_config = config.get_setting("audio", "tailFade", {})
            tail_fade_enabled = tail_fade_config.get("enabled", False)
            fade_duration_ms = tail_fade_config.get("durationMs", 10)
            fade_curve = tail_fade_config.get("curve", "exponential")
            
            # Process the segment through the lightweight playback pipeline
            processed_data = process_segment_for_playback(
                self.source_data_left,
                self.source_data_right,
                start_sample,
                end_sample,
                self.source_sample_rate,
                self.source_is_stereo,
                self.playback_tempo_enabled,
                self.source_bpm,
                self.target_bpm,
                tail_fade_enabled,
                fade_duration_ms,
                fade_curve,
                for_export=False,
                resample_on_export=True
            )
            
            # Use original sample rate since no tempo processing in playback pipeline
            output_sample_rate = self.source_sample_rate
            
            # Create processed segment
            segment = ProcessedSegment(
                data=processed_data,
                sample_rate=output_sample_rate,
                start_time=start_time,
                end_time=end_time,
                is_stereo=self.source_is_stereo,
                reverse=reverse
            )
            
            # Add to buffer
            self.segment_buffer.add_segment(segment)
            logger.debug("Queued segment: %ss to %ss, reverse=%s, frames=%s", start_time, end_time, reverse, segment.frame_count)
            return True
            
        except Exception as e:
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine.queue_segment")
            return False

    def play_segment(self, start_time: float, end_time: float, reverse: bool = False) -> bool:
        """
        Play a single segment

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            reverse: Whether to play in reverse
        """
        # Stop current playback
        self.stop_playback()

        # Clear buffer and queue the new segment
        self.segment_buffer.clear()

        if not self.queue_segment(start_time, end_time, reverse):
            return False

        # Store loop parameters for continuous re-queuing
        self._loop_start_time = start_time
        self._loop_end_time = end_time
        self._loop_reverse = reverse

        # Handle looping by pre-queuing additional segments
        if self.loop_enabled:
            self._queue_loop_segments(start_time, end_time, reverse)

        # Start playback
        self.is_playing = True
        logger.debug("Started playback: %ss to %ss, reverse=%s", start_time, end_time, reverse)
        return True

    def _queue_loop_segments(self, start_time: float, end_time: float, initial_reverse: bool) -> None:
        """Pre-queue segments for looping to ensure seamless transitions"""
        if self.playback_mode == PlaybackMode.LOOP:
            # Simple loop - queue the same segment multiple times
            for i in range(2):  # Pre-queue 2 additional loops
                self.queue_segment(start_time, end_time, initial_reverse)

    def stop_playback(self) -> None:
        """Stop current playback"""
        self.is_playing = False
        self.segment_buffer.clear()
        self.current_segment = None
        self.current_position = 0

        # Clear loop parameters
        self._loop_start_time = None
        self._loop_end_time = None
        self._loop_reverse = False

        logger.debug("Playback stopped")

    def is_playing_audio(self) -> bool:
        """Check if audio is currently playing"""
        return self.is_playing

    def get_playback_position(self) -> tuple[float, float]:
        """
        Get current playback position
        
        Returns:
            Tuple of (current_time, total_time) in seconds
        """
        if self.current_segment is None:
            return 0.0, 0.0
        
        current_time = self.current_position / self.current_segment.sample_rate
        total_time = self.current_segment.duration
        return current_time, total_time

    def get_stream_info(self) -> dict[str, Any]:
        """Get information about the current stream"""
        return {
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'blocksize': self.blocksize,
            'is_streaming': self.is_streaming,
            'is_playing': self.is_playing,
            'buffer_size': self.segment_buffer.size(),
            'underrun_count': self._underrun_count,
            'latency': getattr(self.stream, 'latency', None) if self.stream else None
        }

    def __enter__(self) -> 'ImprovedAudioEngine':
        """Context manager entry"""
        self.start_stream()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit"""
        self.stop_stream()