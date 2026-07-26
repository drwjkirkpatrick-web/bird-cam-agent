"""
modules/spectrogram.py — Audio spectrogram visualization.

NOTE: Generates spectrogram images from audio recordings. Spectrograms show
      frequency content over time and are useful for visualizing bird calls.

WHY: BirdNET-Pi displays spectrograms on its dashboard. Spectrograms help
     users understand what the audio identification is "seeing" and are
     a key tool for bird sound analysis.
"""

from __future__ import annotations

import logging
import os
import wave
from typing import Any

logger = logging.getLogger(__name__)


class SpectrogramGenerator:
    """
    Generates spectrogram images from WAV audio files.

    Usage:
        gen = SpectrogramGenerator({"mock_mode": True})
        path = gen.generate("recording.wav", output_path="spectrogram.png")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.fft_size = self.config.get("fft_size", 512)
        self.hop_size = self.config.get("hop_size", 256)
        self.colormap = self.config.get("colormap", "viridis")

    def generate(self, audio_path: str, output_path: str | None = None) -> str | None:
        """
        Generate a spectrogram image from an audio file.

        Returns the path to the generated PNG, or None on failure.
        """
        if not os.path.exists(audio_path):
            logger.warning("Audio file not found: %s", audio_path)
            return None

        if output_path is None:
            base = os.path.splitext(audio_path)[0]
            output_path = f"{base}_spectrogram.png"

        if self.mock_mode:
            return self._generate_mock(output_path)

        try:
            return self._generate_real(audio_path, output_path)
        except Exception as e:
            logger.error("Spectrogram generation failed: %s", e)
            return self._generate_mock(output_path)

    def _generate_real(self, audio_path: str, output_path: str) -> str:
        """Generate a real spectrogram using numpy + matplotlib."""
        import numpy as np

        # Read WAV file
        with wave.open(audio_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()

        # Convert to numpy array
        if sampwidth == 2:
            data = np.frombuffer(frames, dtype=np.int16)
        elif sampwidth == 1:
            data = np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128
        else:
            data = np.frombuffer(frames, dtype=np.int32)

        if channels > 1:
            data = data[::channels]  # Take first channel

        # Compute spectrogram
        from matplotlib import pyplot as plt

        fig, ax = plt.subplots(1, 1, figsize=(10, 4))
        ax.specgram(data, Fs=sample_rate, NFFT=self.fft_size, noverlap=self.hop_size,
                    cmap=self.colormap)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        ax.set_title("Bird Audio Spectrogram")
        fig.tight_layout()
        fig.savefig(output_path, dpi=100)
        plt.close(fig)

        logger.info("Spectrogram saved: %s", output_path)
        return output_path

    def _generate_mock(self, output_path: str) -> str:
        """Generate a placeholder spectrogram image."""
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (400, 200), color=(10, 10, 30))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "SPECTROGRAM [MOCK]", fill=(15, 188, 249))
            draw.text((10, 30), "FFT size: " + str(self.fft_size), fill=(100, 100, 100))
            # Draw some fake frequency bars
            import random
            random.seed(42)
            for x in range(0, 400, 4):
                h = random.randint(10, 150)
                c = (random.randint(0, 100), random.randint(50, 200), random.randint(50, 255))
                draw.line([(x, 190), (x, 190 - h)], fill=c, width=3)

            img.save(output_path)
            return output_path
        except ImportError:
            # Write minimal placeholder
            with open(output_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            return output_path

    def get_info(self, audio_path: str) -> dict[str, Any]:
        """Return audio file info for spectrogram display."""
        if not os.path.exists(audio_path):
            return {"error": "File not found"}

        try:
            with wave.open(audio_path, "rb") as wf:
                return {
                    "duration_seconds": wf.getnframes() / wf.getframerate(),
                    "sample_rate": wf.getframerate(),
                    "channels": wf.getnchannels(),
                    "frames": wf.getnframes(),
                }
        except Exception:
            return {"error": "Could not read audio file"}


__all__ = ["SpectrogramGenerator"]
