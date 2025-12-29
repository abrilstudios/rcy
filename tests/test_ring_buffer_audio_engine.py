"""
Tests for Ring Buffer Audio Engine

This module contains tests for the new ring-buffer-based audio engine
designed for audition-first EP-133 workflows.

Test coverage follows the test plan in issue #176:
1. Ring buffer correctness (write/read/wraparound/clear)
2. Audio callback behavior (silence, underrun)
3. Mono → stereo conversion
4. One-shot playback semantics
5. Loop playback semantics
6. Autostop behavior
7. Tempo semantics (S1000 style)

Core invariants:
- The audio callback must be dumb (read from ring buffer, write to output, nothing else)
- All intelligence lives outside the callback
- Failure modes are graceful (underruns output silence, not noise)
"""

import numpy as np
import pytest
import threading
import time

# These imports will fail until the implementation exists
# Tests are written first to define the contract
try:
    from ring_buffer_audio import (
        StereoRingBuffer,
        RingBufferAudioEngine,
        EngineState,
        mono_to_stereo,
    )
    IMPLEMENTATION_EXISTS = True
except ImportError:
    IMPLEMENTATION_EXISTS = False
    # Define stubs for type hints during test development
    StereoRingBuffer = None
    RingBufferAudioEngine = None
    EngineState = None
    mono_to_stereo = None


# Skip all tests if implementation doesn't exist yet
pytestmark = pytest.mark.skipif(
    not IMPLEMENTATION_EXISTS,
    reason="ring_buffer_audio module not yet implemented"
)


# =============================================================================
# 1. Ring Buffer Correctness
# =============================================================================

class TestStereoRingBufferBasics:
    """Test basic ring buffer operations"""

    def test_creation_with_capacity(self):
        """Ring buffer should be created with specified capacity in frames"""
        capacity_frames = 1024
        ring = StereoRingBuffer(capacity_frames)

        assert ring.capacity == capacity_frames
        assert ring.available_read() == 0
        assert ring.available_write() == capacity_frames

    def test_write_then_read_exact(self):
        """Frames written should be read back exactly"""
        ring = StereoRingBuffer(1024)

        # Create known stereo audio: 100 frames of (0.5, -0.5)
        frames_to_write = 100
        input_data = np.full((frames_to_write, 2), [0.5, -0.5], dtype=np.float32)

        written = ring.write(input_data)
        assert written == frames_to_write
        assert ring.available_read() == frames_to_write

        output_data = np.zeros((frames_to_write, 2), dtype=np.float32)
        read = ring.read(output_data)

        assert read == frames_to_write
        assert ring.available_read() == 0
        np.testing.assert_array_equal(input_data, output_data)

    def test_partial_read(self):
        """Reading fewer frames than available should work correctly"""
        ring = StereoRingBuffer(1024)

        # Write 100 frames
        input_data = np.random.rand(100, 2).astype(np.float32)
        ring.write(input_data)

        # Read only 30 frames
        output_data = np.zeros((30, 2), dtype=np.float32)
        read = ring.read(output_data)

        assert read == 30
        assert ring.available_read() == 70
        np.testing.assert_array_equal(input_data[:30], output_data)

    def test_multiple_write_read_cycles(self):
        """Multiple write/read cycles should preserve data order"""
        ring = StereoRingBuffer(256)

        for i in range(10):
            # Write a block with identifiable pattern
            input_data = np.full((50, 2), [i * 0.1, -i * 0.1], dtype=np.float32)
            ring.write(input_data)

            # Read it back
            output_data = np.zeros((50, 2), dtype=np.float32)
            ring.read(output_data)

            np.testing.assert_array_almost_equal(input_data, output_data)


