"""Unit tests for audio_pipeline satellite (FEAT-059/LAB-088/REF-03).

Covers PCM byte conversion, sliding-window slicing, peak amplitude
calculation, and threshold signal detection.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.equipment.audio_pipeline import AudioPipeline


# ========================================================================
# 1. pcm_to_numpy
# ========================================================================


class TestPcmToNumpy:
    """Binary Signed Int16 PCM → NumPy array conversion."""

    def test_synthetic_samples(self) -> None:
        """Known little-endian Int16 values survive the round-trip."""
        expected = np.array([0, 100, -100, 32767, -32768], dtype=np.int16)
        raw = expected.tobytes()
        result = AudioPipeline.pcm_to_numpy(raw)
        np.testing.assert_array_equal(result, expected)

    def test_empty_bytes(self) -> None:
        """Empty byte buffer yields an empty array."""
        result = AudioPipeline.pcm_to_numpy(b"")
        assert result.dtype == np.int16
        assert len(result) == 0

    def test_single_sample(self) -> None:
        """A single 2-byte sample is decoded correctly."""
        raw = np.array([42], dtype=np.int16).tobytes()
        result = AudioPipeline.pcm_to_numpy(raw)
        assert result.item() == 42

    def test_custom_dtype(self) -> None:
        """Accepts alternative dtypes (e.g. float32 for 32-bit PCM)."""
        raw = np.array([1.5], dtype=np.float32).tobytes()
        result = AudioPipeline.pcm_to_numpy(raw, dtype=np.float32)
        assert result.dtype == np.float32
        assert result.item() == pytest.approx(1.5)


# ========================================================================
# 2. slice_sliding_window
# ========================================================================


class TestSliceSlidingWindow:
    """Fixed-window extraction with stride-based advancement."""

    def test_buffer_smaller_than_window(self) -> None:
        """Buffer < window_size → (None, full_buffer)."""
        buf = np.arange(100, dtype=np.int16)
        window, remaining = AudioPipeline.slice_sliding_window(buf)
        assert window is None
        np.testing.assert_array_equal(remaining, buf)

    def test_buffer_exactly_window_size(self) -> None:
        """Buffer == window_size → window is first 24000, remainder empty."""
        buf = np.arange(24000, dtype=np.int16)
        window, remaining = AudioPipeline.slice_sliding_window(buf)
        assert window is not None
        assert len(window) == 24000
        np.testing.assert_array_equal(window, buf[:24000])
        # stride == 16000, so remaining = buf[16000:]
        assert len(remaining) == 8000

    def test_buffer_larger_than_window(self) -> None:
        """Buffer > window_size → window of 24000, remaining starts at stride."""
        buf = np.arange(40000, dtype=np.int16)
        window, remaining = AudioPipeline.slice_sliding_window(buf)
        assert window is not None
        assert len(window) == 24000
        np.testing.assert_array_equal(window, buf[:24000])
        np.testing.assert_array_equal(remaining, buf[16000:])
        assert len(remaining) == 24000  # 40000 - 16000

    def test_custom_window_and_stride(self) -> None:
        """Respects non-default window_size and stride parameters."""
        buf = np.arange(20, dtype=np.int16)
        window, remaining = AudioPipeline.slice_sliding_window(
            buf, window_size=8, stride=4
        )
        assert window is not None
        assert len(window) == 8
        np.testing.assert_array_equal(window, buf[:8])
        np.testing.assert_array_equal(remaining, buf[4:])

    def test_drain_large_buffer_iterations(self) -> None:
        """Repeated calls progressively drain a large buffer."""
        buf = np.arange(100000, dtype=np.int16)
        total_consumed = 0
        iterations = 0
        while True:
            window, buf = AudioPipeline.slice_sliding_window(buf)
            if window is None:
                break
            total_consumed += len(window)
            iterations += 1

        # 100000 samples, window=24000, stride=16000
        # Iteration 1: consume 24000 → buf[16000:] = 84000 remaining
        # Iteration 2: consume 24000 → buf[16000:] = 68000 remaining
        # ... until buffer < 24000
        assert iterations > 0
        assert total_consumed == 24000 * iterations
        assert len(buf) < 24000  # final remainder is below window threshold


# ========================================================================
# 3. compute_signal_peak
# ========================================================================


class TestComputeSignalPeak:
    """Peak amplitude calculation for VAD logging."""

    def test_zero_chunk(self) -> None:
        """All-zero chunk returns peak 0."""
        chunk = np.zeros(100, dtype=np.int16)
        assert AudioPipeline.compute_signal_peak(chunk) == 0

    def test_max_positive(self) -> None:
        """Max positive Int16 sample (32767)."""
        chunk = np.array([0, 32767, 0], dtype=np.int16)
        assert AudioPipeline.compute_signal_peak(chunk) == 32767

    def test_max_negative(self) -> None:
        """Min negative Int16 sample (-32768) → absolute peak 32768."""
        chunk = np.array([0, -32768, 0], dtype=np.int16)
        assert AudioPipeline.compute_signal_peak(chunk) == 32768

    def test_mixed_sign(self) -> None:
        """Peak picks the largest absolute value across mixed signs."""
        chunk = np.array([100, -200, 150], dtype=np.int16)
        assert AudioPipeline.compute_signal_peak(chunk) == 200

    def test_empty_chunk(self) -> None:
        """Empty array returns peak 0."""
        chunk = np.array([], dtype=np.int16)
        assert AudioPipeline.compute_signal_peak(chunk) == 0


# ========================================================================
# 4. is_signal_detected
# ========================================================================


class TestIsSignalDetected:
    """Threshold-based signal detection for VAD gating."""

    def test_below_threshold(self) -> None:
        """Peak below default threshold (500) → False."""
        chunk = np.array([100, 200, 300], dtype=np.int16)
        assert AudioPipeline.is_signal_detected(chunk) is False

    def test_above_threshold(self) -> None:
        """Peak above default threshold → True."""
        chunk = np.array([0, 600, 0], dtype=np.int16)
        assert AudioPipeline.is_signal_detected(chunk) is True

    def test_exact_threshold(self) -> None:
        """Peak exactly at threshold → False (must be > threshold)."""
        chunk = np.array([0, 500, 0], dtype=np.int16)
        assert AudioPipeline.is_signal_detected(chunk) is False

    def test_custom_threshold(self) -> None:
        """Non-default threshold is respected."""
        chunk = np.array([0, 100, 0], dtype=np.int16)
        assert AudioPipeline.is_signal_detected(chunk, threshold=50) is True
        assert AudioPipeline.is_signal_detected(chunk, threshold=150) is False

    def test_empty_chunk(self) -> None:
        """Empty chunk → no signal detected."""
        chunk = np.array([], dtype=np.int16)
        assert AudioPipeline.is_signal_detected(chunk) is False
