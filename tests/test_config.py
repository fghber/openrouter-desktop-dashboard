"""
Tests for config load/save functions.

Covers:
- load_config: defaults when no file exists
- load_config: reads existing config
- load_config: decrypts encrypted fields
- load_config: re-saves plaintext keys when encryption enabled
- save_config: encrypts sensitive fields
- save_config: respects encrypt_keys=False
- save_config: round-trip with extra_keys list
"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest

import main


class TestLoadConfig:
    """Tests for load_config."""

    def test_defaults_when_no_config_file(self, tmp_config_dir):
        """Should return defaults when config.json doesn't exist."""
        # Ensure file doesn't exist
        if os.path.exists(tmp_config_dir):
            os.remove(tmp_config_dir)
        result = main.load_config()
        assert result["api_key"] == ""
        assert result["refresh_sec"] == 60
        assert result["alpha"] == 0.93
        assert result["currency"] == "USD"
        assert result["currency_rate"] == 1.0
        assert result["encrypt_keys"] is True

    def test_reads_existing_config(self, clean_config):
        """Should read values from an existing config.json."""
        result = main.load_config()
        assert result["api_key"] == ""
        assert result["refresh_sec"] == 60
        assert result["currency"] == "USD"

    def test_decrypts_encrypted_api_key(self, tmp_config_dir):
        """Should decrypt an encrypted api_key on load."""
        # Save a config with an encrypted key
        encrypted_key = main._encrypt_value("sk-or-v1-secret-key", encrypt=True)
        config = {
            "api_key": encrypted_key,
            "refresh_sec": 30,
            "alpha": 0.9,
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

        result = main.load_config()
        assert result["api_key"] == "sk-or-v1-secret-key"

    def test_decrypts_encrypted_extra_keys(self, tmp_config_dir):
        """Should decrypt each key in the extra_keys list."""
        enc_key1 = main._encrypt_value("sk-or-v1-key1", encrypt=True)
        enc_key2 = main._encrypt_value("sk-or-v1-key2", encrypt=True)
        config = {
            "api_key": "",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": True,
            "extra_keys": [enc_key1, enc_key2],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        result = main.load_config()
        assert result["extra_keys"] == ["sk-or-v1-key1", "sk-or-v1-key2"]

    def test_resaves_plaintext_keys_when_encryption_enabled(self, tmp_config_dir):
        """Should re-save config to encrypt plaintext keys when encrypt_keys is True."""
        config = {
            "api_key": "sk-or-v1-plaintext-key",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": True,
            "extra_keys": ["sk-or-v1-extra-plaintext"],
            "mgmt_key": "sk-or-v1-mgmt-plaintext",
            "pinned": True,
            "island_state": "island",
        }
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            json.dump(config, f)

        result = main.load_config()

        # The in-memory result should have decrypted values
        assert result["api_key"] == "sk-or-v1-plaintext-key"
        assert result["extra_keys"] == ["sk-or-v1-extra-plaintext"]
        assert result["mgmt_key"] == "sk-or-v1-mgmt-plaintext"

        # The file on disk should now have encrypted values
        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["api_key"] != "sk-or-v1-plaintext-key"
        assert saved["extra_keys"][0] != "sk-or-v1-extra-plaintext"
        assert saved["mgmt_key"] != "sk-or-v1-mgmt-plaintext"

    def test_does_not_resave_when_encryption_disabled(self, tmp_config_dir):
        """Should not re-encrypt when encrypt_keys is False."""
        config = {
            "api_key": "sk-or-v1-plaintext-key",
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

        result = main.load_config()
        assert result["api_key"] == "sk-or-v1-plaintext-key"

        # File should still have plaintext
        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["api_key"] == "sk-or-v1-plaintext-key"

    def test_corrupt_config_returns_defaults(self, tmp_config_dir):
        """Should return defaults when config.json is corrupt."""
        with open(tmp_config_dir, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json }")

        result = main.load_config()
        assert result["api_key"] == ""
        assert result["refresh_sec"] == 60


class TestSaveConfig:
    """Tests for save_config."""

    def test_encrypts_api_key_on_save(self, tmp_config_dir):
        """Should encrypt api_key when saving with encrypt_keys=True."""
        cfg = {
            "api_key": "sk-or-v1-secret",
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
        main.save_config(cfg)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["api_key"] != "sk-or-v1-secret"
        # Should be decryptable back
        assert main._decrypt_value(saved["api_key"], encrypt=True) == "sk-or-v1-secret"

    def test_encrypts_extra_keys_on_save(self, tmp_config_dir):
        """Should encrypt each key in extra_keys list."""
        cfg = {
            "api_key": "",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": True,
            "extra_keys": ["sk-or-v1-key1", "sk-or-v1-key2"],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        main.save_config(cfg)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert len(saved["extra_keys"]) == 2
        assert saved["extra_keys"][0] != "sk-or-v1-key1"
        assert saved["extra_keys"][1] != "sk-or-v1-key2"
        # Both should decrypt back
        assert main._decrypt_value(saved["extra_keys"][0], encrypt=True) == "sk-or-v1-key1"
        assert main._decrypt_value(saved["extra_keys"][1], encrypt=True) == "sk-or-v1-key2"

    def test_encrypts_mgmt_key_on_save(self, tmp_config_dir):
        """Should encrypt mgmt_key when saving."""
        cfg = {
            "api_key": "",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": True,
            "extra_keys": [],
            "mgmt_key": "sk-or-v1-mgmt-secret",
            "pinned": True,
            "island_state": "island",
        }
        main.save_config(cfg)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["mgmt_key"] != "sk-or-v1-mgmt-secret"
        assert main._decrypt_value(saved["mgmt_key"], encrypt=True) == "sk-or-v1-mgmt-secret"

    def test_no_encryption_when_disabled(self, tmp_config_dir):
        """Should store plaintext when encrypt_keys=False."""
        cfg = {
            "api_key": "sk-or-v1-plaintext",
            "refresh_sec": 60,
            "alpha": 0.93,
            "timezone": "",
            "currency": "USD",
            "currency_rate": 1.0,
            "encrypt_keys": False,
            "extra_keys": ["sk-or-v1-extra"],
            "mgmt_key": "sk-or-v1-mgmt",
            "pinned": True,
            "island_state": "island",
        }
        main.save_config(cfg)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["api_key"] == "sk-or-v1-plaintext"
        assert saved["extra_keys"] == ["sk-or-v1-extra"]
        assert saved["mgmt_key"] == "sk-or-v1-mgmt"

    def test_round_trip_save_load(self, tmp_config_dir):
        """Save then load should return the same values."""
        original = {
            "api_key": "sk-or-v1-roundtrip",
            "refresh_sec": 45,
            "alpha": 0.85,
            "timezone": "UTC",
            "currency": "EUR",
            "currency_rate": 0.92,
            "encrypt_keys": True,
            "extra_keys": ["sk-or-v1-extra1", "sk-or-v1-extra2"],
            "mgmt_key": "sk-or-v1-mgmt",
            "pinned": False,
            "island_state": "expanded",
        }
        main.save_config(original)
        loaded = main.load_config()

        assert loaded["api_key"] == "sk-or-v1-roundtrip"
        assert loaded["refresh_sec"] == 45
        assert loaded["alpha"] == 0.85
        assert loaded["timezone"] == "UTC"
        assert loaded["currency"] == "EUR"
        assert loaded["currency_rate"] == 0.92
        assert loaded["extra_keys"] == ["sk-or-v1-extra1", "sk-or-v1-extra2"]
        assert loaded["mgmt_key"] == "sk-or-v1-mgmt"
        assert loaded["pinned"] is False
        assert loaded["island_state"] == "expanded"

    def test_save_preserves_non_encrypted_fields(self, tmp_config_dir):
        """Non-encrypted fields should be saved as-is."""
        cfg = {
            "api_key": "sk-or-v1-test",
            "refresh_sec": 120,
            "alpha": 0.5,
            "timezone": "Asia/Shanghai",
            "currency": "CNY",
            "currency_rate": 7.2,
            "encrypt_keys": True,
            "extra_keys": [],
            "mgmt_key": "",
            "pinned": True,
            "island_state": "island",
        }
        main.save_config(cfg)

        with open(tmp_config_dir, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["refresh_sec"] == 120
        assert saved["alpha"] == 0.5
        assert saved["timezone"] == "Asia/Shanghai"
        assert saved["currency"] == "CNY"
        assert saved["currency_rate"] == 7.2
        assert saved["pinned"] is True
        assert saved["island_state"] == "island"