class TestStereoRingBufferWraparound:
    """Test ring buffer wraparound behavior"""

    def test_write_wraps_around(self):
        """Writes that cross buffer end should wrap correctly"""
        capacity = 100
        ring = StereoRingBuffer(capacity)

        # Write 80 frames
        data1 = np.full((80, 2), [0.1, 0.1], dtype=np.float32)
        ring.write(data1)

        # Read 60 frames to move read pointer
        out = np.zeros((60, 2), dtype=np.float32)
        ring.read(out)

        # Now write 50 more frames - this must wrap around
        data2 = np.full((50, 2), [0.2, 0.2], dtype=np.float32)
        written = ring.write(data2)

        assert written == 50
        # 20 remaining from first write + 50 new = 70
        assert ring.available_read() == 70

    def test_read_wraps_around(self):
        """Reads that span wrapped data should return correct order"""
        capacity = 100
        ring = StereoRingBuffer(capacity)

        # Fill buffer near end
        data1 = np.full((80, 2), [0.1, 0.1], dtype=np.float32)
        ring.write(data1)

        # Read most of it
        out1 = np.zeros((70, 2), dtype=np.float32)
        ring.read(out1)

        # Write data that wraps
        data2 = np.arange(60 * 2, dtype=np.float32).reshape(60, 2)
        ring.write(data2)

        # Read all - this should span the wrap point
        out2 = np.zeros((70, 2), dtype=np.float32)
        read = ring.read(out2)

        assert read == 70
        # First 10 frames from data1, next 60 from data2
        np.testing.assert_array_equal(out2[:10], data1[70:80])
        np.testing.assert_array_equal(out2[10:70], data2)

    def test_no_overwrite_before_read(self):
        """Writing to a full buffer should not overwrite unread data"""
        capacity = 100
        ring = StereoRingBuffer(capacity)

        # Fill the buffer completely
        data = np.random.rand(capacity, 2).astype(np.float32)
        written = ring.write(data)
        assert written == capacity
        assert ring.available_write() == 0

        # Try to write more - should write 0 frames
        more_data = np.random.rand(50, 2).astype(np.float32)
        written = ring.write(more_data)
        assert written == 0

        # Original data should be intact
        out = np.zeros((capacity, 2), dtype=np.float32)
        ring.read(out)
        np.testing.assert_array_equal(data, out)


class TestStereoRingBufferClear:
    """Test ring buffer clear semantics"""

    def test_clear_empties_buffer(self):
        """Clear should make buffer appear empty"""
        ring = StereoRingBuffer(1024)

        # Write some data
        data = np.random.rand(500, 2).astype(np.float32)
        ring.write(data)
        assert ring.available_read() == 500

        # Clear
        ring.clear()

        assert ring.available_read() == 0
        assert ring.available_write() == 1024

    def test_read_after_clear_returns_nothing(self):
        """Reading after clear should return 0 frames"""
        ring = StereoRingBuffer(1024)

        data = np.random.rand(100, 2).astype(np.float32)
        ring.write(data)
        ring.clear()

        out = np.zeros((100, 2), dtype=np.float32)
        read = ring.read(out)

        assert read == 0

    def test_write_after_clear_works(self):
        """Writing after clear should work normally"""
        ring = StereoRingBuffer(1024)

        # Write, clear, write again
        data1 = np.full((100, 2), [0.1, 0.1], dtype=np.float32)
        ring.write(data1)
        ring.clear()

        data2 = np.full((50, 2), [0.2, 0.2], dtype=np.float32)
        written = ring.write(data2)

        assert written == 50
        assert ring.available_read() == 50

        out = np.zeros((50, 2), dtype=np.float32)
        ring.read(out)
        np.testing.assert_array_equal(data2, out)


# =============================================================================
# 2. Audio Callback Behavior
# =============================================================================

