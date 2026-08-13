"""
Tests for currency toggle and settings-related logic.

Covers:
- _toggle_currency: cycles through currencies correctly
- _update_currency_ui: updates button label and color
- _toggle_encrypt: toggles encryption setting
- _toggle_pin: toggles pinned state
- _fmt with different currencies in UI context
"""
import json
from unittest.mock import patch, MagicMock

import pytest

import main


class TestToggleCurrency:
    """Tests for Dashboard._toggle_currency."""

    def _make_dashboard(self, tmp_config_dir, currency="USD"):
        """Create a Dashboard-like object with mocked UI widgets."""
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": currency,
            "currency_rate": 1.0,
            "encrypt_keys": False,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()
        dashboard._cny_btn = MagicMock()
        dashboard._last_data = None
        dashboard._tz = main.resolve_tz("")
        return dashboard

    def test_toggle_from_usd_to_next(self, tmp_config_dir):
        """Should cycle from USD to the next currency in the list."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d._toggle_currency()
        # USD is index 0, next should be CNY (index 1)
        assert d.cfg["currency"] == "CNY"

    def test_toggle_from_cny_to_next(self, tmp_config_dir):
        """Should cycle from CNY to EUR."""
        d = self._make_dashboard(tmp_config_dir, currency="CNY")
        d._toggle_currency()
        assert d.cfg["currency"] == "EUR"

    def test_toggle_wraps_around(self, tmp_config_dir):
        """Should wrap around to USD from the last currency."""
        last_currency = list(main.CURRENCIES.keys())[-1]
        d = self._make_dashboard(tmp_config_dir, currency=last_currency)
        d._toggle_currency()
        assert d.cfg["currency"] == "USD"

    def test_toggle_updates_ui(self, tmp_config_dir):
        """Should call _update_currency_ui after toggling."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        with patch.object(d, "_update_currency_ui") as mock_update:
            d._toggle_currency()
            mock_update.assert_called_once()

    def test_toggle_saves_config(self, tmp_config_dir):
        """Should save config after toggling."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d._toggle_currency()
        # Config file should be updated
        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["currency"] == "CNY"

    def test_toggle_with_unknown_currency(self, tmp_config_dir):
        """Should start from USD if current currency is unknown."""
        d = self._make_dashboard(tmp_config_dir, currency="XYZ")
        d._toggle_currency()
        # Unknown currency → index 0 → next is CNY
        assert d.cfg["currency"] == "CNY"


class TestUpdateCurrencyUi:
    """Tests for Dashboard._update_currency_ui."""

    def _make_dashboard(self, tmp_config_dir, currency="USD"):
        """Create a Dashboard-like object with mocked UI widgets."""
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": currency,
            "currency_rate": 1.0,
            "encrypt_keys": False,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()
        dashboard._cny_btn = MagicMock()
        return dashboard

    def test_usd_shows_dollar_gray(self, tmp_config_dir):
        """USD should show $ in GRAY."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d._update_currency_ui()
        d._cny_btn.config.assert_any_call(text="$")
        d._cny_btn.config.assert_any_call(fg=main.GRAY)

    def test_cny_shows_yuan_yellow(self, tmp_config_dir):
        """CNY should show ¥ in YELLOW."""
        d = self._make_dashboard(tmp_config_dir, currency="CNY")
        d._update_currency_ui()
        d._cny_btn.config.assert_any_call(text="¥")
        d._cny_btn.config.assert_any_call(fg=main.YELLOW)

    def test_eur_shows_euro_yellow(self, tmp_config_dir):
        """EUR should show € in YELLOW."""
        d = self._make_dashboard(tmp_config_dir, currency="EUR")
        d._update_currency_ui()
        d._cny_btn.config.assert_any_call(text="€")
        d._cny_btn.config.assert_any_call(fg=main.YELLOW)

    def test_jpy_shows_yen_yellow(self, tmp_config_dir):
        """JPY should show ¥ in YELLOW."""
        d = self._make_dashboard(tmp_config_dir, currency="JPY")
        d._update_currency_ui()
        d._cny_btn.config.assert_any_call(text="¥")
        d._cny_btn.config.assert_any_call(fg=main.YELLOW)

    def test_unknown_currency_shows_dollar_gray(self, tmp_config_dir):
        """Unknown currency should default to $ in GRAY."""
        d = self._make_dashboard(tmp_config_dir, currency="XYZ")
        d._update_currency_ui()
        d._cny_btn.config.assert_any_call(text="$")
        d._cny_btn.config.assert_any_call(fg=main.GRAY)


