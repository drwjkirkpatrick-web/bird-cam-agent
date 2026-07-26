"""
modules/camera_advisor.py — Camera comparison and recommendation system.

NOTE: This module helps users choose the right camera for their bird cam
      setup. It provides detailed comparisons of camera types that work
      with Raspberry Pi, including pros, cons, cost, resolution, and
      specific use-case recommendations.

WHY: The bird cam supports multiple camera types (Pi Camera, USB webcam,
     DSLR, ESP32-CAM). Users need guidance on which to choose based on
     their budget, Pi model, and deployment scenario.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


CAMERA_OPTIONS: list[dict[str, Any]] = [
    {
        "name": "Raspberry Pi Camera Module 3",
        "type": "picamera",
        "price_usd": 35,
        "resolution": "11.9 MP (4056x3040)",
        "fov": "66-102 degrees (adjustable)",
        "auto_focus": True,
        "hdr": True,
        "night_vision": False,
        "pros": [
            "Best image quality for the price",
            "Auto-focus with manual override",
            "HDR support for high-contrast scenes",
            "Low latency CSI-2 connection",
            "Compact and weatherproofable",
            "Wide adjustable FOV — covers feeder area",
        ],
        "cons": [
            "Requires Pi with CSI connector (Pi 4, Pi 5, Zero with adapter)",
            "No IR night vision (get the NoIR version for that)",
            "15cm ribbon cable limits placement",
            "Needs ribbon cable extension for distance",
        ],
        "best_for": "Primary recommendation for most users. Best quality-to-price ratio.",
        "pi_compatibility": ["Pi 4", "Pi 5", "Pi Zero 2 W (with adapter)"],
    },
    {
        "name": "Raspberry Pi Camera Module 2",
        "type": "picamera",
        "price_usd": 25,
        "resolution": "8 MP (3280x2464)",
        "fov": "62 degrees (fixed)",
        "auto_focus": False,
        "hdr": False,
        "night_vision": False,
        "pros": [
            "Very affordable",
            "Well-supported, stable drivers",
            "Good enough quality for bird ID",
            "Fixed focus — no focus drift",
            "Low power consumption",
        ],
        "cons": [
            "Fixed focus (can't adjust for different feeder distances)",
            "No HDR (backlit birds at feeder may be over/underexposed)",
            "Lower resolution than Module 3",
            "62-degree FOV may be too narrow for some setups",
        ],
        "best_for": "Budget option. Good if the feeder is at a fixed distance and lighting is consistent.",
        "pi_compatibility": ["Pi 3", "Pi 4", "Pi 5", "Pi Zero 2 W (with adapter)"],
    },
    {
        "name": "Raspberry Pi NoIR Camera Module 2",
        "type": "picamera",
        "price_usd": 30,
        "resolution": "8 MP (3280x2464)",
        "fov": "62 degrees (fixed)",
        "auto_focus": False,
        "hdr": False,
        "night_vision": True,
        "pros": [
            "No IR filter — sees in near-darkness with IR illuminator",
            "Same image quality as Module 2 in daylight",
            "Works with inexpensive IR LED arrays for night vision",
            "Great for nocturnal bird activity (owls, nightjars)",
        ],
        "cons": [
            "Daytime colors are slightly off (no IR filter means pinkish hues)",
            "Needs separate IR LED illuminator for night use",
            "Fixed focus",
            "IR illuminator adds cost and power draw",
        ],
        "best_for": "Night bird monitoring. Pair with IR LED array for 24/7 coverage.",
        "pi_compatibility": ["Pi 3", "Pi 4", "Pi 5", "Pi Zero 2 W (with adapter)"],
    },
    {
        "name": "Logitech C920 USB Webcam",
        "type": "usb",
        "price_usd": 70,
        "resolution": "1080p (1920x1080)",
        "fov": "78 degrees",
        "auto_focus": True,
        "hdr": False,
        "night_vision": False,
        "pros": [
            "Plug-and-play on any Pi with USB",
            "Auto-focus works well for variable feeder distances",
            "Built-in H.264 encoding (reduces Pi CPU load)",
            "Long USB cable allows flexible placement",
            "Works on Pi models without CSI connector",
        ],
        "cons": [
            "More expensive than Pi Camera modules",
            "Lower image quality than Pi Camera Module 3",
            "USB bandwidth limits frame rate on Pi Zero",
            "Higher power consumption than CSI cameras",
            "78-degree FOV is decent but not adjustable",
        ],
        "best_for": "Easy setup, flexible placement. Best when you can't use a CSI camera.",
        "pi_compatibility": ["Pi 3", "Pi 4", "Pi 5", "Pi Zero 2 W (slower)"],
    },
    {
        "name": "Logitech C270 USB Webcam",
        "type": "usb",
        "price_usd": 30,
        "resolution": "720p (1280x720)",
        "fov": "55 degrees",
        "auto_focus": False,
        "hdr": False,
        "night_vision": False,
        "pros": [
            "Very affordable USB option",
            "Plug-and-play, no drivers needed",
            "Low power consumption",
            "Good enough for basic bird ID at close range",
        ],
        "cons": [
            "Lower resolution (720p)",
            "Fixed focus (may need manual adjustment)",
            "Narrow 55-degree FOV",
            "No HDR",
            "Lower quality than Pi Camera at similar price",
        ],
        "best_for": "Budget USB option. Good for close-range feeder with consistent lighting.",
        "pi_compatibility": ["Pi 3", "Pi 4", "Pi 5", "Pi Zero 2 W"],
    },
    {
        "name": "ESP32-CAM",
        "type": "esp32",
        "price_usd": 10,
        "resolution": "2 MP (1600x1200)",
        "fov": "65 degrees",
        "auto_focus": False,
        "hdr": False,
        "night_vision": False,
        "pros": [
            "Extremely cheap ($6-10)",
            "WiFi built-in — can be placed anywhere in WiFi range",
            "Very low power (can run on battery/solar)",
            "Tiny form factor",
            "No Pi needed — standalone with WiFi streaming",
        ],
        "cons": [
            "Low image quality (2MP, noisy in low light)",
            "Fixed focus, no auto-focus",
            "Limited frame rate (1-5 fps for JPEG)",
            "Requires WiFi (not suitable for remote/offline sites)",
            "Less reliable than Pi Camera (thermal issues in hot weather)",
            "No night vision option",
        ],
        "best_for": "Ultra-budget remote feeder monitoring over WiFi. Great for a second angle.",
        "pi_compatibility": ["Standalone (WiFi connected to Pi's network)"],
    },
    {
        "name": "Waveshare IMX519 Auto-Focus Camera",
        "type": "picamera",
        "price_usd": 40,
        "resolution": "16 MP (4656x3496)",
        "fov": "80 degrees",
        "auto_focus": True,
        "hdr": False,
        "night_vision": False,
        "pros": [
            "Higher resolution than Pi Camera Module 3",
            "Auto-focus with fast VCM motor",
            "Wide 80-degree FOV",
            "Compatible with libcamera on Pi 4/5",
        ],
        "cons": [
            "Third-party (not official Raspberry Pi)",
            "No HDR",
            "Less community support than official modules",
            "Auto-focus motor draws extra power",
        ],
        "best_for": "High-resolution bird photography. Best image quality if HDR isn't needed.",
        "pi_compatibility": ["Pi 4", "Pi 5"],
    },
    {
        "name": "DSLR via gPhoto2 (Canon/Nikon)",
        "type": "dslr",
        "price_usd": 400,
        "resolution": "24+ MP",
        "fov": "Depends on lens",
        "auto_focus": True,
        "hdr": True,
        "night_vision": False,
        "pros": [
            "Professional image quality",
            "Interchangeable lenses (telephoto for distant feeders)",
            "Excellent low-light performance",
            "Full manual control over exposure",
            "Best for high-quality bird photography",
        ],
        "cons": [
            "Expensive (camera + lens)",
            "High power consumption (needs external power or frequent battery changes)",
            "Mechanical shutter wear with frequent captures",
            "Complex setup (gPhoto2 + USB + power)",
            "Bulky — not weatherproofable like Pi Camera",
            "Slow capture-to-ready time compared to Pi Camera",
        ],
        "best_for": "Serious bird photographers who want publication-quality images.",
        "pi_compatibility": ["Pi 4", "Pi 5 (USB to DSLR)"],
    },
    {
        "name": "Arducam 16MP IMX519 with IR-cut NoIR",
        "type": "picamera",
        "price_usd": 45,
        "resolution": "16 MP (4656x3496)",
        "fov": "80 degrees",
        "auto_focus": True,
        "hdr": False,
        "night_vision": True,
        "pros": [
            "High resolution + night vision in one camera",
            "Auto-focus",
            "Removable IR filter for day/night switching",
        ],
        "cons": [
            "Third-party, less community support",
            "IR filter swap is manual (not electronic)",
            "More expensive than Pi Camera NoIR",
        ],
        "best_for": "24/7 monitoring with high resolution. Day and night coverage.",
        "pi_compatibility": ["Pi 4", "Pi 5"],
    },
]


class CameraAdvisor:
    """
    Recommends cameras based on user requirements.

    Usage:
        advisor = CameraAdvisor()
        results = advisor.recommend(budget=50, pi_model="Pi 4", night_vision=False)
        for r in results:
            print(f"{r['name']}: {r['recommendation_reason']}")
    """

    def __init__(self):
        self.options = list(CAMERA_OPTIONS)

    def recommend(
        self,
        budget: float | None = None,
        pi_model: str | None = None,
        night_vision: bool = False,
        auto_focus_required: bool = False,
        min_resolution_mp: float | None = None,
        min_fov_degrees: float | None = None,
        camera_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Recommend cameras matching the given criteria.

        Returns a list of camera options sorted by best match, each with
        a 'recommendation_reason' field explaining why it was selected.
        """
        results = []

        for cam in self.options:
            reasons = []

            # Budget filter
            if budget is not None and cam["price_usd"] > budget:
                continue
            if budget is not None:
                reasons.append(f"within budget (${cam['price_usd']})")

            # Pi compatibility filter
            if pi_model:
                compatible = pi_model in cam.get("pi_compatibility", [])
                if not compatible:
                    continue
                reasons.append(f"compatible with {pi_model}")

            # Night vision filter
            if night_vision and not cam.get("night_vision", False):
                continue
            if night_vision:
                reasons.append("supports night vision")

            # Auto-focus filter
            if auto_focus_required and not cam.get("auto_focus", False):
                continue
            if auto_focus_required:
                reasons.append("has auto-focus")

            # Resolution filter
            if min_resolution_mp is not None:
                res_str = cam.get("resolution", "0 MP")
                mp = self._extract_mp(res_str)
                if mp < min_resolution_mp:
                    continue
                reasons.append(f"{mp:.0f}MP resolution")

            # FOV filter
            if min_fov_degrees is not None:
                fov = self._extract_fov(cam.get("fov", "0 degrees"))
                if fov < min_fov_degrees:
                    continue
                reasons.append(f"{fov:.0f}° FOV")

            # Camera type filter
            if camera_type and cam.get("type") != camera_type:
                continue

            cam_copy = dict(cam)
            cam_copy["recommendation_reason"] = "; ".join(reasons) if reasons else "matches criteria"
            results.append(cam_copy)

        # Sort by price (cheapest first) then by resolution (highest first)
        results.sort(key=lambda c: (c["price_usd"], -self._extract_mp(c.get("resolution", "0 MP"))))

        return results

    def get_camera(self, name: str) -> dict[str, Any] | None:
        """Get details for a specific camera by name."""
        for cam in self.options:
            if name.lower() in cam["name"].lower():
                return dict(cam)
        return None

    def list_all(self) -> list[dict[str, Any]]:
        """List all camera options."""
        return [dict(c) for c in self.options]

    def get_by_type(self, camera_type: str) -> list[dict[str, Any]]:
        """Filter cameras by type (picamera, usb, esp32, dslr)."""
        return [dict(c) for c in self.options if c.get("type") == camera_type]

    def compare(self, name1: str, name2: str) -> dict[str, Any]:
        """Compare two cameras side by side."""
        cam1 = self.get_camera(name1)
        cam2 = self.get_camera(name2)
        if not cam1 or not cam2:
            return {"error": "One or both cameras not found"}

        return {
            "camera_1": cam1,
            "camera_2": cam2,
            "price_difference": cam2["price_usd"] - cam1["price_usd"],
            "resolution_comparison": self._compare_resolution(cam1, cam2),
            "winner": self._determine_winner(cam1, cam2),
        }

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all camera options."""
        return {
            "total_options": len(self.options),
            "price_range": {
                "min": min(c["price_usd"] for c in self.options),
                "max": max(c["price_usd"] for c in self.options),
            },
            "types": list(set(c["type"] for c in self.options)),
            "night_vision_options": [c["name"] for c in self.options if c.get("night_vision")],
            "auto_focus_options": [c["name"] for c in self.options if c.get("auto_focus")],
        }

    def _extract_mp(self, res_str: str) -> float:
        """Extract megapixel count from resolution string."""
        import re

        match = re.search(r"(\d+\.?\d*)\s*MP", res_str)
        if match:
            return float(match.group(1))
        match = re.search(r"(\d+)p", res_str)
        if match:
            # 1080p ≈ 2MP, 720p ≈ 1MP
            p = int(match.group(1))
            return p / 540
        return 0.0

    def _extract_fov(self, fov_str: str) -> float:
        """Extract FOV degrees from string."""
        import re

        match = re.search(r"(\d+\.?\d*)\s*degree", fov_str, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 0.0

    def _compare_resolution(self, cam1: dict, cam2: dict) -> str:
        """Compare resolution of two cameras."""
        mp1 = self._extract_mp(cam1.get("resolution", "0 MP"))
        mp2 = self._extract_mp(cam2.get("resolution", "0 MP"))
        if mp1 > mp2:
            return f"{cam1['name']} has higher resolution ({mp1:.0f}MP vs {mp2:.0f}MP)"
        elif mp2 > mp1:
            return f"{cam2['name']} has higher resolution ({mp2:.0f}MP vs {mp1:.0f}MP)"
        return "Both have similar resolution"

    def _determine_winner(self, cam1: dict, cam2: dict) -> str:
        """Determine which camera is the better overall value."""
        mp1 = self._extract_mp(cam1.get("resolution", "0 MP"))
        mp2 = self._extract_mp(cam2.get("resolution", "0 MP"))

        # Score: resolution per dollar
        score1 = mp1 / max(cam1["price_usd"], 1)
        score2 = mp2 / max(cam2["price_usd"], 1)

        if score1 > score2:
            return cam1["name"]
        return cam2["name"]


__all__ = ["CameraAdvisor", "CAMERA_OPTIONS"]