"""
tests/test_recorder.py — Tests for the video recorder module.

NOTE: These tests focus on the MockRecorder (no hardware required) and on
      the RecorderFactory's selection logic. Hardware-backed recorders
      (PiCameraRecorder, USBRecorder) are tested with importorskip so they
      SKIP cleanly on machines without picamera/cv2 rather than erroring.

WHY: The recorder runs recording in a background thread, so the tests
     exercise the thread lifecycle (start -> is_recording -> stop -> join),
     thread safety under concurrent access, graceful handling of edge cases
     (stop without start, double start), and filename format. All tests run
     on any machine because they use MockRecorder + temp dirs.
"""

import os
import re
import threading
import time

import pytest

from core.types import CameraConfig
from modules.recorder import (
    MockRecorder,
    RecorderBase,
    RecorderFactory,
)

# NOTE: Match the spec's filename format for the timestamp check.
#       recording_{YYYYMMDD_HHMMSS}.mp4
_TIMESTAMP_RE = re.compile(r"^recording_\d{8}_\d{6}\.mp4$")


@pytest.fixture
def tmp_video_config(tmp_path):
    """A CameraConfig pointing video_dir at a unique temp directory."""
    return CameraConfig(
        video_dir=str(tmp_path / "videos"),
        mock_mode=True,
        camera_type="mock",
    )


@pytest.fixture
def mock_recorder(tmp_video_config):
    """A MockRecorder built from the tmp_video_config fixture."""
    return MockRecorder(tmp_video_config)


# ---------------------------------------------------------------------------
# 1. MockRecorder creates a file
# ---------------------------------------------------------------------------


def test_mock_recorder_creates_file(mock_recorder, tmp_video_config):
    """After start+stop, a real .mp4 file exists on disk."""
    path = mock_recorder.start_recording(0.1)
    # NOTE: stop blocks until the recording thread finishes and writes the file
    final = mock_recorder.stop_recording()

    assert final == path
    assert os.path.exists(final), f"Expected file at {final}"
    assert final.endswith(".mp4")
    # WHY: Asserting non-zero size confirms we actually wrote bytes, not just
    #      touched the file — catches regressions where _record exits early.
    assert os.path.getsize(final) > 0
    # The video_dir should have been created too
    assert os.path.isdir(tmp_video_config.video_dir)


# ---------------------------------------------------------------------------
# 2. start/stop lifecycle
# ---------------------------------------------------------------------------


def test_start_stop_lifecycle(mock_recorder):
    """start_recording returns a path; stop_recording returns the same path."""
    path = mock_recorder.start_recording(0.2)
    assert isinstance(path, str)
    assert path  # non-empty
    final = mock_recorder.stop_recording()
    assert final == path


# ---------------------------------------------------------------------------
# 3. is_recording state transitions
# ---------------------------------------------------------------------------


def test_is_recording_state_transitions(mock_recorder):
    """is_recording is False -> True after start -> False after stop."""
    assert mock_recorder.is_recording() is False

    mock_recorder.start_recording(5.0)
    # NOTE: Give the thread a moment to flip the flag.
    time.sleep(0.05)
    assert mock_recorder.is_recording() is True

    mock_recorder.stop_recording()
    assert mock_recording_is_false(mock_recorder)


def mock_recording_is_false(recorder):
    """Helper: poll for up to 1s until is_recording flips to False.

    WHY: stop_recording joins the thread, so the flag should already be
         False by the time stop returns — but polling makes the test
         robust to scheduling jitter on slow CI machines instead of a
         flaky hard assert.
    """
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if not recorder.is_recording():
            return True
        time.sleep(0.01)
    return recorder.is_recording() is False


# ---------------------------------------------------------------------------
# 4. RecorderFactory returns the correct type
# ---------------------------------------------------------------------------


def test_factory_returns_mock_for_mock_mode(tmp_video_config):
    """When mock_mode is True, the factory returns a MockRecorder."""
    tmp_video_config.mock_mode = True
    rec = RecorderFactory.create(tmp_video_config)
    assert isinstance(rec, MockRecorder)


def test_factory_returns_mock_for_mock_camera_type(tmp_path):
    """camera_type='mock' yields a MockRecorder even with mock_mode=False."""
    cfg = CameraConfig(
        video_dir=str(tmp_path / "v"),
        mock_mode=False,
        camera_type="mock",
    )
    rec = RecorderFactory.create(cfg)
    assert isinstance(rec, MockRecorder)


def test_factory_falls_back_to_mock_when_hardware_missing(tmp_path):
    """camera_type='picamera' falls back to MockRecorder when picamera absent.

    NOTE: On machines without picamera (the common case), the factory must
          gracefully degrade rather than raise.
    """
    cfg = CameraConfig(
        video_dir=str(tmp_path / "v"),
        mock_mode=False,
        camera_type="picamera",
    )
    rec = RecorderFactory.create(cfg)
    # WHY: We don't assert the exact backend — it depends on whether picamera
    #      is installed on this machine. We assert it's a valid RecorderBase
    #      and, when picamera is absent, that it's a MockRecorder.
    assert isinstance(rec, RecorderBase)
    try:
        import picamera  # noqa: F401
        # picamera present -> PiCameraRecorder is acceptable
    except ImportError:
        assert isinstance(rec, MockRecorder)


