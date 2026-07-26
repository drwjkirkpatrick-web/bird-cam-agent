"""
modules/sound_identifier.py — Bird sound identification via the Hermes bridge.

NOTE: This module connects the bird cam to Hermes Agent's audio analysis
      capabilities. It supports two modes:
      - live:  HTTP POST to a Hermes API server endpoint with the audio file
      - mock:  returns a canned result for development/testing

WHY: Birds are often heard before they are seen. Sound identification lets
     the agent detect species that are vocalizing out of frame or at night.
     The bridge routes the audio through Hermes so the identification
     benefits from Hermes's provider fallback chain and caching.

The prompt asks the LLM for JSON:
    {species, scientific_name, confidence, is_bird, description, alternative_species}

JSON parsing follows the same _extract_json pattern as hermes_bridge.py:
    1. try direct json.loads
    2. regex for ```json fences
    3. regex for the first {...} block
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)


class SoundIdentifier:
    """
    Identify bird species from audio recordings using the Hermes bridge.

    Usage:
        identifier = SoundIdentifier()  # mock mode by default
        result = identifier.identify_sound("data/audio/call_001.wav")
        if result["is_bird"]:
            print(f"Detected a {result['species']}!")
    """

    # NOTE: This prompt asks the audio model for structured JSON output.
    # The model should identify the bird species from its call or song.
    # If the audio doesn't contain a bird, is_bird=false.
    SOUND_ID_PROMPT = """You are an expert ornithologist specializing in bioacoustics. Analyze this audio recording and identify any bird species from its call, song, or vocalization.

Respond in JSON format ONLY:
{
  "species": "common name of the bird species",
  "scientific_name": "scientific/binomial name",
  "confidence": 0.0 to 1.0,
  "is_bird": true or false,
  "description": "brief description of the call/song and behavior",
  "alternative_species": ["possible alternative identifications"]
}

