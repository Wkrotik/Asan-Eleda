"""Unit tests for core/metadata.py functions."""
from __future__ import annotations

import math
import pytest

from core.metadata import haversine_m, _dms_to_deg, _rational_to_float


class TestHaversineM:
    """Tests for haversine_m distance calculation."""

    def test_same_point_returns_zero(self):
        """Distance from a point to itself should be 0."""
        result = haversine_m(lat1=40.4093, lon1=49.8671, lat2=40.4093, lon2=49.8671)
        assert result == 0.0

    def test_known_distance_baku_to_nyc(self):
        """Distance from Baku to NYC should be approximately 9360km."""
        # Baku: 40.4093, 49.8671
        # NYC: 40.7128, -74.0060
        result = haversine_m(lat1=40.4093, lon1=49.8671, lat2=40.7128, lon2=-74.0060)
        # Actual distance is ~9,362 km (haversine formula)
        assert 9_300_000 < result < 9_400_000

    def test_short_distance_approximately_100m(self):
        """Test a short distance calculation (approx 100m)."""
        # ~100m north of origin point
        # 1 degree latitude ≈ 111km, so 0.0009 degrees ≈ 100m
        result = haversine_m(lat1=0.0, lon1=0.0, lat2=0.0009, lon2=0.0)
        assert 90 < result < 110

    def test_antipodal_points(self):
        """Distance between antipodal points should be ~20,000km (half Earth circumference)."""
        result = haversine_m(lat1=0.0, lon1=0.0, lat2=0.0, lon2=180.0)
        # Half Earth circumference is ~20,037km
        assert 19_900_000 < result < 20_100_000

    def test_north_south_pole(self):
        """Distance from North to South pole should be ~20,000km."""
        result = haversine_m(lat1=90.0, lon1=0.0, lat2=-90.0, lon2=0.0)
        assert 19_900_000 < result < 20_100_000

    def test_negative_coordinates(self):
        """Should handle negative coordinates correctly."""
        # Sydney to Buenos Aires (both southern hemisphere)
        result = haversine_m(lat1=-33.8688, lon1=151.2093, lat2=-34.6037, lon2=-58.3816)
        # Actual distance is ~11,800 km
        assert 11_500_000 < result < 12_000_000


class TestRationalToFloat:
    """Tests for _rational_to_float helper."""

    def test_tuple_fraction(self):
        """Tuple (numerator, denominator) should be converted to float."""
        result = _rational_to_float((3, 2))
        assert result == 1.5

    def test_tuple_whole_number(self):
        """Tuple (n, 1) should return n as float."""
        result = _rational_to_float((42, 1))
        assert result == 42.0

    def test_float_passthrough(self):
        """Float input should pass through unchanged."""
        result = _rational_to_float(1.5)
        assert result == 1.5

    def test_int_passthrough(self):
        """Int input should be converted to float."""
        result = _rational_to_float(42)
        assert result == 42.0

    def test_zero_denominator_returns_none(self):
        """Division by zero should return None, not raise."""
        result = _rational_to_float((1, 0))
        assert result is None

    def test_none_returns_none(self):
        """None input should return None."""
        result = _rational_to_float(None)
        assert result is None

    def test_invalid_type_returns_none(self):
        """Invalid type should return None."""
        result = _rational_to_float("not a number")
        assert result is None


class TestDmsToDeg:
    """Tests for _dms_to_deg (degrees-minutes-seconds to decimal degrees)."""

    def test_north_latitude(self):
        """North latitude should be positive."""
        # 40° 24' 35.3" N
        dms = (40, 24, 35.3)
        result = _dms_to_deg(dms, "N")
        assert result is not None
        assert 40.409 < result < 40.410

    def test_south_latitude(self):
        """South latitude should be negative."""
        # 40° 24' 35.3" S
        dms = (40, 24, 35.3)
        result = _dms_to_deg(dms, "S")
        assert result is not None
        assert -40.410 < result < -40.409

    def test_east_longitude(self):
        """East longitude should be positive."""
        # 49° 52' 1.6" E
        dms = (49, 52, 1.6)
        result = _dms_to_deg(dms, "E")
        assert result is not None
        assert 49.867 < result < 49.868

    def test_west_longitude(self):
        """West longitude should be negative."""
        # 74° 0' 21.6" W
        dms = (74, 0, 21.6)
        result = _dms_to_deg(dms, "W")
        assert result is not None
        assert -74.007 < result < -74.005

    def test_none_ref_defaults_positive(self):
        """None reference should default to positive."""
        dms = (40, 24, 35.3)
        result = _dms_to_deg(dms, None)
        assert result is not None
        assert result > 0

    def test_none_dms_returns_none(self):
        """None DMS input should return None."""
        result = _dms_to_deg(None, "N")
        assert result is None

    def test_partial_dms_returns_none(self):
        """Incomplete DMS tuple should return None."""
        result = _dms_to_deg((40, 24), "N")  # Missing seconds
        assert result is None

    def test_rational_tuple_dms(self):
        """DMS values can be (numerator, denominator) tuples."""
        # 40° 24' 35.3" expressed as rationals
        dms = ((40, 1), (24, 1), (353, 10))
        result = _dms_to_deg(dms, "N")
        assert result is not None
        assert 40.409 < result < 40.410

    def test_zero_coordinates(self):
        """Zero coordinates should work correctly."""
        dms = (0, 0, 0)
        result = _dms_to_deg(dms, "N")
        assert result == 0.0
