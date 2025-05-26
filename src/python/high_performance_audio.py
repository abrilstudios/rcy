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
from typing import Optional, Tuple, Callable, List
from dataclasses import dataclass
from enum import Enum
import time

from audio_utils import process_segment_for_output, process_segment_for_playback
from config_manager import config
from error_handler import ErrorHandler


class PlaybackMode(Enum):
    """Playback mode enumeration"""
    ONE_SHOT = "one-shot"
    LOOP = "loop"
    LOOP_REVERSE = "loop-reverse"


@dataclass
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
    
    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self._buffer = collections.deque(maxlen=max_size)
        self._lock = threading.Lock()
        
    def add_segment(self, segment: ProcessedSegment):
        """Add a processed segment to the buffer"""
        with self._lock:
            self._buffer.append(segment)
            
    def get_next_segment(self) -> Optional[ProcessedSegment]:
        """Get the next segment from the buffer"""
        with self._lock:
            if self._buffer:
                return self._buffer.popleft()
            return None
            
    def peek_next_segment(self) -> Optional[ProcessedSegment]:
        """Peek at the next segment without removing it"""
        with self._lock:
            if self._buffer:
                return self._buffer[0]
            return None
            
    def clear(self):
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
    
    def __init__(self, sample_rate: int = 44100, channels: int = 2, blocksize: int = 512):
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
        self.stream: Optional[sd.OutputStream] = None
        self.is_playing = False
        self.is_streaming = False
        
        # Segment management
        self.segment_buffer = SegmentBuffer()
        self.current_segment: Optional[ProcessedSegment] = None
        self.current_position = 0  # Position within current segment
        
        # Playback configuration
        self.playback_mode = PlaybackMode.ONE_SHOT
        self.loop_enabled = False
        self.is_playing_reverse = False
        
        # Source audio data (reference to the main audio processor data)
        self.source_data_left: Optional[np.ndarray] = None
        self.source_data_right: Optional[np.ndarray] = None
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
        self.playback_ended_callback: Optional[Callable] = None
        
        print(f"ImprovedAudioEngine initialized: {sample_rate}Hz, {channels}ch, blocksize={blocksize}")
    
    def set_source_audio(self, data_left: np.ndarray, data_right: np.ndarray, 
                        sample_rate: int, is_stereo: bool):
        """Set the source audio data for processing"""
        self.source_data_left = data_left
        self.source_data_right = data_right
        self.source_sample_rate = sample_rate
        self.source_is_stereo = is_stereo
        print(f"Source audio set: {len(data_left)} samples at {sample_rate}Hz, stereo={is_stereo}")
    
    def set_playback_tempo(self, enabled: bool, source_bpm: float, target_bpm: int):
        """Configure playback tempo using engine sample rate adjustment"""
        self.playback_tempo_enabled = enabled
        self.source_bpm = source_bpm
        self.target_bpm = target_bpm
        
        print(f"Playback tempo: enabled={enabled}, {source_bpm:.1f} -> {target_bpm} BPM")
        
        if enabled and source_bpm > 0:
            tempo_ratio = target_bpm / source_bpm
            new_sample_rate = int(self.source_sample_rate * tempo_ratio)
            print(f"Tempo ratio: {tempo_ratio:.3f}, new sample rate: {new_sample_rate}Hz")
            self.restart_with_sample_rate(new_sample_rate)
        else:
            print(f"Resetting to original sample rate: {self.source_sample_rate}Hz")
            self.restart_with_sample_rate(self.source_sample_rate)
    
    def set_playback_mode(self, mode: PlaybackMode):
        """Set the playback mode"""
        self.playback_mode = mode
        self.loop_enabled = mode in [PlaybackMode.LOOP, PlaybackMode.LOOP_REVERSE]
        print(f"Playback mode set to: {mode.value}")
    
    def set_playback_ended_callback(self, callback: Callable):
        """Set callback to be called when playback ends"""
        self.playback_ended_callback = callback
    
    def start_stream(self):
        """Start the audio stream"""
        if self.is_streaming:
            print("Stream already running")
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
            print(f"Audio stream started: {self.sample_rate}Hz, {self.channels}ch, blocksize={self.blocksize}")
        except Exception as e:
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine.start_stream")
            raise
    
    def stop_stream(self):
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
            print("Audio stream stopped")
        except Exception as e:
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine.stop_stream")
    
    def restart_with_sample_rate(self, new_sample_rate: int):
        """Restart the audio engine with a new sample rate for tempo adjustment"""
        print(f"Restarting audio engine: {self.sample_rate}Hz → {new_sample_rate}Hz")
        
        self.stop_stream()
        self.sample_rate = new_sample_rate
        self.start_stream()
        
        print(f"Audio engine restarted: {new_sample_rate}Hz")
    
    def _audio_callback(self, outdata: np.ndarray, frames: int, time, status):
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
                print(f"WARNING: Multiple audio callback errors ({self._underrun_count})")
    
    def _handle_loop_continuation(self):
        """Handle loop continuation logic"""
        # This would be called from the audio callback to handle looping
        # For now, we'll implement a simple mechanism to signal that we need
        # the next segment to be queued
        pass
    
    def _end_playback(self):
        """Handle end of playback"""
        self.is_playing = False
        self.current_segment = None
        self.current_position = 0
        
        # Notify callback if set
        if self.playback_ended_callback:
            # Call in a separate thread to avoid blocking the audio callback
            threading.Thread(target=self.playback_ended_callback, daemon=True).start()
    
    def queue_segment(self, start_time: float, end_time: float, reverse: bool = False):
        """
        Queue a segment for playback
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds  
            reverse: Whether to play the segment in reverse
        """
        if self.source_data_left is None:
            print("ERROR: No source audio data set")
            return False
        
        try:
            # Convert times to sample positions
            start_sample = int(start_time * self.source_sample_rate)
            end_sample = int(end_time * self.source_sample_rate)
            
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
            print(f"Queued segment: {start_time:.2f}s to {end_time:.2f}s, reverse={reverse}, frames={segment.frame_count}")
            return True
            
        except Exception as e:
            ErrorHandler.log_exception(e, context="ImprovedAudioEngine.queue_segment")
            return False
    
    def play_segment(self, start_time: float, end_time: float, reverse: bool = False):
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
        
        # Handle looping by pre-queuing additional segments
        if self.loop_enabled:
            self._queue_loop_segments(start_time, end_time, reverse)
        
        # Start playback
        self.is_playing = True
        print(f"Started playback: {start_time:.2f}s to {end_time:.2f}s, mode={self.playback_mode.value}")
        return True
    
    def _queue_loop_segments(self, start_time: float, end_time: float, initial_reverse: bool):
        """Pre-queue segments for looping to ensure seamless transitions"""
        if self.playback_mode == PlaybackMode.LOOP:
            # Simple loop - queue the same segment multiple times
            for i in range(2):  # Pre-queue 2 additional loops
                self.queue_segment(start_time, end_time, initial_reverse)
        
        elif self.playback_mode == PlaybackMode.LOOP_REVERSE:
            # Alternating direction loop
            self.queue_segment(start_time, end_time, not initial_reverse)  # Opposite direction
            self.queue_segment(start_time, end_time, initial_reverse)      # Back to original
    
    def stop_playback(self):
        """Stop current playback"""
        self.is_playing = False
        self.segment_buffer.clear()
        self.current_segment = None
        self.current_position = 0
        print("Playback stopped")
    
    def is_playing_audio(self) -> bool:
        """Check if audio is currently playing"""
        return self.is_playing
    
    def get_playback_position(self) -> Tuple[float, float]:
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
    
    def get_stream_info(self) -> dict:
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
    
    def __enter__(self):
        """Context manager entry"""
        self.start_stream()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_stream()