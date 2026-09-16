# Findings log

Local dedup log for confirmed, reproduced issues. Date: 2026-09-15.

## [dup-extra-keys] main.py `_fetch` / `_unique_extra_keys` — duplicate extra keys double-counted
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestDuplicateExtraKeys::test_duplicate_extra_keys_are_not_double_counted

## [stuck-key-bearer] main.py `_fetch` / `_usable_secret` — stuck Fernet tokens sent as Authorization Bearer
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestStuckKeyNotSent

## [auth-json-crash] main.py `_fetch` — JSONDecodeError on HTTP 200 non-JSON body
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestAuthKeyInvalidJson

## [tz-overflow] main.py `resolve_tz` — OverflowError on inf/huge numeric offsets
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestResolveTzOutOfRange

## [refresh-sec-type] main.py `_on_fetch_done` / `_refresh_interval_ms` — TypeError if refresh_sec is null or string
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestRefreshSecNull

## [fmt-bad-rate] main.py `_fmt` / `_currency_rate` — ValueError/TypeError on non-numeric rate
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestFmtBadRate

## [extra-keys-string] main.py `_unique_extra_keys` — string extra_keys iterated per character
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestExtraKeysType

## [encrypt-keys-null] main.py `load_config` — JSON null encrypt_keys coerced to True
- Date: 2026-09-15
- Status: fixed
- Repro: tests/test_repro_candidates.py::TestEncryptKeysNull::test_null_encrypt_keys_coerced_to_true
