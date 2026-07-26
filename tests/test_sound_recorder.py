"""
tests/test_sound_recorder.py — Tests for the audio recording module.

NOTE: These tests focus on the mock path (no microphone required) and on
      the thread lifecycle. The hardware path (pyaudio) is tested with
      pytest.importorskip so it SKIPS cleanly on machines without pyaudio
      rather than erroring.

WHY: The recorder runs recording in a background thread, so the tests
     exercise the thread lifecycle (record -> is_recording -> stop ->
     join), thread safety under concurrent access, graceful handling of
     edge cases (stop without start, double record), the WAV file format,
     and the metadata/filename helpers. All tests run on any machine
     because they use mock_mode=True + temp dirs.
"""

import os
import re
import struct
import threading
import time

import pytest

from modules.sound_recorder import SoundRecorder


# NOTE: Match the spec's filename format for the timestamp check.
#       audio_{YYYYMMDD_HHMMSS}.wav
_TIMESTAMP_RE = re.compile(r"^audio_\d{8}_\d{6}\.wav$")


@pytest.fixture
def tmp_audio_dir(tmp_path):
    """A unique temp directory to use as audio_dir."""
    return str(tmp_path / "audio")


@pytest.fixture
def recorder(tmp_audio_dir):
    """A mock-mode SoundRecorder pointing at a temp audio_dir."""
    return SoundRecorder(
        {
            "audio_dir": tmp_audio_dir,
            "mock_mode": True,
            "sample_rate": 44100,
            "duration_seconds": 10,
            "channels": 1,
        }
    )


def _wait_until_not_recording(rec: SoundRecorder, timeout: float = 2.0) -> bool:
    """Poll for up to `timeout` seconds until is_recording() is False.

    WHY: stop_recording() joins the thread, so the flag should already be
         False by the time stop returns — but polling makes the test
         robust to scheduling jitter on slow CI machines instead of a
         flaky hard assert.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not rec.is_recording():
            return True
        time.sleep(0.01)
    return rec.is_recording() is False


# ---------------------------------------------------------------------------
# 1. Mock record creates a file
# ---------------------------------------------------------------------------


def test_mock_record_creates_file(recorder, tmp_audio_dir):
    """After record+stop, a real .wav file exists on disk."""
    path = recorder.record(0.1)
    # NOTE: stop blocks until the recording thread finishes and writes the file
    final = recorder.stop_recording()

    assert final == path
    assert os.path.exists(final), f"Expected file at {final}"
    assert final.endswith(".wav")
    # WHY: Asserting non-zero size confirms we actually wrote bytes, not just
    #      touched the file — catches regressions where _record exits early.
    assert os.path.getsize(final) > 0
    # The audio_dir should have been created too
    assert os.path.isdir(tmp_audio_dir)


def test_mock_wav_has_valid_header(recorder):
    """The mock file starts with the RIFF/WAVE magic and a 44-byte header."""
    path = recorder.record(0.1)
    recorder.stop_recording()

    with open(path, "rb") as f:
        header = f.read(44)
    assert header[:4] == b"RIFF", "WAV must start with RIFF"
    assert header[8:12] == b"WAVE", "WAV must have WAVE marker"
    # NOTE: 44-byte canonical PCM header — fmt chunk size 16, format 1 (PCM)
    assert struct.unpack("<I", header[16:20])[0] == 16
    assert struct.unpack("<H", header[20:22])[0] == 1  # PCM


# ---------------------------------------------------------------------------
# 2. start/stop lifecycle
# ---------------------------------------------------------------------------


def test_record_stop_lifecycle(recorder):
    """record() returns a path; stop_recording() returns the same path."""
    path = recorder.record(0.2)
    assert isinstance(path, str)
    assert path  # non-empty
    final = recorder.stop_recording()
    assert final == path


# ---------------------------------------------------------------------------
# 3. is_recording state transitions
# ---------------------------------------------------------------------------


def test_is_recording_state_transitions(recorder):
    """is_recording is False -> True after record -> False after stop."""
    assert recorder.is_recording() is False

    recorder.record(5.0)
    # NOTE: Give the thread a moment to flip the flag.
    time.sleep(0.05)
    assert recorder.is_recording() is True

    recorder.stop_recording()
    assert _wait_until_not_recording(recorder)


# ---------------------------------------------------------------------------
# 4. Filename contains a timestamp in the spec'd format
# ---------------------------------------------------------------------------


def test_filename_contains_timestamp(recorder, tmp_audio_dir):
    """The generated filename matches audio_{YYYYMMDD_HHMMSS}.wav."""
    path = recorder.record(0.1)
    recorder.stop_recording()

    basename = os.path.basename(path)
    assert _TIMESTAMP_RE.match(basename), (
        f"Filename {basename!r} does not match audio_{{YYYYMMDD_HHMMSS}}.wav"
    )
    # And it lives under the configured audio_dir
    assert os.path.dirname(path) == os.path.normpath(tmp_audio_dir)


# ---------------------------------------------------------------------------
# 5. get_recording_info returns a dict
# ---------------------------------------------------------------------------


def test_get_recording_info_returns_dict(recorder):
    """get_recording_info returns file_size, duration, sample_rate, etc."""
    path = recorder.record(0.1)
    recorder.stop_recording()

    info = recorder.get_recording_info(path)
    assert isinstance(info, dict)
    assert info["exists"] is True
    assert info["file_size"] > 0
    assert info["sample_rate"] == 44100
    assert info["channels"] == 1
    # NOTE: The mock writes 1000 frames of silence -> duration = 1000/44100
    assert info["duration_seconds"] == pytest.approx(1000 / 44100, rel=0.01)


def test_get_recording_info_missing_file(recorder):
    """get_recording_info on a non-existent path returns exists=False."""
    info = recorder.get_recording_info("/nonexistent/audio_123.wav")
    assert info["exists"] is False
    assert info["file_size"] == 0
    assert info["duration_seconds"] == 0.0


# ---------------------------------------------------------------------------
# 6. list_recordings returns a list
# ---------------------------------------------------------------------------


def test_list_recordings_returns_list(recorder, tmp_audio_dir):
    """list_recordings returns .wav paths in the audio_dir."""
    # NOTE: Empty at first (dir may not even exist yet)
    assert recorder.list_recordings() == []

    path = recorder.record(0.1)
    recorder.stop_recording()

    listings = recorder.list_recordings()
    assert isinstance(listings, list)
    assert len(listings) == 1
    assert listings[0] == path
    assert path.endswith(".wav")


def test_list_recordings_empty_when_dir_missing(recorder, tmp_audio_dir):
    """list_recordings returns [] when the audio_dir doesn't exist."""
    # NOTE: Use a subdir that was never created
    recorder.audio_dir = os.path.join(tmp_audio_dir, "never_created")
    assert recorder.list_recordings() == []


