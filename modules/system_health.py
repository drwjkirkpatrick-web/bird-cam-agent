"""
modules/system_health.py — Pi system health monitoring.

NOTE: Monitors CPU temperature, disk space, memory usage, and uptime.
      Alerts on critical conditions that could affect bird cam operation.

WHY: BirdNET-Pi includes system health monitoring. A Pi deployed outdoors
     can overheat, run out of disk space from photos, or run low on memory.
     This module watches for these conditions.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from typing import Any

logger = logging.getLogger(__name__)


class SystemHealthMonitor:
    """
    Monitors Raspberry Pi system health.

    Usage:
        monitor = SystemHealthMonitor()
        health = monitor.get_health()
        if health["cpu_temp_c"] > 80:
            print("Pi is overheating!")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.temp_warning = self.config.get("temp_warning_c", 75)
        self.temp_critical = self.config.get("temp_critical_c", 85)
        self.disk_warning_pct = self.config.get("disk_warning_pct", 80)
        self.disk_critical_pct = self.config.get("disk_critical_pct", 90)
        self.mem_warning_pct = self.config.get("mem_warning_pct", 80)
        self._start_time = time.time()
        self._mock_temp = 45.0
        self._mock_mode = self.config.get("mock_mode", False)

    def get_health(self) -> dict[str, Any]:
        """Get comprehensive system health status."""
        return {
            "cpu_temp_c": self.get_cpu_temp(),
            "disk_usage": self.get_disk_usage(),
            "memory_usage": self.get_memory_usage(),
            "uptime_seconds": round(time.time() - self._start_time, 0),
            "load_average": self.get_load_average(),
            "warnings": self.get_warnings(),
            "status": self.get_status(),
        }

    def get_cpu_temp(self) -> float:
        """Get CPU temperature in Celsius."""
        if self._mock_mode:
            self._mock_temp += (hash(time.time()) % 10 - 5) * 0.1
            return round(max(30, min(90, self._mock_temp)), 1)

        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                raw = f.read().strip()
                return round(int(raw) / 1000, 1)
        except (FileNotFoundError, PermissionError):
            # NOTE: Not on a Pi — try vcgencmd
            try:
                import subprocess
                result = subprocess.run(
                    ["vcgencmd", "measure_temp"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
                    return float(temp_str)
            except Exception:
                pass
            return self._mock_temp

    def get_disk_usage(self) -> dict[str, float]:
        """Get disk usage for the project partition."""
        try:
            usage = shutil.disk_usage("/")
            total = usage.total
            used = usage.used
            free = usage.free
            pct = (used / total) * 100 if total > 0 else 0
            return {
                "total_gb": round(total / (1024**3), 1),
                "used_gb": round(used / (1024**3), 1),
                "free_gb": round(free / (1024**3), 1),
                "used_pct": round(pct, 1),
            }
        except Exception:
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "used_pct": 0}

    def get_memory_usage(self) -> dict[str, float]:
        """Get memory usage."""
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemFree:", "MemAvailable:", "Buffers:", "Cached:"):
                    info[parts[0]] = int(parts[1]) * 1024  # Convert KB to bytes

            total = info.get("MemTotal:", 0)
            available = info.get("MemAvailable:", info.get("MemFree:", 0))
            used = total - available
            pct = (used / total) * 100 if total > 0 else 0

            return {
                "total_mb": round(total / (1024**2), 1),
                "used_mb": round(used / (1024**2), 1),
                "available_mb": round(available / (1024**2), 1),
                "used_pct": round(pct, 1),
            }
        except (FileNotFoundError, PermissionError):
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "used_pct": 0}

    def get_load_average(self) -> float:
        """Get 1-minute load average."""
        try:
            return os.getloadavg()[0]
        except (AttributeError, OSError):
            return 0.0

    def get_warnings(self) -> list[str]:
        """Get list of active system warnings."""
        warnings = []
        temp = self.get_cpu_temp()
        if temp >= self.temp_critical:
            warnings.append(f"CRITICAL: CPU temperature {temp}°C")
        elif temp >= self.temp_warning:
            warnings.append(f"WARNING: CPU temperature {temp}°C")

        disk = self.get_disk_usage()
        if disk["used_pct"] >= self.disk_critical_pct:
            warnings.append(f"CRITICAL: Disk usage {disk['used_pct']:.0f}%")
        elif disk["used_pct"] >= self.disk_warning_pct:
            warnings.append(f"WARNING: Disk usage {disk['used_pct']:.0f}%")

        mem = self.get_memory_usage()
        if mem["used_pct"] >= self.mem_warning_pct:
            warnings.append(f"WARNING: Memory usage {mem['used_pct']:.0f}%")

        return warnings

    def get_status(self) -> str:
        """Overall system status: healthy, warning, or critical."""
        warnings = self.get_warnings()
        if any("CRITICAL" in w for w in warnings):
            return "critical"
        elif warnings:
            return "warning"
        return "healthy"

    def get_summary(self) -> dict[str, Any]:
        """Get a compact summary for dashboard display."""
        return {
            "cpu_temp": self.get_cpu_temp(),
            "disk_pct": self.get_disk_usage()["used_pct"],
            "mem_pct": self.get_memory_usage()["used_pct"],
            "status": self.get_status(),
            "warnings": self.get_warnings(),
        }


__all__ = ["SystemHealthMonitor"]
