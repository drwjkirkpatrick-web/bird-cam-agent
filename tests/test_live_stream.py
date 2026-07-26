"""tests/test_live_stream.py"""

import pytest
from modules.live_stream import LiveStream

@pytest.fixture
def stream():
    return LiveStream({"mock_mode": True, "fps": 5})

class TestStream:
    def test_start(self, stream):
        assert stream.start() is True
        assert stream.is_streaming() is True
    def test_stop(self, stream):
        stream.start()
        assert stream.stop() is True
        assert stream.is_streaming() is False
    def test_get_frame(self, stream):
        stream.start()
        frame = stream.get_frame()
        assert frame is not None
        assert isinstance(frame, bytes)
    def test_no_frame_when_stopped(self, stream):
        assert stream.get_frame() is None
    def test_stream_info(self, stream):
        stream.start()
        info = stream.get_stream_info()
        assert info["streaming"] is True
        assert info["mode"] == "mock"
    def test_mjpeg_headers(self, stream):
        headers = stream.generate_mjpeg_headers()
        assert b"multipart" in headers
    def test_mjpeg_frame(self, stream):
        frame = stream.format_mjpeg_frame(b"fake_jpeg_data")
        assert b"--frame" in frame
        assert b"fake_jpeg_data" in frame
    def test_frame_count_increments(self, stream):
        stream.start()
        stream.get_frame()
        stream.get_frame()
        info = stream.get_stream_info()
        assert info["frame_count"] >= 2