# ---------------------------------------------------------------------------
# 7. delete_recording works
# ---------------------------------------------------------------------------


def test_delete_recording_removes_file(recorder):
    """delete_recording removes the file and returns True."""
    path = recorder.record(0.1)
    recorder.stop_recording()
    assert os.path.exists(path)

    assert recorder.delete_recording(path) is True
    assert not os.path.exists(path)


def test_delete_recording_missing_file(recorder):
    """delete_recording returns False for a non-existent file."""
    assert recorder.delete_recording("/nonexistent/audio_1.wav") is False


def test_delete_recording_refuses_outside_audio_dir(recorder, tmp_path):
    """delete_recording refuses to delete files outside audio_dir."""
    # NOTE: Create a stray .wav outside the recorder's audio_dir
    stray = str(tmp_path / "stray.wav")
    with open(stray, "wb") as f:
        f.write(b"RIFF\x00\x00\x00\x00WAVE")
    assert os.path.exists(stray)

    # WHY: The guard should block this — we don't want a buggy caller to
    #      delete arbitrary files by passing an unrelated path.
    assert recorder.delete_recording(stray) is False
    assert os.path.exists(stray), "Guard should have prevented deletion"


# ---------------------------------------------------------------------------
# 8. Thread safety — concurrent record/stop doesn't corrupt state
# ---------------------------------------------------------------------------


def test_thread_safety_concurrent_record_stop(recorder):
    """Many threads calling record/stop/is_recording concurrently must not
    corrupt state or deadlock. Exactly one record should win; the rest either
    see 'already recording' (RuntimeError) or a False is_recording.
    """
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(20):
                try:
                    recorder.record(0.01)
                except RuntimeError:
                    # NOTE: Expected when another thread is already recording.
                    pass
                recorder.is_recording()
                try:
                    recorder.stop_recording()
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
    assert recorder.is_recording() is False


def test_double_record_raises(recorder):
    """A second record() while one is in flight must raise, not silently
    clobber the first recording's file path."""
    recorder.record(5.0)
    try:
        with pytest.raises(RuntimeError):
            recorder.record(1.0)
    finally:
        recorder.stop_recording()


