"""
modules/export_csv.py — CSV/JSON data export for bird sightings.

NOTE: Exports sighting data to CSV and JSON formats for analysis in
      spreadsheets, eBird, or other birding platforms.

WHY: Birders want to export their sightings for eBird submissions, personal
     records, or data analysis. This module provides structured export
     with multiple format options.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Exports bird sighting data to various formats.

    Usage:
        exporter = DataExporter()
        exporter.export_csv(sightings, "sightings.csv")
        exporter.export_json(sightings, "sightings.json")
        exporter.export_ebird(sightings, "ebird_import.csv")
    """

    # NOTE: eBird CSV import format — specific column names required
    EBIRD_HEADERS = [
        "Species Name",
        "Date",
        "Time",
        "Count",
        "Location",
        "Latitude",
        "Longitude",
        "Protocol",
        "Duration (Min)",
        "All Observed",
        "Comments",
    ]

    CSV_HEADERS = [
        "sighting_id",
        "species",
        "scientific_name",
        "confidence",
        "photo_path",
        "timestamp",
        "rarity_level",
        "notes",
        "location",
        "is_bird",
        "alternative_species",
    ]

    def export_csv(
        self, sightings: list[BirdSighting], output_path: str
    ) -> str:
        """Export sightings to a CSV file."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
            writer.writeheader()
            for s in sightings:
                row = s.to_dict()
                # NOTE: alternative_species is a list — join for CSV
                row["alternative_species"] = ", ".join(row.get("alternative_species", []))
                writer.writerow(row)

        logger.info("Exported %d sightings to CSV: %s", len(sightings), output_path)
        return output_path

    def export_json(
        self, sightings: list[BirdSighting], output_path: str
    ) -> str:
        """Export sightings to a JSON file."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        data = [s.to_dict() for s in sightings]
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Exported %d sightings to JSON: %s", len(sightings), output_path)
        return output_path

    def export_ebird(
        self, sightings: list[BirdSighting], output_path: str
    ) -> str:
        """
        Export in eBird CSV import format.

        NOTE: eBird requires specific column headers and date/time format.
              Count defaults to 1 (single bird). Adjust as needed before
              submitting to eBird.
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.EBIRD_HEADERS)
            writer.writeheader()

            for s in sightings:
                try:
                    dt = datetime.fromisoformat(s.timestamp.replace("Z", "+00:00"))
                    date_str = dt.strftime("%m/%d/%Y")
                    time_str = dt.strftime("%I:%M %p")
                except (ValueError, AttributeError):
                    date_str = ""
                    time_str = ""

                writer.writerow({
                    "Species Name": s.species,
                    "Date": date_str,
                    "Time": time_str,
                    "Count": 1,
                    "Location": s.location or "Bird Cam",
                    "Latitude": "",
                    "Longitude": "",
                    "Protocol": "Casual",
                    "Duration (Min)": "",
                    "All Observed": "No",
                    "Comments": f"Auto-identified by Bird Cam (confidence: {s.confidence:.0%}). {s.notes}",
                })

        logger.info("Exported %d sightings to eBird format: %s", len(sightings), output_path)
        return output_path

    def export_summary(
        self, sightings: list[BirdSighting], output_path: str
    ) -> str:
        """Export a summary report as JSON."""
        species_counts: dict[str, int] = {}
        rarity_counts: dict[str, int] = {}

        for s in sightings:
            species_counts[s.species] = species_counts.get(s.species, 0) + 1
            rarity = s.rarity_level.value
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1

        summary = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_sightings": len(sightings),
            "unique_species": len(species_counts),
            "species_counts": dict(sorted(species_counts.items())),
            "rarity_breakdown": rarity_counts,
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info("Exported summary to: %s", output_path)
        return output_path


__all__ = ["DataExporter"]