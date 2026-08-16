"""
Tests for Dashboard._update_ui — UI update logic.

Since _update_ui interacts heavily with tkinter widgets, these tests
mock the widget references and verify that the correct values are passed
to config() calls.

Covers:
- Error states: no_key, 401, generic error
- Success state: balance, daily, monthly, total, top3
- Monthly limit percentage calculation
- Currency formatting in UI
"""
import json
from unittest.mock import patch, MagicMock, call

import pytest

import main


def make_mock_label():
    """Create a mock label that records config() calls."""
    label = MagicMock()
    label.config = MagicMock()
    return label


class TestUpdateUiErrors:
    """Tests for _update_ui error handling."""

    def _make_dashboard(self, tmp_config_dir, api_key="sk-or-v1-test"):
        """Create a Dashboard-like object with mocked UI widgets."""
        config = {
            "api_key": api_key,
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

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()
        dashboard._tz = main.resolve_tz("")

        # Mock all UI widgets that _update_ui touches
        dashboard._dot = make_mock_label()
        dashboard._status = make_mock_label()
        dashboard._island_logo = make_mock_label()
        dashboard._island_bal_lbl = make_mock_label()
        dashboard._island_sep = MagicMock()
        dashboard._island_daily_lbl = make_mock_label()
        dashboard._time_lbl = make_mock_label()
        dashboard._vals = {
            "balance": make_mock_label(),
            "daily": make_mock_label(),
            "total": make_mock_label(),
            "monthly": make_mock_label(),
        }
        dashboard._monthly_pct = make_mock_label()
        dashboard._monthly_bar = MagicMock()
        dashboard._top3_title = make_mock_label()
        dashboard._top3_lbls = [(make_mock_label(), make_mock_label()) for _ in range(3)]
        dashboard._daily_breakdown = {}

        return dashboard

    def test_no_key_error(self, tmp_config_dir):
        """Should show 'No Key Set' status when error is 'no_key'."""
        d = self._make_dashboard(tmp_config_dir, api_key="")
        d._update_ui({"error": "no_key"})

        d._dot.config.assert_called_with(fg=main.YELLOW)
        d._status.config.assert_called_with(text="No Key Set", fg=main.YELLOW)
        d._island_logo.config.assert_called_with(fg=main.YELLOW)
        d._island_bal_lbl.config.assert_called_with(text="No Key Set", fg=main.YELLOW)

    def test_401_error(self, tmp_config_dir):
        """Should show 'Invalid Key' status on 401 error."""
        d = self._make_dashboard(tmp_config_dir)
        d._update_ui({"error": "401"})

        d._dot.config.assert_called_with(fg=main.RED)
        d._status.config.assert_called_with(text="Invalid Key", fg=main.RED)
        d._island_logo.config.assert_called_with(fg=main.RED)
        d._island_bal_lbl.config.assert_called_with(text="Invalid Key", fg=main.RED)

    def test_generic_error(self, tmp_config_dir):
        """Should show 'Network Error' status on generic error."""
        d = self._make_dashboard(tmp_config_dir)
        d._update_ui({"error": "some network failure"})

        d._dot.config.assert_called_with(fg=main.RED)
        d._status.config.assert_called_with(text="Network Error", fg=main.RED)
        d._island_logo.config.assert_called_with(fg=main.RED)
        d._island_bal_lbl.config.assert_called_with(text="Network Error", fg=main.RED)

    def test_no_key_hides_separator_and_daily(self, tmp_config_dir):
        """Should hide separator and daily label on no_key error."""
        d = self._make_dashboard(tmp_config_dir, api_key="")
        d._update_ui({"error": "no_key"})

        d._island_sep.pack_forget.assert_called_once()
        d._island_daily_lbl.pack_forget.assert_called_once()


class TestUpdateUiSuccess:
    """Tests for _update_ui with successful data."""

    def _make_dashboard(self, tmp_config_dir, currency="USD", rate=1.0, mgmt_key=""):
        """Create a Dashboard-like object with mocked UI widgets."""
        config = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": currency,
            "currency_rate": rate,
            "encrypt_keys": False,
            "extra_keys": [],
            "mgmt_key": mgmt_key,
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = main.load_config()
        dashboard._tz = main.resolve_tz("")

        # Mock all UI widgets
        dashboard._dot = make_mock_label()
        dashboard._status = make_mock_label()
        dashboard._island_logo = make_mock_label()
        dashboard._island_bal_lbl = make_mock_label()
        dashboard._island_sep = MagicMock()
        dashboard._island_daily_lbl = make_mock_label()
        dashboard._time_lbl = make_mock_label()
        dashboard._vals = {
            "balance": make_mock_label(),
            "daily": make_mock_label(),
            "total": make_mock_label(),
            "monthly": make_mock_label(),
        }
        dashboard._monthly_pct = make_mock_label()
        dashboard._monthly_bar = MagicMock()
        dashboard._top3_title = make_mock_label()
        dashboard._top3_lbls = [(make_mock_label(), make_mock_label()) for _ in range(3)]
        dashboard._daily_breakdown = {}

        return dashboard

    def test_success_shows_connected(self, tmp_config_dir):
        """Should show 'Connected' status on successful data."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._dot.config.assert_called_with(fg=main.GREEN)
        d._status.config.assert_called_with(text="Connected", fg=main.GREEN)
        d._island_logo.config.assert_called_with(fg=main.GREEN)

    def test_balance_display(self, tmp_config_dir):
        """Should display balance with correct color."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        # Balance > 5 → GREEN
        d._vals["balance"].config.assert_called_with(text="$80.00", fg=main.GREEN)

    def test_balance_low_color(self, tmp_config_dir):
        """Balance < 1 should be RED with '!' suffix."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 0.5,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._vals["balance"].config.assert_called_with(text="$0.50 !", fg=main.RED)

    def test_balance_warning_color(self, tmp_config_dir):
        """Balance < 5 should be YELLOW."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 3.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._vals["balance"].config.assert_called_with(text="$3.00", fg=main.YELLOW)

    def test_daily_spend_display(self, tmp_config_dir):
        """Should display daily spend in RED when > 0."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._vals["daily"].config.assert_called_with(text="$5.00", fg=main.RED)

    def test_daily_spend_zero_gray(self, tmp_config_dir):
        """Should display daily spend in GRAY when 0."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 0.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._vals["daily"].config.assert_called_with(text="$0.00", fg=main.GRAY)

    def test_monthly_from_all_monthly_even_with_breakdown(self, tmp_config_dir):
        """Monthly card always uses all_monthly (activity breakdown is delayed)."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {
                "2026-08-01": {"cost": 10.0, "tokens": 1000},
                "2026-08-02": {"cost": 5.0, "tokens": 500},
            },
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        # Monthly = all_monthly, not sum of delayed activity breakdown
        d._vals["monthly"].config.assert_called_with(text="$50.00", fg=main.WHITE)

    def test_total_dash_when_credits_failed(self, tmp_config_dir):
        """Total spend should show —— when credits API failed (global_total_usage is None)."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": None,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": None,
        }
        d._update_ui(data)

        d._vals["total"].config.assert_called_with(text="——", fg=main.GRAY)
        d._vals["balance"].config.assert_called_with(text="——", fg=main.GRAY)

    def test_monthly_from_all_monthly(self, tmp_config_dir):
        """Should use all_monthly when no daily_breakdown."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._vals["monthly"].config.assert_called_with(text="$50.00", fg=main.WHITE)

    def test_total_spend_display(self, tmp_config_dir):
        """Should display total spend with correct color."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 25.0,
        }
        d._update_ui(data)

        # total > 20 → RED
        d._vals["total"].config.assert_called_with(text="$25.00", fg=main.RED)

    def test_total_spend_warning(self, tmp_config_dir):
        """Total spend between 5 and 20 should be YELLOW."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 10.0,
        }
        d._update_ui(data)

        d._vals["total"].config.assert_called_with(text="$10.00", fg=main.YELLOW)

    def test_total_spend_normal(self, tmp_config_dir):
        """Total spend < 5 should be WHITE."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 3.0,
        }
        d._update_ui(data)

        d._vals["total"].config.assert_called_with(text="$3.00", fg=main.WHITE)

    def test_monthly_limit_percentage(self, tmp_config_dir):
        """Should calculate and display monthly limit percentage."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 200,  # 80% used
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        # 80% used → YELLOW (>= 70%)
        d._monthly_pct.config.assert_called_with(
            text="80.0%  Limit $1000.00", fg=main.YELLOW
        )

    def test_monthly_limit_critical(self, tmp_config_dir):
        """Should show RED when limit usage >= 90%."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 50,  # 95% used
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._monthly_pct.config.assert_called_with(
            text="95.0%  Limit $1000.00", fg=main.RED
        )

    def test_monthly_limit_normal(self, tmp_config_dir):
        """Should show CYAN when limit usage < 70%."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 500,  # 50% used
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._monthly_pct.config.assert_called_with(
            text="50.0%  Limit $1000.00", fg=main.CYAN
        )

    def test_no_quota_limit(self, tmp_config_dir):
        """Should show 'No Quota Limit' when limit is not set."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": None,
            "limit_rem": None,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._monthly_pct.config.assert_called_with(text="No Quota Limit", fg=main.GRAY)

    def test_top3_with_mgmt_key(self, tmp_config_dir):
        """Should display top3 models when mgmt_key is set."""
        d = self._make_dashboard(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [
                ("anthropic/claude-3-5-sonnet", 50.0),
                ("openai/gpt-4", 30.0),
                ("google/gemini-2.0", 10.0),
            ],
            "top3_latest_date": "2026-08-15",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        # Title should include the date
        d._top3_title.config.assert_called_with(
            text="Monthly TOP 3 (2026-08-15)"
        )

        # First top3 entry
        name_lbl, cost_lbl = d._top3_lbls[0]
        name_lbl.config.assert_called_with(text="3-5-sonnet", fg=main.WHITE)
        cost_lbl.config.assert_called_with(text="$50.00", fg=main.CYAN)

    def test_top3_without_mgmt_key(self, tmp_config_dir):
        """Should show 'Enter Management Key' prompt when no mgmt_key."""
        d = self._make_dashboard(tmp_config_dir, mgmt_key="")
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        name_lbl, cost_lbl = d._top3_lbls[0]
        name_lbl.config.assert_called_with(
            text="Enter Management Key in Settings", fg=main.GRAY
        )
        cost_lbl.config.assert_called_with(text="", fg=main.GRAY)

    def test_top3_fewer_than_3(self, tmp_config_dir):
        """Should show dashes for missing top3 entries."""
        d = self._make_dashboard(tmp_config_dir, mgmt_key="sk-or-v1-mgmt")
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [("model-a", 10.0)],
            "top3_latest_date": "2026-08-15",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        # First entry should have data
        name_lbl, cost_lbl = d._top3_lbls[0]
        name_lbl.config.assert_called_with(text="model-a", fg=main.WHITE)
        cost_lbl.config.assert_called_with(text="$10.00", fg=main.CYAN)

        # Second and third should show dashes
        name_lbl2, cost_lbl2 = d._top3_lbls[1]
        name_lbl2.config.assert_called_with(text="——", fg=main.GRAY)
        cost_lbl2.config.assert_called_with(text="", fg=main.GRAY)

    def test_island_display_balance_and_daily(self, tmp_config_dir):
        """Should update island balance and daily labels."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        d._island_bal_lbl.config.assert_called_with(text="Balance:$80.00", fg=main.GREEN)
        d._island_daily_lbl.config.assert_called_with(text="Today:$5.00", fg=main.RED)

    def test_time_label_updated(self, tmp_config_dir):
        """Should update the time label with current time."""
        d = self._make_dashboard(tmp_config_dir)
        data = {
            "ok": True,
            "limit": 1000,
            "limit_rem": 800,
            "balance": 80.0,
            "label": "Test Key",
            "top3": [],
            "top3_latest_date": "",
            "daily_breakdown": {},
            "all_daily": 5.0,
            "all_monthly": 50.0,
            "global_total_usage": 20.0,
        }
        d._update_ui(data)

        # Time label should contain "Right-click for more options"
        time_call = d._time_lbl.config.call_args
        assert "Right-click for more options" in str(time_call)
