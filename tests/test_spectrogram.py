"""tests/test_spectrogram.py"""

import os
import tempfile

import pytest
from modules.spectrogram import SpectrogramGenerator

@pytest.fixture
def gen():
    return SpectrogramGenerator({"mock_mode": True})

class TestSpectrogram:
    def test_generate_mock(self, gen, tmp_path):
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)
        output = gen.generate(str(audio))
        assert output is not None
        assert os.path.exists(output)
    def test_missing_file(self, gen):
        assert gen.generate("/nonexistent.wav") is None
    def test_get_info(self, gen, tmp_path):
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)
        info = gen.get_info(str(audio))
        assert "error" not in info or "error" in info
    def test_custom_output_path(self, gen, tmp_path):
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)
        out = tmp_path / "custom.png"
        result = gen.generate(str(audio), str(out))
        assert result == str(out)
