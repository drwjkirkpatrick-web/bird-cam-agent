"""tests/test_call_library.py"""

import os
import tempfile

import pytest
from modules.call_library import CallLibrary

@pytest.fixture
def library(tmp_path):
    return CallLibrary(str(tmp_path / "calls"))

@pytest.fixture
def audio_file(tmp_path):
    p = tmp_path / "robin.mp3"
    p.write_bytes(b"fake audio data")
    return str(p)

class TestLibrary:
    def test_add_call(self, library, audio_file):
        assert library.add_call("American Robin", audio_file, "cheer-up") is True
    def test_get_calls(self, library, audio_file):
        library.add_call("American Robin", audio_file)
        calls = library.get_calls("American Robin")
        assert len(calls) == 1
    def test_search(self, library, audio_file):
        library.add_call("American Robin", audio_file, "cheerily")
        results = library.search_calls("robin")
        assert len(results) >= 1
    def test_list_species(self, library, audio_file):
        library.add_call("Robin", audio_file)
        library.add_call("Crow", audio_file)
        species = library.list_all_species()
        assert len(species) == 2
    def test_stats(self, library, audio_file):
        library.add_call("Robin", audio_file)
        stats = library.get_stats()
        assert stats["total_species"] == 1
    def test_remove_call(self, library, audio_file):
        library.add_call("Robin", audio_file)
        assert library.remove_call("Robin", audio_file) is True
    def test_species_count(self, library, audio_file):
        library.add_call("Robin", audio_file)
        assert library.species_count == 1
