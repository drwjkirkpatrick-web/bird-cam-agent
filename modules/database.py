"""
modules/database.py — SQLite persistence layer for bird sightings.

NOTE: This is the ONLY module that touches SQLite directly. Every other
      module goes through SightingDatabase to read or write sighting data.
      That keeps schema changes localized to this one file.

WHY: A single persistence boundary means we can swap SQLite for Postgres
     or a cloud store later by changing only this module. It also gives us
     one place to enforce parameterized queries (no SQL injection) and
     consistent row-to-object conversion.

Design decisions:
  - DDL lives in class-level constants (SCHEMA_*). WHY: schema is data, not
    logic; keeping it as constants makes it easy to read and diff, and lets
    tests assert against it without instantiating the class.
  - sqlite3.Row for dict-like row access. WHY: lets us write
    row["species"] instead of row[2], which is robust to column reordering.
  - Parameterized queries everywhere with ? placeholders. WHY: string-
    formatting SQL with user input is THE classic injection vector. The
    sqlite3 driver escapes ?-bound parameters for us.
  - alternative_species (a list[str] on BirdSighting) is stored as a single
    comma-joined TEXT column. WHY: SQLite has no native list/array type.
    A join/split serialization is simple and good enough for short lists.
  - BirdSighting.from_dict() is used to convert rows back to objects. WHY:
    it already handles the RarityLevel string→enum conversion, so we don't
    reinvent that logic here.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class SightingDatabase:
    """
    SQLite-backed store for BirdSighting records.

    Usage:
        db = SightingDatabase(":memory:", mock_mode=True)
        sid = db.store_sighting(sighting)
        got = db.get_sighting(sid)
        db.close()

    NOTE: In mock_mode=True the db_path argument is ignored and an in-memory
          database is used. This is how tests run without touching the disk
          and how the agent runs on a dev machine with no real database file.
    """

    # ------------------------------------------------------------------
    # Schema (DDL) — class-level constants
    # ------------------------------------------------------------------
    # NOTE: IF NOT EXISTS makes _init_schema() idempotent, so calling it on
    #       an already-initialized database file is safe (e.g. on restart).
    # WHY:  Bird-cam agents restart often (Pi power bumps, systemd restarts),
    #       so the schema setup must never fail just because tables exist.

    SCHEMA_SIGHTINGS = """
    CREATE TABLE IF NOT EXISTS sightings (
        sighting_id        TEXT PRIMARY KEY,
        species            TEXT,
        scientific_name    TEXT,
        confidence         REAL,
        photo_path         TEXT,
        timestamp          TEXT,
        rarity_level       TEXT,
        notes              TEXT,
        location           TEXT,
        is_bird            INTEGER,
        alternative_species TEXT
    )
    """

    SCHEMA_PHOTOS = """
    CREATE TABLE IF NOT EXISTS photos (
        photo_id    TEXT PRIMARY KEY,
        sighting_id TEXT,
        file_path   TEXT,
        file_size   INTEGER,
        file_hash   TEXT
    )
    """

    SCHEMA_RECORDS = """
    CREATE TABLE IF NOT EXISTS records (
        record_id   TEXT PRIMARY KEY,
        sighting_id TEXT,
        stored_at   TEXT,
        file_size   INTEGER,
        file_hash   TEXT
    )
    """

    # NOTE: Non-unique indexes speed up the common lookup patterns without
    #       enforcing uniqueness. sightings(species) backs list/filter-by-
    #       species; photos/records(sighting_id) back join-on-delete paths.
    INDEX_SIGHTINGS_SPECIES = (
        "CREATE INDEX IF NOT EXISTS idx_sightings_species "
        "ON sightings(species)"
    )
    INDEX_PHOTOS_SIGHTING = (
        "CREATE INDEX IF NOT EXISTS idx_photos_sighting_id "
        "ON photos(sighting_id)"
    )
    INDEX_RECORDS_SIGHTING = (
        "CREATE INDEX IF NOT EXISTS idx_records_sighting_id "
        "ON records(sighting_id)"
    )

    def __init__(self, db_path: str, mock_mode: bool = True):
        """
        Open (or create) the database.

        NOTE: mock_mode=True forces ':memory:' regardless of db_path. An
              in-memory DB is destroyed when the connection closes, which
              is exactly what tests want — full isolation, no cleanup.
        WHY:  We keep db_path as the first arg even in mock mode so the
              constructor signature stays stable for the real (file) path
              used in production. Callers don't have to branch.
        """
        self.db_path = db_path
        self.mock_mode = mock_mode
        # NOTE: check_same_thread=False lets the dashboard thread read while
        #       the orchestrator thread writes. sqlite3 serializes writes
        #       internally; we add no extra locking here because the
        #       orchestrator is the single writer.
        self.conn = sqlite3.connect(
            ":memory:" if mock_mode else db_path,
            check_same_thread=False,
        )
        # WHY: Row factory → rows support row["col"] instead of row[idx].
        #      This is what makes _row_to_sighting robust to column order.
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------
    def _init_schema(self) -> None:
        """Create all tables and indexes if they don't already exist."""
        cur = self.conn.cursor()
        try:
            cur.execute(self.SCHEMA_SIGHTINGS)
            cur.execute(self.SCHEMA_PHOTOS)
            cur.execute(self.SCHEMA_RECORDS)
            cur.execute(self.INDEX_SIGHTINGS_SPECIES)
            cur.execute(self.INDEX_PHOTOS_SIGHTING)
            cur.execute(self.INDEX_RECORDS_SIGHTING)
            self.conn.commit()
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Row <-> object conversion
    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_sighting(row: sqlite3.Row) -> BirdSighting:
        """
        Convert a sqlite3.Row from the sightings table into a BirdSighting.

        NOTE: We build a plain dict from the row and hand it to
              BirdSighting.from_dict(), which already knows how to turn the
              rarity_level string back into a RarityLevel enum. We only have
              to undo our alternative_species serialization here.
        WHY:  Reusing from_dict() keeps the enum-conversion logic in ONE
              place (core/types.py). If RarityLevel gains a new member,
              this module doesn't need to change.
        """
        d = dict(row)
        # NOTE: alternative_species is stored as comma-joined TEXT.
        #       Reverse the join, stripping whitespace and dropping empties
        #       so a missing/NULL column becomes [] not [''].
        raw_alts = d.get("alternative_species") or ""
        d["alternative_species"] = [
            s.strip() for s in raw_alts.split(",") if s.strip()
        ]
        # NOTE: is_bird is stored as INTEGER (0/1) because SQLite has no
        #       native BOOLEAN. Coerce back to a real bool here so callers
        #       get the same type they stored. core/types.from_dict() only
        #       handles rarity_level enum conversion, not bool↔int, so the
        #       DB layer owns this deserialization (it did the encoding).
        if "is_bird" in d and d["is_bird"] is not None:
            d["is_bird"] = bool(d["is_bird"])
        return BirdSighting.from_dict(d)

    @staticmethod
    def _sighting_to_row_tuple(s: BirdSighting) -> tuple:
        """
        Convert a BirdSighting into a positional tuple matching the
        sightings INSERT column order.

        NOTE: alternative_species (list[str]) is joined with commas because
              SQLite has no array type. is_bird (bool) is stored as 0/1
              INTEGER because SQLite has no native BOOLEAN.
        WHY:  Centralizing the serialization here means the column order is
              declared in exactly one spot (the INSERT statement) and this
              tuple is built to match it.
        """
        return (
            s.sighting_id,
            s.species,
            s.scientific_name,
            s.confidence,
            s.photo_path,
            s.timestamp,
            s.rarity_level.value,  # enum → string
            s.notes,
            s.location,
            1 if s.is_bird else 0,  # bool → int
            ",".join(s.alternative_species),  # list → comma string
        )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def store_sighting(self, sighting: BirdSighting) -> str:
        """
        Insert a BirdSighting and return its sighting_id.

        NOTE: We use INSERT OR REPLACE so re-storing a sighting with the
              same sighting_id upserts rather than raising IntegrityError.
              That makes store_sighting idempotent — handy when the
              orchestrator retries after a crash.
        WHY:  The primary key is sighting_id (a UUID generated in
              core/types.py). Replay-safe upserts prevent duplicate rows
              when the same sighting is processed more than once.
        """
        cur = self.conn.cursor()
        try:
            cur.execute(
                "INSERT OR REPLACE INTO sightings "
                "(sighting_id, species, scientific_name, confidence, "
                " photo_path, timestamp, rarity_level, notes, location, "
                " is_bird, alternative_species) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._sighting_to_row_tuple(sighting),
            )
            self.conn.commit()
            logger.debug(
                "Stored sighting %s (%s)", sighting.sighting_id, sighting.species
            )
            return sighting.sighting_id
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------
    def get_sighting(self, sighting_id: str) -> BirdSighting | None:
        """
        Fetch a single sighting by ID, or None if not found.

        NOTE: Parameterized with ? so a malformed/garbage sighting_id can
              never escape into SQL syntax. This is the single most
              important anti-injection habit.
        """
        cur = self.conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM sightings WHERE sighting_id = ?",
                (sighting_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return self._row_to_sighting(row)
        finally:
            cur.close()

    def list_sightings(
        self,
        limit: int = 50,
        offset: int = 0,
        species: str | None = None,
    ) -> list[BirdSighting]:
        """
        Return a page of sightings, optionally filtered by species.

        NOTE: species filter is exact match (case-sensitive) to keep the
              query sargable — the idx_sightings_species index can serve it.
              For fuzzy/free-text matching use search_sighting() instead.
        WHY:  Pagination (LIMIT/OFFSET) keeps result sets bounded even when
              the DB grows to thousands of rows; the dashboard never loads
              the whole table at once.
        """
        cur = self.conn.cursor()
        try:
            if species is not None:
                # NOTE: filtered path — index-backed exact match
                cur.execute(
                    "SELECT * FROM sightings WHERE species = ? "
                    "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (species, limit, offset),
                )
            else:
                cur.execute(
                    "SELECT * FROM sightings "
                    "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            rows = cur.fetchall()
            return [self._row_to_sighting(r) for r in rows]
        finally:
            cur.close()

    def get_sightings_by_species(self, species: str) -> list[BirdSighting]:
        """
        Return every sighting for a given species (no pagination).

        NOTE: This is a convenience wrapper around list_sightings with a
              huge limit. Use list_sightings(species=..., limit=...) when
              you actually want a page.
        WHY:  Some callers (e.g. "has this species been seen before?")
              want the full set; paging there is just friction.
        """
        return self.list_sightings(limit=10**9, offset=0, species=species)

    def search_sightings(self, query: str) -> list[BirdSighting]:
        """
        Free-text search across species, scientific_name, and notes.

        NOTE: We use LIKE with %query% for substring matching. LIKE is
              case-insensitive for ASCII in SQLite, which is good enough
              for free-text over bird names and notes.
        WHY:  No FTS5 virtual table is used — we keep the schema simple and
              dependency-free. For the scale of a single bird cam (hundreds
              to low thousands of rows) a linear LIKE scan is plenty fast.
        """
        if not query:
            return []
        like = f"%{query}%"
        cur = self.conn.cursor()
        try:
            # NOTE: Each ? is bound separately — we reuse `like` three times
            #       because sqlite3 binds positional, not named-by-repeat.
            cur.execute(
                "SELECT * FROM sightings "
                "WHERE species LIKE ? "
                "   OR scientific_name LIKE ? "
                "   OR notes LIKE ? "
                "ORDER BY timestamp DESC",
                (like, like, like),
            )
            rows = cur.fetchall()
            return [self._row_to_sighting(r) for r in rows]
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Stats / aggregation
    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        """
        Return aggregate statistics about the sightings table.

        Returns a dict shaped like:
            {
                "total_sightings": int,
                "unique_species": int,
                "rarity_breakdown": { "<rarity_value>": count, ... },
            }

        NOTE: We include EVERY RarityLevel value in the breakdown (even
              those with zero sightings) so downstream consumers (the
              dashboard) can render a stable legend without guessing which
              buckets might be missing.
        WHY:  A fixed key set means the dashboard template can iterate over
              a known list of rarity labels and always show them, rather
              than only showing labels that happen to have >0 count.
        """
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) AS c FROM sightings")
            total = cur.fetchone()["c"]

            cur.execute(
                "SELECT COUNT(DISTINCT species) AS c FROM sightings "
                "WHERE species IS NOT NULL AND species != ''"
            )
            unique_species = cur.fetchone()["c"]

            cur.execute(
                "SELECT rarity_level, COUNT(*) AS c "
                "FROM sightings GROUP BY rarity_level"
            )
            rows = cur.fetchall()
            # NOTE: Seed every known rarity with 0, then overlay real counts.
            breakdown = {level.value: 0 for level in RarityLevel}
            for r in rows:
                key = r["rarity_level"]
                if key:
                    # NOTE: from_string() coerces unknown/garbage values to
                    #       COMMON, so a legacy row with a bad rarity string
                    #       is counted under 'common' rather than crashing.
                    level = RarityLevel.from_string(key)
                    breakdown[level.value] = breakdown.get(level.value, 0) + r["c"]

            return {
                "total_sightings": total,
                "unique_species": unique_species,
                "rarity_breakdown": breakdown,
            }
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Delete + teardown
    # ------------------------------------------------------------------
    def delete_sighting(self, sighting_id: str) -> bool:
        """
        Delete a sighting by ID. Returns True if a row was removed.

        NOTE: We do NOT cascade into photos/records here — those tables are
              for future photo/file storage and may be managed by other
              code. Deleting a sighting only touches the sightings table.
        WHY:  Keeping delete scoped avoids surprising side effects. If you
              want orphan cleanup, do it explicitly in a higher layer.
        """
        cur = self.conn.cursor()
        try:
            cur.execute(
                "DELETE FROM sightings WHERE sighting_id = ?",
                (sighting_id,),
            )
            self.conn.commit()
            # NOTE: rowcount is 1 if deleted, 0 if the ID didn't exist.
            return cur.rowcount > 0
        finally:
            cur.close()

    def close(self) -> None:
        """
        Close the database connection.

        NOTE: For an in-memory (mock_mode) database, closing the connection
              destroys all data — there's no file to persist to. That's the
              desired behavior for tests.
        WHY:  Explicit close avoids leaking file descriptors and (for file
              DBs) ensures the WAL/checkpoint is flushed to disk.
        """
        if self.conn is not None:
            self.conn.close()
            logger.debug("Database connection closed")


__all__ = ["SightingDatabase"]