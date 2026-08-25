"""Audio Pipeline Satellite [FEAT-059/LAB-088/REF-03].

Pure-functional PCM conversion, sliding-window slicing, and peak signal
detection extracted from sensory_manager.py for independent testability.
"""

from __future__ import annotations

import numpy as np


class AudioPipeline:
    """Stateless audio processing utilities for PCM stream handling."""

    @staticmethod
    def pcm_to_numpy(raw_bytes: bytes, dtype: type = np.int16) -> np.ndarray:
        """Convert binary Signed Int16 PCM bytes to a NumPy array.

        Parameters
        ----------
        raw_bytes : bytes
            Raw PCM audio data (little-endian Int16).
        dtype : type, optional
            Target NumPy dtype (default ``np.int16``).

        Returns
        -------
        np.ndarray
            1-D array of sample values.
        """
        return np.frombuffer(raw_bytes, dtype=dtype)

    @staticmethod
    def slice_sliding_window(
        buffer: np.ndarray,
        window_size: int = 24000,
        stride: int = 16000,
    ) -> tuple[None, np.ndarray] | tuple[np.ndarray, np.ndarray]:
        """Extract a fixed-size window and advance the buffer by *stride*.

        If the buffer contains fewer than *window_size* samples the window
        is ``None`` and the buffer is returned unchanged.

        Returns
        -------
        tuple[Optional[np.ndarray], np.ndarray]
            ``(window, remaining_buffer)`` where *window* is the extracted
            chunk (or ``None``) and *remaining_buffer* is the unconsumed tail.
        """
        if len(buffer) >= window_size:
            return buffer[:window_size], buffer[stride:]
        return None, buffer

    @staticmethod
    def compute_signal_peak(chunk: np.ndarray) -> int:
        """Return the absolute-maximum sample amplitude in *chunk*.

        An empty array returns ``0``.
        """
        if len(chunk) == 0:
            return 0
        return int(np.abs(chunk.astype(np.int32)).max())

    @staticmethod
    def is_signal_detected(chunk: np.ndarray, threshold: int = 500) -> bool:
        """Return ``True`` if the peak amplitude exceeds *threshold*."""
        return bool(AudioPipeline.compute_signal_peak(chunk) > threshold)
