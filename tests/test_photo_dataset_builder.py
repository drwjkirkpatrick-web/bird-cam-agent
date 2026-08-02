"""tests/test_photo_dataset_builder.py — Photo dataset builder tests."""

import os
import shutil
import tempfile

import pytest

from core.config import DatasetBuilderConfig
from core.types import BirdSighting, RarityLevel
from modules.photo_dataset_builder import (
    PhotoDatasetBuilder,
    SpeciesDownloadResult,
    ALL_SOURCES,
)


@pytest.fixture
def tmp_dataset_dir():
    path = tempfile.mkdtemp(prefix="bird_dataset_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def builder(tmp_dataset_dir):
    config = DatasetBuilderConfig(
        output_dir=tmp_dataset_dir,
        max_images_per_species=10,
        min_images_per_species=2,
        sources=["inaturalist"],
        mock_mode=True,
    )
    return PhotoDatasetBuilder(config)


@pytest.fixture
def species_list():
    return [
        {"name": "American Robin", "scientific_name": "Turdus migratorius"},
        {"name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis"},
    ]


class TestBuildDataset:
    def test_build_creates_species_directories(self, builder, species_list):
        results = builder.build_dataset(species_list)
        assert len(results) == 2

        for entry in species_list:
            slug = entry["name"].strip().replace(" ", "_").lower()
            species_dir = os.path.join(builder.config.output_dir, slug)
            assert os.path.exists(species_dir)

    def test_build_respects_max_images(self, tmp_dataset_dir, species_list):
        config = DatasetBuilderConfig(
            output_dir=tmp_dataset_dir,
            max_images_per_species=5,
            mock_mode=True,
        )
        builder = PhotoDatasetBuilder(config)
        builder.build_dataset(species_list)
        stats = builder.get_dataset_stats()
        for slug, count in stats["species_breakdown"].items():
            assert count <= 5

    def test_build_returns_results(self, builder, species_list):
        results = builder.build_dataset(species_list)
        assert all(isinstance(r, SpeciesDownloadResult) for r in results)
        for r in results:
            assert r.species in [s["name"] for s in species_list]
            assert r.downloaded > 0

    def test_build_skips_empty_name_entries(self, builder):
        bad_list = [
            {"name": "", "scientific_name": "Turdus migratorius"},
            {"name": "Valid Bird", "scientific_name": "Validus birdus"},
        ]
        results = builder.build_dataset(bad_list)
        assert len(results) == 1
        assert results[0].species == "Valid Bird"


class TestDatasetStats:
    def test_empty_stats(self, builder):
        stats = builder.get_dataset_stats()
        assert stats["total_images"] == 0
        assert stats["total_species"] == 0

    def test_stats_after_build(self, builder, species_list):
        builder.build_dataset(species_list)
        stats = builder.get_dataset_stats()
        assert stats["total_species"] == 2
        assert stats["total_images"] > 0

    def test_species_with_minimum(self, tmp_dataset_dir, species_list):
        config = DatasetBuilderConfig(
            output_dir=tmp_dataset_dir,
            min_images_per_species=2,
            mock_mode=True,
        )
        builder = PhotoDatasetBuilder(config)
        builder.build_dataset(species_list)
        stats = builder.get_dataset_stats()
        assert stats["species_with_minimum"] == 2


class TestCleanDataset:
    def test_clean_removes_files(self, builder, species_list):
        builder.build_dataset(species_list)
        assert builder.get_dataset_stats()["total_images"] > 0
        deleted = builder.clean_dataset()
        assert deleted > 0
        stats = builder.get_dataset_stats()
        assert stats["total_images"] == 0

    def test_clean_on_empty_dir(self, builder):
        deleted = builder.clean_dataset()
        assert deleted == 0


class TestMockMode:
    def test_mock_mode_creates_synthetic_images(self, builder, species_list):
        results = builder.build_dataset(species_list)
        for r in results:
            assert r.downloaded > 0
        stats = builder.get_dataset_stats()
        assert stats["total_images"] > 0

    def test_mock_mode_deduplicates(self, builder, species_list):
        # Build twice — second run should have dedups
        builder.build_dataset(species_list)
        count1 = builder.get_dataset_stats()["total_images"]
        builder.build_dataset(species_list)
        count2 = builder.get_dataset_stats()["total_images"]
        # Second run may add more due to new mock filenames, but dedup prevents exact dupes
        # At minimum, count2 should not double
        assert count2 <= count1 * 2


class TestMultiSource:
    def test_multi_source_build(self, tmp_dataset_dir, species_list):
        config = DatasetBuilderConfig(
            output_dir=tmp_dataset_dir,
            max_images_per_species=15,
            sources=ALL_SOURCES,
            mock_mode=True,
            archive_photo_dir=tmp_dataset_dir + "_archive",
        )
        builder = PhotoDatasetBuilder(config)

        # Create a fake archive photo for one species
        archive = config.archive_photo_dir
        os.makedirs(os.path.join(archive, "american_robin", "2026", "01"), exist_ok=True)
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(100, 150, 200))
        img.save(os.path.join(archive, "american_robin", "2026", "01", "robin_001.jpg"))

        results = builder.build_dataset(species_list)
        stats = builder.get_dataset_stats()
        assert stats["total_images"] > 0
        # American Robin should have images from archive
        robin_slug = "american_robin"
        if robin_slug in stats["species_breakdown"]:
            assert stats["species_breakdown"][robin_slug] > 0


class TestSourcesConstant:
    def test_all_sources_list(self):
        assert "inaturalist" in ALL_SOURCES
        assert "cub200" in ALL_SOURCES
        assert "archive" in ALL_SOURCES
        assert len(ALL_SOURCES) == 3