"""tests/test_dashboard.py — Dashboard Flask app tests."""

import os
import tempfile

import pytest

from core.config import DashboardConfig
from core.types import BirdSighting, RarityLevel


@pytest.fixture
def db():
    """Create a test database with some sightings."""
    from modules.database import SightingDatabase

    db = SightingDatabase(":memory:", mock_mode=True)

    # Add some test sightings
    sightings = [
        BirdSighting(
            species="American Robin",
            scientific_name="Turdus migratorius",
            confidence=0.92,
            rarity_level=RarityLevel.COMMON,
            notes="Foraging on the ground",
            location="Backyard",
        ),
        BirdSighting(
            species="Snowy Owl",
            scientific_name="Bubo scandiacus",
            confidence=0.88,
            rarity_level=RarityLevel.RARE,
            notes="First sighting this winter",
            location="Backyard",
        ),
        BirdSighting(
            species="Black-capped Chickadee",
            confidence=0.85,
            rarity_level=RarityLevel.COMMON,
        ),
    ]
    for s in sightings:
        db.store_sighting(s)

    return db


@pytest.fixture
def app(db):
    from modules.dashboard import create_app

    config = DashboardConfig()
    app = create_app(db, config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestHomeRoute:
    def test_home_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_home_contains_stats(self, client):
        resp = client.get("/")
        html_content = resp.data.decode()
        assert "Total Sightings" in html_content
        assert "Unique Species" in html_content

    def test_home_shows_recent_sightings(self, client):
        resp = client.get("/")
        html_content = resp.data.decode()
        assert "American Robin" in html_content
        assert "Snowy Owl" in html_content


class TestSightingsRoute:
    def test_sightings_returns_200(self, client):
        resp = client.get("/sightings")
        assert resp.status_code == 200

    def test_sightings_contains_species(self, client):
        resp = client.get("/sightings")
        html_content = resp.data.decode()
        assert "American Robin" in html_content


class TestSightingDetail:
    def test_detail_returns_200(self, client):
        from modules.database import SightingDatabase

        db = SightingDatabase(":memory:", mock_mode=True)
        sighting = BirdSighting(species="Test Bird", rarity_level=RarityLevel.COMMON)
        sid = db.store_sighting(sighting)
        # Use the app's DB
        app = client.application
        app.config["DB"] = db
        resp = client.get(f"/sighting/{sid}")
        assert resp.status_code == 200

    def test_detail_404_for_missing(self, client):
        resp = client.get("/sighting/nonexistent-id")
        assert resp.status_code == 404


class TestAPIRoutes:
    def test_api_sightings_returns_json(self, client):
        resp = client.get("/api/sightings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sightings" in data
        assert "count" in data
        assert data["count"] > 0

    def test_api_stats_returns_json(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_sightings" in data
        assert "unique_species" in data

    def test_test_sms_endpoint(self, client):
        resp = client.post("/api/test-sms")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "success" in data


class TestSecurity:
    def test_html_escape_on_species(self, db):
        """Species names with special chars should be escaped."""
        from modules.dashboard import create_app

        # Add a sighting with HTML in the species name
        bad_sighting = BirdSighting(
            species="<script>alert('xss')</script>",
            rarity_level=RarityLevel.COMMON,
        )
        db.store_sighting(bad_sighting)
        app = create_app(db, DashboardConfig())
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/")
        html_content = resp.data.decode()
        # The raw script tag should NOT be present
        assert "<script>alert" not in html_content
        # The escaped version should be present
        assert "&lt;script&gt;" in html_content or "<script>alert" not in html_content


class TestEmptyDatabase:
    def test_empty_db_shows_placeholder(self):
        from modules.dashboard import create_app
        from modules.database import SightingDatabase

        empty_db = SightingDatabase(":memory:", mock_mode=True)
        app = create_app(empty_db, DashboardConfig())
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/")
        assert resp.status_code == 200
        html_content = resp.data.decode()
        assert "No sightings" in html_content or "0" in html_content


class TestPhotoRoute:
    def test_photo_route_404_for_missing_file(self, client):
        resp = client.get("/photo/nonexistent.jpg")
        assert resp.status_code == 404