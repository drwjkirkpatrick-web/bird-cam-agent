"""
modules/sound_recorder.py — Audio recording module for the Bird Cam Agent.

NOTE: This module captures bird sounds to .wav files. It supports a real
      hardware path (pyaudio) and a mock path that writes a minimal valid
      WAV file. The orchestrator just calls record() / stop_recording() and
      gets a file path back — it never branches on whether a mic is present.

WHY: Audio is valuable for bird identification: many species are far easier
     to distinguish by call/song than by plumage in a photo. Pairing a short
     audio clip with each photo sighting gives the identifier (and a human
     reviewer) a second modality. The mock path lets the full pipeline run
     on a dev laptop with no microphone, exactly like the video recorder.

DESIGN: Recording runs in a background thread so the orchestrator loop isn't
        blocked while audio is captured. record() spawns the thread (or
        writes the mock file synchronously for very short clips);
        stop_recording() signals the thread to stop and joins. A
        threading.Lock protects the shared recording state and file path so
        concurrent calls (e.g. a timer firing while the user stops manually)
        can't corrupt state. A threading.Event lets stop_recording() wake
        the recording thread early instead of waiting for the full duration.
"""

from __future__ import annotations

import logging
import os
import struct
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# NOTE: Guard the optional hardware library at import time so this module
#       loads on any machine — a dev laptop without pyaudio can still import
#       SoundRecorder and run in mock mode. The hardware path checks this
#       flag in __init__ and raises a clear RuntimeError if pyaudio is
#       missing, so misuse fails loudly instead of with an obscure
#       ImportError deep inside a recording thread.
try:
    import pyaudio  # type: ignore
    _PYAUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None  # type: ignore
    _PYAUDIO_AVAILABLE = False


# NOTE: Defaults applied when a key is absent from the config dict. Keeping
#       them in one place (not sprinkled through __init__) makes the default
#       surface easy to audit and document.
_DEFAULTS: dict[str, Any] = {
    "sample_rate": 44100,
    "duration_seconds": 10,
    "channels": 1,
    "audio_dir": "data/audio",
    "mock_mode": True,
}


