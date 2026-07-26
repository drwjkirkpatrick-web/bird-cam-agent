"""
modules/daily_report.py — Daily bird activity report generator.

NOTE: Generates a summary report of bird activity for a given day, including
      species seen, rarity highlights, activity patterns, and notable events.

WHY: A daily report gives the bird cam owner a digestible summary — "today
     you saw 12 species, including a rare Cooper's Hawk, with peak activity
     at 8 AM." Great for email delivery or dashboard display.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class DailyReport:
    """
    Generates daily bird activity reports.

    Usage:
        report_gen = DailyReport()
        report = report_gen.generate(sightings, date="2026-07-25")
        print(report_gen.format_text(report))
    """

    def generate(
        self, sightings: list[BirdSighting], date: str | None = None
    ) -> dict[str, Any]:
        """
        Generate a daily report from a list of sightings.

        Args:
            sightings: List of BirdSighting objects for the day
            date: Optional date string (YYYY-MM-DD). If None, uses today.

        Returns a report dict with:
            - date, total_sightings, unique_species, species_list
            - rarity_highlights, peak_activity_hour, new_species
            - most_common_species, notable_events
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Filter sightings to the given date
        day_sightings = [
            s for s in sightings
            if s.timestamp.startswith(date)
        ]

        # Species analysis
        species_counts: dict[str, int] = {}
        rarity_highlights: list[dict[str, str]] = []
        hourly_activity: dict[int, int] = {}

        for s in day_sightings:
            species_counts[s.species] = species_counts.get(s.species, 0) + 1

            if s.rarity_level >= RarityLevel.RARE:
                rarity_highlights.append({
                    "species": s.species,
                    "rarity": s.rarity_level.value,
                    "time": s.timestamp[:19],
                })

            try:
                dt = datetime.fromisoformat(s.timestamp.replace("Z", "+00:00"))
                hourly_activity[dt.hour] = hourly_activity.get(dt.hour, 0) + 1
            except (ValueError, AttributeError):
                pass

        # Most common species
        most_common = None
        if species_counts:
            most_common = max(species_counts, key=lambda k: species_counts[k])

        # Peak activity hour
        peak_hour = None
        if hourly_activity:
            peak_hour = max(hourly_activity, key=lambda k: hourly_activity[k])

        return {
            "date": date,
            "total_sightings": len(day_sightings),
            "unique_species": len(species_counts),
            "species_list": sorted(species_counts.keys()),
            "species_counts": species_counts,
            "rarity_highlights": rarity_highlights,
            "peak_activity_hour": peak_hour,
            "hourly_activity": dict(sorted(hourly_activity.items())),
            "most_common_species": most_common,
        }

    def format_text(self, report: dict[str, Any]) -> str:
        """Format a report as a human-readable text summary."""
        lines = [
            f"=== Bird Cam Daily Report — {report['date']} ===",
            "",
            f"Total sightings: {report['total_sightings']}",
            f"Unique species:   {report['unique_species']}",
        ]

        if report["most_common_species"]:
            lines.append(f"Most common:     {report['most_common_species']}")

        if report["peak_activity_hour"] is not None:
            lines.append(f"Peak activity:   {report['peak_activity_hour']:02d}:00")

        if report["species_list"]:
            lines.append("")
            lines.append("Species seen today:")
            for species in report["species_list"]:
                count = report["species_counts"].get(species, 0)
                lines.append(f"  - {species} ({count})")

        if report["rarity_highlights"]:
            lines.append("")
            lines.append("Rarity highlights:")
            for h in report["rarity_highlights"]:
                lines.append(f"  * {h['species']} ({h['rarity']}) at {h['time']}")

        if report["hourly_activity"]:
            lines.append("")
            lines.append("Hourly activity:")
            for hour, count in report["hourly_activity"].items():
                bar = "#" * count
                lines.append(f"  {hour:02d}:00 [{bar}] {count}")

        return "\n".join(lines)

    def format_html(self, report: dict[str, Any]) -> str:
        """Format a report as HTML for email or dashboard."""
        import html as html_mod

        rows = ""
        for species in report.get("species_list", []):
            count = report["species_counts"].get(species, 0)
            rows += f"<tr><td>{html_mod.escape(species)}</td><td>{count}</td></tr>"

        highlights = ""
        for h in report.get("rarity_highlights", []):
            highlights += f"<li><strong>{html_mod.escape(h['species'])}</strong> ({html_mod.escape(h['rarity'])}) at {h['time']}</li>"

        return f"""
        <html><body>
        <h2>Bird Cam Daily Report — {html_mod.escape(report['date'])}</h2>
        <p>Total sightings: {report['total_sightings']}<br>
           Unique species: {report['unique_species']}</p>
        <table border="1"><tr><th>Species</th><th>Count</th></tr>{rows}</table>
        {"<h3>Rarity Highlights</h3><ul>" + highlights + "</ul>" if highlights else ""}
        </body></html>
        """


__all__ = ["DailyReport"]