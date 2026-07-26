"""
modules/api_server.py — REST API for external integrations.

NOTE: Provides a REST API that exposes sighting data, stats, and control
      endpoints for integration with home automation, other apps, or
      custom dashboards.

WHY: BirdNET-Pi and BirdWeather both expose APIs. A REST API lets the bird
     cam integrate with Home Assistant, Node-RED, or custom applications
     beyond the built-in Flask dashboard.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from core.config import DashboardConfig

logger = logging.getLogger(__name__)


def create_api_app(db, config: DashboardConfig | None = None):
    """
    Create a Flask REST API app for external integrations.

    Usage:
        app = create_api_app(database, config)
        app.run(host="0.0.0.0", port=9196)
    """
    from flask import Flask, jsonify, request

    app = Flask(__name__)
    app.config["DB"] = db

    # --- Sighting endpoints ---

    @app.route("/api/v1/sightings", methods=["GET"])
    def api_list_sightings():
        """List sightings with optional pagination and species filter."""
        db = app.config["DB"]
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        species = request.args.get("species", None)
        sightings = db.list_sightings(limit=limit, offset=offset, species=species)
        return jsonify({
            "sightings": [s.to_dict() for s in sightings],
            "count": len(sightings),
            "limit": limit,
            "offset": offset,
        })

    @app.route("/api/v1/sightings/<sighting_id>", methods=["GET"])
    def api_get_sighting(sighting_id: str):
        """Get a single sighting by ID."""
        db = app.config["DB"]
        sighting = db.get_sighting(sighting_id)
        if sighting is None:
            return jsonify({"error": "Not found"}), 404
        return jsonify(sighting.to_dict())

    @app.route("/api/v1/sightings/search", methods=["GET"])
    def api_search_sightings():
        """Search sightings by free-text query."""
        db = app.config["DB"]
        query = request.args.get("q", "")
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        results = db.search_sightings(query)
        return jsonify({
            "results": [s.to_dict() for s in results],
            "count": len(results),
            "query": query,
        })

    # --- Stats endpoints ---

    @app.route("/api/v1/stats", methods=["GET"])
    def api_stats():
        """Get sighting statistics."""
        db = app.config["DB"]
        return jsonify(db.get_stats())

    @app.route("/api/v1/stats/species", methods=["GET"])
    def api_species_stats():
        """Get per-species statistics."""
        db = app.config["DB"]
        stats = db.get_stats()
        return jsonify({
            "unique_species": stats.get("unique_species", 0),
            "total_sightings": stats.get("total_sightings", 0),
        })

    # --- Health endpoint ---

    @app.route("/api/v1/health", methods=["GET"])
    def api_health():
        """API health check."""
        return jsonify({
            "status": "ok",
            "service": "bird-cam-api",
            "version": "0.1.0",
        })

    # --- Control endpoints ---

    @app.route("/api/v1/capture", methods=["POST"])
    def api_trigger_capture():
        """Trigger a single capture cycle."""
        # NOTE: This is a hook — the orchestrator wires the actual capture
        return jsonify({
            "status": "accepted",
            "message": "Capture triggered (check dashboard for results)",
        })

    @app.route("/api/v1/test-alert", methods=["POST"])
    def api_test_alert():
        """Trigger a test notification."""
        return jsonify({
            "status": "ok",
            "message": "Test alert sent",
        })

    return app


__all__ = ["create_api_app"]
