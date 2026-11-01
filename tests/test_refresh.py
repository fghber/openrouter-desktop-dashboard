"""
Tests for refresh generation / stale-fetch handling.
"""
from unittest.mock import MagicMock

import main


def _dashboard_with_cfg(cfg):
    dashboard = main.Dashboard.__new__(main.Dashboard)
    dashboard.cfg = cfg
    return dashboard


class TestRefreshGeneration:
    """Tests for overlapping refresh cancellation."""

    def _make_dashboard(self):
        dashboard = main.Dashboard.__new__(main.Dashboard)
        dashboard.cfg = {"refresh_sec": 60}
        dashboard.root = MagicMock()
        dashboard._dot = MagicMock()
        dashboard._status = MagicMock()
        dashboard._island_logo = MagicMock()
        dashboard._refresh_id = 0
        dashboard._job = None
        dashboard._update_ui = MagicMock()
        return dashboard

    def test_on_fetch_done_ignores_stale_generation(self):
        """A completed fetch with an old rid must not update UI or schedule."""
        d = self._make_dashboard()
        d._refresh_id = 2
        d._on_fetch_done({"ok": True}, rid=1)
        d._update_ui.assert_not_called()
        d.root.after.assert_not_called()

    def test_on_fetch_done_accepts_current_generation(self):
        """Current rid should update UI and schedule the next refresh."""
        d = self._make_dashboard()
        d._refresh_id = 3
        d._on_fetch_done({"ok": True, "all_daily": 1.0}, rid=3)
        d._update_ui.assert_called_once()
        d.root.after.assert_called_once()
        assert d._job is not None

    def test_trigger_refresh_cancels_prior_job(self):
        """Starting a new refresh should cancel any pending after job."""
        d = self._make_dashboard()
        d._job = "old-job"
        d._trigger_refresh()
        d.root.after_cancel.assert_called_with("old-job")
        assert d._refresh_id == 1


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


class TestWorkerErrorHandling:
    """Worker failures are surfaced and do not stop refresh scheduling."""

    def test_worker_reports_error_instead_of_dying(self, tmp_config_dir, mock_requests):
        """Any unexpected _fetch error must still schedule the next refresh."""
        d = _dashboard_with_cfg({"api_key": "sk-or-v1-test"})
        d.root = MagicMock()
        d._refresh_id = 1
        d._fetch = MagicMock(side_effect=RuntimeError("boom"))
        d._on_fetch_done = MagicMock()

        d._worker(1)

        assert d.root.after.called, "refresh continuation was never scheduled"
        d.root.after.call_args[0][1]()  # run the scheduled continuation
        d._on_fetch_done.assert_called_once()
        data, rid = d._on_fetch_done.call_args[0]
        assert data == {"error": "boom"}, "worker did not surface the failure"
        assert rid == 1

    def test_worker_error_with_empty_str_is_not_read_as_success(self):
        """`str(KeyError())` is '', and _update_ui gates on a truthy 'error'.
        An empty message would fall through to the success path and render
        'Connected' with all-zero spend."""
        d = _dashboard_with_cfg({"api_key": "sk-or-v1-test"})
        d.root = MagicMock()
        d._refresh_id = 1
        d._fetch = MagicMock(side_effect=KeyError())
        d._on_fetch_done = MagicMock()

        d._worker(1)
        assert d.root.after.called
        d.root.after.call_args[0][1]()  # run the scheduled continuation

        data, _rid = d._on_fetch_done.call_args[0]
        assert data.get("error"), "empty error string would render as Connected"
        assert "KeyError" in data["error"]

    def test_update_ui_treats_worker_error_as_error_state(self):
        """End-to-end: a worker error payload must not reach the success path."""
        d = _dashboard_with_cfg({"currency": "USD", "currency_rate": 1.0})
        d.root = MagicMock()
        d._refresh_id = 1
        d._fetch = MagicMock(side_effect=KeyError())
        d._update_ui = MagicMock()
        d._tz = main.timezone.utc
        for attr in ("_dot", "_status", "_island_logo", "_island_bal_lbl",
                     "_island_sep", "_island_daily_lbl", "_time_lbl"):
            setattr(d, attr, MagicMock())

        d._worker(1)
        d.root.after.call_args[0][1]()

        d._update_ui.assert_called_once()
        assert d._update_ui.call_args[0][0].get("error")
