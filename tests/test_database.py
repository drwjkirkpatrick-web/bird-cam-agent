"""
tests/test_database.py — Tests for modules/database.py SightingDatabase.

NOTE: Every test uses mock_mode=True so the database lives in :memory: and
      is destroyed when the connection closes. No files are written to disk,
      so tests are fully hermetic and parallel-safe.

WHY: These tests pin the contract documented in the module:
     - store_sighting returns the sighting_id and round-trips via get_sighting
     - list_sightings paginates and filters by species
     - search_sightings does free-text across species/scientific_name/notes
     - get_stats reports totals, unique species, and a full rarity breakdown
     - delete_sighting removes rows and reports whether anything was removed
     - alternative_species list survives a store→read round-trip
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest

# NOTE: Make `core` and `modules` importable regardless of pytest's rootdir.
#       The project isn't installed as a package, so we add the repo root to
#       sys.path explicitly. This keeps tests runnable from any cwd.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.types import BirdSighting, RarityLevel  # noqa: E402
from modules.database import SightingDatabase  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def db() -> Iterator[SightingDatabase]:
    """A fresh in-memory database for each test (full isolation)."""
    d = SightingDatabase(":memory:", mock_mode=True)
    yield d
    d.close()


def _make_sighting(
    species: str = "American Robin",
    scientific_name: str = "Turdus migratorius",
    confidence: float = 0.92,
    rarity: RarityLevel = RarityLevel.COMMON,
    notes: str = "Singing on the fence",
    location: str = "Backyard",
    is_bird: bool = True,
    alternative_species: list[str] | None = None,
    sighting_id: str | None = None,
) -> BirdSighting:
    """Helper to build a BirdSighting with sane defaults."""
    return BirdSighting(
        sighting_id=sighting_id or "sid-0001",
        species=species,
        scientific_name=scientific_name,
        confidence=confidence,
        photo_path="/photos/0001.jpg",
        timestamp="2026-07-25T12:00:00+00:00",
        rarity_level=rarity,
        notes=notes,
        location=location,
        is_bird=is_bird,
        alternative_species=alternative_species or [],
    )


# ---------------------------------------------------------------------------
# 1. Store + retrieve round-trip
# ---------------------------------------------------------------------------
def test_store_and_retrieve(db: SightingDatabase):
    """store_sighting returns the id and get_sighting returns the same object."""
    s = _make_sighting(notes="Round trip test")
    returned_id = db.store_sighting(s)
    assert returned_id == s.sighting_id

    got = db.get_sighting(s.sighting_id)
    assert got is not None
    assert got.species == s.species
    assert got.scientific_name == s.scientific_name
    assert got.confidence == pytest.approx(s.confidence)
    assert got.notes == s.notes
    assert got.rarity_level == s.rarity_level
    assert got.is_bird is True


# ---------------------------------------------------------------------------
# 2. get_sighting on a missing id returns None
# ---------------------------------------------------------------------------
def test_get_missing_returns_none(db: SightingDatabase):
    assert db.get_sighting("does-not-exist") is None


# ---------------------------------------------------------------------------
# 3. List with pagination
# ---------------------------------------------------------------------------
def test_list_pagination(db: SightingDatabase):
    """Insert 5 rows, then page with limit=2 across 3 pages."""
    for i in range(5):
        db.store_sighting(_make_sighting(sighting_id=f"sid-{i:04d}"))

    page1 = db.list_sightings(limit=2, offset=0)
    page2 = db.list_sightings(limit=2, offset=2)
    page3 = db.list_sightings(limit=2, offset=4)

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1  # only the 5th row remains


# ---------------------------------------------------------------------------
# 4. Filter by species
# ---------------------------------------------------------------------------
def test_filter_by_species(db: SightingDatabase):
    db.store_sighting(_make_sighting(species="American Robin", sighting_id="r1"))
    db.store_sighting(_make_sighting(species="Blue Jay", sighting_id="b1"))
    db.store_sighting(_make_sighting(species="American Robin", sighting_id="r2"))

    robins = db.list_sightings(species="American Robin", limit=100)
    assert len(robins) == 2
    assert all(s.species == "American Robin" for s in robins)

    jays = db.get_sightings_by_species("Blue Jay")
    assert len(jays) == 1
    assert jays[0].species == "Blue Jay"


# ---------------------------------------------------------------------------
# 5. Search by notes (free-text)
# ---------------------------------------------------------------------------
def test_search_by_notes(db: SightingDatabase):
    db.store_sighting(_make_sighting(notes="Singing loudly at dawn", sighting_id="s1"))
    db.store_sighting(_make_sighting(notes="Foraging on the ground", sighting_id="s2"))
    db.store_sighting(
        _make_sighting(species="Northern Cardinal", notes="Bright red plumage", sighting_id="s3")
    )

    # NOTE: search is case-insensitive substring across species + notes.
    results = db.search_sightings("singing")
    assert len(results) == 1
    assert results[0].sighting_id == "s1"

    # Search by species name too
    results = db.search_sightings("cardinal")
    assert len(results) == 1
    assert results[0].species == "Northern Cardinal"

    # Empty query returns nothing
    assert db.search_sightings("") == []


# ---------------------------------------------------------------------------
# 6. Stats on a populated db
# ---------------------------------------------------------------------------
def test_stats_populated(db: SightingDatabase):
    db.store_sighting(_make_sighting(species="American Robin", rarity=RarityLevel.COMMON, sighting_id="a"))
    db.store_sighting(_make_sighting(species="Blue Jay", rarity=RarityLevel.UNCOMMON, sighting_id="b"))
    db.store_sighting(_make_sighting(species="Snowy Owl", rarity=RarityLevel.RARE, sighting_id="c"))
    db.store_sighting(_make_sighting(species="American Robin", rarity=RarityLevel.COMMON, sighting_id="d"))

    stats = db.get_stats()
    assert stats["total_sightings"] == 4
    assert stats["unique_species"] == 3
    # NOTE: breakdown includes every RarityLevel key, with 0 for unseen ones.
    rb = stats["rarity_breakdown"]
    assert rb["common"] == 2
    assert rb["uncommon"] == 1
    assert rb["rare"] == 1
    assert rb["very_rare"] == 0
    assert rb["accidental"] == 0


# ---------------------------------------------------------------------------
# 7. Delete a sighting
# ---------------------------------------------------------------------------
def test_delete(db: SightingDatabase):
    db.store_sighting(_make_sighting(sighting_id="del-1"))
    assert db.get_sighting("del-1") is not None

    assert db.delete_sighting("del-1") is True
    assert db.get_sighting("del-1") is None

    # Deleting again returns False (nothing removed)
    assert db.delete_sighting("del-1") is False


# ---------------------------------------------------------------------------
# 8. Duplicate / upsert handling
# ---------------------------------------------------------------------------
def test_duplicate_upsert(db: SightingDatabase):
    """Storing the same sighting_id twice upserts, not errors."""
    s = _make_sighting(species="Crow", notes="first", sighting_id="dup-1")
    db.store_sighting(s)

    # Store again with updated notes
    s2 = _make_sighting(species="Crow", notes="second", sighting_id="dup-1")
    db.store_sighting(s2)

    got = db.get_sighting("dup-1")
    assert got is not None
    assert got.notes == "second"
    # Only one row, not two
    assert db.get_stats()["total_sightings"] == 1


# ---------------------------------------------------------------------------
# 9. Empty database stats
# ---------------------------------------------------------------------------
def test_empty_db_stats(db: SightingDatabase):
    stats = db.get_stats()
    assert stats["total_sightings"] == 0
    assert stats["unique_species"] == 0
    # NOTE: breakdown still has every rarity key set to 0
    rb = stats["rarity_breakdown"]
    for level in RarityLevel:
        assert rb[level.value] == 0


# ---------------------------------------------------------------------------
# 10. Multiple species stats
# ---------------------------------------------------------------------------
def test_multiple_species_stats(db: SightingDatabase):
    """Three distinct species, one each, varied rarity."""
    db.store_sighting(_make_sighting(species="Robin", rarity=RarityLevel.COMMON, sighting_id="m1"))
    db.store_sighting(_make_sighting(species="Jay", rarity=RarityLevel.UNCOMMON, sighting_id="m2"))
    db.store_sighting(_make_sighting(species="Owl", rarity=RarityLevel.VERY_RARE, sighting_id="m3"))

    stats = db.get_stats()
    assert stats["total_sightings"] == 3
    assert stats["unique_species"] == 3
    assert stats["rarity_breakdown"]["common"] == 1
    assert stats["rarity_breakdown"]["uncommon"] == 1
    assert stats["rarity_breakdown"]["very_rare"] == 1


# ---------------------------------------------------------------------------
# 11. Round-trip with alternative_species list
# ---------------------------------------------------------------------------
def test_alternative_species_round_trip(db: SightingDatabase):
    alts = ["Steller's Jay", "Blue Jay", "Scrub-Jay"]
    s = _make_sighting(alternative_species=alts, sighting_id="alt-1")
    db.store_sighting(s)

    got = db.get_sighting("alt-1")
    assert got is not None
    # NOTE: order and content must survive the comma-join/split.
    assert got.alternative_species == alts


# ---------------------------------------------------------------------------
# 12. alternative_species empty list round-trips to empty list
# ---------------------------------------------------------------------------
def test_empty_alternative_species(db: SightingDatabase):
    s = _make_sighting(alternative_species=[], sighting_id="alt-empty")
    db.store_sighting(s)
    got = db.get_sighting("alt-empty")
    assert got is not None
    assert got.alternative_species == []


# ---------------------------------------------------------------------------
# 13. is_bird=False survives the round-trip (stored as INTEGER 0)
# ---------------------------------------------------------------------------
def test_is_bird_false_round_trip(db: SightingDatabase):
    s = _make_sighting(is_bird=False, species="Unknown", sighting_id="nb-1")
    db.store_sighting(s)
    got = db.get_sighting("nb-1")
    assert got is not None
    assert got.is_bird is False


# ---------------------------------------------------------------------------
# 14. SQL-injection safety: a malicious query string is treated as data
# ---------------------------------------------------------------------------
def test_injection_safety(db: SightingDatabase):
    """A classic injection payload must be treated as a literal string."""
    evil = "'; DROP TABLE sightings; --"
    db.store_sighting(_make_sighting(species=evil, sighting_id="inj-1"))
    # Table must still exist and be queryable
    got = db.get_sighting("inj-1")
    assert got is not None
    assert got.species == evil
    assert db.get_stats()["total_sightings"] == 1


# ---------------------------------------------------------------------------
# 15. search_sightings hits scientific_name
# ---------------------------------------------------------------------------
def test_search_scientific_name(db: SightingDatabase):
    db.store_sighting(
        _make_sighting(
            species="American Robin",
            scientific_name="Turdus migratorius",
            sighting_id="sci-1",
        )
    )
    results = db.search_sightings("Turdus")
    assert len(results) == 1
    assert results[0].sighting_id == "sci-1"