class SoundRecorder:
    """
    Audio recorder for bird sounds, with mock and hardware backends.

    NOTE: A single class covers both backends (unlike the video recorder's
          ABC + factory split) because the audio surface is smaller and the
          mock/hardware paths share most of the thread/lifecycle code. The
          backend is selected by mock_mode in config.

    WHY: One class means one import, one type to mock in tests, and one
         place to maintain the lifecycle. The cost is a couple of `if
         self.mock_mode` branches in the recording thread — a fine trade
         for a leaf module that isn't expected to grow new backends.

    Thread model:
        - record() spawns a daemon thread running _record_worker().
        - stop_recording() sets a stop Event and joins the thread.
        - is_recording() reports the current state under the lock.
        - The lock guards _recording and _file_path; the Event signals
          early stop. Never touch _recording/_file_path without the lock.
    """

    # NOTE: 16-bit PCM is the lingua franca of WAV — every player and
    #       analysis tool reads it. Hardcoding bits_per_sample=16 keeps the
    #       header math simple and the mock file universally valid.
    _BITS_PER_SAMPLE = 16
    # NOTE: A real WAV needs at least a few sample frames so downstream
    #       tools don't reject it as truncated. 1000 frames of silence is
    #       tiny (~44KB at 44.1kHz mono) but unambiguously valid.
    _MOCK_FRAMES = 1000

    def __init__(self, config: dict | None = None):
        # NOTE: Merge user config over defaults so callers only override
        #       what they care about. A fresh dict is built so the caller's
        #       config object is never mutated.
        cfg = dict(_DEFAULTS)
        if config:
            # WHY: Only copy known keys — silently ignoring unknown keys
            #      keeps typos from creating phantom attributes, and a
            #      later typo'd key won't accidentally disable mock mode.
            for key in _DEFAULTS:
                if key in config:
                    cfg[key] = config[key]

        self.sample_rate: int = int(cfg["sample_rate"])
        self.duration_seconds: float = float(cfg["duration_seconds"])
        self.channels: int = int(cfg["channels"])
        self.audio_dir: str = str(cfg["audio_dir"])
        self.mock_mode: bool = bool(cfg["mock_mode"])

        # NOTE: One lock guards the shared recording state and file path.
        #       All reads/writes of _recording and _file_path go through it.
        self._lock = threading.Lock()
        self._recording: bool = False
        self._thread: threading.Thread | None = None
        # WHY: An Event (not a bare bool) lets stop_recording() wake a
        #      recording thread that's sleeping/waiting on duration so it
        #      can exit immediately instead of blocking for the full length.
        self._stop_event = threading.Event()
        self._file_path: str = ""

        # NOTE: Validate hardware availability up front for the non-mock
        #       path so a missing pyaudio fails at construction (clear
        #       message) rather than mid-recording. Mock mode never checks.
        if not self.mock_mode and not _PYAUDIO_AVAILABLE:
            raise RuntimeError(
                "SoundRecorder: mock_mode=False requires the 'pyaudio' "
                "library, which is not installed. Install it or use "
                "mock_mode=True."
            )

    # ---- public API ----

    def record(self, duration_sec: float | None = None) -> str:
        """
        Begin recording in a background thread. Returns the planned file
        path (the file is finalized when recording stops or the duration
        elapses).

        NOTE: If duration_sec is None, the instance default
              self.duration_seconds is used. The file is always written,
              even on early stop, so stop_recording() yields a real path.

        WHY: Returning the planned path (not waiting for the file) lets the
             orchestrator reference the future clip immediately, e.g. to
             attach it to a sighting record before it's finalized.
        """
        if duration_sec is None:
            duration_sec = self.duration_seconds
        if duration_sec <= 0:
            # NOTE: Reject non-positive duration up front — a zero/negative
            #       clip makes no sense and would produce an empty file.
            raise ValueError("duration_sec must be positive")

        with self._lock:
            if self._recording:
                # WHY: Refuse a double-start rather than silently clobbering
                #      an in-flight recording — the caller likely has a bug.
                raise RuntimeError("Recording already in progress")

            self._ensure_audio_dir()
            self._stop_event.clear()
            self._file_path = self._generate_filename()
            path = self._file_path
            self._recording = True
            # NOTE: daemon=True so a forgotten stop_recording() can't keep
            #       the process alive at shutdown.
            self._thread = threading.Thread(
                target=self._record_worker,
                args=(duration_sec,),
                daemon=True,
                name="SoundRecorder-record",
            )
            self._thread.start()

        logger.info(
            "SoundRecorder started recording %.1fs -> %s",
            duration_sec,
            path,
        )
        return path

    def is_recording(self) -> bool:
        """Return True if a recording is currently in progress."""
        with self._lock:
            return self._recording

    def stop_recording(self) -> str:
        """
        Stop the in-flight recording, join its thread, and return the file
        path. Returns "" if nothing was recording.

        NOTE: Joins with a timeout so a wedged hardware thread can't hang
              the caller forever.
        """
        with self._lock:
            if not self._recording:
                # WHY: stop without start is a no-op returning "" — graceful
                #      handling per the spec, not an error.
                return ""
            path = self._file_path
            thread = self._thread
            self._stop_event.set()

        if thread is not None:
            # NOTE: Join outside the lock so the recording thread — which
            #       needs the lock in some paths — can't deadlock against
            #       us. A generous timeout guards against hung hardware.
            thread.join(timeout=30.0)
            if thread.is_alive():
                logger.warning(
                    "SoundRecorder thread did not stop within 30s — continuing"
                )

        with self._lock:
            self._recording = False
            self._thread = None
            self._stop_event.clear()
            final_path = self._file_path
            self._file_path = ""

        logger.info("SoundRecorder stopped recording -> %s", final_path)
        return final_path

    def get_recording_info(self, path: str) -> dict:
        """
        Return metadata about a recording file.

        NOTE: Returns a dict with keys: file_size (bytes), duration_seconds
              (float estimate from the WAV data chunk), sample_rate (int),
              channels (int), exists (bool). If the file is missing, exists
              is False and the numeric fields are zero.

        WHY: The duration is *estimated* from the WAV header rather than
             measured at record time, because the file may have been
             created by another tool or copied in. Reading it back from the
             header is authoritative for what's actually on disk.
        """
        info: dict[str, Any] = {
            "file_size": 0,
            "duration_seconds": 0.0,
            "sample_rate": 0,
            "channels": 0,
            "exists": False,
        }
        if not os.path.exists(path):
            return info

        info["exists"] = True
        info["file_size"] = os.path.getsize(path)

        # NOTE: Parse the WAV header to recover sample_rate / channels /
        #       data size. We only need the fmt chunk (offset 22-35) and
        #       the data chunk size (offset 40). This is the canonical
        #       44-byte PCM header our mock writes and pyaudio produces.
        try:
            with open(path, "rb") as f:
                header = f.read(44)
            if len(header) >= 44 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                # NOTE: struct.unpack with little-endian ('<') matches WAV.
                channels = struct.unpack("<H", header[22:24])[0]
                sample_rate = struct.unpack("<I", header[24:28])[0]
                bits_per_sample = struct.unpack("<H", header[34:36])[0]
                data_size = struct.unpack("<I", header[40:44])[0]
                info["channels"] = channels
                info["sample_rate"] = sample_rate
                # WHY: duration = data_bytes / (sample_rate * channels *
                #      bytes_per_sample). Guard against zero divisors.
                bytes_per_sample = bits_per_sample // 8
                denom = sample_rate * channels * bytes_per_sample
                if denom > 0:
                    info["duration_seconds"] = data_size / denom
        except (OSError, struct.error) as e:
            # NOTE: If the header is malformed, fall back to a coarse
            #       estimate from the raw file size using the configured
            #       sample rate — better than crashing the caller.
            logger.warning("get_recording_info: header parse failed for %s: %s", path, e)
            bytes_per_sample = self._BITS_PER_SAMPLE // 8
            denom = self.sample_rate * self.channels * bytes_per_sample
            if denom > 0:
                info["duration_seconds"] = info["file_size"] / denom
                info["sample_rate"] = self.sample_rate
                info["channels"] = self.channels

        return info

    def list_recordings(self) -> list[str]:
        """
        List all .wav files in audio_dir, sorted by name (oldest first).

        NOTE: Returns full paths, not basenames, so the caller can pass
              them straight to get_recording_info / delete_recording.

        WHY: Sorting by name works because the filename starts with a
             timestamp (audio_YYYYMMDD_HHMMSS.wav) — name order == time
             order. This avoids an extra stat per file just to sort.
        """
        if not os.path.isdir(self.audio_dir):
            return []
        try:
            entries = os.listdir(self.audio_dir)
        except OSError as e:
            logger.warning("list_recordings: cannot read %s: %s", self.audio_dir, e)
            return []
        # NOTE: Filter to .wav (case-insensitive) and build full paths.
        wavs = [
            os.path.join(self.audio_dir, name)
            for name in entries
            if name.lower().endswith(".wav")
        ]
        wavs.sort()
        return wavs

    def delete_recording(self, path: str) -> bool:
        """
        Delete a recording file. Returns True if deleted, False if the
        file didn't exist or couldn't be removed.

        NOTE: Only deletes files that look like our recordings (.wav under
              audio_dir) — this guard prevents accidental deletion of
              arbitrary paths passed by a buggy caller.

        WHY: A recorder that can create files should also be able to clean
             them up; without a path-prefix check, a mistaken caller could
             ask it to delete a system file.
        """
        if not path or not os.path.exists(path):
            return False
        # NOTE: Normalize before comparing so relative/absolute mismatches
        #       don't cause a false-negative guard.
        norm_path = os.path.normpath(path)
        norm_dir = os.path.normpath(self.audio_dir)
        if not norm_path.startswith(norm_dir):
            logger.warning(
                "delete_recording: refusing to delete %s (outside audio_dir %s)",
                path,
                self.audio_dir,
            )
            return False
        if not path.lower().endswith(".wav"):
            logger.warning("delete_recording: refusing to delete non-wav %s", path)
            return False
        try:
            os.remove(path)
            logger.info("delete_recording: removed %s", path)
            return True
        except OSError as e:
            logger.warning("delete_recording: failed to remove %s: %s", path, e)
            return False

    def cleanup(self) -> None:
        """
        Stop any in-flight recording and release resources.

        NOTE: Safe to call multiple times. In mock mode there are no
              resources to release; in hardware mode any open pyaudio
              stream is closed by stop_recording()'s join. This is the
              hook the orchestrator calls at shutdown.
        """
        # NOTE: If a recording is in flight, stop it cleanly first so the
        #       file is finalized before the process exits.
        if self.is_recording():
            self.stop_recording()
        # WHY: No persistent pyaudio instance is held between recordings
        #      (each _record_worker opens/closes its own stream), so there
        #      is nothing else to tear down here. The method exists for
        #      API symmetry with other modules and future resource holders.
        logger.info("SoundRecorder cleanup complete")

    # ---- internal helpers ----

    def _generate_filename(self) -> str:
        """
        Build a timestamped .wav path under audio_dir.

        NOTE: Format is audio_{YYYYMMDD_HHMMSS}.wav. The timestamp is local
              time — audio is for human review, so local time is more
              meaningful than UTC for a single-location bird cam.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.audio_dir, f"audio_{timestamp}.wav")

    def _ensure_audio_dir(self) -> None:
        """Create the audio output directory if it doesn't exist."""
        os.makedirs(self.audio_dir, exist_ok=True)

    def _record_worker(self, duration_sec: float) -> None:
        """
        Background-thread capture loop. Delegates to the mock or hardware
        path based on self.mock_mode. Always finalizes the file before
        returning so stop_recording() yields a real path.
        """
        if self.mock_mode:
            self._record_mock(duration_sec)
        else:
            self._record_hardware(duration_sec)

    def _record_mock(self, duration_sec: float) -> None:
        """
        Mock recording: wait for the duration (or early stop), then write a
        minimal valid WAV file containing silence.

        NOTE: The file is written on exit regardless of whether the full
              duration elapsed, so an early stop still produces a valid
              (short) clip. The mock writes a fixed number of silent
              frames rather than scaling to duration — the point is a
              valid, parseable WAV, not an accurate-duration silence.
        """
        # NOTE: Wait on the stop Event with the full duration as timeout.
        #       If stop_recording() fires, wait() returns True immediately
        #       and we skip to file writing. Otherwise it times out after
        #       duration_sec and we proceed naturally.
        self._stop_event.wait(timeout=duration_sec)

        path = ""
        with self._lock:
            path = self._file_path
        if not path:
            return
        try:
            self._write_mock_wav(path)
        except OSError as e:
            logger.error("SoundRecorder mock write failed for %s: %s", path, e)

    def _write_mock_wav(self, path: str) -> None:
        """
        Write a minimal but valid 16-bit PCM WAV file of silence.

        NOTE: A WAV file is a RIFF container with fmt and data chunks. The
              44-byte header below is the canonical PCM WAV header. We
              write _MOCK_FRAMES frames of zero-valued samples so the file
              is unambiguously a real (if silent) WAV that any player or
              analysis tool can open.
        """
        sample_rate = self.sample_rate
        channels = self.channels
        bits_per_sample = self._BITS_PER_SAMPLE
        num_frames = self._MOCK_FRAMES
        # NOTE: data_size = frames * channels * bytes_per_sample.
        bytes_per_sample = bits_per_sample // 8
        data_size = num_frames * channels * bytes_per_sample
        # WHY: Each silent sample is all-zero bytes; b"\x00" * data_size
        #      gives the right length and represents digital silence.
        audio_data = b"\x00" * data_size

        # NOTE: Build the 44-byte header per the WAV/PCM spec. '<' means
        #       little-endian, which WAV requires.
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,        # ChunkSize = 36 + Subchunk2Size
            b"WAVE",
            b"fmt ",
            16,                    # Subchunk1Size for PCM
            1,                     # AudioFormat = 1 (PCM, no compression)
            channels,
            sample_rate,
            sample_rate * channels * bytes_per_sample,  # ByteRate
            channels * bytes_per_sample,                # BlockAlign
            bits_per_sample,
            b"data",
            data_size,
        )
        with open(path, "wb") as f:
            f.write(header)
            f.write(audio_data)

    def _record_hardware(self, duration_sec: float) -> None:
        """
        Hardware recording path using pyaudio. Opens a stream, reads
        chunks until the duration elapses or stop is requested, then
        writes a real WAV file.

        NOTE: This path is only reached when mock_mode is False and
              pyaudio was confirmed available in __init__. We still guard
              the import symbol defensively in case of runtime unload.
        """
        if not _PYAUDIO_AVAILABLE or pyaudio is None:
            # WHY: Defensive — __init__ should have caught this, but a
            #      clean error here beats a NoneType crash mid-thread.
            logger.error("SoundRecorder: pyaudio not available for hardware recording")
            return

        path = ""
        with self._lock:
            path = self._file_path
        if not path:
            return

        sample_rate = self.sample_rate
        channels = self.channels
        bits_per_sample = self._BITS_PER_SAMPLE
        bytes_per_sample = bits_per_sample // 8
        # NOTE: 1024 frames per chunk is a common, low-latency read size.
        chunk_frames = 1024
        chunk_bytes = chunk_frames * channels * bytes_per_sample

        frames: list[bytes] = []
        pa = None
        stream = None
        try:
            pa = pyaudio.PyAudio()  # type: ignore[union-attr]
            stream = pa.open(  # type: ignore[union-attr]
                format=pyaudio.paInt16,  # type: ignore[union-attr]
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_frames,
            )
            logger.info("SoundRecorder hardware stream opened -> %s", path)

            elapsed = 0.0
            # NOTE: Loop in chunk-sized steps so stop_recording() is
            #       responsive (checked each iteration via _was_stopped).
            while elapsed < duration_sec and not self._was_stopped():
                # WHY: Don't read past the requested duration — trim the
                #      final chunk so the clip length matches the ask.
                remaining = duration_sec - elapsed
                this_chunk = min(chunk_frames, int(sample_rate * remaining))
                if this_chunk <= 0:
                    break
                read_bytes = this_chunk * channels * bytes_per_sample
                data = stream.read(read_bytes, exception_on_overflow=False)
                frames.append(data)
                elapsed += this_chunk / sample_rate
        except Exception as e:
            logger.error("SoundRecorder hardware recording failed: %s", e)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if pa is not None:
                try:
                    pa.terminate()
                except Exception:
                    pass

        # NOTE: Always write whatever we captured, even on error/early stop,
        #       so stop_recording() returns a real file path.
        try:
            self._write_wav(path, frames, sample_rate, channels, bits_per_sample)
        except OSError as e:
            logger.error("SoundRecorder hardware write failed for %s: %s", path, e)

    def _write_wav(
        self,
        path: str,
        frames: list[bytes],
        sample_rate: int,
        channels: int,
        bits_per_sample: int,
    ) -> None:
        """Write a standard 16-bit PCM WAV file from captured frames."""
        audio_data = b"".join(frames)
        data_size = len(audio_data)
        bytes_per_sample = bits_per_sample // 8
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            channels,
            sample_rate,
            sample_rate * channels * bytes_per_sample,
            channels * bytes_per_sample,
            bits_per_sample,
            b"data",
            data_size,
        )
        with open(path, "wb") as f:
            f.write(header)
            f.write(audio_data)

    def _was_stopped(self) -> bool:
        """True if stop_recording() has been called for the current clip."""
        return self._stop_event.is_set()


# NOTE: __all__ documents the public API and keeps star-imports clean.
__all__ = ["SoundRecorder"]