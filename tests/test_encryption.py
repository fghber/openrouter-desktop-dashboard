"""
Tests for encryption/decryption helper functions.

Covers:
- _machine_keys: stable key candidates, deterministic per machine
- _get_fernet: returns Fernet or None when cryptography unavailable
- _encrypt_value / _decrypt_value: round-trip encryption
- _decrypt_value statuses: 'plain', 'ok', 'stuck'
- _decrypt_values: re-save / stuck bookkeeping used by load_config
"""
import hashlib
import sys
from unittest.mock import patch

import pytest

import main

_win32 = pytest.mark.skipif(sys.platform != "win32",
                            reason="reads MachineGuid from the Windows registry")


@_win32
class TestMachineKeys:
    """Tests for _machine_keys."""

    def test_returns_list_of_32byte_keys(self):
        """Should return a non-empty list of 32-byte (SHA-256) keys."""
        result = main._machine_keys()
        assert isinstance(result, list)
        assert len(result) >= 1
        for key in result:
            assert isinstance(key, bytes)
            assert len(key) == 32

    def test_deterministic(self):
        """Should return the same candidates on repeated calls (same machine)."""
        assert main._machine_keys() == main._machine_keys()

    def test_machine_guid_key_first(self):
        """The primary key should be sha256(MachineGuid) from the 64-bit view."""
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SOFTWARE\Microsoft\Cryptography', 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            guid = winreg.QueryValueEx(key, 'MachineGuid')[0]
        expected = hashlib.sha256(guid.encode()).digest()
        assert main._machine_keys()[0] == expected

    def test_mac_fallback_without_registry(self):
        """With the registry unavailable, the legacy MAC key is still offered."""
        with patch("winreg.OpenKey", side_effect=OSError("no registry")):
            import uuid
            keys = main._machine_keys()
            assert keys == [hashlib.sha256(str(uuid.getnode()).encode()).digest()]

    def test_empty_when_all_derivations_fail(self):
        """No hardcoded fallback: both MachineGuid and MAC failing yields no keys."""
        with patch("winreg.OpenKey", side_effect=OSError("no registry")), \
             patch("uuid.getnode", side_effect=Exception("mock error")):
            assert main._machine_keys() == []


class TestGetFernet:
    """Tests for _get_fernet."""

    def test_returns_fernet_when_cryptography_available(self):
        """Should return a Fernet instance when cryptography is installed."""
        pytest.importorskip("cryptography")
        result = main._get_fernet()
        from cryptography.fernet import Fernet
        assert isinstance(result, Fernet)

    def test_returns_none_when_cryptography_unavailable(self):
        """Should return None when cryptography import fails."""
        import builtins
        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "cryptography.fernet" or name.startswith("cryptography"):
                raise ImportError("mocked missing cryptography")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            result = main._get_fernet()
            assert result is None


