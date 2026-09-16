"""
Regression tests for bugs reproduced during review.

Each test failed against the pre-fix code; they must keep passing.
"""
import json
from unittest.mock import MagicMock

import pytest

import main
from tests.test_fetch import make_mock_response, route_requests


def _dashboard_with_cfg(cfg):
    dashboard = main.Dashboard.__new__(main.Dashboard)
    dashboard.cfg = cfg
    return dashboard


class TestDuplicateExtraKeys:
    """Identical extra_keys were fetched twice and double-counted."""

    def test_duplicate_extra_keys_are_not_double_counted(self, tmp_config_dir, mock_requests):
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": False,
            "extra_keys": ["sk-or-v1-extra", "sk-or-v1-extra"],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000, "limit_remaining": 800, "label": "Main",
                "usage_daily": 1.0, "usage_monthly": 10.0,
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        extra_response = make_mock_response(json_data={
            "data": {"usage_daily": 5.0, "usage_monthly": 50.0}
        })
        route_requests(
            mock_requests,
            url_responses={"credits": credits_response},
            key_responses={
                "sk-or-v1-test": auth_response,
                "sk-or-v1-extra": extra_response,
            },
        )

        dashboard = _dashboard_with_cfg(main.load_config()[0])
        result = dashboard._fetch()

        assert result["all_daily"] == 6.0  # 1 + 5, not 1 + 5 + 5
        assert result["all_monthly"] == 60.0
        assert mock_requests.call_count == 3


class TestStuckKeyNotSent:
    """Undecryptable Fernet tokens were sent as Bearer credentials."""

    def test_stuck_api_key_is_not_sent_to_openrouter(self, tmp_config_dir, mock_requests):
        stuck = "gAAAAA-not-a-real-token"
        config = {
            "api_key": stuck,
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": True,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        cfg, stuck_fields, _ = main.load_config()
        assert "api_key" in stuck_fields
        dashboard = _dashboard_with_cfg(cfg)
        result = dashboard._fetch()

        mock_requests.assert_not_called()
        assert result.get("error") == "no_key"

    def test_stuck_extra_key_is_not_sent_to_openrouter(self, tmp_config_dir, mock_requests):
        stuck = "gAAAAA-not-a-real-token"
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": True,
            "extra_keys": [stuck],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000, "limit_remaining": 800, "label": "Main",
                "usage_daily": 1.0, "usage_monthly": 10.0,
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        route_requests(
            mock_requests,
            url_responses={"auth/key": auth_response, "credits": credits_response},
        )

        cfg = main.load_config()[0]
        dashboard = _dashboard_with_cfg(cfg)
        result = dashboard._fetch()

        for call in mock_requests.call_args_list:
            headers = call.kwargs.get("headers") or {}
            assert stuck not in headers.get("Authorization", "")
        assert result["all_daily"] == 1.0
        assert result["all_monthly"] == 10.0
        # Ciphertext remains in memory/config so Settings save cannot wipe it
        assert stuck in cfg["extra_keys"]


class TestAuthKeyInvalidJson:
    """HTTP 200 with a non-JSON body crashed _fetch with JSONDecodeError."""

    def test_auth_key_200_with_invalid_json_returns_error(self, tmp_config_dir, mock_requests):
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
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        resp = make_mock_response(status_code=200, json_data=None)
        resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_requests.return_value = resp

        dashboard = _dashboard_with_cfg(main.load_config()[0])
        result = dashboard._fetch()
        assert "error" in result


class TestResolveTzOutOfRange:
    """Huge/infinite numeric TZ specs raised OverflowError instead of falling back."""

    def test_huge_numeric_offset_does_not_raise(self):
        result = main.resolve_tz("1e20")
        assert result is not None

    def test_inf_offset_does_not_raise(self):
        result = main.resolve_tz("inf")
        assert result is not None


class TestRefreshSecNull:
    """refresh_sec null/string crashed scheduling with TypeError."""

    def _make_dashboard(self, refresh_sec):
        d = main.Dashboard.__new__(main.Dashboard)
        d.cfg = {"refresh_sec": refresh_sec}
        d.root = MagicMock()
        d._dot = MagicMock()
        d._status = MagicMock()
        d._island_logo = MagicMock()
        d._refresh_id = 1
        d._job = None
        d._update_ui = MagicMock()
        return d

    def test_null_refresh_sec_still_schedules(self):
        d = self._make_dashboard(None)
        d._on_fetch_done({"ok": True}, rid=1)
        d.root.after.assert_called_once()
        assert d.root.after.call_args[0][0] == 60000

    def test_string_refresh_sec_still_schedules(self):
        d = self._make_dashboard("60")
        d._on_fetch_done({"ok": True}, rid=1)
        d.root.after.assert_called_once()
        assert d.root.after.call_args[0][0] == 60000


class TestFmtBadRate:
    """Non-numeric currency_rate crashed _fmt during UI updates."""

    def test_non_numeric_rate_does_not_raise(self):
        d = _dashboard_with_cfg({"currency": "EUR", "currency_rate": "?"})
        assert d._fmt(10.0) == "€10.00"

    def test_none_rate_does_not_raise(self):
        d = _dashboard_with_cfg({"currency": "EUR", "currency_rate": None})
        assert d._fmt(10.0) == "€10.00"


class TestExtraKeysType:
    """A string extra_keys value was iterated character-by-character."""

    def test_string_extra_keys_does_not_iterate_characters(self, mock_requests):
        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000, "limit_remaining": 800, "label": "Main",
                "usage_daily": 1.0, "usage_monthly": 10.0,
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        extra_response = make_mock_response(json_data={
            "data": {"usage_daily": 5.0, "usage_monthly": 50.0}
        })
        route_requests(
            mock_requests,
            url_responses={"credits": credits_response},
            key_responses={
                "sk-or-v1-test": auth_response,
                "sk-or-v1-extra": extra_response,
            },
        )
        dashboard = _dashboard_with_cfg({
            "api_key": "sk-or-v1-test",
            "extra_keys": "sk-or-v1-extra",
            "mgmt_key": "",
        })
        result = dashboard._fetch()
        assert result["all_daily"] == 6.0
        assert result["all_monthly"] == 60.0
        assert mock_requests.call_count == 3


class TestEncryptKeysNull:
    """JSON null encrypt_keys is falsy and would re-save decrypted keys as plaintext."""

    def test_null_encrypt_keys_coerced_to_true(self, tmp_config_dir):
        config = {
            "api_key": "sk-or-v1-secret",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": None,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        result = main.load_config()[0]
        assert result["encrypt_keys"] is True

    def test_null_encrypt_keys_does_not_plaintext_resave(self, tmp_config_dir):
        pytest.importorskip("cryptography")
        token = main._encrypt_value("sk-or-v1-secret", encrypt=True)
        if not main._is_encrypted(token):
            pytest.skip("encryption unavailable")
        config = {
            "api_key": token,
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": None,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        result = main.load_config()[0]
        assert result["api_key"] == "sk-or-v1-secret"
        assert result["encrypt_keys"] is True
        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["api_key"] != "sk-or-v1-secret"
        assert main._is_encrypted(saved["api_key"])
