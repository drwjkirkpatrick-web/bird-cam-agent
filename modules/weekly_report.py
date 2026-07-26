"""
modules/weekly_report.py — Weekly and monthly summary report generator.

NOTE: Generates week-long and month-long bird activity reports with species
      counts, diversity trends, rarity highlights, and comparison to prior periods.

WHY: Birdfy generates daily, weekly, and monthly activity summaries. These
     longer-period reports show trends that daily reports miss.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class WeeklyReport:
    """
    Generates weekly and monthly bird activity reports.

    Usage:
        report_gen = WeeklyReport()
        report = report_gen.generate_weekly(sightings, week_start="2026-07-20")
        text = report_gen.format_text(report)
    """

    def generate_weekly(
        self, sightings: list[BirdSighting], week_start: str | None = None
    ) -> dict[str, Any]:
        """Generate a weekly report."""
        if week_start is None:
            today = datetime.now(timezone.utc)
            week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

        start = datetime.fromisoformat(week_start + "T00:00:00+00:00")
        end = start + timedelta(days=7)

        week_sightings = [
            s for s in sightings
            if start.isoformat() <= s.timestamp < end.isoformat()
        ]

        return self._generate_report(week_sightings, "week", week_start)

    def generate_monthly(
        self, sightings: list[BirdSighting], year: int, month: int
    ) -> dict[str, Any]:
        """Generate a monthly report."""
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        month_sightings = [
            s for s in sightings
            if start.isoformat() <= s.timestamp < end.isoformat()
        ]

        period = f"{year}-{month:02d}"
        return self._generate_report(month_sightings, "month", period)

    def _generate_report(
        self, sightings: list[BirdSighting], period_type: str, period_label: str
    ) -> dict[str, Any]:
        """Generate report from a list of sightings."""
        species_counts: Counter = Counter()
        rarity_counts: Counter = Counter()
        daily_counts: dict[str, int] = defaultdict(int)

        for s in sightings:
            species_counts[s.species] += 1
            rarity_counts[s.rarity_level.value] += 1
            try:
                day = s.timestamp[:10]
                daily_counts[day] += 1
            except (ValueError, AttributeError):
                pass

        rare_highlights = [
            {"species": s.species, "rarity": s.rarity_level.value, "date": s.timestamp[:10]}
            for s in sightings
            if s.rarity_level >= RarityLevel.RARE
        ]

        return {
            "period_type": period_type,
            "period": period_label,
            "total_sightings": len(sightings),
            "unique_species": len(species_counts),
            "species_counts": dict(species_counts.most_common()),
            "rarity_breakdown": dict(rarity_counts),
            "daily_counts": dict(sorted(daily_counts.items())),
            "rare_highlights": rare_highlights,
            "most_active_day": max(daily_counts, key=lambda k: daily_counts[k]) if daily_counts else None,
            "most_common_species": species_counts.most_common(1)[0][0] if species_counts else None,
        }

    def format_text(self, report: dict[str, Any]) -> str:
        """Format a report as readable text."""
        period_type = report["period_type"].title()
        lines = [
            f"=== Bird Cam {period_type}ly Report — {report['period']} ===",
            "",
            f"Total sightings: {report['total_sightings']}",
            f"Unique species:   {report['unique_species']}",
        ]

        if report.get("most_common_species"):
            lines.append(f"Most common:      {report['most_common_species']}")
        if report.get("most_active_day"):
            lines.append(f"Most active day:  {report['most_active_day']}")

        if report["species_counts"]:
            lines.append("")
            lines.append("Species this period:")
            for species, count in list(report["species_counts"].items())[:15]:
                lines.append(f"  - {species}: {count}")

        if report["rare_highlights"]:
            lines.append("")
            lines.append("Rarity highlights:")
            for h in report["rare_highlights"]:
                lines.append(f"  * {h['species']} ({h['rarity']}) on {h['date']}")

        return "\n".join(lines)


__all__ = ["WeeklyReport"]
