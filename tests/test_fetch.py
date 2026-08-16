"""
Tests for Dashboard._fetch — the data aggregation logic.

The _fetch method makes multiple API calls:
1. GET /auth/key (primary key) — for limit, limit_remaining, label
2. GET /credits — for balance and total_usage
3. GET /auth/key (each extra key) — for usage_daily and usage_monthly
4. GET /activity (mgmt key) — for model top3 and daily breakdown

These tests mock requests.get to simulate various API responses and verify
that _fetch correctly aggregates the data.
"""
import json
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

import main


def make_mock_response(status_code=200, json_data=None, text=""):
    """Helper to create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


class TestFetchNoKey:
    """Tests for _fetch when no API key is set."""

    def test_no_key_returns_error(self, tmp_config_dir):
        """Should return {'error': 'no_key'} when api_key is empty."""
        config = {
            "api_key": "",
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

        # Create a Dashboard-like object without calling __init__
        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()
        assert result == {"error": "no_key"}


class TestFetchAuthKey:
    """Tests for _fetch auth/key endpoint handling."""

    def test_401_returns_error(self, tmp_config_dir, mock_requests):
        """Should return {'error': '401'} on 401 from auth/key."""
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

        mock_requests.return_value = make_mock_response(status_code=401)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()
        assert result == {"error": "401"}

    def test_non_200_returns_error(self, tmp_config_dir, mock_requests):
        """Should return HTTP error on non-200 status."""
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

        mock_requests.return_value = make_mock_response(status_code=500)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()
        assert result == {"error": "HTTP 500"}

    def test_network_error_returns_error(self, tmp_config_dir, mock_requests):
        """Should return error string on network exception."""
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

        mock_requests.side_effect = ConnectionError("Network unreachable")

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()
        assert "error" in result
        assert "Network unreachable" in result["error"]


class TestFetchSuccess:
    """Tests for _fetch with successful API responses."""

    def _setup_config(self, tmp_config_dir, api_key="sk-or-v1-test",
                      extra_keys=None, mgmt_key=""):
        """Helper to write a config file."""
        config = {
            "api_key": api_key,
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": False,
            "extra_keys": extra_keys or [],
            "mgmt_key": mgmt_key,
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)
        return config

    def test_successful_fetch_basic(self, tmp_config_dir, mock_requests):
        """Should return aggregated data on successful API calls."""
        self._setup_config(tmp_config_dir)

        # Mock responses: auth/key, credits, auth/key (extra keys - none here)
        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000,
                "limit_remaining": 800,
                "label": "Test Key",
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {
                "total_credits": 100.0,
                "total_usage": 20.0,
            }
        })

        mock_requests.side_effect = [auth_response, credits_response]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["ok"] is True
        assert result["limit"] == 1000
        assert result["limit_rem"] == 800
        assert result["label"] == "Test Key"
        assert result["balance"] == 80.0  # 100 - 20
        assert result["global_total_usage"] == 20.0
        assert result["all_daily"] == 0.0
        assert result["all_monthly"] == 0.0
        assert result["top3"] == []
        assert result["daily_breakdown"] == {}

    def test_fetch_with_extra_keys(self, tmp_config_dir, mock_requests):
        """Should aggregate usage_daily and usage_monthly from main + extra keys."""
        self._setup_config(tmp_config_dir, extra_keys=["sk-or-v1-extra1", "sk-or-v1-extra2"])

        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000, "limit_remaining": 800, "label": "Main",
                "usage_daily": 2.0, "usage_monthly": 20.0,
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        extra1_response = make_mock_response(json_data={
            "data": {"usage_daily": 5.0, "usage_monthly": 50.0}
        })
        extra2_response = make_mock_response(json_data={
            "data": {"usage_daily": 3.0, "usage_monthly": 30.0}
        })

        mock_requests.side_effect = [
            auth_response, credits_response,
            extra1_response, extra2_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["all_daily"] == 10.0  # 2 + 5 + 3
        assert result["all_monthly"] == 100.0  # 20 + 50 + 30
        # auth + credits + 2 extras (main key not re-fetched)
        assert mock_requests.call_count == 4

    def test_fetch_does_not_double_count_duplicate_extra_key(self, tmp_config_dir, mock_requests):
        """Extra key matching the main key should be skipped."""
        self._setup_config(
            tmp_config_dir,
            api_key="sk-or-v1-test",
            extra_keys=["sk-or-v1-test", "sk-or-v1-extra1"],
        )

        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000, "limit_remaining": 800, "label": "Main",
                "usage_daily": 4.0, "usage_monthly": 40.0,
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        extra1_response = make_mock_response(json_data={
            "data": {"usage_daily": 1.0, "usage_monthly": 10.0}
        })

        mock_requests.side_effect = [
            auth_response, credits_response, extra1_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["all_daily"] == 5.0  # 4 + 1 (duplicate main skipped)
        assert result["all_monthly"] == 50.0
        assert mock_requests.call_count == 3

    def test_fetch_seeds_usage_from_first_auth(self, tmp_config_dir, mock_requests):
        """Should use usage_daily/monthly from the first auth/key response."""
        self._setup_config(tmp_config_dir)

        auth_response = make_mock_response(json_data={
            "data": {
                "limit": 1000, "limit_remaining": 800, "label": "Main",
                "usage_daily": 7.5, "usage_monthly": 42.0,
            }
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })

        mock_requests.side_effect = [auth_response, credits_response]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["all_daily"] == 7.5
        assert result["all_monthly"] == 42.0
        assert mock_requests.call_count == 2

    def test_fetch_with_mgmt_key_activity(self, tmp_config_dir, mock_requests):
        """Should fetch top3 and daily_breakdown when mgmt_key is set."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        activity_response = make_mock_response(json_data={
            "data": [
                {"date": "2026-08-01", "model": "anthropic/claude-3", "usage": 5.0,
                 "prompt_tokens": 1000, "completion_tokens": 500},
                {"date": "2026-08-02", "model": "openai/gpt-4", "usage": 3.0,
                 "prompt_tokens": 500, "completion_tokens": 200},
                {"date": "2026-08-01", "model": "anthropic/claude-3", "usage": 2.0,
                 "prompt_tokens": 300, "completion_tokens": 100},
            ]
        })

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        # top3 should be sorted by cost descending
        assert len(result["top3"]) == 2  # claude-3 and gpt-4
        assert result["top3"][0][0] == "anthropic/claude-3"
        assert result["top3"][0][1] == 7.0  # 5 + 2
        assert result["top3"][1][0] == "openai/gpt-4"
        assert result["top3"][1][1] == 3.0

        # daily_breakdown should aggregate by day
        assert "2026-08-01" in result["daily_breakdown"]
        assert result["daily_breakdown"]["2026-08-01"]["cost"] == 7.0
        assert result["daily_breakdown"]["2026-08-01"]["tokens"] == 1900  # 1000+500+300+100
        assert result["daily_breakdown"]["2026-08-02"]["cost"] == 3.0
        assert result["daily_breakdown"]["2026-08-02"]["tokens"] == 700

    def test_fetch_activity_filters_by_month(self, tmp_config_dir, mock_requests):
        """Should only include activity items from the current month."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        # Activity with items from different months
        activity_response = make_mock_response(json_data={
            "data": [
                {"date": "2026-08-15", "model": "model-a", "usage": 5.0,
                 "prompt_tokens": 100, "completion_tokens": 50},
                {"date": "2026-07-15", "model": "model-b", "usage": 10.0,
                 "prompt_tokens": 200, "completion_tokens": 100},
            ]
        })

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        # Only August data should be in daily_breakdown
        assert "2026-08-15" in result["daily_breakdown"]
        assert "2026-07-15" not in result["daily_breakdown"]
        # top3 should only have model-a
        assert len(result["top3"]) == 1
        assert result["top3"][0][0] == "model-a"

    def test_fetch_activity_empty_data(self, tmp_config_dir, mock_requests):
        """Should handle empty activity data gracefully."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        activity_response = make_mock_response(json_data={"data": []})

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["top3"] == []
        assert result["daily_breakdown"] == {}
        assert result["top3_latest_date"] == ""

    def test_fetch_activity_non_200(self, tmp_config_dir, mock_requests):
        """Should handle non-200 from activity API gracefully."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        activity_response = make_mock_response(status_code=500)

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["top3"] == []
        assert result["daily_breakdown"] == {}

    def test_fetch_credits_failure_returns_none_balance(self, tmp_config_dir, mock_requests):
        """Should return None balance when credits API fails."""
        self._setup_config(tmp_config_dir)

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(status_code=500)

        mock_requests.side_effect = [auth_response, credits_response]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["balance"] is None
        assert result["global_total_usage"] is None

    def test_fetch_extra_key_failure_skips_key(self, tmp_config_dir, mock_requests):
        """Should skip extra keys that fail to fetch."""
        self._setup_config(tmp_config_dir, extra_keys=["sk-or-v1-extra1"])

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        # Extra key returns 401
        extra_response = make_mock_response(status_code=401)

        mock_requests.side_effect = [
            auth_response, credits_response, extra_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        # Extra key failed, so all_daily and all_monthly should be 0
        assert result["all_daily"] == 0.0
        assert result["all_monthly"] == 0.0

    def test_fetch_top3_sorted_descending(self, tmp_config_dir, mock_requests):
        """top3 should be sorted by cost in descending order."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        activity_response = make_mock_response(json_data={
            "data": [
                {"date": "2026-08-01", "model": "model-low", "usage": 1.0,
                 "prompt_tokens": 10, "completion_tokens": 5},
                {"date": "2026-08-01", "model": "model-high", "usage": 50.0,
                 "prompt_tokens": 100, "completion_tokens": 50},
                {"date": "2026-08-01", "model": "model-mid", "usage": 10.0,
                 "prompt_tokens": 20, "completion_tokens": 10},
            ]
        })

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert len(result["top3"]) == 3
        assert result["top3"][0][0] == "model-high"
        assert result["top3"][0][1] == 50.0
        assert result["top3"][1][0] == "model-mid"
        assert result["top3"][1][1] == 10.0
        assert result["top3"][2][0] == "model-low"
        assert result["top3"][2][1] == 1.0

    def test_fetch_top3_limited_to_3(self, tmp_config_dir, mock_requests):
        """top3 should be limited to 3 entries even if more models exist."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        activity_response = make_mock_response(json_data={
            "data": [
                {"date": "2026-08-01", "model": f"model-{i}", "usage": float(i),
                 "prompt_tokens": 10, "completion_tokens": 5}
                for i in range(1, 6)
            ]
        })

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert len(result["top3"]) == 3
        # Should be the top 3 by cost: model-5, model-4, model-3
        assert result["top3"][0][0] == "model-5"
        assert result["top3"][1][0] == "model-4"
        assert result["top3"][2][0] == "model-3"

    def test_fetch_daily_breakdown_aggregates_same_day(self, tmp_config_dir, mock_requests):
        """Should aggregate multiple entries for the same day."""
        self._setup_config(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")

        auth_response = make_mock_response(json_data={
            "data": {"limit": 1000, "limit_remaining": 800, "label": "Main"}
        })
        credits_response = make_mock_response(json_data={
            "data": {"total_credits": 100.0, "total_usage": 20.0}
        })
        activity_response = make_mock_response(json_data={
            "data": [
                {"date": "2026-08-01", "model": "model-a", "usage": 5.0,
                 "prompt_tokens": 100, "completion_tokens": 50},
                {"date": "2026-08-01", "model": "model-b", "usage": 3.0,
                 "prompt_tokens": 200, "completion_tokens": 100},
                {"date": "2026-08-01", "model": "model-a", "usage": 2.0,
                 "prompt_tokens": 50, "completion_tokens": 25},
            ]
        })

        mock_requests.side_effect = [
            auth_response, credits_response, activity_response
        ]

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()

        result = dashboard._fetch()

        assert result["daily_breakdown"]["2026-08-01"]["cost"] == 10.0  # 5 + 3 + 2
        assert result["daily_breakdown"]["2026-08-01"]["tokens"] == 525  # 150 + 300 + 75