def test_factory_returns_recorderbase_subtype(tmp_video_config):
    """Whatever the factory returns, it must be a RecorderBase."""
    rec = RecorderFactory.create(tmp_video_config)
    assert isinstance(rec, RecorderBase)


# ---------------------------------------------------------------------------
# 5. Hardware tests skip cleanly
# ---------------------------------------------------------------------------


def test_picamera_recorder_skips_without_hardware(tmp_path):
    """PiCameraRecorder tests skip cleanly when picamera isn't installed."""
    pytest.importorskip("picamera")
    from modules.recorder import PiCameraRecorder

    cfg = CameraConfig(
        video_dir=str(tmp_path / "v"),
        mock_mode=False,
        camera_type="picamera",
    )
    rec = PiCameraRecorder(cfg)
    assert isinstance(rec, RecorderBase)


def test_usb_recorder_skips_without_hardware(tmp_path):
    """USBRecorder tests skip cleanly when cv2 isn't installed."""
    pytest.importorskip("cv2")
    from modules.recorder import USBRecorder

    cfg = CameraConfig(
        video_dir=str(tmp_path / "v"),
        mock_mode=False,
        camera_type="usb",
    )
    rec = USBRecorder(cfg)
    assert isinstance(rec, RecorderBase)


# ---------------------------------------------------------------------------
# 6. Thread safety — concurrent start/stop doesn't corrupt state
# ---------------------------------------------------------------------------


def test_thread_safety_concurrent_start_stop(mock_recorder):
    """Many threads calling start/stop/is_recording concurrently must not
    corrupt state or deadlock. Exactly one start should win; the rest either
    see 'already recording' (RuntimeError) or a False is_recording.
    """
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(20):
                try:
                    mock_recorder.start_recording(0.01)
                except RuntimeError:
                    # NOTE: Expected when another thread is already recording.
                    pass
                mock_recorder.is_recording()
                try:
                    mock_recorder.stop_recording()
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert not errors, f"Concurrent access produced errors: {errors}"
    # WHY: After everything settles, the recorder must report not-recording
    #      — a stuck True would indicate a leaked lock or unjoined thread.
    assert mock_recorder.is_recording() is False


def test_double_start_raises(mock_recorder):
    """A second start_recording while one is in flight must raise, not
    silently clobber the first recording's file path."""
    mock_recorder.start_recording(5.0)
    try:
        with pytest.raises(RuntimeError):
            mock_recorder.start_recording(1.0)
    finally:
        mock_recorder.stop_recording()


# ---------------------------------------------------------------------------
# 7. Filename contains a timestamp in the spec'd format
# ---------------------------------------------------------------------------


def test_filename_contains_timestamp(mock_recorder, tmp_video_config):
    """The generated filename matches recording_{YYYYMMDD_HHMMSS}.mp4."""
    path = mock_recorder.start_recording(0.1)
    mock_recorder.stop_recording()

    basename = os.path.basename(path)
    assert _TIMESTAMP_RE.match(basename), (
        f"Filename {basename!r} does not match recording_{{YYYYMMDD_HHMMSS}}.mp4"
    )
    # And it lives under the configured video_dir
    assert os.path.dirname(path) == os.path.normpath(tmp_video_config.video_dir)


# ---------------------------------------------------------------------------
# 8. stop without start handles gracefully
# ---------------------------------------------------------------------------


def test_stop_without_start_returns_empty_string(mock_recorder):
    """Calling stop_recording before start must return '' and not raise."""
    result = mock_recorder.stop_recording()
    assert result == ""
    assert mock_recorder.is_recording() is False


def test_stop_without_start_is_idempotent(mock_recorder):
    """Repeated stop without a start stays a safe no-op."""
    assert mock_recorder.stop_recording() == ""
    assert mock_recorder.stop_recording() == ""
    assert mock_recorder.is_recording() is False


# ---------------------------------------------------------------------------
# Extras: early stop and invalid duration
# ---------------------------------------------------------------------------


def test_early_stop_before_duration(mock_recorder):
    """stop_recording before the duration elapses still yields a file."""
    path = mock_recorder.start_recording(60.0)  # long
    time.sleep(0.1)  # let the thread start waiting
    final = mock_recorder.stop_recording()
    assert final == path
    # NOTE: Even an early stop should produce a (mock) file.
    assert os.path.exists(final)


def test_start_recording_invalid_duration_raises(mock_recorder):
    """Non-positive duration is rejected up front."""
    with pytest.raises(ValueError):
        mock_recorder.start_recording(0.0)
    with pytest.raises(ValueError):
        mock_recorder.start_recording(-1.0)
    assert mock_recorder.is_recording() is False


def test_factory_unknown_camera_type_falls_back_to_mock(tmp_path):
    """An unrecognized camera_type degrades to MockRecorder, not an error."""
    cfg = CameraConfig(
        video_dir=str(tmp_path / "v"),
        mock_mode=False,
        camera_type="nonsense",
    )
    rec = RecorderFactory.create(cfg)
    assert isinstance(rec, MockRecorder)