"""
Tests for currency toggle and settings-related logic.

Covers:
- _toggle_currency: USD ↔ last_currency (no-op when no valid alternate)
- _update_currency_ui: updates button label and color
- _toggle_encrypt: toggles encryption setting
- _toggle_pin: toggles pinned state
- _fmt with different currencies in UI context
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import main


def _tk_available():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
        return True
    except Exception:
        return False


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


_BASE_CFG = {
    "refresh_sec": 60, "alpha": 0.93, "timezone": "", "currency": "USD",
    "currency_rate": 1.0, "encrypt_keys": False, "extra_keys": [],
    "mgmt_key": "", "pinned": True, "island_state": "island",
}


def _write_cfg(path, **over):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(_BASE_CFG, **over), f)


def _reject(name):
    raise AssertionError(f"config.json contains non-standard JSON literal {name!r}")


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
        dashboard.cfg = main.load_config()[0]
        dashboard._currency_btn = MagicMock()
        dashboard._tz = main.resolve_tz("")
        return dashboard

    def test_toggle_from_usd_to_last_currency(self, tmp_config_dir):
        """Should toggle from USD to last_currency."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d.cfg["last_currency"] = "CNY"
        d.cfg["currency_rate"] = 7.2
        d._toggle_currency()
        assert d.cfg["currency"] == "CNY"
        assert d.cfg["currency_rate"] == 7.2  # rate preserved

    def test_toggle_from_cny_to_usd(self, tmp_config_dir):
        """Should toggle from CNY back to USD and remember last_currency."""
        d = self._make_dashboard(tmp_config_dir, currency="CNY")
        d.cfg["currency_rate"] = 7.2
        d._toggle_currency()
        assert d.cfg["currency"] == "USD"
        assert d.cfg["last_currency"] == "CNY"
        assert d.cfg["currency_rate"] == 7.2

    def test_toggle_usd_eur_roundtrip_preserves_rate(self, tmp_config_dir):
        """USD ↔ EUR should keep the EUR exchange rate."""
        d = self._make_dashboard(tmp_config_dir, currency="EUR")
        d.cfg["currency_rate"] = 0.92
        d.cfg["last_currency"] = "EUR"
        d._toggle_currency()  # EUR → USD
        assert d.cfg["currency"] == "USD"
        d._toggle_currency()  # USD → EUR
        assert d.cfg["currency"] == "EUR"
        assert d.cfg["currency_rate"] == 0.92

    def test_toggle_updates_ui(self, tmp_config_dir):
        """Should call _update_currency_ui after toggling."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d.cfg["last_currency"] = "EUR"
        with patch.object(d, "_update_currency_ui") as mock_update:
            d._toggle_currency()
            mock_update.assert_called_once()

    def test_toggle_saves_config(self, tmp_config_dir):
        """Should save config after toggling."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d.cfg["last_currency"] = "CNY"
        d._toggle_currency()
        # Config file should be updated
        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["currency"] == "CNY"

    def test_toggle_with_unknown_last_currency(self, tmp_config_dir):
        """Should stay on USD if last_currency is missing or unknown."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d.cfg["last_currency"] = "XYZ"
        d._toggle_currency()
        assert d.cfg["currency"] == "USD"

    def test_toggle_with_no_last_currency(self, tmp_config_dir):
        """Should stay on USD when no alternate currency has been chosen."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d.cfg.pop("last_currency", None)
        d._toggle_currency()
        assert d.cfg["currency"] == "USD"


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
        dashboard.cfg = main.load_config()[0]
        dashboard._currency_btn = MagicMock()
        return dashboard

    def test_usd_shows_dollar_gray(self, tmp_config_dir):
        """USD should show $ in GRAY."""
        d = self._make_dashboard(tmp_config_dir, currency="USD")
        d._update_currency_ui()
        d._currency_btn.config.assert_any_call(text="$")
        d._currency_btn.config.assert_any_call(fg=main.GRAY)

    def test_cny_shows_yuan_yellow(self, tmp_config_dir):
        """CNY should show ¥ in YELLOW."""
        d = self._make_dashboard(tmp_config_dir, currency="CNY")
        d._update_currency_ui()
        d._currency_btn.config.assert_any_call(text="¥")
        d._currency_btn.config.assert_any_call(fg=main.YELLOW)

    def test_eur_shows_euro_yellow(self, tmp_config_dir):
        """EUR should show € in YELLOW."""
        d = self._make_dashboard(tmp_config_dir, currency="EUR")
        d._update_currency_ui()
        d._currency_btn.config.assert_any_call(text="€")
        d._currency_btn.config.assert_any_call(fg=main.YELLOW)

    def test_jpy_shows_yen_yellow(self, tmp_config_dir):
        """JPY should show ¥ in YELLOW."""
        d = self._make_dashboard(tmp_config_dir, currency="JPY")
        d._update_currency_ui()
        d._currency_btn.config.assert_any_call(text="¥")
        d._currency_btn.config.assert_any_call(fg=main.YELLOW)

    def test_unknown_currency_shows_dollar_gray(self, tmp_config_dir):
        """Unknown currency should default to $ in GRAY."""
        d = self._make_dashboard(tmp_config_dir, currency="XYZ")
        d._update_currency_ui()
        d._currency_btn.config.assert_any_call(text="$")
        d._currency_btn.config.assert_any_call(fg=main.GRAY)


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
        dashboard.cfg = main.load_config()[0]
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

        with patch.object(main, "_get_fernet", return_value=MagicMock()):
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

        with patch.object(main, "_get_fernet", return_value=MagicMock()), \
             patch.object(main, "save_config"):
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

        with patch.object(main, "_get_fernet", return_value=MagicMock()):
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

        with patch.object(main, "_get_fernet", return_value=MagicMock()):
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

        with patch.object(main, "_get_fernet", return_value=MagicMock()):
            d._toggle_encrypt(encrypt_var, lock_row)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["encrypt_keys"] is False

    def test_toggle_noop_without_fernet(self, tmp_config_dir):
        """Should not toggle when cryptography/Fernet is unavailable."""
        d = self._make_dashboard(tmp_config_dir, encrypt_keys=True)
        encrypt_var = MagicMock()
        encrypt_var.get.return_value = True
        lock_row = MagicMock()
        with patch.object(main, "_get_fernet", return_value=None):
            d._toggle_encrypt(encrypt_var, lock_row)
        encrypt_var.set.assert_not_called()
        assert d.cfg["encrypt_keys"] is True


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
        dashboard.cfg = main.load_config()[0]
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