# ---------------------------------------------------------------------------
# 9. stop without start handles gracefully
# ---------------------------------------------------------------------------


def test_stop_without_start_returns_empty_string(recorder):
    """Calling stop_recording before record must return '' and not raise."""
    result = recorder.stop_recording()
    assert result == ""
    assert recorder.is_recording() is False


def test_stop_without_start_is_idempotent(recorder):
    """Repeated stop without a record stays a safe no-op."""
    assert recorder.stop_recording() == ""
    assert recorder.stop_recording() == ""
    assert recorder.is_recording() is False


# ---------------------------------------------------------------------------
# 10. Hardware tests skip cleanly
# ---------------------------------------------------------------------------


def test_hardware_recorder_skips_without_pyaudio(tmp_path):
    """Hardware-mode SoundRecorder tests skip cleanly when pyaudio isn't
    installed."""
    pytest.importorskip("pyaudio")
    # NOTE: If pyaudio IS installed, construct a hardware-mode recorder and
    #       confirm it doesn't raise at construction. We don't actually
    #       record (no mic guaranteed) — just verify the object builds.
    rec = SoundRecorder(
        {
            "audio_dir": str(tmp_path / "audio"),
            "mock_mode": False,
        }
    )
    assert rec.mock_mode is False


def test_hardware_mode_raises_without_pyaudio(tmp_path):
    """When pyaudio is absent, hardware mode raises a clear RuntimeError at
    construction rather than failing later mid-recording."""
    try:
        import pyaudio  # noqa: F401
        # pyaudio present -> this test is N/A; skip it.
        pytest.skip("pyaudio installed; cannot test the missing-library path")
    except ImportError:
        pass

    with pytest.raises(RuntimeError):
        SoundRecorder(
            {
                "audio_dir": str(tmp_path / "audio"),
                "mock_mode": False,
            }
        )


# ---------------------------------------------------------------------------
# Extras: config defaults, cleanup, invalid duration, early stop
# ---------------------------------------------------------------------------


def test_default_config_when_none_passed(tmp_path):
    """SoundRecorder(config=None) uses the documented defaults."""
    # NOTE: Point audio_dir at a temp path so we don't litter the repo.
    rec = SoundRecorder({"audio_dir": str(tmp_path / "audio")})
    assert rec.sample_rate == 44100
    assert rec.duration_seconds == 10
    assert rec.channels == 1
    assert rec.mock_mode is True


def test_config_overrides_defaults(tmp_path):
    """Caller-supplied config keys override the defaults."""
    rec = SoundRecorder(
        {
            "audio_dir": str(tmp_path / "audio"),
            "sample_rate": 22050,
            "duration_seconds": 5,
            "channels": 2,
            "mock_mode": True,
        }
    )
    assert rec.sample_rate == 22050
    assert rec.duration_seconds == 5
    assert rec.channels == 2


def test_record_invalid_duration_raises(recorder):
    """Non-positive duration is rejected up front."""
    with pytest.raises(ValueError):
        recorder.record(0.0)
    with pytest.raises(ValueError):
        recorder.record(-1.0)
    assert recorder.is_recording() is False


def test_record_uses_default_duration_when_none(recorder):
    """record(None) uses the instance's duration_seconds default."""
    # NOTE: Set a short default so the test doesn't wait 10s.
    recorder.duration_seconds = 0.1
    path = recorder.record(None)
    final = recorder.stop_recording()
    assert final == path
    assert os.path.exists(final)


def test_early_stop_before_duration(recorder):
    """stop_recording before the duration elapses still yields a file."""
    path = recorder.record(60.0)  # long
    time.sleep(0.1)  # let the thread start waiting
    final = recorder.stop_recording()
    assert final == path
    # NOTE: Even an early stop should produce a (mock) file.
    assert os.path.exists(final)


def test_cleanup_stops_in_flight_recording(recorder):
    """cleanup() stops an in-flight recording and leaves not-recording."""
    recorder.record(60.0)
    time.sleep(0.05)
    assert recorder.is_recording() is True

    recorder.cleanup()
    assert recorder.is_recording() is False
    # NOTE: cleanup is idempotent — calling again is a safe no-op.
    recorder.cleanup()
    assert recorder.is_recording() is False


def test_cleanup_no_op_when_idle(recorder):
    """cleanup() on an idle recorder is a safe no-op."""
    assert recorder.is_recording() is False
    recorder.cleanup()
    assert recorder.is_recording() is False