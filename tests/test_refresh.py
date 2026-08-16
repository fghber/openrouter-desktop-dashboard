"""
Tests for refresh generation / stale-fetch handling.
"""
from unittest.mock import MagicMock

import main


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