class TestSettingsRateWriteBack:
    """The Settings rate field persisted inf/1e400, writing the non-standard
    JSON literal `Infinity` into config.json."""

    def test_settings_field_keeps_current_rate_for_inf(self):
        assert main._sanitize_rate_field("inf", 7.5) == 7.5

    def test_settings_field_keeps_current_rate_for_huge_float(self):
        assert main._sanitize_rate_field("1e400", 7.5) == 7.5

    def test_settings_field_keeps_current_rate_for_garbage(self):
        assert main._sanitize_rate_field("abc", 7.5) == 7.5
        assert main._sanitize_rate_field("", 7.5) == 7.5

    def test_settings_field_accepts_valid_rate(self):
        assert main._sanitize_rate_field("7.25", 1.0) == 7.25

    def test_saved_config_is_strict_json(self, tmp_config_dir):
        _write_cfg(tmp_config_dir, api_key="sk", currency="EUR", currency_rate=7.5)
        cfg = main.load_config()[0]
        cfg["currency_rate"] = main._sanitize_rate_field("inf", cfg["currency_rate"])
        main.save_config(cfg)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            text = f.read()
        assert "Infinity" not in text
        assert json.loads(text, parse_constant=_reject)["currency_rate"] == 7.5


@pytest.mark.skipif(not _tk_available(), reason="Tk display unavailable")
class TestSettingsStaleRateOnCurrencyChange:
    def _drive_save(self, monkeypatch, tmp_config_dir, old_currency, old_rate,
                    new_currency, fetched):
        import tkinter as tk
        import tkinter.ttk as ttk

        # _save ends with _trigger_refresh; keep the worker off the network.
        monkeypatch.setattr(main.Dashboard, '_worker', lambda self, rid: None)
        # Blocking fetch in _save: control the network result.
        monkeypatch.setattr(main, 'fetch_exchange_rate', lambda cur: fetched)

        d = main.Dashboard.__new__(main.Dashboard)
        d.cfg = {
            'api_key': 'sk-or-v1-test', 'refresh_sec': 60,
            'x': None, 'y': None, 'alpha': 0.93, 'timezone': '',
            'currency': old_currency, 'currency_rate': old_rate,
            'encrypt_keys': False, 'extra_keys': [], 'mgmt_key': '',
            'pinned': True, 'island_state': 'island',
        }
        d._tz = main.resolve_tz('')
        d.root = tk.Tk()
        d.root.withdraw()
        # Widgets touched after the config is saved (mock the boundary).
        d._currency_btn = MagicMock()
        d._dot = MagicMock()
        d._status = MagicMock()
        try:
            d._open_settings()
            dlg = next(w for w in d.root.winfo_children()
                       if isinstance(w, tk.Toplevel))

            def as_tuple(values):
                if isinstance(values, str):
                    return (values,)
                return tuple(values)

            currency_combo = next(
                w for w in _walk(dlg)
                if isinstance(w, ttk.Combobox)
                and 'EUR' in as_tuple(w.cget('values'))
                and 'UTC' not in as_tuple(w.cget('values')))
            currency_combo.set(new_currency)

            def entry_value(e):
                name = str(e.cget('textvariable'))
                return d.root.getvar(name) if name and name != 'None' else ''

            rate_entry = next(
                e for e in _walk(dlg)
                if isinstance(e, tk.Entry) and entry_value(e) == str(old_rate))
            assert entry_value(rate_entry) == str(old_rate)  # sanity: stale rate shown

            save_btn = next(w for w in _walk(dlg)
                            if isinstance(w, tk.Button) and w.cget('text') == 'Save')
            save_btn.invoke()
        finally:
            try:
                d.root.destroy()
            except Exception:
                pass

        return json.loads(Path(tmp_config_dir).read_text(encoding='utf-8'))

    def test_switching_currency_without_refetch_does_not_keep_old_rate(
            self, tmp_config_dir, monkeypatch):
        saved = self._drive_save(monkeypatch, tmp_config_dir,
                                 old_currency='CNY', old_rate=7.2,
                                 new_currency='EUR', fetched=0.92)
        assert saved['currency'] == 'EUR'
        assert saved['last_currency'] == 'EUR'
        # Stale CNY rate must not be applied to euros; blocking fetch wins.
        assert saved['currency_rate'] == pytest.approx(0.92)

    def test_switching_to_usd_resets_rate_without_network(
            self, tmp_config_dir, monkeypatch):
        import tkinter as tk
        saved = self._drive_save(monkeypatch, tmp_config_dir,
                                 old_currency='CNY', old_rate=7.2,
                                 new_currency='USD', fetched=None)
        assert saved['currency'] == 'USD'
        assert saved['currency_rate'] == pytest.approx(1.0)

    def test_fetch_failure_falls_back_to_1_not_stale(
            self, tmp_config_dir, monkeypatch):
        saved = self._drive_save(monkeypatch, tmp_config_dir,
                                 old_currency='CNY', old_rate=7.2,
                                 new_currency='EUR', fetched=None)
        assert saved['currency'] == 'EUR'
        assert saved['currency_rate'] == pytest.approx(1.0)

    def test_same_currency_keeps_hand_edited_rate(
            self, tmp_config_dir, monkeypatch):
        import tkinter as tk
        import tkinter.ttk as ttk

        monkeypatch.setattr(main.Dashboard, '_worker', lambda self, rid: None)
        calls = []
        monkeypatch.setattr(main, 'fetch_exchange_rate',
                            lambda cur: calls.append(cur) or 0.92)

        d = main.Dashboard.__new__(main.Dashboard)
        d.cfg = {
            'api_key': 'sk-or-v1-test', 'refresh_sec': 60,
            'x': None, 'y': None, 'alpha': 0.93, 'timezone': '',
            'currency': 'EUR', 'currency_rate': 0.5,
            'encrypt_keys': False, 'extra_keys': [], 'mgmt_key': '',
            'pinned': True, 'island_state': 'island',
        }
        d._tz = main.resolve_tz('')
        d.root = tk.Tk()
        d.root.withdraw()
        d._currency_btn = MagicMock()
        d._dot = MagicMock()
        d._status = MagicMock()
        try:
            d._open_settings()
            dlg = next(w for w in d.root.winfo_children()
                       if isinstance(w, tk.Toplevel))

            def entry_value(e):
                name = str(e.cget('textvariable'))
                return d.root.getvar(name) if name and name != 'None' else ''

            rate_entry = next(
                e for e in _walk(dlg)
                if isinstance(e, tk.Entry) and entry_value(e) == '0.5')
            var_name = str(rate_entry.cget('textvariable'))
            d.root.setvar(var_name, '0.61')

            save_btn = next(w for w in _walk(dlg)
                            if isinstance(w, tk.Button) and w.cget('text') == 'Save')
            save_btn.invoke()
        finally:
            try:
                d.root.destroy()
            except Exception:
                pass

        saved = json.loads(Path(tmp_config_dir).read_text(encoding='utf-8'))
        assert saved['currency'] == 'EUR'
        assert saved['currency_rate'] == pytest.approx(0.61)
        assert calls == []
