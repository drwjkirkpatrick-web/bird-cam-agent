"""
main.py — Bird Cam Agent orchestrator.

NOTE: This is the main loop that ties all modules together. It captures
      photos, identifies birds via the Hermes vision bridge, checks rarity,
      sends SMS alerts for rare birds, and stores everything in SQLite.

WHY: The orchestrator is built directly (not delegated) because it needs
     exact constructor signatures and cross-module wiring. A single author
     prevents integration drift between modules built by different agents.

MOCK MODE: By default, everything runs in mock mode — no camera hardware,
           no real Hermes API calls, no real SMS. This lets you develop and
           test on any machine. Set mock_mode=False in the config when
           deploying to a real Pi with hardware.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

from core.config import Config
from core.types import BirdSighting, IdentificationResult, RarityLevel

logger = logging.getLogger(__name__)


class BirdCamAgent:
    """
    Main bird cam agent — orchestrates the full capture → identify → alert pipeline.

    Usage (mock mode):
        agent = BirdCamAgent()
        agent.run_single_capture()  # one cycle
        agent.stop()

    Usage (real deployment):
        agent = BirdCamAgent("config.yaml")
        agent.run()  # continuous loop
    """

    def __init__(self, config_path: str | None = None):
        # NOTE: Load config from YAML if provided, otherwise use defaults
        if config_path:
            self.config = Config.from_yaml(config_path)
        else:
            self.config = Config.create_default_config()

        self._running = False
        self._dashboard_thread: threading.Thread | None = None
        self._dashboard_app: Any = None

        # Initialize modules based on config
        self._init_modules()

        # Signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_modules(self) -> None:
        """Initialize all sub-modules based on configuration."""
        # NOTE: Import inside method to avoid circular imports at module level

        # Camera
        from modules.camera import CameraFactory

        self.camera = CameraFactory.create(self.config.camera)

        # Database
        from modules.database import SightingDatabase

        self.db = SightingDatabase(
            self.config.database.db_path,
            mock_mode=self.config.orchestrator.mock_mode,
        )

        # Hermes Bridge + Identifier
        from modules.hermes_bridge import HermesBridge
        from modules.identifier import BirdIdentifier

        self.bridge = HermesBridge(self.config.hermes_bridge)

        # Local classifier (optional — uses if model exists on disk)
        self.local_classifier = None
        if getattr(self.config, "local_classifier", None):
            from modules.local_bird_classifier import LocalBirdClassifier

            local_clf = LocalBirdClassifier(self.config.local_classifier)
            if local_clf.load():
                self.local_classifier = local_clf
            else:
                logger.info(
                    "Local classifier not available (run training first). "
                    "Falling back to Hermes bridge only."
                )

        # Local audio classifier (optional — uses if model exists on disk)
        self.local_audio_classifier = None
        if getattr(self.config, "local_audio_classifier", None):
            from modules.local_audio_classifier import LocalAudioClassifier

            local_audio_clf = LocalAudioClassifier(self.config.local_audio_classifier)
            if local_audio_clf.load():
                self.local_audio_classifier = local_audio_clf
                logger.info(
                    "Local audio classifier ready (%d species)",
                    len(local_audio_clf.get_supported_species()),
                )
            else:
                logger.info(
                    "Local audio classifier not available (run training first). "
                    "Falling back to Hermes bridge for audio ID."
                )

        self.identifier = BirdIdentifier(self.bridge, self.config, self.local_classifier)

        # Rarity Checker
        from modules.rarity_checker import RarityChecker

        self.rarity_checker = RarityChecker(self.config.rarity)

        # SMS Notifier
        from modules.sms_notifier import SMSNotifier

        self.notifier = SMSNotifier(self.config.sms)

        # Recorder (optional)
        self.recorder = None
        if self.config.orchestrator.recording_enabled:
            from modules.recorder import RecorderFactory

            self.recorder = RecorderFactory.create(self.config.camera)

        logger.info("Bird Cam Agent initialized (mock_mode=%s)", self.config.orchestrator.mock_mode)

    def run(self) -> None:
        """
        Start the main capture loop.

        Captures a photo every `capture_interval` seconds, identifies the
        bird, checks rarity, sends alerts if rare, and stores the sighting.
        Runs until stop() is called or SIGINT/SIGTERM is received.
        """
        self._running = True
        interval = self.config.orchestrator.capture_interval

        logger.info("Starting bird cam loop (interval=%.1fs)", interval)

        while self._running:
            try:
                self.run_single_capture()
            except Exception as e:
                logger.error("Capture cycle error: %s", e, exc_info=True)

            if self._running:
                # NOTE: In mock mode, use a shorter sleep for faster testing
                sleep_time = interval if not self.config.orchestrator.mock_mode else min(interval, 5.0)
                time.sleep(sleep_time)

        logger.info("Bird cam loop stopped")

    def run_single_capture(self) -> BirdSighting | None:
        """
        Execute one capture cycle: photo → identify → rarity → notify → store.

        Returns the BirdSighting if a bird was identified, None otherwise.
        """
        # Step 1: Capture photo
        photo_path = self.camera.capture_photo()
        logger.debug("Captured photo: %s", photo_path)

        if not self.config.orchestrator.identification_enabled:
            logger.info("Identification disabled — skipping")
            return None

        # Step 2: Identify bird via Hermes bridge
        result = self.identifier.identify(photo_path)

        if not result.is_bird:
            logger.debug("No bird detected in photo")
            return None

        # Step 3: Check rarity
        rarity = self.rarity_checker.check_rarity(
            result.species, result.scientific_name
        )
        logger.info(
            "Identified: %s (rarity=%s, confidence=%.0f%%)",
            result.species,
            rarity.value,
            result.confidence,
        )

        # Step 4: Create sighting record
        sighting = BirdSighting(
            species=result.species,
            scientific_name=result.scientific_name,
            confidence=result.confidence,
            photo_path=photo_path,
            rarity_level=rarity,
            location=self.config.rarity.location_name,
            is_bird=result.is_bird,
            alternative_species=result.alternative_species,
            notes=result.description,
        )

        # Step 5: Store in database
        try:
            self.db.store_sighting(sighting)
            logger.debug("Stored sighting in database")
        except Exception as e:
            logger.error("Failed to store sighting: %s", e)

        # Step 6: Notify if rare
        if (
            self.config.orchestrator.notification_enabled
            and self.rarity_checker.is_rare(result.species)
        ):
            try:
                sent = self.notifier.send_rare_bird_alert(sighting)
                if sent:
                    logger.info("Rare bird alert sent for %s", result.species)
            except Exception as e:
                logger.error("Failed to send alert: %s", e)

        # Step 7: Record video (optional)
        if self.recorder and self.config.orchestrator.recording_enabled:
            try:
                video_path = self.recorder.start_recording(
                    self.config.orchestrator.record_duration
                )
                logger.debug("Recording started: %s", video_path)
            except Exception as e:
                logger.error("Recording failed: %s", e)

        return sighting

    def start_dashboard(self) -> None:
        """Start the Flask dashboard in a background thread."""
        if not self.config.dashboard.enabled:
            logger.info("Dashboard disabled in config")
            return

        try:
            from modules.dashboard import create_app

            self._dashboard_app = create_app(self.db, self.config.dashboard)

            def run_dashboard():
                self._dashboard_app.run(
                    host=self.config.dashboard.host,
                    port=self.config.dashboard.port,
                    debug=False,
                    use_reloader=False,
                )

            self._dashboard_thread = threading.Thread(
                target=run_dashboard, daemon=True, name="dashboard"
            )
            self._dashboard_thread.start()
            logger.info(
                "Dashboard started at http://%s:%d",
                self.config.dashboard.host,
                self.config.dashboard.port,
            )
        except ImportError:
            logger.warning("Flask not installed — dashboard unavailable")
        except Exception as e:
            logger.error("Failed to start dashboard: %s", e)

    def stop(self) -> None:
        """Graceful shutdown — stop loop and clean up resources."""
        logger.info("Stopping Bird Cam Agent...")
        self._running = False

        if self.recorder:
            try:
                self.recorder.stop_recording()
            except Exception:
                pass

        if self.db:
            try:
                self.db.close()
            except Exception:
                pass

        logger.info("Bird Cam Agent stopped")

    def _signal_handler(self, signum, frame) -> None:
        """Handle SIGINT/SIGTERM for clean shutdown."""
        logger.info("Received signal %d — shutting down", signum)
        self._running = False

    def get_stats(self) -> dict[str, Any]:
        """Get sighting statistics from the database."""
        return self.db.get_stats()

    def list_sightings(self, limit: int = 50) -> list[BirdSighting]:
        """List recent sightings."""
        return self.db.list_sightings(limit=limit)

    def health_check(self) -> dict[str, Any]:
        """Check health of all subsystems."""
        local_clf_info: dict[str, Any] = {"ready": False}
        if self.local_classifier is not None:
            local_clf_info = {
                "ready": self.local_classifier.is_ready(),
                "species_count": len(self.local_classifier.get_supported_species()),
            }

        local_audio_clf_info: dict[str, Any] = {"ready": False}
        if self.local_audio_classifier is not None:
            local_audio_clf_info = {
                "ready": self.local_audio_classifier.is_ready(),
                "species_count": len(self.local_audio_classifier.get_supported_species()),
            }

        return {
            "camera": self.camera.get_camera_info(),
            "hermes_bridge": self.bridge.health_check(),
            "local_classifier": local_clf_info,
            "local_audio_classifier": local_audio_clf_info,
            "database": {"healthy": True, "path": self.config.database.db_path},
            "rarity_checker": {
                "species_count": self.rarity_checker.species_count,
                "location": self.rarity_checker.location_name,
            },
            "sms_sent_count": self.notifier.sent_count,
        }


def main():
    """Entry point for running the agent directly."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    agent = BirdCamAgent(config_path)

    # Start dashboard if enabled
    agent.start_dashboard()

    # Run the main loop
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()