"""Pytest configuration and shared fixtures for Asan Eleda tests."""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def tmp_path_factory_wrapper(tmp_path: Path) -> Path:
    """Alias for tmp_path that's clearer in test context."""
    return tmp_path


@pytest.fixture
def sample_gps_coords() -> dict:
    """Sample GPS coordinates for testing (Baku, Azerbaijan)."""
    return {
        "lat": 40.4093,
        "lon": 49.8671,
    }


@pytest.fixture
def sample_gps_coords_nyc() -> dict:
    """Sample GPS coordinates for testing (New York City)."""
    return {
        "lat": 40.7128,
        "lon": -74.0060,
    }
