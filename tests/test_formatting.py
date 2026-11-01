"""
Tests for _fmt and _fmt2 currency formatting methods.

_fmt: formats a USD float according to current currency (used for spend amounts)
_fmt2: formats with 2 decimal places (used for balance / limit)

Both methods depend on self.cfg['currency'] and self.cfg['currency_rate'].
"""
import json

import pytest

import main


def _dashboard_with_cfg(cfg):
    dashboard = main.Dashboard.__new__(main.Dashboard)
    dashboard.cfg = cfg
    return dashboard


_BASE_CFG = {
    "refresh_sec": 60, "alpha": 0.93, "timezone": "", "currency": "USD",
    "currency_rate": 1.0, "encrypt_keys": False, "extra_keys": [],
    "mgmt_key": "", "pinned": True, "island_state": "island",
}


def _write_cfg(path, **over):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(_BASE_CFG, **over), f)


class TestFmt:
    """Tests for Dashboard._fmt."""

    def _make_dashboard(self, currency="USD", rate=1.0):
        """Create a Dashboard-like object without calling __init__."""
        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = {"currency": currency, "currency_rate": rate}
        return dashboard

    def test_usd_formatting(self):
        """USD should format with $ and 2 decimal places."""
        d = self._make_dashboard("USD", 1.0)
        assert d._fmt(10.5) == "$10.50"
        assert d._fmt(0) == "$0.00"
        assert d._fmt(1234.5678) == "$1234.57"

    def test_cny_formatting(self):
        """CNY should convert using rate and format with ¥."""
        d = self._make_dashboard("CNY", 7.2)
        assert d._fmt(10.0) == "¥72.00"
        assert d._fmt(0) == "¥0.00"

    def test_eur_formatting(self):
        """EUR should convert using rate and format with €."""
        d = self._make_dashboard("EUR", 0.92)
        assert d._fmt(10.0) == "€9.20"

    def test_jpy_zero_decimal(self):
        """JPY should format with 0 decimal places."""
        d = self._make_dashboard("JPY", 150.0)
        assert d._fmt(10.0) == "¥1500"
        assert d._fmt(0.5) == "¥75"

    def test_krw_zero_decimal(self):
        """KRW should format with 0 decimal places."""
        d = self._make_dashboard("KRW", 1400.0)
        assert d._fmt(10.0) == "₩14000"

    def test_unknown_currency_defaults_to_usd(self):
        """Unknown currency should default to USD formatting."""
        d = self._make_dashboard("XYZ", 1.0)
        assert d._fmt(10.5) == "$10.50"

    def test_negative_value(self):
        """Should handle negative values."""
        d = self._make_dashboard("USD", 1.0)
        assert d._fmt(-5.0) == "$-5.00"

    def test_large_value(self):
        """Should handle large values."""
        d = self._make_dashboard("USD", 1.0)
        assert d._fmt(1000000.0) == "$1000000.00"

    def test_all_supported_currencies(self):
        """All currencies in CURRENCIES should format without error."""
        for currency in main.CURRENCIES:
            d = self._make_dashboard(currency, 1.0)
            result = d._fmt(10.0)
            assert isinstance(result, str)
            assert len(result) > 0


class TestFmt2:
    """Tests for Dashboard._fmt2."""

    def _make_dashboard(self, currency="USD", rate=1.0):
        """Create a Dashboard-like object without calling __init__."""
        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = {"currency": currency, "currency_rate": rate}
        return dashboard

    def test_usd_formatting(self):
        """USD should format with $ and 2 decimal places."""
        d = self._make_dashboard("USD", 1.0)
        assert d._fmt2(10.5) == "$10.50"
        assert d._fmt2(0) == "$0.00"

    def test_cny_formatting(self):
        """CNY should convert using rate and format with ¥."""
        d = self._make_dashboard("CNY", 7.2)
        assert d._fmt2(10.0) == "¥72.00"

    def test_jpy_zero_decimal(self):
        """JPY should format with 0 decimal places."""
        d = self._make_dashboard("JPY", 150.0)
        assert d._fmt2(10.0) == "¥1500"

    def test_unknown_currency_defaults_to_usd(self):
        """Unknown currency should default to USD formatting."""
        d = self._make_dashboard("XYZ", 1.0)
        assert d._fmt2(10.5) == "$10.50"

    def test_negative_value(self):
        """Should handle negative values."""
        d = self._make_dashboard("USD", 1.0)
        assert d._fmt2(-5.0) == "$-5.00"

    def test_all_supported_currencies(self):
        """All currencies in CURRENCIES should format without error."""
        for currency in main.CURRENCIES:
            d = self._make_dashboard(currency, 1.0)
            result = d._fmt2(10.0)
            assert isinstance(result, str)
            assert len(result) > 0


class TestFmtBadRate:
    """Non-numeric currency_rate crashed _fmt during UI updates."""

    def test_non_numeric_rate_does_not_raise(self):
        d = _dashboard_with_cfg({"currency": "EUR", "currency_rate": "?"})
        assert d._fmt(10.0) == "€10.00"

    def test_none_rate_does_not_raise(self):
        d = _dashboard_with_cfg({"currency": "EUR", "currency_rate": None})
        assert d._fmt(10.0) == "€10.00"


class TestNonFiniteRate:
    """currency_rate 'inf' is numeric and positive, so it passed the guard and
    rendered every amount as '€inf'."""

    def test_inf_rate_falls_back_to_default(self):
        assert main._currency_rate("inf") == 1.0
        assert main._currency_rate(float("inf")) == 1.0

    def test_nan_rate_falls_back_to_default(self):
        assert main._currency_rate("nan") == 1.0

    def test_fmt_with_inf_rate_renders_no_inf(self):
        d = _dashboard_with_cfg({"currency": "EUR", "currency_rate": float("inf")})
        assert d._fmt(10.0) == "€10.00"

    def test_inf_rate_in_config_does_not_render_inf(self, tmp_config_dir):
        _write_cfg(tmp_config_dir, api_key="sk", currency="EUR", currency_rate="inf")
        cfg = main.load_config()[0]
        assert _dashboard_with_cfg(cfg)._fmt(10.0) == "€10.00"
