"""
Tests for locale-aware short date formatting.

The _format_date_locale method formats YYYY-MM-DD date strings according to
the user's configured IANA timezone, using a built-in TZ_TO_LOCALE mapping
and LOCALE_PATTERNS table. No locale.setlocale calls are made.
"""
import locale as locale_module

import pytest

import main


class TestFormatDateLocale:
    """Tests for Dashboard._format_date_locale."""

    def _make_dashboard(self, timezone=""):
        """Create a Dashboard-like object without calling __init__."""
        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = {"timezone": timezone}
        return dashboard

    def test_us_format(self):
        """America/Los_Angeles should produce US short format: MM/DD/YYYY."""
        d = self._make_dashboard("America/Los_Angeles")
        assert d._format_date_locale("2026-08-12") == "08/12/2026"

    def test_eu_format(self):
        """Europe/Berlin should produce EU short format: DD/MM/YYYY."""
        d = self._make_dashboard("Europe/Berlin")
        assert d._format_date_locale("2026-08-12") == "12/08/2026"

    def test_cn_format(self):
        """Asia/Shanghai should produce Chinese format: YYYY年MM月DD日."""
        d = self._make_dashboard("Asia/Shanghai")
        assert d._format_date_locale("2026-08-12") == "2026年08月12日"

    def test_jp_format(self):
        """Asia/Tokyo should produce Japanese format: YYYY/MM/DD."""
        d = self._make_dashboard("Asia/Tokyo")
        assert d._format_date_locale("2026-08-12") == "2026/08/12"

    def test_ru_format(self):
        """Europe/Moscow should produce Russian format: DD.MM.YYYY."""
        d = self._make_dashboard("Europe/Moscow")
        assert d._format_date_locale("2026-08-12") == "12.08.2026"

    def test_br_format(self):
        """America/Sao_Paulo should produce Brazilian format: DD/MM/YYYY."""
        d = self._make_dashboard("America/Sao_Paulo")
        assert d._format_date_locale("2026-08-12") == "12/08/2026"

    def test_default_format(self):
        """Unknown timezone should fall back to ISO format: YYYY-MM-DD."""
        d = self._make_dashboard("Unknown/Zone")
        assert d._format_date_locale("2026-08-12") == "2026-08-12"

    def test_empty_timezone_format(self):
        """Empty timezone (system local) should fall back to ISO format."""
        d = self._make_dashboard("")
        assert d._format_date_locale("2026-08-12") == "2026-08-12"

    def test_invalid_date_string(self):
        """Invalid date strings should be returned unchanged."""
        d = self._make_dashboard("America/Los_Angeles")
        assert d._format_date_locale("invalid") == "invalid"
        assert d._format_date_locale("") == ""
        assert d._format_date_locale("2026-08") == "2026-08"

    def test_no_locale_mutation(self):
        """_format_date_locale must not call locale.setlocale."""
        before = locale_module.getlocale()
        d = self._make_dashboard("Europe/Berlin")
        d._format_date_locale("2026-08-12")
        after = locale_module.getlocale()
        assert before == after


class TestTzToLocaleMapping:
    """Tests for the TZ_TO_LOCALE mapping completeness."""

    def test_all_common_timezones_mapped(self):
        """Every IANA zone in COMMON_TIMEZONES (except empty/UTC) should map to a known locale key."""
        for tz in main.COMMON_TIMEZONES:
            if tz in ("", "UTC"):
                continue
            locale_key = main.TZ_TO_LOCALE.get(tz)
            assert locale_key is not None, f"Timezone '{tz}' is not in TZ_TO_LOCALE"
            assert locale_key in main.LOCALE_PATTERNS, (
                f"Locale key '{locale_key}' for timezone '{tz}' is not in LOCALE_PATTERNS"
            )

    def test_known_mappings(self):
        """Spot-check a few well-known timezone-to-locale mappings."""
        assert main.TZ_TO_LOCALE["Asia/Shanghai"] == "cn"
        assert main.TZ_TO_LOCALE["Asia/Tokyo"] == "jp"
        assert main.TZ_TO_LOCALE["Europe/Berlin"] == "eu"
        assert main.TZ_TO_LOCALE["America/Los_Angeles"] == "us"
        assert main.TZ_TO_LOCALE["America/Sao_Paulo"] == "br"
        assert main.TZ_TO_LOCALE["Europe/Moscow"] == "ru"

    def test_all_locale_keys_valid(self):
        """Every value in TZ_TO_LOCALE must be a valid key in LOCALE_PATTERNS."""
        for tz, locale_key in main.TZ_TO_LOCALE.items():
            assert locale_key in main.LOCALE_PATTERNS, (
                f"TZ_TO_LOCALE['{tz}'] = '{locale_key}' is not a valid LOCALE_PATTERNS key"
            )