class TestEncryptDecrypt:
    """Tests for _encrypt_value and _decrypt_value round-trip."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        pytest.importorskip("cryptography")
        if main._get_fernet() is None:
            pytest.skip("cryptography/Fernet unavailable")

    def test_encrypt_decrypt_round_trip(self):
        """Encrypting then decrypting should return the original value."""
        original = "sk-or-v1-test-key-12345"
        encrypted = main._encrypt_value(original, encrypt=True)
        # Encrypted value should differ from original
        assert encrypted != original
        decrypted, status = main._decrypt_value(encrypted)
        assert (decrypted, status) == (original, "ok")

    def test_encrypt_disabled_returns_original(self):
        """When encrypt=False, should return the original value unchanged."""
        original = "sk-or-v1-test-key-12345"
        result = main._encrypt_value(original, encrypt=False)
        assert result == original

    def test_encrypt_empty_value_returns_empty(self):
        """Empty string should be returned as-is."""
        result = main._encrypt_value("", encrypt=True)
        assert result == ""

    def test_encrypt_none_value_returns_none(self):
        """None should be returned as-is."""
        result = main._encrypt_value(None, encrypt=True)
        assert result is None

    def test_encrypt_skips_already_encrypted_value(self):
        """A value that already looks like a Fernet token is not double-encrypted."""
        original = "sk-or-v1-test-key-12345"
        encrypted = main._encrypt_value(original, encrypt=True)
        assert main._encrypt_value(encrypted, encrypt=True) == encrypted

    def test_decrypt_empty_value_returns_plain(self):
        """Empty string should be returned as-is."""
        assert main._decrypt_value("") == ("", "plain")

    def test_decrypt_none_value_returns_plain(self):
        assert main._decrypt_value(None) == (None, "plain")

    def test_decrypt_plaintext_returns_plaintext(self):
        """Decrypting a non-encrypted (plaintext) value should return it as-is."""
        plaintext = "sk-or-v1-plaintext-key"
        assert main._decrypt_value(plaintext) == (plaintext, "plain")

    def test_decrypt_token_shaped_but_undecryptable_is_stuck(self):
        """Ciphertext no known key can open is returned byte-identical, flagged stuck."""
        stuck = "gAAAAA-not-a-real-token"
        assert main._decrypt_value(stuck) == (stuck, "stuck")

    def test_decrypt_plaintext_looking_like_token_is_stuck(self):
        """A plaintext value starting with the token prefix is stuck, not silently kept."""
        # 'plain' only applies to values that don't look encrypted at all
        assert main._decrypt_value("gAAAAA plaintext with whitespace") == (
            "gAAAAA plaintext with whitespace", "stuck")

    def test_encrypt_produces_different_ciphertexts(self):
        """Encrypting the same value twice should produce different ciphertexts (Fernet uses random IV)."""
        original = "sk-or-v1-test-key"
        enc1 = main._encrypt_value(original, encrypt=True)
        enc2 = main._encrypt_value(original, encrypt=True)
        assert enc1 != enc2
        # But both should decrypt back to the same value
        assert main._decrypt_value(enc1) == (original, "ok")
        assert main._decrypt_value(enc2) == (original, "ok")

    def test_encrypt_long_value(self):
        """Should handle long values correctly."""
        original = "sk-or-v1-" + "a" * 500
        encrypted = main._encrypt_value(original, encrypt=True)
        assert main._decrypt_value(encrypted) == (original, "ok")


class TestDecryptValues:
    """Tests for _decrypt_values bookkeeping (used by load_config)."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        pytest.importorskip("cryptography")
        if main._get_fernet() is None:
            pytest.skip("cryptography/Fernet unavailable")

    def test_plaintext_with_encryption_on_needs_resave(self):
        """Plaintext while encryption is on must be re-saved as ciphertext."""
        out, stuck, resave = main._decrypt_values(["sk-or-v1-plain"], True)
        assert out == ["sk-or-v1-plain"]
        assert stuck == 0
        assert resave is True

    def test_ciphertext_with_encryption_off_needs_resave(self):
        """Ciphertext while encryption is off must be re-saved as plaintext."""
        token = main._encrypt_value("sk-or-v1-secret", encrypt=True)
        out, stuck, resave = main._decrypt_values([token], False)
        assert out == ["sk-or-v1-secret"]
        assert stuck == 0
        assert resave is True

    def test_stuck_value_counts_and_never_resaves(self):
        """Stuck values are counted but never rewritten (can't recover them)."""
        stuck = "gAAAAA-not-a-real-token"
        out, stuck_count, resave = main._decrypt_values([stuck], True)
        assert out == [stuck]
        assert stuck_count == 1
        assert resave is False

    def test_round_trip_is_stable(self):
        """Freshly encrypted values decrypt cleanly with no re-save needed."""
        token = main._encrypt_value("sk-or-v1-secret", encrypt=True)
        out, stuck, resave = main._decrypt_values([token], True)
        assert (out, stuck, resave) == (["sk-or-v1-secret"], 0, False)
