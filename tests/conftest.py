"""
Shared pytest fixtures for OpenRouter Dashboard tests.

These fixtures isolate tests from the real filesystem and network so that
unit tests run fast and deterministically.
"""
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest


# Ensure the project root is on sys.path so `import main` works regardless
# of where pytest is invoked from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """
    Create a temporary directory and patch CONFIG_PATH so that
    load_config / save_config operate on a throwaway file.
    """
    config_file = tmp_path / "config.json"
    # Patch the module-level CONFIG_PATH
    import main
    monkeypatch.setattr(main, "CONFIG_PATH", str(config_file))
    return config_file


@pytest.fixture
def clean_config(tmp_config_dir):
    """
    Provide a clean config.json with default values and return the path.
    """
    defaults = {
        "api_key": "",
        "refresh_sec": 60,
        "x": None,
        "y": None,
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
        json.dump(defaults, f)
    return tmp_config_dir


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Patch `requests.get` in the main module so tests can control API responses.
    Returns a MagicMock that tests can configure.
    """
    import main
    mock_get = MagicMock()
    monkeypatch.setattr(main.requests, "get", mock_get)
    return mock_get


@pytest.fixture
def no_tk():
    """
    Patch tkinter so Dashboard can be instantiated without a real display.
    Returns the mock module.
    """
    import sys
    from unittest.mock import MagicMock

    mock_tk = MagicMock()
    mock_tk.Tk.return_value = MagicMock()
    mock_tk.Toplevel.return_value = MagicMock()
    mock_tk.Frame.return_value = MagicMock()
    mock_tk.Label.return_value = MagicMock()
    mock_tk.Button.return_value = MagicMock()
    mock_tk.Entry.return_value = MagicMock()
    mock_tk.Checkbutton.return_value = MagicMock()
    mock_tk.Menu.return_value = MagicMock()
    mock_tk.BooleanVar.return_value = MagicMock()
    mock_tk.StringVar.return_value = MagicMock()

    mock_ttk = MagicMock()
    mock_ttk.Combobox.return_value = MagicMock()

    monkeypatch_tk = MagicMock()
    monkeypatch_tk.setattr = lambda mod, name, val: setattr(mod, name, val)

    # We'll use monkeypatch fixture instead; this fixture just provides the mocks
    return mock_tk, mock_ttk