class TestToggleEncrypt:
    """Tests for Dashboard._toggle_encrypt."""

    def _make_dashboard(self, tmp_config_dir, encrypt_keys=True):
        """Create a Dashboard-like object with mocked UI widgets."""
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": encrypt_keys,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()
        return dashboard

    def test_toggle_from_true_to_false(self, tmp_config_dir):
        """Should toggle encrypt_keys from True to False."""
        d = self._make_dashboard(tmp_config_dir, encrypt_keys=True)
        encrypt_var = MagicMock()
        encrypt_var.get.return_value = True
        encrypt_var.set = MagicMock()

        lock_row = MagicMock()
        lock_icon = MagicMock()
        lock_btn = MagicMock()
        lock_row.winfo_children.return_value = [lock_icon, lock_btn]

        d._toggle_encrypt(encrypt_var, lock_row)

        encrypt_var.set.assert_called_with(False)
        assert d.cfg["encrypt_keys"] is False

    def test_toggle_from_false_to_true(self, tmp_config_dir):
        """Should toggle encrypt_keys from False to True."""
        d = self._make_dashboard(tmp_config_dir, encrypt_keys=False)
        encrypt_var = MagicMock()
        encrypt_var.get.return_value = False
        encrypt_var.set = MagicMock()

        lock_row = MagicMock()
        lock_icon = MagicMock()
        lock_btn = MagicMock()
        lock_row.winfo_children.return_value = [lock_icon, lock_btn]

        d._toggle_encrypt(encrypt_var, lock_row)

        encrypt_var.set.assert_called_with(True)
        assert d.cfg["encrypt_keys"] is True

    def test_toggle_updates_lock_icon_color(self, tmp_config_dir):
        """Should update lock icon color based on encryption state."""
        d = self._make_dashboard(tmp_config_dir, encrypt_keys=True)
        encrypt_var = MagicMock()
        encrypt_var.get.return_value = True
        encrypt_var.set = MagicMock()

        lock_row = MagicMock()
        lock_icon = MagicMock()
        lock_btn = MagicMock()
        lock_row.winfo_children.return_value = [lock_icon, lock_btn]

        d._toggle_encrypt(encrypt_var, lock_row)

        # After toggling to False, lock icon should be GRAY
        lock_icon.config.assert_called_with(fg=main.GRAY)

    def test_toggle_updates_lock_button_text(self, tmp_config_dir):
        """Should update lock button text based on encryption state."""
        d = self._make_dashboard(tmp_config_dir, encrypt_keys=True)
        encrypt_var = MagicMock()
        encrypt_var.get.return_value = True
        encrypt_var.set = MagicMock()

        lock_row = MagicMock()
        lock_icon = MagicMock()
        lock_btn = MagicMock()
        lock_row.winfo_children.return_value = [lock_icon, lock_btn]

        d._toggle_encrypt(encrypt_var, lock_row)

        # After toggling to False, button should say "Store keys unencrypted"
        lock_btn.config.assert_called_with(text="Store keys unencrypted")

    def test_toggle_saves_config(self, tmp_config_dir):
        """Should save config after toggling encryption."""
        d = self._make_dashboard(tmp_config_dir, encrypt_keys=True)
        encrypt_var = MagicMock()
        encrypt_var.get.return_value = True
        encrypt_var.set = MagicMock()

        lock_row = MagicMock()
        lock_row.winfo_children.return_value = [MagicMock(), MagicMock()]

        d._toggle_encrypt(encrypt_var, lock_row)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["encrypt_keys"] is False


class TestTogglePin:
    """Tests for Dashboard._toggle_pin."""

    def _make_dashboard(self, tmp_config_dir, pinned=True):
        """Create a Dashboard-like object with mocked UI widgets."""
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": False,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": pinned,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()
        dashboard._pinned = pinned
        dashboard.root = MagicMock()
        dashboard._pin_lbl = MagicMock()
        return dashboard

    def test_toggle_from_pinned_to_unpinned(self, tmp_config_dir):
        """Should toggle from pinned to unpinned."""
        d = self._make_dashboard(tmp_config_dir, pinned=True)
        d._toggle_pin()
        assert d._pinned is False
        d.root.attributes.assert_called_with("-topmost", False)
        d._pin_lbl.config.assert_called_with(fg=main.GRAY)

    def test_toggle_from_unpinned_to_pinned(self, tmp_config_dir):
        """Should toggle from unpinned to pinned."""
        d = self._make_dashboard(tmp_config_dir, pinned=False)
        d._toggle_pin()
        assert d._pinned is True
        d.root.attributes.assert_called_with("-topmost", True)
        d._pin_lbl.config.assert_called_with(fg=main.WHITE)

    def test_toggle_saves_config(self, tmp_config_dir):
        """Should save config after toggling pin."""
        d = self._make_dashboard(tmp_config_dir, pinned=True)
        d._toggle_pin()
        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["pinned"] is False
