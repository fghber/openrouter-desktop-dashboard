"""Configuration persistence and machine-key encryption."""

import base64
import hashlib
import json
import os
import sys

ENCRYPTED_FIELDS = {'api_key', 'extra_keys', 'mgmt_key'}

def _get_config_dir():
    """Return config file directory: use exe directory when packaged, script directory when running .py directly."""
    if getattr(sys, 'frozen', False):
        # After PyInstaller packaging, sys.executable is the exe path
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(_get_config_dir(), 'config.json')

def _machine_keys():
    """32-byte key candidates, preferred first: Windows MachineGuid (stable
    across network/adapter changes), then the legacy MAC derivation so configs
    written by older builds still decrypt and migrate on the next save.

    MachineGuid is read from the 64-bit registry view so a 32-bit Python build
    doesn't silently lose the stable key to WOW64 redirection.
    """
    keys = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SOFTWARE\Microsoft\Cryptography', 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            guid = winreg.QueryValueEx(key, 'MachineGuid')[0]
        keys.append(hashlib.sha256(guid.encode()).digest())
    except Exception:
        pass
    try:
        import uuid
        keys.append(hashlib.sha256(str(uuid.getnode()).encode()).digest())
    except Exception:
        pass
    return keys

def _key_id():
    """Short fingerprint of the primary key, stored in config.json so the next
    load can tell when the machine key changed. Not a secret: MachineGuid
    itself is readable by any local process."""
    keys = _machine_keys()
    return hashlib.sha256(keys[0]).hexdigest()[:8] if keys else None

def _fernet_candidates():
    """Fernet ciphers for all key candidates; candidates[0] encrypts, all decrypt."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return []
    return [Fernet(base64.urlsafe_b64encode(k)) for k in _machine_keys()]

def _get_fernet():
    """Primary Fernet cipher (stable machine key), or None if cryptography is missing."""
    candidates = _fernet_candidates()
    return candidates[0] if candidates else None

def _is_encrypted(value):
    """Check if a value looks like a Fernet-encrypted token."""
    # strip() so a token padded by a manual config.json edit can't slip past
    # the guard and get encrypted a second time
    return isinstance(value, str) and value.strip().startswith('gAAAAA')

def _encrypt_value(value, encrypt=True):
    """Encrypt a string value. Returns the encrypted string or the original if encryption unavailable or disabled."""
    if not value or not encrypt:
        return value
    # Don't re-encrypt a value that's already encrypted
    if _is_encrypted(value):
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.encrypt(value.encode('utf-8')).decode('utf-8')
    except Exception:
        return value

def _decrypt_value(value, max_layers=3):
    """Peel up to max_layers nested Fernet tokens (older builds without the
    re-encryption guard wrote doubles).

    Returns (value, status):
      'plain'  – not an encrypted token, returned unchanged
      'ok'     – fully decrypted with the current stable machine key
      'legacy' – decrypted via a legacy key, or with redundant layers; caller
                 should re-save to normalize the token to the stable key
      'stuck'  – looks encrypted but no known key can decrypt it; returned
                 byte-identical so dead ciphertext is never silently used,
                 rewritten, or half-peeled
    """
    if not value or not isinstance(value, str):
        return value, 'plain'
    if not _is_encrypted(value):
        return value, 'plain'
    token, ring, legacy = value.strip(), _fernet_candidates(), False
    for layers in range(1, max_layers + 1):
        for i, f in enumerate(ring):
            try:
                token = f.decrypt(token.encode('utf-8')).decode('utf-8')
            except Exception:  # wrong key, or malformed token (binascii.Error)
                continue
            legacy = legacy or i > 0
            break
        else:
            # No key opened this layer: keep the original bytes in memory and
            # on disk rather than leaving half-peeled ciphertext around.
            return value, 'stuck'
        if not _is_encrypted(token):
            return token, ('legacy' if (legacy or layers > 1) else 'ok')
    return value, 'stuck'

def _as_secret(value):
    """Config secret as a stripped string; a non-string (e.g. JSON null) reads
    as empty so a hand-edited config can't crash the refresh thread."""
    return value.strip() if isinstance(value, str) else ''

