"""
Tests for encryption/decryption helper functions.

Covers:
- _get_machine_id: deterministic, returns bytes
- _get_fernet: returns Fernet or None when cryptography unavailable
- _encrypt_value / _decrypt_value: round-trip encryption
- _encrypt_value with encrypt=False: returns original
- _encrypt_value with empty value: returns original
- _decrypt_value with plaintext (non-encrypted) value: returns original
"""
import base64
import hashlib
from unittest.mock import patch, MagicMock

import pytest

import main


class TestGetMachineId:
    """Tests for _get_machine_id."""

    def test_returns_bytes(self):
        """Should return a bytes object."""
        result = main._get_machine_id()
        assert isinstance(result, bytes)

    def test_deterministic(self):
        """Should return the same value on repeated calls (same machine)."""
        result1 = main._get_machine_id()
        result2 = main._get_machine_id()
        assert result1 == result2

    def test_is_sha256_length(self):
        """Should be 32 bytes (SHA-256 digest)."""
        result = main._get_machine_id()
        assert len(result) == 32

    def test_fallback_on_exception(self):
        """Should fall back to a fixed key when uuid.getnode fails."""
        with patch("uuid.getnode", side_effect=Exception("mock error")):
            result = main._get_machine_id()
            expected = hashlib.sha256(b"openrouter-dashboard-local-key").digest()
            assert result == expected


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
        decrypted = main._decrypt_value(encrypted, encrypt=True)
        assert decrypted == original

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

    def test_decrypt_disabled_returns_original(self):
        """When encrypt=False, decrypt should return the original value."""
        original = "sk-or-v1-test-key-12345"
        result = main._decrypt_value(original, encrypt=False)
        assert result == original

    def test_decrypt_empty_value_returns_empty(self):
        """Empty string should be returned as-is."""
        result = main._decrypt_value("", encrypt=True)
        assert result == ""

    def test_decrypt_plaintext_returns_plaintext(self):
        """Decrypting a non-encrypted (plaintext) value should return it as-is."""
        plaintext = "sk-or-v1-plaintext-key"
        result = main._decrypt_value(plaintext, encrypt=True)
        assert result == plaintext

    def test_decrypt_invalid_encrypted_value_returns_original(self):
        """Decrypting a corrupted/invalid encrypted value should return it as-is."""
        invalid = "not-a-valid-fernet-token"
        result = main._decrypt_value(invalid, encrypt=True)
        assert result == invalid

    def test_encrypt_produces_different_ciphertexts(self):
        """Encrypting the same value twice should produce different ciphertexts (Fernet uses random IV)."""
        original = "sk-or-v1-test-key"
        enc1 = main._encrypt_value(original, encrypt=True)
        enc2 = main._encrypt_value(original, encrypt=True)
        assert enc1 != enc2
        # But both should decrypt back to the same value
        assert main._decrypt_value(enc1, encrypt=True) == original
        assert main._decrypt_value(enc2, encrypt=True) == original

    def test_encrypt_long_value(self):
        """Should handle long values correctly."""
        original = "sk-or-v1-" + "a" * 500
        encrypted = main._encrypt_value(original, encrypt=True)
        decrypted = main._decrypt_value(encrypted, encrypt=True)
        assert decrypted == original
