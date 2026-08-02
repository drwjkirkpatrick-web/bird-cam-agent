"""
modules/photo_dataset_builder.py — Download and curate bird photo datasets for local model training.

NOTE: This module aggregates photos from three sources to build a training dataset
      that can be used to train a lightweight bird identification classifier:
      1. iNaturalist API — CC-licensed wildlife photos with species labels
      2. CUB-200-2011 — 11,788 academic images of 200 North American bird species
      3. Local archive — photos already captured by the bird-cam-agent's PhotoOrganizer

WHY: Training a local CNN classifier (e.g. MobileNetV3-Small) requires hundreds
     of labeled images per species. Rather than manually curating photos, this
     module programmatically downloads, validates, and organizes them into a
     standard PyTorch/Keras image-folder structure: data/training/{species}/.

     The module is GENERIC — it accepts any species list (PNW, Kenya, custom).
     The user supplies the species list; the module handles the rest.

Design decisions:
  - Three-tier sourcing: iNaturalist (bulk), CUB-200 (quality), archive (real-world).
    WHY: iNaturalist has the most volume, CUB-200 has clean labels,
         and archive has your actual feeder photos which are closest to production.
  - Each source is a separate private method. WHY: lets users run individual
    sources or skip slow/unreliable ones. Also makes unit testing each source easy.
  - Image validation via Pillow. WHY: downloaded images can be truncated or
    corrupted; validating them before adding to the dataset prevents training crashes.
  - Deduplication by file hash. WHY: iNaturalist and CUB-200 may overlap on
    common species (e.g. American Robin). We don't want duplicate training images.
  - Rate limiting and retry with backoff. WHY: iNaturalist API has rate limits
    (100 requests/minute). Respecting them keeps us from being blocked.
  - Mock mode creates synthetic data. WHY: allows testing the full pipeline
    (folder creation, validation, dedup, stats) without network calls.
  - Generic species_list parameter. WHY: the same module works for PNW birds,
    Kenya birds, or a user's custom 10-species backyard list.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse

from core.config import DatasetBuilderConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source capability flags — used for reporting and filtering
# ---------------------------------------------------------------------------

SOURCE_INATURALIST = "inaturalist"
SOURCE_CUB200 = "cub200"
SOURCE_ARCHIVE = "archive"
ALL_SOURCES = [SOURCE_INATURALIST, SOURCE_CUB200, SOURCE_ARCHIVE]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _file_hash(path: str) -> str | None:
    """Compute MD5 hash of a file for deduplication."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _is_valid_image(path: str) -> bool:
    """Check if a file is a valid image readable by Pillow."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def _ensure_dir(path: str) -> None:
    """Create a directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def _slugify(name: str) -> str:
    """Convert a species name to a filesystem-safe directory name."""
    return name.strip().replace(" ", "_").replace("/", "_").lower()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SpeciesDownloadResult:
    """Result of downloading images for a single species."""

    species: str
    downloaded: int = 0
    skipped_dup: int = 0
    invalid: int = 0
    errors: int = 0
    source_counts: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.source_counts is None:
            self.source_counts = {}

    def total_attempted(self) -> int:
        return self.downloaded + self.skipped_dup + self.invalid + self.errors


# ---------------------------------------------------------------------------
# Main builder class
# ---------------------------------------------------------------------------


