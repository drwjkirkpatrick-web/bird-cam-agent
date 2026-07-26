"""tests/test_api_server.py"""

import pytest
from core.config import DashboardConfig
from modules.api_server import create_api_app

@pytest.fixture
def db():
    from modules.database import SightingDatabase
    from core.types import BirdSighting, RarityLevel
    db = SightingDatabase(":memory:", mock_mode=True)
    db.store_sighting(BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp="2026-07-25T08:00:00+00:00",
    ))
    return db

@pytest.fixture
def app(db):
    return create_api_app(db, DashboardConfig())

@pytest.fixture
def client(app):
    app.config["TESTING"] = True
    return app.test_client()

class TestAPI:
    def test_list_sightings(self, client):
        resp = client.get("/api/v1/sightings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sightings" in data
        assert data["count"] > 0
    def test_get_sighting(self, client, db):
        sightings = db.list_sightings()
        if sightings:
            resp = client.get(f"/api/v1/sightings/{sightings[0].sighting_id}")
            assert resp.status_code == 200
    def test_get_sighting_not_found(self, client):
        resp = client.get("/api/v1/sightings/nonexistent")
        assert resp.status_code == 404
    def test_search(self, client):
        resp = client.get("/api/v1/sightings/search?q=Robin")
        assert resp.status_code == 200
    def test_search_no_query(self, client):
        resp = client.get("/api/v1/sightings/search")
        assert resp.status_code == 400
    def test_stats(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
    def test_capture(self, client):
        resp = client.post("/api/v1/capture")
        assert resp.status_code == 200
    def test_test_alert(self, client):
        resp = client.post("/api/v1/test-alert")
        assert resp.status_code == 200
