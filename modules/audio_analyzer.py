"""
modules/audio_analyzer.py — Audio frequency pattern analysis.

NOTE: Analyzes bird audio recordings for frequency patterns, call duration,
      and acoustic features. Useful for distinguishing similar species and
      understanding call structure.

WHY: BirdNET analyzes audio features for identification. This module provides
     basic audio analysis that complements the Hermes bridge's holistic
     identification approach.
"""

from __future__ import annotations

import logging
import os
import wave
from typing import Any

logger = logging.getLogger(__name__)


class AudioAnalyzer:
    """
    Analyzes bird audio recordings for acoustic features.

    Usage:
        analyzer = AudioAnalyzer({"mock_mode": True})
        features = analyzer.analyze("recording.wav")
        print(f"Peak freq: {features['peak_freq_hz']} Hz")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)

    def analyze(self, audio_path: str) -> dict[str, Any]:
        """
        Analyze an audio file and return acoustic features.

        Returns dict with: duration, sample_rate, peak_freq, avg_freq,
        freq_range, amplitude, silence_ratio
        """
        if not os.path.exists(audio_path):
            return {"error": "File not found"}

        if self.mock_mode:
            return self._mock_analyze(audio_path)

        try:
            return self._real_analyze(audio_path)
        except Exception as e:
            logger.error("Audio analysis failed: %s", e)
            return self._mock_analyze(audio_path)

    def _real_analyze(self, audio_path: str) -> dict[str, Any]:
        """Analyze audio using numpy FFT."""
        import numpy as np

        with wave.open(audio_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()

        if sampwidth == 2:
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        else:
            data = np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128

        if channels > 1:
            data = data[::channels]

        # Normalize
        if len(data) > 0:
            data = data / max(abs(data.max()), abs(data.min()), 1)

        # Compute FFT
        if len(data) > 0:
            fft = np.abs(np.fft.rfft(data))
            freqs = np.fft.rfftfreq(len(data), 1 / sample_rate)

            peak_idx = np.argmax(fft)
            peak_freq = freqs[peak_idx] if len(freqs) > 0 else 0
            avg_freq = np.average(freqs, weights=fft) if np.sum(fft) > 0 else 0
            freq_range = (freqs[1] - freqs[0]) * len(freqs) if len(freqs) > 1 else 0

            # Amplitude and silence ratio
            amplitude = float(np.sqrt(np.mean(data**2)))
            silence_threshold = 0.01
            silence_ratio = float(np.sum(np.abs(data) < silence_threshold) / len(data))
        else:
            peak_freq = 0
            avg_freq = 0
            freq_range = 0
            amplitude = 0
            silence_ratio = 1.0

        duration = len(data) / sample_rate if sample_rate > 0 else 0

        return {
            "duration_seconds": round(duration, 2),
            "sample_rate": sample_rate,
            "peak_freq_hz": round(peak_freq, 1),
            "avg_freq_hz": round(avg_freq, 1),
            "freq_range_hz": round(freq_range, 1),
            "amplitude": round(amplitude, 4),
            "silence_ratio": round(silence_ratio, 3),
        }

    def _mock_analyze(self, audio_path: str) -> dict[str, Any]:
        """Generate mock analysis results."""
        try:
            with wave.open(audio_path, "rb") as wf:
                duration = wf.getnframes() / wf.getframerate()
                sample_rate = wf.getframerate()
        except Exception:
            duration = 10.0
            sample_rate = 44100

        return {
            "duration_seconds": round(duration, 2),
            "sample_rate": sample_rate,
            "peak_freq_hz": 3500.0,
            "avg_freq_hz": 2800.0,
            "freq_range_hz": 8000.0,
            "amplitude": 0.35,
            "silence_ratio": 0.15,
            "mock": True,
        }

    def compare_calls(self, path1: str, path2: str) -> dict[str, Any]:
        """Compare two audio files and return similarity metrics."""
        f1 = self.analyze(path1)
        f2 = self.analyze(path2)

        if "error" in f1 or "error" in f2:
            return {"error": "Could not analyze one or both files"}

        freq_diff = abs(f1.get("peak_freq_hz", 0) - f2.get("peak_freq_hz", 0))
        amp_diff = abs(f1.get("amplitude", 0) - f2.get("amplitude", 0))

        # Simple similarity score (0-1, higher = more similar)
        freq_similarity = max(0, 1 - freq_diff / 5000)
        amp_similarity = max(0, 1 - amp_diff)
        overall = (freq_similarity + amp_similarity) / 2

        return {
            "freq_difference_hz": round(freq_diff, 1),
            "amplitude_difference": round(amp_diff, 4),
            "similarity_score": round(overall, 3),
            "similar": overall > 0.7,
        }


__all__ = ["AudioAnalyzer"]
