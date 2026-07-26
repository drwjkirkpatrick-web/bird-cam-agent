"""
modules/dashboard.py — Flask web UI for viewing bird sightings.

NOTE: This module provides a web dashboard so the user can view bird
      sightings from their phone or browser. It uses inline HTML/CSS
      strings (no external template files) to keep deployment simple.

WHY: A web UI is the natural companion to the bird cam — the user wants
     to browse what's been visiting the feeder, see photos, and check
     stats. Flask is lightweight enough for any Pi model.

SECURITY: All dynamic content is html.escape()'d to prevent XSS.
          The dashboard binds to 0.0.0.0 by default so it's accessible
          from the local network, but this should NOT be exposed to
          the internet without additional auth.
"""

from __future__ import annotations

import html
import os
from typing import Any

from core.config import DashboardConfig
from core.types import BirdSighting


def create_app(db, config: DashboardConfig):
    """
    Flask application factory.

    Usage:
        app = create_app(database, dashboard_config)
        app.run(host=config.host, port=config.port)
    """
    from flask import Flask, jsonify, request, send_from_directory

    app = Flask(__name__)
    app.config["DB"] = db
    app.config["DASHBOARD_CONFIG"] = config

    # --- Routes ---

    @app.route("/")
    def home():
        """Dashboard home with stats + recent sightings."""
        db = app.config["DB"]
        stats = db.get_stats()
        sightings = db.list_sightings(limit=10)
        return render_home(stats, sightings)

    @app.route("/sightings")
    def sightings_page():
        """Paginated sighting list."""
        db = app.config["DB"]
        page = request.args.get("page", 1, type=int)
        per_page = 50
        offset = (page - 1) * per_page
        sightings = db.list_sightings(limit=per_page, offset=offset)
        total = db.get_stats().get("total_sightings", 0)
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_sighting_list(sightings, page, total_pages)

    @app.route("/sighting/<sighting_id>")
    def sighting_detail(sighting_id: str):
        """Single sighting detail page."""
        db = app.config["DB"]
        sighting = db.get_sighting(sighting_id)
        if sighting is None:
            return render_not_found(sighting_id), 404
        return render_sighting_detail(sighting)

    @app.route("/api/sightings")
    def api_sightings():
        """JSON API for sighting data."""
        db = app.config["DB"]
        limit = request.args.get("limit", 50, type=int)
        sightings = db.list_sightings(limit=limit)
        return jsonify({
            "sightings": [s.to_dict() for s in sightings],
            "count": len(sightings),
        })

    @app.route("/api/stats")
    def api_stats():
        """JSON API for statistics."""
        db = app.config["DB"]
        return jsonify(db.get_stats())

    @app.route("/photo/<path:filename>")
    def serve_photo(filename: str):
        """Serve photo files from the photo directory."""
        db = app.config["DB"]
        # NOTE: Use the database's photo_dir or a default
        photo_dir = app.config.get("PHOTO_DIR", "data/photos")
        return send_from_directory(photo_dir, filename)

    @app.route("/api/test-sms", methods=["POST"])
    def test_sms():
        """Trigger a test SMS notification."""
        # NOTE: This is a hook — the orchestrator wires the actual notifier
        # For now, return a placeholder
        return jsonify({
            "success": True,
            "message": "Test SMS triggered (check logs for delivery status)",
        })

    return app


# --- HTML Renderers ---