class TestAudioCallbackSilence:
    """Test callback behavior when engine is idle"""

    def test_idle_engine_outputs_silence(self):
        """Engine that hasn't started playing should output silence"""
        engine = RingBufferAudioEngine()
        engine.start()  # Start the engine but don't play anything

        # Simulate callback
        outdata = np.ones((256, 2), dtype=np.float32)  # Pre-fill with non-zero
        engine._audio_callback(outdata, 256, None, None)

        # Should be all zeros
        np.testing.assert_array_equal(outdata, np.zeros((256, 2), dtype=np.float32))

        engine.stop()

    def test_stopped_engine_outputs_silence(self):
        """Engine that was playing but stopped should output silence"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Play something then stop
        test_audio = np.random.rand(1000, 2).astype(np.float32)
        engine.play_one_shot(test_audio)
        engine.stop_playback()

        # Callback should output silence
        outdata = np.ones((256, 2), dtype=np.float32)
        engine._audio_callback(outdata, 256, None, None)

        np.testing.assert_array_equal(outdata, np.zeros((256, 2), dtype=np.float32))

        engine.stop()


class TestAudioCallbackUnderrun:
    """Test underrun handling"""

    def test_underrun_outputs_partial_then_silence(self):
        """When buffer has less data than requested, output what's available then silence"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Queue only 100 frames (but with fade applied, so short audio gets heavily faded)
        test_audio = np.full((100, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(test_audio)

        # Wait for producer to fill buffer
        for _ in range(50):
            if engine._ring_buffer.available_read() > 50:
                break
            time.sleep(0.01)

        # Request 256 frames
        outdata = np.zeros((256, 2), dtype=np.float32)
        engine._audio_callback(outdata, 256, None, None)

        # Some frames should have audio (fade makes values very small, but non-zero)
        # The max value should be above 0 (due to fade-in + fade-out, peak is small)
        max_val = np.max(np.abs(outdata))
        assert max_val > 0.0001, f"Expected some audio output, got max={max_val}"

        # Tail should be silence since we only queued 100 frames
        np.testing.assert_array_equal(outdata[150:], np.zeros((106, 2), dtype=np.float32))

        engine.stop()

    def test_underrun_does_not_crash(self):
        """Underrun should not raise exceptions or crash"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Empty buffer - this is an underrun condition
        outdata = np.zeros((256, 2), dtype=np.float32)

        # Should not raise
        engine._audio_callback(outdata, 256, None, None)

        engine.stop()

    def test_underrun_is_counted(self):
        """Underruns should be tracked for diagnostics"""
        engine = RingBufferAudioEngine()
        engine.start()

        initial_count = engine.underrun_count

        # Force underrun by requesting from empty buffer during playback
        engine._ring_buffer.clear()  # Empty the buffer
        engine._state = EngineState.PLAYING

        outdata = np.zeros((256, 2), dtype=np.float32)
        engine._audio_callback(outdata, 256, None, None)

        assert engine.underrun_count > initial_count

        engine.stop()


# =============================================================================
# 3. Mono → Stereo Conversion
# =============================================================================

class TestMonoToStereoConversion:
    """Test mono to stereo conversion for engine format"""

    def test_mono_duplicated_to_both_channels(self):
        """Mono input should appear identically on both channels"""
        mono_data = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

        stereo_data = mono_to_stereo(mono_data)

        assert stereo_data.shape == (5, 2)
        np.testing.assert_array_equal(stereo_data[:, 0], mono_data)
        np.testing.assert_array_equal(stereo_data[:, 1], mono_data)

    def test_mono_amplitude_unchanged(self):
        """Mono duplication should NOT scale amplitude"""
        mono_data = np.array([1.0, -1.0, 0.5], dtype=np.float32)

        stereo_data = mono_to_stereo(mono_data)

        # Amplitude should be exactly the same, not reduced
        np.testing.assert_array_equal(stereo_data[:, 0], mono_data)
        np.testing.assert_array_equal(stereo_data[:, 1], mono_data)

    def test_constant_amplitude_preserved(self):
        """A constant mono signal should have same constant in stereo"""
        constant_value = 0.7
        mono_data = np.full(100, constant_value, dtype=np.float32)

        stereo_data = mono_to_stereo(mono_data)

        # Both channels should have the exact same constant
        np.testing.assert_allclose(stereo_data[:, 0], constant_value)
        np.testing.assert_allclose(stereo_data[:, 1], constant_value)


# =============================================================================
# 4. One-Shot Playback Semantics
# =============================================================================

class TestOneShotHardCut:
    """Test hard-cut behavior for one-shot playback"""

    def test_new_trigger_replaces_current_audio(self):
        """Triggering new one-shot should immediately replace current audio"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Start playing first audio
        audio1 = np.full((10000, 2), [0.1, 0.1], dtype=np.float32)
        engine.play_one_shot(audio1)
        time.sleep(0.01)  # Let producer fill buffer

        # Trigger new audio - should hard cut
        audio2 = np.full((10000, 2), [0.9, 0.9], dtype=np.float32)
        engine.play_one_shot(audio2)
        time.sleep(0.01)  # Let producer fill buffer

        # Read from buffer - should be audio2, not audio1
        outdata = np.zeros((256, 2), dtype=np.float32)
        engine._audio_callback(outdata, 256, None, None)

        # After fade-in, values should be close to 0.9, not 0.1
        # Check samples after fade region
        fade_samples = int(engine.config.fade_in_ms * 44.1)
        if fade_samples < 256:
            np.testing.assert_allclose(outdata[fade_samples + 10:fade_samples + 20, 0], 0.9, atol=0.01)

        engine.stop()

    def test_no_overlap_or_layering(self):
        """Hard cut means no audio from previous trigger should remain"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Play distinctive audio
        audio1 = np.full((5000, 2), [0.3, 0.3], dtype=np.float32)
        engine.play_one_shot(audio1)
        time.sleep(0.01)

        # Hard cut to silence (zeros)
        audio2 = np.zeros((5000, 2), dtype=np.float32)
        engine.play_one_shot(audio2)
        time.sleep(0.01)

        # After fade-in region, output should be silent
        outdata = np.zeros((1000, 2), dtype=np.float32)
        engine._audio_callback(outdata, 1000, None, None)

        fade_samples = int(engine.config.fade_in_ms * 44.1)
        # After fade, should be zero (no audio1 leaking through)
        np.testing.assert_allclose(outdata[fade_samples + 50:], 0, atol=0.001)

        engine.stop()


class TestOneShotFadeIn:
    """Test fade-in behavior for anti-click"""

    def test_fade_in_starts_from_silence(self):
        """First samples should ramp up from near-zero"""
        # Test the fade function directly since engine timing is unreliable
        from ring_buffer_audio import apply_fade_in

        audio = np.full((1000, 2), [1.0, 1.0], dtype=np.float32)
        apply_fade_in(audio, 132, "exponential")  # ~3ms at 44.1kHz

        # First sample should be near zero
        assert abs(audio[0, 0]) < 0.01  # Exponential starts very low

    def test_fade_in_reaches_full_amplitude(self):
        """After fade duration, signal should reach full amplitude"""
        # Test the fade function directly
        from ring_buffer_audio import apply_fade_in

        audio = np.full((2000, 2), [0.8, 0.8], dtype=np.float32)
        fade_samples = 132  # ~3ms at 44.1kHz
        apply_fade_in(audio, fade_samples, "exponential")

        # After fade, should be at full amplitude
        np.testing.assert_allclose(audio[fade_samples + 10:fade_samples + 50, 0], 0.8, atol=0.01)


class TestOneShotTailFade:
    """Test tail fade behavior at slice end"""

    def test_tail_fade_applied(self):
        """End of slice should fade smoothly to silence"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Short audio that will fit in one callback worth
        audio = np.full((200, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        # Read all of it
        outdata = np.zeros((300, 2), dtype=np.float32)
        engine._audio_callback(outdata, 300, None, None)

        # Last samples before silence should be fading
        # Find where audio ends
        non_zero_mask = np.abs(outdata[:, 0]) > 0.001
        if np.any(non_zero_mask):
            last_non_zero = np.where(non_zero_mask)[0][-1]
            # Samples before the end should be smaller than peak
            if last_non_zero > 10:
                assert outdata[last_non_zero, 0] < 0.4  # Should be faded

        engine.stop()


# =============================================================================
# 5. Loop Playback Semantics
# =============================================================================

class TestLoopGapless:
    """Test gapless loop concatenation"""

    def test_loop_slices_in_order(self):
        """Loop should play slices in specified order"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Create distinguishable slices - use larger values for clearer distinction
        slice1 = np.full((1000, 2), [0.2, 0.2], dtype=np.float32)
        slice2 = np.full((1000, 2), [0.5, 0.5], dtype=np.float32)
        slice3 = np.full((1000, 2), [0.8, 0.8], dtype=np.float32)

        engine.start_loop([slice1, slice2, slice3])

        # Wait until buffer has data
        for _ in range(100):  # Max 1s wait
            if engine._ring_buffer.available_read() > 2500:
                break
            time.sleep(0.01)

        # Read enough to verify order
        outdata = np.zeros((2800, 2), dtype=np.float32)
        engine._audio_callback(outdata, 2800, None, None)

        # Sample at middle of each expected slice position
        # (accounting for fade-in at start)
        fade_samples = int(engine.config.fade_in_ms * 44.1)

        # Check we see progression from lower to higher values
        # Slice1 should be around 0.2, slice2 around 0.5
        val_at_500 = outdata[fade_samples + 500, 0]
        val_at_1500 = outdata[fade_samples + 1500, 0]

        # slice1 value should be less than slice2 value
        assert val_at_500 < val_at_1500, f"Expected progression: {val_at_500} < {val_at_1500}"
        # Values should be reasonable (not zeros)
        assert val_at_500 > 0.1, f"Slice1 value too low: {val_at_500}"
        assert val_at_1500 > 0.3, f"Slice2 value too low: {val_at_1500}"

        engine.stop()

    def test_no_silence_between_slices(self):
        """There should be no gaps between loop slices"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Two slices of constant audio
        slice1 = np.full((500, 2), [0.5, 0.5], dtype=np.float32)
        slice2 = np.full((500, 2), [0.5, 0.5], dtype=np.float32)

        engine.start_loop([slice1, slice2])
        time.sleep(0.05)

        outdata = np.zeros((1000, 2), dtype=np.float32)
        engine._audio_callback(outdata, 1000, None, None)

        fade_samples = int(engine.config.fade_in_ms * 44.1)

        # After fade-in, there should be no zeros until the loop restarts
        audio_region = outdata[fade_samples:900]
        assert np.all(np.abs(audio_region[:, 0]) > 0.3)

        engine.stop()

    def test_loop_repeats_seamlessly(self):
        """Loop should repeat without clicks or gaps"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Short loop
        loop_slice = np.full((500, 2), [0.4, 0.4], dtype=np.float32)
        engine.start_loop([loop_slice])
        time.sleep(0.05)

        # Read multiple loop cycles
        outdata = np.zeros((2000, 2), dtype=np.float32)
        engine._audio_callback(outdata, 2000, None, None)

        fade_samples = int(engine.config.fade_in_ms * 44.1)

        # After initial fade, should maintain consistent amplitude
        audio_region = outdata[fade_samples + 50:1500]
        mean_amp = np.mean(np.abs(audio_region[:, 0]))

        # Should be close to 0.4 throughout
        assert abs(mean_amp - 0.4) < 0.1

        engine.stop()


class TestLoopHardCutOnTrigger:
    """Test that one-shot trigger hard-cuts a loop"""

    def test_one_shot_interrupts_loop(self):
        """One-shot trigger should immediately stop loop and play new audio"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Start a loop
        loop_audio = np.full((5000, 2), [0.2, 0.2], dtype=np.float32)
        engine.start_loop([loop_audio])
        time.sleep(0.02)

        # Interrupt with one-shot
        one_shot = np.full((5000, 2), [0.8, 0.8], dtype=np.float32)
        engine.play_one_shot(one_shot)
        time.sleep(0.02)

        # Should now be playing one-shot, not loop
        outdata = np.zeros((500, 2), dtype=np.float32)
        engine._audio_callback(outdata, 500, None, None)

        fade_samples = int(engine.config.fade_in_ms * 44.1)
        # After fade, should be 0.8, not 0.2
        np.testing.assert_allclose(outdata[fade_samples + 50:fade_samples + 100, 0], 0.8, atol=0.1)

        engine.stop()


# =============================================================================
# 6. Autostop Behavior
# =============================================================================

class TestAutostopEnabled:
    """Test autostop behavior when enabled (default)"""

    def test_transitions_to_idle_when_drained(self):
        """Engine should transition to IDLE when audio drains"""
        engine = RingBufferAudioEngine(autostop_one_shot=True)
        engine.start()

        # Play short audio
        audio = np.full((200, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.1)  # Give producer more time to fill buffer

        # Verify we're playing (may already have transitioned if very fast)
        initial_state = engine.state

        # Drain the buffer
        outdata = np.zeros((500, 2), dtype=np.float32)
        engine._audio_callback(outdata, 500, None, None)

        # Should transition to IDLE after drain
        # Give a moment for state transition
        time.sleep(0.01)
        assert engine.state == EngineState.IDLE

        engine.stop()

    def test_playback_ended_callback_fires(self):
        """Playback ended callback should fire when audio drains"""
        engine = RingBufferAudioEngine(autostop_one_shot=True)
        engine.start()

        callback_fired = threading.Event()
        engine.set_playback_ended_callback(lambda: callback_fired.set())

        audio = np.full((100, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        # Drain buffer
        outdata = np.zeros((500, 2), dtype=np.float32)
        engine._audio_callback(outdata, 500, None, None)

        # Callback should have fired (give it a moment)
        assert callback_fired.wait(timeout=0.1)

        engine.stop()


class TestAutostopDisabled:
    """Test behavior when autostop is disabled"""

    def test_remains_armed_after_drain(self):
        """Engine should stay armed (not IDLE) when autostop disabled"""
        engine = RingBufferAudioEngine(autostop_one_shot=False)
        engine.start()

        audio = np.full((100, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        # Drain buffer
        outdata = np.zeros((500, 2), dtype=np.float32)
        engine._audio_callback(outdata, 500, None, None)

        # Should remain armed, not IDLE
        assert engine.state != EngineState.IDLE
        assert engine.state == EngineState.ARMED

        engine.stop()

    def test_outputs_silence_when_drained(self):
        """Should output silence (not noise) when buffer drained"""
        engine = RingBufferAudioEngine(autostop_one_shot=False)
        engine.start()

        audio = np.full((100, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        # Drain buffer
        out1 = np.zeros((200, 2), dtype=np.float32)
        engine._audio_callback(out1, 200, None, None)

        # Continue reading - should be silence
        out2 = np.ones((256, 2), dtype=np.float32)  # Pre-fill with ones
        engine._audio_callback(out2, 256, None, None)

        np.testing.assert_array_equal(out2, np.zeros((256, 2), dtype=np.float32))

        engine.stop()

    def test_next_trigger_works_without_restart(self):
        """Next trigger should work immediately without restarting engine"""
        engine = RingBufferAudioEngine(autostop_one_shot=False)
        engine.start()

        # First one-shot
        audio1 = np.full((500, 2), [0.3, 0.3], dtype=np.float32)
        engine.play_one_shot(audio1)

        # Wait for buffer to fill
        for _ in range(50):
            if engine._ring_buffer.available_read() > 100:
                break
            time.sleep(0.01)

        # Drain
        out1 = np.zeros((600, 2), dtype=np.float32)
        engine._audio_callback(out1, 600, None, None)

        # Wait for state to update
        time.sleep(0.02)

        # Verify state is ARMED (not IDLE because autostop=False)
        assert engine.state == EngineState.ARMED

        # Second trigger without restart
        audio2 = np.full((1000, 2), [0.7, 0.7], dtype=np.float32)
        engine.play_one_shot(audio2)

        # Wait for buffer to fill
        for _ in range(50):
            if engine._ring_buffer.available_read() > 100:
                break
            time.sleep(0.01)

        # Should get audio2
        out2 = np.zeros((500, 2), dtype=np.float32)
        engine._audio_callback(out2, 500, None, None)

        fade_samples = int(engine.config.fade_in_ms * 44.1)
        # Verify we got audio (allowing for fade-in)
        np.testing.assert_allclose(out2[fade_samples + 50:fade_samples + 100, 0], 0.7, atol=0.1)

        engine.stop()


# =============================================================================
# 7. Tempo Semantics (S1000 Style)
# =============================================================================

class TestTempoChangeWhileStopped:
    """Test tempo changes when engine is stopped"""

    def test_tempo_change_restarts_engine(self):
        """Tempo change should cleanly restart engine"""
        engine = RingBufferAudioEngine()
        engine.start()
        engine.stop()

        original_rate = engine.sample_rate

        # Change tempo (simulated via sample rate adjustment)
        engine.set_tempo(bpm=140, source_bpm=120)
        engine.start()

        # Sample rate should have changed
        expected_rate = int(44100 * (140 / 120))
        assert engine.sample_rate == expected_rate

        engine.stop()

    def test_ring_buffer_cleared_on_tempo_change(self):
        """Ring buffer should be cleared when tempo changes"""
        engine = RingBufferAudioEngine()
        engine.start()

        # Queue some audio
        audio = np.full((1000, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        engine.stop()

        # Change tempo
        engine.set_tempo(bpm=140, source_bpm=120)

        # Buffer should be empty
        assert engine._ring_buffer.available_read() == 0

        engine.start()
        engine.stop()


class TestTempoChangeWhilePlaying:
    """Test tempo change behavior during playback"""

    def test_tempo_change_rejected_or_deferred(self):
        """Tempo change during playback should be rejected or deferred"""
        engine = RingBufferAudioEngine()
        engine.start()

        audio = np.full((10000, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        original_rate = engine.sample_rate

        # Try to change tempo while playing
        result = engine.set_tempo(bpm=140, source_bpm=120)

        # Either returns False (rejected) or tempo is unchanged
        if result is False:
            pass  # Explicitly rejected - good
        else:
            # If not explicitly rejected, current playback should continue unchanged
            assert engine.sample_rate == original_rate

        engine.stop()

    def test_playback_continues_unchanged(self):
        """Current playback should continue unchanged if tempo change attempted"""
        engine = RingBufferAudioEngine()
        engine.start()

        audio = np.full((5000, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        # Get some output before tempo attempt
        out1 = np.zeros((256, 2), dtype=np.float32)
        engine._audio_callback(out1, 256, None, None)

        # Attempt tempo change
        engine.set_tempo(bpm=140, source_bpm=120)

        # Playback should continue
        out2 = np.zeros((256, 2), dtype=np.float32)
        engine._audio_callback(out2, 256, None, None)

        # Should still have audio (not silence)
        assert np.any(np.abs(out2) > 0.1)

        engine.stop()


# =============================================================================
# 8. Regression / Safety Tests
# =============================================================================

class TestCallbackSimplicity:
    """Test that callback remains simple and safe"""

    def test_callback_handles_zero_frames(self):
        """Callback should handle request for 0 frames gracefully"""
        engine = RingBufferAudioEngine()
        engine.start()

        outdata = np.zeros((0, 2), dtype=np.float32)
        # Should not raise
        engine._audio_callback(outdata, 0, None, None)

        engine.stop()

    def test_callback_handles_large_request(self):
        """Callback should handle unusually large frame requests"""
        engine = RingBufferAudioEngine()
        engine.start()

        audio = np.full((100, 2), [0.5, 0.5], dtype=np.float32)
        engine.play_one_shot(audio)
        time.sleep(0.01)

        # Request way more than buffer has
        outdata = np.zeros((10000, 2), dtype=np.float32)
        # Should not raise
        engine._audio_callback(outdata, 10000, None, None)

        engine.stop()


class TestDeterminism:
    """Test output determinism"""

    def test_same_input_same_output(self):
        """Same input with same config should produce identical output"""
        # Test determinism of audio processing (fade functions) directly
        # since engine timing is inherently non-deterministic

        from ring_buffer_audio import apply_fade_in, apply_tail_fade

        results = []
        for _ in range(3):
            # Use deterministic input
            audio = np.linspace(0, 1, 1000, dtype=np.float32)
            audio = np.column_stack([audio, audio]).copy()

            # Apply fades (this is the deterministic part of audio processing)
            apply_fade_in(audio, 50, "exponential")
            apply_tail_fade(audio, 50, "exponential")

            results.append(audio.copy())

        # All results should be identical
        np.testing.assert_array_equal(results[0], results[1])
        np.testing.assert_array_equal(results[1], results[2])

    def test_ring_buffer_deterministic(self):
        """Ring buffer operations should be deterministic"""
        results = []

        for _ in range(3):
            ring = StereoRingBuffer(1024)

            # Write known data
            input_data = np.arange(200, dtype=np.float32).reshape(100, 2)
            ring.write(input_data)

            # Read it back
            output = np.zeros((100, 2), dtype=np.float32)
            ring.read(output)

            results.append(output.copy())

        np.testing.assert_array_equal(results[0], results[1])
        np.testing.assert_array_equal(results[1], results[2])


class TestThreadSafety:
    """Test thread safety of ring buffer and engine"""

    def test_concurrent_write_read(self):
        """Concurrent writes and reads should not corrupt data"""
        ring = StereoRingBuffer(1024)
        errors = []

        def writer():
            try:
                for i in range(100):
                    data = np.full((10, 2), [i * 0.01, i * 0.01], dtype=np.float32)
                    ring.write(data)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    out = np.zeros((10, 2), dtype=np.float32)
                    ring.read(out)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)

        writer_thread.start()
        reader_thread.start()

        writer_thread.join()
        reader_thread.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