def _as_key_list(value):
    """Normalize extra_keys, which hand-edited configs may store as a plain
    string (encrypting per character would destroy it) or not a list at all."""
    if isinstance(value, str):
        return [value] if value else []
    return value if isinstance(value, list) else []

def _usable_secret(value):
    """False for empty values or stuck ciphertext that must not be sent as a credential."""
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value:
        return False
    return _decrypt_value(value)[1] != 'stuck'

def _unique_extra_keys(extra_keys, main_key=''):
    """Distinct usable extra keys, skipping the main key, duplicates, and stuck tokens."""
    out, seen = [], {main_key} if main_key else set()
    for k in _as_key_list(extra_keys):
        if not isinstance(k, str):
            continue
        k = k.strip()
        if not k or k in seen or not _usable_secret(k):
            continue
        seen.add(k)
        out.append(k)
    return out

def _currency_rate(value, default=1.0):
    """USD→display FX rate; non-numeric, non-positive, and infinite values
    fall back to default so amounts never render as 'inf'. (nan was already
    rejected by the positivity test, since every nan comparison is False.)"""
    try:
        rate = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return rate if 0 < rate < float('inf') else default

def _sanitize_rate_field(value, current):
    """Validated rate for the Settings field: keep `current` unless the input
    is a usable positive finite rate. Guards the write path too — persisting
    inf/1e400 would emit the non-standard JSON literal `Infinity`."""
    rate = _currency_rate(value, default=0.0)
    return rate if rate > 0 else current

def _window_alpha(value, default=0.93):
    """Window opacity clamped to Tk's usable 0.1–1.0 range; anything
    non-numeric falls back to the default. A non-numeric string reaches
    `wm attributes -alpha` verbatim and crashes startup with a TclError, and
    0.0 makes the window invisible and unreachable."""
    try:
        alpha = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if alpha != alpha:  # nan: every comparison is False
        return default
    return min(1.0, max(0.1, alpha))

def _window_pos(value):
    """Window x/y as an int for the Tk geometry string, or None for
    auto-position. A string raises TypeError in the geometry max() clamp and
    a float raises TclError ('bad geometry specifier')."""
    try:
        pos = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if pos != pos or pos in (float('inf'), float('-inf')):
        return None
    return int(pos)

def _decrypt_values(values, encrypt):
    """Decrypt a list of sensitive values.

    Returns (values, stuck_count, needs_resave) — re-save when the disk state
    doesn't match the requested storage mode: plaintext present while
    encryption is on, tokens written by a legacy key (or carrying redundant
    layers) while it is on, or any ciphertext left while it is off. Stuck
    values never trigger a re-save; rewriting dead ciphertext can't recover
    it and would only hide the problem from the user.
    """
    out, stuck, resave = [], 0, False
    for v in values:
        dec, status = _decrypt_value(v)
        if status == 'stuck':
            stuck += 1
        elif ((encrypt and status == 'plain' and bool(dec))
              or status == 'legacy'
              or (not encrypt and status != 'plain')):
            resave = True
        out.append(dec)
    return out, stuck, resave

def _has_stuck_values(cfg):
    """True if any sensitive field holds a token no known key can decrypt."""
    for field in ENCRYPTED_FIELDS:
        if field == 'extra_keys':
            values = _as_key_list(cfg.get(field))
        else:
            values = [cfg.get(field)]
        for v in values:
            if _decrypt_value(v)[1] == 'stuck':
                return True
    return False

