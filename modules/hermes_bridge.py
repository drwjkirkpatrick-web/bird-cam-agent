"""
modules/hermes_bridge.py — Bridge to Hermes Agent for vision-based bird ID.

NOTE: This module connects the bird cam to Hermes Agent's vision capabilities.
      It supports three modes:
      - "api":  HTTP POST to a Hermes API server endpoint
      - "cli":  subprocess call to `hermes chat -q` with the image
      - "mock": returns a canned result for development/testing

WHY: The Hermes Agent has built-in vision tool support (vision_analyze).
     Rather than calling a raw vision API, we route through Hermes so the
     identification benefits from Hermes's provider fallback chain,
     temperature normalization, and caching. The bridge translates
     between Hermes's response format and our IdentificationResult type.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from typing import Any

from core.config import HermesBridgeConfig
from core.types import IdentificationResult

logger = logging.getLogger(__name__)


class HermesBridge:
    """
    Bridge to Hermes Agent for bird identification via vision LLM.

    Usage:
        bridge = HermesBridge(config)
        result = bridge.identify_bird("data/photos/bird_001.jpg")
        if result.is_bird:
            print(f"Found a {result.species}!")
    """

    # NOTE: This prompt asks the vision model for structured JSON output.
    # The model should identify the bird species, scientific name, and
    # key attributes. If the image doesn't contain a bird, is_bird=false.
    BIRD_ID_PROMPT = """You are an expert ornithologist. Analyze this image and identify any bird visible.

Respond in JSON format ONLY:
{
  "species": "common name of the bird species",
  "scientific_name": "scientific/binomial name",
  "confidence": 0.0 to 1.0,
  "is_bird": true or false,
  "attributes": {
    "color": "dominant colors",
    "size": "small/medium/large",
    "beak_shape": "description",
    "habitat": "likely habitat"
  },
  "description": "brief description of the bird and its behavior",
  "alternative_species": ["possible alternative identifications"]
}

