"""
tests/conftest.py — Shared pytest fixtures and path setup for the Bird Cam Agent.

NOTE: Adding the project root to sys.path lets tests do `from core...` and
      `from modules...` without a packaged install. This keeps the test
      suite runnable directly via `pytest` from the repo root.
"""

import os
import sys

# WHY: pytest is invoked from the project root, but Python's sys.path
#      starts at the tests/ dir. Inserting the project root once, at
#      collection time, makes the package-style imports work everywhere.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)