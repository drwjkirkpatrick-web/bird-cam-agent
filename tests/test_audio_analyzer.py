"""tests/test_audio_analyzer.py"""

import pytest
from modules.audio_analyzer import AudioAnalyzer

@pytest.fixture
def analyzer():
    return AudioAnalyzer({"mock_mode": True})

@pytest.fixture
def audio_file(tmp_path):
    import wave, struct
    p = tmp_path / "test.wav"
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        # Write 1 second of silence
        frames = struct.pack("<" + "h" * 44100, *([0] * 44100))
        wf.writeframes(frames)
    return str(p)

class TestAnalyzer:
    def test_analyze(self, analyzer, audio_file):
        result = analyzer.analyze(audio_file)
        assert "duration_seconds" in result
        assert "peak_freq_hz" in result
    def test_missing_file(self, analyzer):
        result = analyzer.analyze("/nonexistent.wav")
        assert "error" in result
    def test_compare_calls(self, analyzer, audio_file):
        result = analyzer.compare_calls(audio_file, audio_file)
        assert "similarity_score" in result
    def test_mock_analyze(self, analyzer, audio_file):
        result = analyzer._mock_analyze(audio_file)
        assert result["mock"] is True