If no bird sound is present, set is_bird to false, species to "Unknown", and confidence to 0.0.
Be precise with species identification based on call characteristics (frequency, rhythm, tone).
Include the scientific name if possible."""

    def __init__(self, config: dict | None = None):
        """
        Initialize the sound identifier.

        Args:
            config: Optional dict with keys:
                - hermes_api_url: URL of the Hermes API server
                - mock_mode: if True, return canned results (default True)
                - confidence_threshold: minimum confidence to accept (default 0.5)
        """
        config = config or {}
        self.hermes_api_url: str = config.get(
            "hermes_api_url", "http://127.0.0.1:9119"
        )
        self.mock_mode: bool = config.get("mock_mode", True)
        self.confidence_threshold: float = config.get(
            "confidence_threshold", 0.5
        )

        # NOTE: Canned results cycle through 3 common North American
        #       songbirds for development and testing.
        self._mock_results: list[dict[str, Any]] = [
            {
                "species": "American Robin",
                "scientific_name": "Turdus migratorius",
                "confidence": 0.91,
                "is_bird": True,
                "description": (
                    "A series of clear whistled carols, often delivered "
                    "at dawn. Cheerily, cheer-up, cheerio pattern."
                ),
                "alternative_species": ["Western Robin"],
            },
            {
                "species": "Northern Cardinal",
                "scientific_name": "Cardinalis cardinalis",
                "confidence": 0.87,
                "is_bird": True,
                "description": (
                    "A clear, whistled 'what-cheer, what-cheer, what-cheer' "
                    "song with a metallic quality."
                ),
                "alternative_species": ["Scarlet Tanager"],
            },
            {
                "species": "Black-capped Chickadee",
                "scientific_name": "Poecile atricapillus",
                "confidence": 0.84,
                "is_bird": True,
                "description": (
                    "The familiar two-note 'fee-bee' whistle or the "
                    "chick-a-dee-dee-dee call."
                ),
                "alternative_species": ["Carolina Chickadee"],
            },
        ]
        self._mock_index = 0

        # History of recent identifications (most recent last)
        self._history: list[dict[str, Any]] = []
        self._max_history = 100

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def identify_sound(self, audio_path: str) -> dict[str, Any]:
        """
        Identify a bird from an audio recording.

        Returns a dict with keys:
            species, scientific_name, confidence, is_bird, description,
            alternative_species

        Never raises — always returns a valid dict. If the file is missing
        or identification fails, returns an "Unknown" non-bird result.
        """
        if not os.path.exists(audio_path):
            logger.warning("Audio file not found: %s — returning unknown", audio_path)
            result = self._unknown_result(
                f"Audio file not found: {audio_path}"
            )
            self._add_to_history(result)
            return result

        if self.mock_mode:
            result = self.mock_identify(audio_path)
        else:
            raw = self._call_api(audio_path)
            if raw is None:
                logger.error("No response from Hermes bridge — returning unknown")
                result = self._unknown_result(
                    "Hermes bridge returned no response"
                )
            else:
                result = self._parse_response(raw)

        self._add_to_history(result)
        return result

    def identify_batch(self, audio_paths: list[str]) -> list[dict[str, Any]]:
        """Identify birds in multiple audio files sequentially."""
        if not audio_paths:
            return []
        results: list[dict[str, Any]] = []
        for path in audio_paths:
            results.append(self.identify_sound(path))
        return results

    def identify_with_retry(
        self, audio_path: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Identify a sound with exponential backoff retry on failure.

        NOTE: "Failure" means the bridge returned an Unknown result with
              confidence 0.0 and no species — indicating a transport error
              rather than a legitimate non-bird detection. A genuine
              non-bird result (is_bird=False with a description) is NOT
              retried.
        """
        last_result: dict[str, Any] | None = None
        for attempt in range(max_retries):
            result = self.identify_sound(audio_path)
            last_result = result

            # Success: we got a bird OR a definitive non-bird
            if result["is_bird"]:
                return result
            if result["is_bird"] is False and result.get("description"):
                # Legitimate non-bird detection — don't retry
                return result

            # Transport failure — retry with backoff
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(
                    "Sound ID attempt %d failed, retrying in %ds",
                    attempt + 1,
                    wait,
                )
                # NOTE: In mock mode, backoff is skipped for speed
                if self.mock_mode:
                    continue
                time.sleep(wait)

        logger.error(
            "All %d sound ID attempts failed for %s",
            max_retries,
            audio_path,
        )
        return last_result or self._unknown_result(
            "All identification attempts failed"
        )

    def get_history(self) -> list[dict[str, Any]]:
        """Return recent identifications (most recent first)."""
        return list(reversed(self._history))

    def health_check(self) -> dict[str, Any]:
        """Check if the sound identifier / Hermes bridge is reachable."""
        if self.mock_mode:
            return {"healthy": True, "mode": "mock", "message": "Mock mode active"}

        try:
            import requests
        except ImportError:
            return {
                "healthy": False,
                "mode": "api",
                "error": "requests library not installed",
            }

        url = f"{self.hermes_api_url}/health"
        try:
            resp = requests.get(url, timeout=5)
            healthy = resp.status_code == 200
            return {
                "healthy": healthy,
                "mode": "api",
                "url": self.hermes_api_url,
                "status_code": resp.status_code,
            }
        except Exception as e:
            return {
                "healthy": False,
                "mode": "api",
                "url": self.hermes_api_url,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Prompt & parsing
    # ------------------------------------------------------------------

    def _build_prompt(self) -> str:
        """Return the bird sound identification prompt for the LLM."""
        return self.SOUND_ID_PROMPT

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """
        Parse the LLM response into a result dict.

        NOTE: Handles malformed JSON, missing fields, and non-bird
              detections gracefully. Never raises — always returns a
              valid dict with all expected keys.
        """
        json_str = self._extract_json(raw)
        if json_str is None:
            logger.warning("No JSON found in response, treating as text")
            return self._unknown_result(raw[:500])

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Malformed JSON in response: %s", e)
            return self._unknown_result(f"Malformed response: {raw[:200]}")

        if not isinstance(data, dict):
            return self._unknown_result("Response was not a JSON object")

        # NOTE: Build result with safe defaults
        species = str(data.get("species", "Unknown"))
        is_bird = bool(data.get("is_bird", False))
        confidence = float(data.get("confidence", 0.0) or 0.0)
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        alt_species = data.get("alternative_species", [])
        if not isinstance(alt_species, list):
            alt_species = []

        return {
            "species": species,
            "scientific_name": str(data.get("scientific_name", "")),
            "confidence": confidence,
            "is_bird": is_bird,
            "description": str(data.get("description", "")),
            "alternative_species": [str(s) for s in alt_species],
        }

    def _extract_json(self, text: str) -> str | None:
        """
        Extract a JSON object from a text response.

        Same approach as hermes_bridge.py:
          1. Try direct json.loads
          2. Look for ```json ... ``` code fences
          3. Find the first { ... } block
        """
        # Try direct parse first
        try:
            json.loads(text)
            return text.strip()
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find JSON in code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                json.loads(match.group(1).strip())
                return match.group(1).strip()
            except (json.JSONDecodeError, TypeError):
                pass

        # Try to find first { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                json.loads(match.group(0))
                return match.group(0)
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    # ------------------------------------------------------------------
    # Mock & helpers
    # ------------------------------------------------------------------

    def mock_identify(self, audio_path: str) -> dict[str, Any]:
        """Return a canned identification result for testing."""
        result = self._mock_results[self._mock_index % len(self._mock_results)]
        self._mock_index += 1
        # NOTE: Return a copy so callers can't mutate our mock data
        return {
            "species": result["species"],
            "scientific_name": result["scientific_name"],
            "confidence": result["confidence"],
            "is_bird": result["is_bird"],
            "description": result["description"],
            "alternative_species": list(result["alternative_species"]),
        }

    def _unknown_result(self, description: str = "") -> dict[str, Any]:
        """Build a default Unknown / non-bird result dict."""
        return {
            "species": "Unknown",
            "scientific_name": "",
            "confidence": 0.0,
            "is_bird": False,
            "description": description,
            "alternative_species": [],
        }

    def _add_to_history(self, result: dict[str, Any]) -> None:
        """Add a result to the in-memory history (capped at _max_history)."""
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    def _call_api(self, audio_path: str) -> str | None:
        """
        POST the audio file to the Hermes API server endpoint.

        NOTE: Uses the requests library. The Hermes API server runs on
              port 9119 by default. The /api/chat endpoint accepts an
              audio path + prompt.
        """
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed — cannot use API mode")
            return None

        url = f"{self.hermes_api_url}/api/chat"
        payload = {
            "prompt": self._build_prompt(),
            "audio_path": os.path.abspath(audio_path),
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            # NOTE: Hermes API returns {"response": "...", "success": true}
            return data.get("response", data.get("content", ""))
        except requests.exceptions.Timeout:
            logger.error("Hermes API request timed out")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Hermes API at %s", url)
            return None
        except Exception as e:
            logger.error("Hermes API error: %s", e)
            return None