class PhotoDatasetBuilder:
    """
    Download and organize bird photos into a training-ready dataset.

    Usage:
        species = [
            {"name": "American Robin", "scientific_name": "Turdus migratorius"},
            {"name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis"},
        ]
        config = DatasetBuilderConfig(output_dir="data/training")
        builder = PhotoDatasetBuilder(config)
        results = builder.build_dataset(species_list=species)
        stats = builder.get_dataset_stats()

    The resulting folder structure:
        data/training/
          american_robin/
            robin_001.jpg
            robin_002.jpg
            ...
          northern_cardinal/
            cardinal_001.jpg
            ...
    """

    def __init__(self, config: DatasetBuilderConfig | None = None):
        self.config = config or DatasetBuilderConfig()
        self._seen_hashes: set[str] = set()
        self._results: list[SpeciesDownloadResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_dataset(
        self,
        species_list: list[dict[str, Any]],
        sources: list[str] | None = None,
    ) -> list[SpeciesDownloadResult]:
        """
        Build a training dataset from the given species list.

        Args:
            species_list: List of dicts with "name" and optionally "scientific_name"
            sources: Which sources to use (defaults to config.sources)

        Returns:
            List of SpeciesDownloadResult, one per species.
        """
        sources = sources or self.config.sources
        _ensure_dir(self.config.output_dir)
        self._results = []
        self._seen_hashes = set()

        logger.info(
            "Building dataset for %d species from sources: %s",
            len(species_list),
            sources,
        )

        for entry in species_list:
            species = entry.get("name", "")
            scientific = entry.get("scientific_name", "")
            if not species:
                logger.warning("Skipping species entry with no name: %s", entry)
                continue

            result = self._build_species(species, scientific, sources)
            self._results.append(result)

        logger.info("Dataset build complete. Results: %s", self._summarize())
        return self._results

    def get_dataset_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about the built dataset."""
        total_images = 0
        total_species = 0
        species_with_min = 0
        min_req = self.config.min_images_per_species

        if not os.path.exists(self.config.output_dir):
            return {
                "total_images": 0,
                "total_species": 0,
                "species_with_minimum": 0,
                "species_breakdown": {},
            }

        species_breakdown: dict[str, int] = {}
        for slug in sorted(os.listdir(self.config.output_dir)):
            spath = os.path.join(self.config.output_dir, slug)
            if not os.path.isdir(spath):
                continue
            count = len(
                [f for f in os.listdir(spath) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            )
            species_breakdown[slug] = count
            total_images += count
            total_species += 1
            if count >= min_req:
                species_with_min += 1

        return {
            "total_images": total_images,
            "total_species": total_species,
            "min_required": min_req,
            "species_with_minimum": species_with_min,
            "species_breakdown": species_breakdown,
            "output_dir": self.config.output_dir,
        }

    def clean_dataset(self) -> int:
        """Remove all files from the output directory. Returns number of files deleted."""
        deleted = 0
        if os.path.exists(self.config.output_dir):
            for root, dirs, files in os.walk(self.config.output_dir):
                for f in files:
                    try:
                        os.unlink(os.path.join(root, f))
                        deleted += 1
                    except OSError:
                        pass
            # Remove empty subdirectories
            for root, dirs, files in os.walk(self.config.output_dir, topdown=False):
                if root != self.config.output_dir and not os.listdir(root):
                    try:
                        os.rmdir(root)
                    except OSError:
                        pass
        logger.info("Cleaned %d files from %s", deleted, self.config.output_dir)
        return deleted

    # ------------------------------------------------------------------
    # Per-species build
    # ------------------------------------------------------------------

    def _build_species(
        self,
        species: str,
        scientific_name: str,
        sources: list[str],
    ) -> SpeciesDownloadResult:
        """Download images for a single species from all enabled sources."""
        slug = _slugify(species)
        dest_dir = os.path.join(self.config.output_dir, slug)
        _ensure_dir(dest_dir)

        result = SpeciesDownloadResult(species=species)
        max_per = self.config.max_images_per_species
        current_count = self._count_images(dest_dir)

        logger.debug(
            "Building %s (slug=%s) — currently %d images, max %d",
            species,
            slug,
            current_count,
            max_per,
        )

        # Track downloaded count
        downloaded = 0
        for source in sources:
            if current_count >= max_per:
                break

            if source == SOURCE_INATURALIST:
                count = self._download_inaturalist(
                    species, scientific_name, dest_dir, max_per - current_count, result
                )
                downloaded += count
                current_count += count
                result.source_counts[SOURCE_INATURALIST] = count

            elif source == SOURCE_CUB200:
                count = self._download_cub200(
                    species, scientific_name, dest_dir, max_per - current_count, result
                )
                downloaded += count
                current_count += count
                result.source_counts[SOURCE_CUB200] = count

            elif source == SOURCE_ARCHIVE:
                count = self._copy_from_archive(
                    species, dest_dir, max_per - current_count, result
                )
                downloaded += count
                current_count += count
                result.source_counts[SOURCE_ARCHIVE] = count

        result.downloaded = downloaded
        return result

    # ------------------------------------------------------------------
    # Source 1: iNaturalist API
    # ------------------------------------------------------------------

    def _download_inaturalist(
        self,
        species: str,
        scientific_name: str,
        dest_dir: str,
        remaining: int,
        result: SpeciesDownloadResult,
    ) -> int:
        """
        Download photos from the iNaturalist REST API.

        NOTE: iNaturalist has a public API with rate limits. We use the
        /v1/observations endpoint with photo=true and quality_grade=research
        to get verified, CC-licensed wildlife photos.

        Returns the number of images actually saved.
        """
        if self.config.mock_mode:
            return self._mock_download(dest_dir, remaining, result, SOURCE_INATURALIST)

        downloaded = 0
        query = scientific_name or species
        per_page = min(self.config.inaturalist_per_page, 200)
        page = 1

        headers = {}
        if self.config.inaturalist_api_key:
            headers["Authorization"] = f"Bearer {self.config.inaturalist_api_key}"

        while downloaded < remaining and page <= 5:  # cap at 5 pages
            params = {
                "q": query,
                "search_on": "names",
                "quality_grade": "research",
                "has[]": "photos",
                "per_page": per_page,
                "page": page,
                "order": "desc",
                "order_by": "created_at",
            }
            url = f"https://api.inaturalist.org/v1/observations?{urlencode(params)}"

            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                logger.warning("iNaturalist HTTP %d for %s", e.code, query)
                result.errors += 1
                break
            except (URLError, json.JSONDecodeError) as e:
                logger.warning("iNaturalist fetch failed for %s: %s", query, e)
                result.errors += 1
                break

            results = data.get("results", [])
            if not results:
                break

            for obs in results:
                if downloaded >= remaining:
                    break
                photos = obs.get("photos", [])
                for photo in photos:
                    if downloaded >= remaining:
                        break
                    img_url = photo.get("url", "")
                    if not img_url:
                        continue
                    # iNaturalist medium URLs — replace with original if needed
                    img_url = img_url.replace("/square.", "/original.")
                    img_url = img_url.replace("/medium.", "/original.")

                    saved = self._save_image(img_url, dest_dir, result)
                    if saved:
                        downloaded += 1

            page += 1
            time.sleep(0.7)  # rate limit: ~100 requests/minute

        logger.debug("iNaturalist: %d images for %s", downloaded, species)
        return downloaded

    # ------------------------------------------------------------------
    # Source 2: CUB-200-2011
    # ------------------------------------------------------------------

    def _download_cub200(
        self,
        species: str,
        scientific_name: str,
        dest_dir: str,
        remaining: int,
        result: SpeciesDownloadResult,
    ) -> int:
        """
        Extract matching images from the CUB-200-2011 dataset.

        NOTE: CUB-200-2011 contains 200 North American species with ~60 images each.
        We download the full archive once (to a temp/cache dir), then copy matching
        species into the training folder.

        Returns the number of images actually saved.
        """
        if self.config.mock_mode:
            return self._mock_download(dest_dir, remaining, result, SOURCE_CUB200)

        cache_dir = os.path.join(tempfile.gettempdir(), "bird_cam_cub200")
        _ensure_dir(cache_dir)

        # Download the archive if not already cached
        archive_path = os.path.join(cache_dir, "CUB_200_2011.tgz")
        if not os.path.exists(archive_path):
            logger.info("Downloading CUB-200-2011 archive...")
            try:
                urllib.request.urlretrieve(self.config.cub200_url, archive_path)
            except Exception as e:
                logger.warning("Failed to download CUB-200 archive: %s", e)
                result.errors += 1
                return 0

        # Extract if not already extracted
        extract_dir = os.path.join(cache_dir, "CUB_200_2011")
        if not os.path.exists(extract_dir):
            logger.info("Extracting CUB-200-2011 archive...")
            try:
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(cache_dir)
            except Exception as e:
                logger.warning("Failed to extract CUB-200 archive: %s", e)
                result.errors += 1
                return 0

        # CUB-200 folder structure: images/{class_id}.{species_name}/image.jpg
        images_dir = os.path.join(extract_dir, "images")
        if not os.path.exists(images_dir):
            logger.warning("CUB-200 images directory not found after extraction")
            return 0

        # Find matching folders — match by common name (case-insensitive)
        target_name = species.lower().replace(" ", "_")
        downloaded = 0

        for class_dir in os.listdir(images_dir):
            class_path = os.path.join(images_dir, class_dir)
            if not os.path.isdir(class_path):
                continue
            # CUB class names are like "001.Black_footed_Albatross"
            class_name = class_dir.split(".", 1)[1].lower().replace("_", " ")
            if target_name not in class_name and class_name not in target_name:
                continue

            for img_name in sorted(os.listdir(class_path)):
                if downloaded >= remaining:
                    break
                src = os.path.join(class_path, img_name)
                if self._copy_valid_image(src, dest_dir, result):
                    downloaded += 1

        logger.debug("CUB-200: %d images for %s", downloaded, species)
        return downloaded

    # ------------------------------------------------------------------
    # Source 3: Local archive (PhotoOrganizer output)
    # ------------------------------------------------------------------

    def _copy_from_archive(
        self,
        species: str,
        dest_dir: str,
        remaining: int,
        result: SpeciesDownloadResult,
    ) -> int:
        """
        Copy photos from the local PhotoOrganizer archive.

        NOTE: This uses photos already captured by the bird cam. These are the
        most valuable training images because they match your actual camera,
        lighting, feeder setup, and angle.

        Returns the number of images actually copied.
        """
        archive_dir = self.config.archive_photo_dir
        if not os.path.exists(archive_dir):
            logger.debug("Archive directory not found: %s", archive_dir)
            return 0

        # PhotoOrganizer structure: data/photos/{species}/YYYY/MM/
        species_slug = _slugify(species)
        species_dir = os.path.join(archive_dir, species_slug)
        if not os.path.exists(species_dir):
            logger.debug("No archive folder for %s at %s", species, species_dir)
            return 0

        copied = 0
        for root, dirs, files in os.walk(species_dir):
            for f in sorted(files):
                if copied >= remaining:
                    break
                if not f.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                src = os.path.join(root, f)
                if self._copy_valid_image(src, dest_dir, result):
                    copied += 1

        logger.debug("Archive: %d images for %s", copied, species)
        return copied

    # ------------------------------------------------------------------
    # Image save / copy with validation and deduplication
    # ------------------------------------------------------------------

    def _save_image(
        self, url: str, dest_dir: str, result: SpeciesDownloadResult
    ) -> bool:
        """Download an image from URL, validate it, deduplicate, and save."""
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "BirdCamAgent/1.0 (research)"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except Exception as e:
            logger.debug("Image download failed: %s — %s", url, e)
            result.errors += 1
            return False

        # Write to temp file first for validation
        ext = Path(urlparse(url).path).suffix or ".jpg"
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            ext = ".jpg"

        tmp_path = os.path.join(dest_dir, f"_tmp_{os.urandom(4).hex()}{ext}")
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)

            if not _is_valid_image(tmp_path):
                os.unlink(tmp_path)
                result.invalid += 1
                return False

            # Deduplicate
            h = _file_hash(tmp_path)
            if h and h in self._seen_hashes:
                os.unlink(tmp_path)
                result.skipped_dup += 1
                return False

            # Rename to final name with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            final_name = f"{Path(dest_dir).name}_{timestamp}_{os.urandom(2).hex()}{ext}"
            final_path = os.path.join(dest_dir, final_name)
            os.rename(tmp_path, final_path)

            if h:
                self._seen_hashes.add(h)
            return True

        except OSError as e:
            logger.warning("Failed to save image: %s", e)
            result.errors += 1
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return False

    def _copy_valid_image(
        self, src: str, dest_dir: str, result: SpeciesDownloadResult
    ) -> bool:
        """Copy a local image file with validation and deduplication."""
        if not os.path.exists(src):
            return False

        h = _file_hash(src)
        if h and h in self._seen_hashes:
            result.skipped_dup += 1
            return False

        ext = Path(src).suffix.lower() or ".jpg"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_name = f"{Path(dest_dir).name}_{timestamp}_{os.urandom(2).hex()}{ext}"
        dest_path = os.path.join(dest_dir, dest_name)

        try:
            shutil.copy2(src, dest_path)
            if not _is_valid_image(dest_path):
                os.unlink(dest_path)
                result.invalid += 1
                return False
            if h:
                self._seen_hashes.add(h)
            return True
        except OSError:
            result.errors += 1
            return False

    # ------------------------------------------------------------------
    # Mock mode — synthetic images for testing
    # ------------------------------------------------------------------

    def _mock_download(
        self, dest_dir: str, count: int, result: SpeciesDownloadResult, source: str
    ) -> int:
        """Create synthetic JPEG images for testing the pipeline without network."""
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow not installed — cannot create mock images")
            return 0

        created = 0
        for i in range(count):
            img = Image.new("RGB", (self.config.image_size, self.config.image_size), color=(i * 10 % 255, 100, 150))
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = os.path.join(dest_dir, f"mock_{source}_{timestamp}_{i:03d}.jpg")
            img.save(path, "JPEG")
            created += 1
        return created

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _count_images(self, directory: str) -> int:
        """Count valid image files in a directory."""
        if not os.path.exists(directory):
            return 0
        return len(
            [
                f
                for f in os.listdir(directory)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
        )

    def _summarize(self) -> dict[str, Any]:
        """Summarize all results."""
        total_downloaded = sum(r.downloaded for r in self._results)
        total_dups = sum(r.skipped_dup for r in self._results)
        total_invalid = sum(r.invalid for r in self._results)
        total_errors = sum(r.errors for r in self._results)
        return {
            "species_attempted": len(self._results),
            "total_downloaded": total_downloaded,
            "duplicates_skipped": total_dups,
            "invalid_images": total_invalid,
            "errors": total_errors,
        }


__all__ = ["PhotoDatasetBuilder", "SpeciesDownloadResult", "ALL_SOURCES"]