"""
modules/updater.py — Project self-update mechanism.

NOTE: Checks for and applies updates to the bird cam agent code. Supports
      git pull-based updates for the project repository.

WHY: Smart feeders like Birdfy receive OTA firmware updates. While a Pi-based
     system doesn't need firmware, the project code should be updateable
     without manual SSH intervention.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class ProjectUpdater:
    """
    Updates the bird cam agent project code.

    Usage:
        updater = ProjectUpdater({"project_dir": "/home/walker/projects/bird-cam-agent"})
        if updater.check_for_updates():
            updater.update()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.project_dir = self.config.get("project_dir", os.getcwd())
        self.mock_mode = self.config.get("mock_mode", True)
        self.git_identity = self.config.get("git_ssh_key", "~/.ssh/id_ed25519_hermes")

    def check_for_updates(self) -> dict[str, Any]:
        """Check if updates are available."""
        if self.mock_mode:
            return {"updates_available": False, "current_version": "0.1.0", "mock": True}

        try:
            # Fetch latest from remote
            env = dict(os.environ, GIT_SSH_COMMAND=f"ssh -i {self.git_identity}")
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=self.project_dir, capture_output=True, env=env, timeout=30
            )

            # Compare local vs remote
            local = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_dir, capture_output=True, text=True, timeout=10
            ).stdout.strip()

            remote = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                cwd=self.project_dir, capture_output=True, text=True, timeout=10
            ).stdout.strip()

            return {
                "updates_available": local != remote,
                "local_commit": local[:8],
                "remote_commit": remote[:8],
            }
        except Exception as e:
            logger.error("Update check failed: %s", e)
            return {"updates_available": False, "error": str(e)}

    def update(self) -> dict[str, Any]:
        """Apply updates via git pull."""
        if self.mock_mode:
            logger.info("[MOCK] Project update applied")
            return {"success": True, "mock": True}

        try:
            env = dict(os.environ, GIT_SSH_COMMAND=f"ssh -i {self.git_identity}")
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.project_dir, capture_output=True, text=True,
                env=env, timeout=60
            )
            if result.returncode == 0:
                logger.info("Project updated successfully")
                return {"success": True, "output": result.stdout[:500]}
            return {"success": False, "error": result.stderr[:500]}
        except Exception as e:
            logger.error("Update failed: %s", e)
            return {"success": False, "error": str(e)}

    def get_current_version(self) -> str:
        """Get the current project version."""
        if self.mock_mode:
            return "0.1.0"
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.project_dir, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def get_changelog(self, limit: int = 10) -> list[str]:
        """Get recent git commit messages."""
        if self.mock_mode:
            return ["Mock: initial release", "Mock: 20 modules added", "Mock: gap analysis complete"]
        try:
            result = subprocess.run(
                ["git", "log", f"--oneline", f"-{limit}"],
                cwd=self.project_dir, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip().split("\n")
        except Exception:
            return []


__all__ = ["ProjectUpdater"]