If no bird is visible, set is_bird to false, species to "Unknown", and confidence to 0.0.
Be precise with species identification. Include the scientific name if possible."""

    def __init__(self, config: HermesBridgeConfig):
        self.config = config
        self._mock_results = [
            IdentificationResult(
                species="American Robin",
                scientific_name="Turdus migratorius",
                confidence=0.92,
                is_bird=True,
                attributes={
                    "color": "gray-brown back, orange breast",
                    "size": "medium",
                    "beak_shape": "straight, yellow",
                    "habitat": "gardens, lawns",
                },
                description="A medium-sized songbird with an orange breast, commonly found foraging on the ground.",
                alternative_species=["European Robin"],
            ),
            IdentificationResult(
                species="Northern Cardinal",
                scientific_name="Cardinalis cardinalis",
                confidence=0.88,
                is_bird=True,
                attributes={
                    "color": "bright red, black mask",
                    "size": "medium",
                    "beak_shape": "thick, conical, orange",
                    "habitat": "woodland edges, gardens",
                },
                description="A bright red songbird with a distinctive crest and black face mask.",
                alternative_species=["Scarlet Tanager"],
            ),
            IdentificationResult(
                species="Black-capped Chickadee",
                scientific_name="Poecile atricapillus",
                confidence=0.85,
                is_bird=True,
                attributes={
                    "color": "black cap, white cheeks, gray-brown",
                    "size": "small",
                    "beak_shape": "short, thick",
                    "habitat": "deciduous forests, feeders",
                },
                description="A small songbird with a black cap and bib, white cheeks, visiting a bird feeder.",
                alternative_species=["Carolina Chickadee"],
            ),
        ]
        self._mock_index = 0

    def identify_bird(self, photo_path: str) -> IdentificationResult:
        """
        Identify a bird in a photo using the Hermes vision bridge.

        Returns an IdentificationResult. If the image doesn't contain a
        bird, is_bird will be False and species will be "Unknown".
        """
        if not os.path.exists(photo_path):
            logger.warning("Photo not found: %s — returning unknown", photo_path)
            return IdentificationResult(
                species="Unknown",
                is_bird=False,
                description=f"Photo file not found: {photo_path}",
            )

        mode = self.config.mode if not self.config.mock_mode else "mock"

        if mode == "mock":
            return self.mock_identify(photo_path)
        elif mode == "api":
            raw = self._call_api(photo_path)
        elif mode == "cli":
            raw = self._call_cli(photo_path)
        else:
            logger.error("Unknown bridge mode: %s — falling back to mock", mode)
            return self.mock_identify(photo_path)

        if raw is None:
            logger.error("No response from Hermes bridge — returning unknown")
            return IdentificationResult(
                species="Unknown",
                is_bird=False,
                description="Hermes bridge returned no response",
            )

        return self._parse_response(raw)

    def _build_prompt(self) -> str:
        """Return the bird identification prompt for the vision model."""
        return self.BIRD_ID_PROMPT

    def _parse_response(self, raw: str) -> IdentificationResult:
        """
        Parse the LLM response into an IdentificationResult.

        NOTE: Handles malformed JSON, missing fields, and non-bird detections
              gracefully. Never raises — always returns a valid result.
        """
        # NOTE: The vision model may wrap JSON in markdown code fences
        # or add prose. Extract the JSON block first.
        json_str = self._extract_json(raw)
        if json_str is None:
            logger.warning("No JSON found in response, treating as text")
            return IdentificationResult(
                species="Unknown",
                is_bird=False,
                description=raw[:500],
                confidence=0.0,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Malformed JSON in response: %s", e)
            return IdentificationResult(
                species="Unknown",
                is_bird=False,
                description=f"Malformed response: {raw[:200]}",
                confidence=0.0,
            )

        # NOTE: Build IdentificationResult with safe defaults
        species = str(data.get("species", "Unknown"))
        is_bird = bool(data.get("is_bird", False))
        confidence = float(data.get("confidence", 0.0) or 0.0)

        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        attributes = data.get("attributes", {})
        if not isinstance(attributes, dict):
            attributes = {}

        alt_species = data.get("alternative_species", [])
        if not isinstance(alt_species, list):
            alt_species = []

        return IdentificationResult(
            species=species,
            scientific_name=str(data.get("scientific_name", "")),
            confidence=confidence,
            is_bird=is_bird,
            attributes=attributes,
            description=str(data.get("description", "")),
            alternative_species=[str(s) for s in alt_species],
        )

    def _extract_json(self, text: str) -> str | None:
        """Extract a JSON object from a text response."""
        # Try direct parse first
        try:
            json.loads(text)
            return text.strip()
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find JSON in code fences
        import re

        # ```json ... ``` pattern
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

    def _call_api(self, photo_path: str) -> str | None:
        """
        POST the photo to the Hermes API server endpoint.

        NOTE: Uses the requests library. The Hermes API server runs on
              port 9119 by default. The /api/chat endpoint accepts
              an image path + prompt.
        """
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed — cannot use API mode")
            return None

        url = f"{self.config.api_url}/api/chat"
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "prompt": self._build_prompt(),
            "image_path": os.path.abspath(photo_path),
            "model": self.config.model or None,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            # NOTE: Hermes API returns {"response": "...", "success": true}
            return data.get("response", data.get("content", ""))
        except requests.exceptions.Timeout:
            logger.error("Hermes API request timed out after %ds", self.config.timeout)
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Hermes API at %s", url)
            return None
        except Exception as e:
            logger.error("Hermes API error: %s", e)
            return None

    def _call_cli(self, photo_path: str) -> str | None:
        """
        Call `hermes chat -q` as a subprocess with the image.

        NOTE: This uses the Hermes CLI's single-query mode. The image
              path is included in the prompt so the vision tool picks it up.
        """
        abs_path = os.path.abspath(photo_path)
        prompt = f"{self._build_prompt()}\n\nImage: {abs_path}"

        cmd = ["hermes", "chat", "-q", prompt]
        if self.config.model:
            cmd.extend(["-m", self.config.model])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
            )
            if result.returncode != 0:
                logger.error(
                    "Hermes CLI exited with code %d: %s",
                    result.returncode,
                    result.stderr[:200],
                )
                return None
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error("Hermes CLI timed out after %ds", self.config.timeout)
            return None
        except FileNotFoundError:
            logger.error("hermes CLI not found — is Hermes Agent installed?")
            return None
        except Exception as e:
            logger.error("Hermes CLI error: %s", e)
            return None

    def mock_identify(self, photo_path: str) -> IdentificationResult:
        """Return a canned identification result for testing."""
        result = self._mock_results[self._mock_index % len(self._mock_results)]
        self._mock_index += 1
        # NOTE: Return a copy so callers can't mutate our mock data
        return IdentificationResult(
            species=result.species,
            scientific_name=result.scientific_name,
            confidence=result.confidence,
            is_bird=result.is_bird,
            attributes=dict(result.attributes),
            description=result.description,
            alternative_species=list(result.alternative_species),
        )

    def health_check(self) -> dict[str, Any]:
        """Check if the Hermes bridge is reachable."""
        mode = self.config.mode if not self.config.mock_mode else "mock"

        if mode == "mock":
            return {"healthy": True, "mode": "mock", "message": "Mock mode active"}
        elif mode == "api":
            try:
                import requests

                url = f"{self.config.api_url}/health"
                resp = requests.get(url, timeout=5)
                healthy = resp.status_code == 200
                return {
                    "healthy": healthy,
                    "mode": "api",
                    "url": self.config.api_url,
                    "status_code": resp.status_code,
                }
            except Exception as e:
                return {
                    "healthy": False,
                    "mode": "api",
                    "error": str(e),
                }
        elif mode == "cli":
            try:
                result = subprocess.run(
                    ["hermes", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                healthy = result.returncode == 0
                return {
                    "healthy": healthy,
                    "mode": "cli",
                    "version": result.stdout.strip(),
                }
            except Exception as e:
                return {
                    "healthy": False,
                    "mode": "cli",
                    "error": str(e),
                }
        return {"healthy": False, "mode": mode, "error": "Unknown mode"}