def load_config(config_path=None):
    config_path = config_path or CONFIG_PATH
    d = {'api_key': '', 'refresh_sec': 60, 'x': None, 'y': None, 'alpha': 0.93,
         'timezone': '', 'currency': 'USD', 'currency_rate': 1.0, 'encrypt_keys': True}
    raw = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding='utf-8') as f:
                raw = json.load(f)
                d.update(raw)
        except Exception:
            pass
    if not isinstance(raw, dict):
        # A config.json holding a valid JSON non-object (corrupt or
        # hand-edited, e.g. `[]`) must not crash the raw.get() checks below.
        raw = {}
    # Migrate old cny_mode/cny_rate → currency/currency_rate.
    # Defaults always set currency='USD' and currency_rate=1.0 before merge, so
    # detect legacy files by the presence of cny_* keys in the raw file.
    # Only apply cny_rate when the user was actually in CNY mode (or currency is CNY)
    # — never copy a leftover cny_rate onto a USD/EUR config.
    needs_resave = False
    if raw.get('cny_mode') or 'cny_rate' in raw:
        migrating_to_cny = False
        if raw.get('cny_mode') and (
            'currency' not in raw or raw.get('currency') in (None, '', 'USD')
        ):
            d['currency'] = 'CNY'
            migrating_to_cny = True
            needs_resave = True
        if 'cny_rate' in raw and (migrating_to_cny or d.get('currency') == 'CNY'):
            if 'currency_rate' not in raw or _currency_rate(raw.get('currency_rate')) == 1.0:
                try:
                    d['currency_rate'] = float(raw['cny_rate'])
                    needs_resave = True
                except (TypeError, ValueError, OverflowError):
                    pass
        if 'cny_mode' in d or 'cny_rate' in d:
            d.pop('cny_mode', None)
            d.pop('cny_rate', None)
            needs_resave = True
    if not d.get('currency'):
        d['currency'] = 'USD'
    d['currency_rate'] = _currency_rate(d.get('currency_rate'))
    d['alpha'] = _window_alpha(d.get('alpha'))
    d['x'] = _window_pos(d.get('x'))
    d['y'] = _window_pos(d.get('y'))
    try:
        d['refresh_sec'] = max(10, int(float(d.get('refresh_sec') or 60)))
    except (TypeError, ValueError, OverflowError):
        d['refresh_sec'] = 60
    encrypt = d.get('encrypt_keys', True)
    if not isinstance(encrypt, bool):
        encrypt = True
        d['encrypt_keys'] = True
        needs_resave = True
    # Detect a machine-key change (vs what was on disk) so the stuck-keys
    # warning can say why instead of guessing.
    key_changed = bool(raw.get('key_id')) and raw['key_id'] != _key_id()
    # Decrypt sensitive fields. _decrypt_values decides per value whether the
    # config needs a re-save; stuck values are reported for the warning.
    stuck_fields = []
    for field in ENCRYPTED_FIELDS:
        if field not in d:
            continue
        if field == 'extra_keys':
            d[field], stuck, resave = _decrypt_values(_as_key_list(d[field]), encrypt)
        else:
            vals, stuck, resave = _decrypt_values([d[field]], encrypt)
            d[field] = vals[0]
        if stuck:
            stuck_fields.append(field)
        if resave:
            needs_resave = True
    # Re-save to encrypt plaintext keys, migrate legacy-key or redundant-layer
    # tokens to the stable machine key, or persist the cny_* migration.
    if needs_resave:
        save_config(d, config_path)
    d['key_id'] = _key_id()
    return d, stuck_fields, key_changed

def save_config(cfg, config_path=None):
    config_path = config_path or CONFIG_PATH
    # Encrypt sensitive fields before saving if encryption is enabled
    encrypt = cfg.get('encrypt_keys', True)
    cfg_to_save = dict(cfg)
    for field in ENCRYPTED_FIELDS:
        if field in cfg_to_save:
            if field == 'extra_keys':
                keys = _as_key_list(cfg_to_save[field])
                cfg_to_save[field] = [_encrypt_value(k, encrypt) for k in keys]
            else:
                cfg_to_save[field] = _encrypt_value(cfg_to_save[field], encrypt)
    # Fingerprint of the primary key so the next load can tell when it changed
    cfg_to_save['key_id'] = _key_id()
    # Write to a temp file and atomically replace, so a crash or full disk
    # mid-write can never leave a truncated config.json behind.
    tmp_path = f'{config_path}.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(cfg_to_save, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, config_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
