"""
Tests for resolve_tz — timezone resolution logic.

Covers:
- Empty / None / whitespace → system local
- Numeric offset strings → fixed offset timezone
- IANA zone names → ZoneInfo
- Unknown IANA name → fallback to system local with warning
"""
import sys
from datetime import timezone, timedelta
from unittest.mock import patch

import pytest

import main


class TestResolveTz:
    """Tests for the resolve_tz function."""

    def test_empty_string_returns_system_local(self):
        """Empty string should return system local timezone."""
        result = main.resolve_tz("")
        # Should be a tzinfo object (not None)
        assert result is not None

    def test_none_returns_system_local(self):
        """None should return system local timezone."""
        result = main.resolve_tz(None)
        assert result is not None

    def test_whitespace_returns_system_local(self):
        """Whitespace-only string should return system local timezone."""
        result = main.resolve_tz("   ")
        assert result is not None

    def test_numeric_offset_positive(self):
        """Positive numeric offset should produce a fixed-offset timezone."""
        result = main.resolve_tz("8")
        assert result == timezone(timedelta(hours=8))

    def test_numeric_offset_negative(self):
        """Negative numeric offset should produce a fixed-offset timezone."""
        result = main.resolve_tz("-5")
        assert result == timezone(timedelta(hours=-5))

    def test_numeric_offset_fractional(self):
        """Fractional numeric offset should produce a fixed-offset timezone."""
        result = main.resolve_tz("5.75")
        assert result == timezone(timedelta(hours=5, minutes=45))

    def test_numeric_offset_negative_fractional(self):
        """Negative fractional numeric offset should produce a fixed-offset timezone."""
        result = main.resolve_tz("-3.5")
        assert result == timezone(timedelta(hours=-3, minutes=-30))

    def test_iana_zone_utc(self):
        """UTC should resolve to a ZoneInfo object."""
        result = main.resolve_tz("UTC")
        # ZoneInfo('UTC') should equal timezone.utc
        assert result == timezone.utc

    def test_iana_zone_asia_shanghai(self):
        """Asia/Shanghai should resolve to a ZoneInfo object."""
        result = main.resolve_tz("Asia/Shanghai")
        # Should be a ZoneInfo instance
        from zoneinfo import ZoneInfo
        assert isinstance(result, ZoneInfo)

    def test_iana_zone_europe_berlin(self):
        """Europe/Berlin should resolve to a ZoneInfo object."""
        result = main.resolve_tz("Europe/Berlin")
        from zoneinfo import ZoneInfo
        assert isinstance(result, ZoneInfo)

    def test_unknown_iana_falls_back_to_system_local(self):
        """Unknown IANA zone name should fall back to system local with a warning."""
        with patch("builtins.print") as mock_print:
            result = main.resolve_tz("Invalid/Zone_Name")
            # Should have printed a warning
            mock_print.assert_called_once()
            # The warning should mention the unknown timezone
            call_args = mock_print.call_args
            assert "Invalid/Zone_Name" in str(call_args)
        # Should still return a valid tzinfo
        assert result is not None

    def test_numeric_offset_takes_precedence_over_iana(self):
        """Numeric strings should be treated as offsets, not IANA names."""
        # '8' is numeric, should be offset, not a zone name
        result = main.resolve_tz("8")
        assert result == timezone(timedelta(hours=8))

    def test_whitespace_around_numeric(self):
        """Whitespace around numeric offset should be stripped."""
        result = main.resolve_tz("  8  ")
        assert result == timezone(timedelta(hours=8))

    def test_whitespace_around_iana(self):
        """Whitespace around IANA zone name should be stripped."""
        result = main.resolve_tz("  UTC  ")
        assert result == timezone.utc