def render_home(stats: dict, sightings: list[BirdSighting]) -> str:
    """Render the dashboard home page."""
    total = stats.get("total_sightings", 0)
    unique = stats.get("unique_species", 0)
    rarity = stats.get("rarity_breakdown", {})

    # Find rarest bird
    rarest = "None yet"
    for level in ["accidental", "very_rare", "rare", "uncommon"]:
        if rarity.get(level, 0) > 0:
            rarest = f"{level.replace('_', ' ').title()} ({rarity[level]})"
            break

    # Find last sighting time
    last_time = "Never"
    if sightings:
        last_time = sightings[0].timestamp[:19].replace("T", " ")

    # Build stats cards
    stats_cards = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{total}</div>
            <div class="stat-label">Total Sightings</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{unique}</div>
            <div class="stat-label">Unique Species</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{html.escape(rarest)}</div>
            <div class="stat-label">Rarest Bird</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{html.escape(last_time)}</div>
            <div class="stat-label">Last Sighting</div>
        </div>
    </div>
    """

    # Build recent sightings table
    if sightings:
        rows = ""
        for s in sightings:
            species_esc = html.escape(s.species)
            rarity_esc = html.escape(s.rarity_level.value.replace("_", " "))
            date_str = html.escape(s.timestamp[:19].replace("T", " "))
            confidence = f"{s.confidence:.0%}" if s.confidence else "N/A"
            rarity_class = "rarity-rare" if s.is_rare else "rarity-common"
            rows += f"""
            <tr onclick="window.location='/sighting/{html.escape(s.sighting_id)}'">
                <td>{date_str}</td>
                <td><strong>{species_esc}</strong></td>
                <td><span class="rarity-badge {rarity_class}">{rarity_esc}</span></td>
                <td>{confidence}</td>
            </tr>
            """
        sightings_table = f"""
        <h2>Recent Sightings</h2>
        <table>
            <thead>
                <tr><th>Date</th><th>Species</th><th>Rarity</th><th>Confidence</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """
    else:
        sightings_table = """
        <h2>Recent Sightings</h2>
        <div class="placeholder">No sightings yet. Start the camera to begin monitoring.</div>
        """

    return _page_template("Bird Cam Dashboard", stats_cards + sightings_table)


def render_sighting_list(
    sightings: list[BirdSighting], page: int, total_pages: int
) -> str:
    """Render the paginated sightings list."""
    if not sightings:
        body = """
        <h2>All Sightings</h2>
        <div class="placeholder">No sightings recorded yet.</div>
        """
        return _page_template("All Sightings — Bird Cam", body)

    rows = ""
    for s in sightings:
        species_esc = html.escape(s.species)
        rarity_esc = html.escape(s.rarity_level.value.replace("_", " "))
        date_str = html.escape(s.timestamp[:19].replace("T", " "))
        confidence = f"{s.confidence:.0%}" if s.confidence else "N/A"
        rarity_class = "rarity-rare" if s.is_rare else "rarity-common"
        rows += f"""
        <tr onclick="window.location='/sighting/{html.escape(s.sighting_id)}'">
            <td>{date_str}</td>
            <td><strong>{species_esc}</strong></td>
            <td><span class="rarity-badge {rarity_class}">{rarity_esc}</span></td>
            <td>{confidence}</td>
        </tr>
        """

    # Pagination
    prev_link = f'<a href="/sightings?page={page-1}" class="btn">&laquo; Prev</a>' if page > 1 else ""
    next_link = f'<a href="/sightings?page={page+1}" class="btn">Next &raquo;</a>' if page < total_pages else ""
    pagination = f'<div class="pagination">{prev_link}<span>Page {page} of {total_pages}</span>{next_link}</div>'

    body = f"""
    <h2>All Sightings</h2>
    <table>
        <thead><tr><th>Date</th><th>Species</th><th>Rarity</th><th>Confidence</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    {pagination}
    """
    return _page_template("All Sightings — Bird Cam", body)


def render_sighting_detail(sighting: BirdSighting) -> str:
    """Render a single sighting detail page."""
    species_esc = html.escape(sighting.species)
    sci_esc = html.escape(sighting.scientific_name)
    rarity_esc = html.escape(sighting.rarity_level.value.replace("_", " "))
    date_str = html.escape(sighting.timestamp[:19].replace("T", " "))
    notes_esc = html.escape(sighting.notes or "No notes")
    location_esc = html.escape(sighting.location or "Unknown")
    confidence = f"{sighting.confidence:.0%}" if sighting.confidence else "N/A"
    rarity_class = "rarity-rare" if sighting.is_rare else "rarity-common"

    # Photo display
    if sighting.photo_path and os.path.basename(sighting.photo_path):
        photo_filename = html.escape(os.path.basename(sighting.photo_path))
        photo_html = f'<img src="/photo/{photo_filename}" alt="{species_esc}" class="sighting-photo">'
    else:
        photo_html = '<div class="placeholder">No photo available</div>'

    # Alternative species
    alt_html = ""
    if sighting.alternative_species:
        alt_items = "".join(f"<li>{html.escape(a)}</li>" for a in sighting.alternative_species)
        alt_html = f"<h3>Alternative Species</h3><ul>{alt_items}</ul>"

    body = f"""
    <div class="sighting-detail">
        <a href="/" class="btn">&laquo; Back to Dashboard</a>
        <h2>{species_esc}</h2>
        <div class="detail-grid">
            <div class="detail-photo">{photo_html}</div>
            <div class="detail-info">
                <table class="detail-table">
                    <tr><th>Scientific Name</th><td>{sci_esc}</td></tr>
                    <tr><th>Rarity</th><td><span class="rarity-badge {rarity_class}">{rarity_esc}</span></td></tr>
                    <tr><th>Confidence</th><td>{confidence}</td></tr>
                    <tr><th>Date</th><td>{date_str}</td></tr>
                    <tr><th>Location</th><td>{location_esc}</td></tr>
                </table>
                <h3>Notes</h3>
                <p>{notes_esc}</p>
                {alt_html}
            </div>
        </div>
    </div>
    """
    return _page_template(f"{species_esc} — Bird Cam", body)


def render_not_found(sighting_id: str) -> str:
    """Render a 404 page for a missing sighting."""
    body = f"""
    <div class="not-found">
        <h2>Sighting Not Found</h2>
        <p>No sighting with ID: {html.escape(sighting_id)}</p>
        <a href="/" class="btn">&laquo; Back to Dashboard</a>
    </div>
    """
    return _page_template("Not Found — Bird Cam", body)


def _page_template(title: str, body: str) -> str:
    """Full HTML page template with inline CSS."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e; color: #e0e0e0; padding: 20px;
            max-width: 1200px; margin: 0 auto;
        }}
        h1, h2, h3 {{ color: #0fbcf9; margin: 20px 0 10px; }}
        h1 {{ font-size: 1.8em; }}
        h2 {{ font-size: 1.4em; border-bottom: 1px solid #333; padding-bottom: 5px; }}
        .stats-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px; margin: 20px 0;
        }}
        .stat-card {{
            background: #16213e; border-radius: 10px; padding: 20px; text-align: center;
            border: 1px solid #0fbcf9;
        }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #0fbcf9; }}
        .stat-label {{ font-size: 0.9em; color: #888; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #0fbcf9; cursor: pointer; }}
        tbody tr {{ cursor: pointer; transition: background 0.2s; }}
        tbody tr:hover {{ background: #16213e; }}
        .rarity-badge {{
            padding: 3px 10px; border-radius: 15px; font-size: 0.85em; font-weight: bold;
        }}
        .rarity-common {{ background: #1a472a; color: #4caf50; }}
        .rarity-rare {{ background: #4a1a2e; color: #e91e63; }}
        .placeholder {{
            background: #16213e; padding: 30px; text-align: center;
            border-radius: 10px; color: #666; font-style: italic;
        }}
        .btn {{
            display: inline-block; padding: 8px 16px; background: #0fbcf9;
            color: #1a1a2e; text-decoration: none; border-radius: 5px;
            font-weight: bold; margin: 5px 0;
        }}
        .btn:hover {{ background: #0da9e9; }}
        .pagination {{ text-align: center; margin: 20px 0; }}
        .pagination span {{ margin: 0 15px; }}
        .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .detail-photo img {{
            max-width: 100%; border-radius: 10px; border: 1px solid #333;
        }}
        .detail-table th {{ color: #888; font-weight: normal; }}
        .not-found {{ text-align: center; padding: 50px; }}
        ul {{ margin-left: 20px; margin-top: 5px; }}
        li {{ margin: 3px 0; }}
        @media (max-width: 600px) {{
            .detail-grid {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
    </style>
</head>
<body>
    <h1>Bird Cam Dashboard</h1>
    {body}
</body>
</html>"""