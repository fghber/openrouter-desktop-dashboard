# Unproven follow-ups

Candidates from the 2026-09-15 repro-gate review that were **not** confirmed with a failing production-path test, but still look plausible. Do not treat these as findings until they reproduce.

Confirmed/fixed issues live in `changelog.md` (`## [Unreleased]` → `### Fixed`).

## Product / data

### Stale FX rate when changing currency in Settings
- **Fixed 2026-09-28**: `tests/test_repro_gate_20260927.py::TestSettingsStaleRateOnCurrencyChange` — `_save` in `main.py` now ignores the stale rate field when the currency changed and blocking-fetches a fresh rate (`USD` → `1.0`; fetch failure → `1.0` + `?` marker). Same-currency saves still honor the hand-edited field.
- **Where:** `_open_settings` → nested `_save` in `main.py` (currency / `rate_var`); rate field is only updated by “↻ Fetch” or by hand.

### Activity list truncated at 1000 rows
- **Why it might be real:** `_fetch_activity` requests `params={'limit': 1000}` with no pagination. Heavy accounts could undercount TOP 3 and the daily popup.
- **Where:** `Dashboard._fetch_activity`.
- **To confirm:** Live OpenRouter `/activity` (or a fixture with `>1000` rows plus documented paging). Check whether the API supports `offset` / cursor / extra pages.
- **Possible fix:** Page until a short page, or document the cap in the UI/README.

### UTC month vs configured timezone
- **Why it might be real:** Activity filtering uses `datetime.now(timezone.utc)` → `YYYY-MM`, while the rest of the UI uses `resolve_tz(config timezone)`. Near month boundaries (e.g. UTC+12 early on the 1st), TOP 3 / daily popup can show the other calendar month vs the clock.
- **Where:** `_fetch_activity` `month_prefix` vs `_now()`.
- **To confirm:** Freeze time at a boundary (e.g. 2026-09-01 04:00 `Pacific/Auckland` = still August UTC) with mixed-month activity dates; compare popup vs “Monthly Spend” (`usage_monthly`). README already says activity is last-30 **UTC** days — may be design, not a bug.
- **Possible fix:** If product intent is local month, filter with configured tz; if UTC, label the popup “UTC month”.

### HTTP 5xx not retried on credits / extra keys
- **Fixed 2026-09-28**: `tests/test_repro_gate_20260927.py::TestHttpErrorNoRetry` — `_fetch_credits` and `_fetch_extra_key_usage` in `main.py` now retry transient 429/5xx within the existing attempt budget (honoring `Retry-After` on 429, capped at 10s) while 401 and other client errors fail fast.
- **Where:** `_fetch_credits` (3 attempts), `_fetch_extra_key_usage` (2 attempts). Main `/auth/key` and `/activity` keep the existing fail-fast pattern (out of scope).

### Legacy activity token field names
- **Why it might be real:** Code reads `prompt_tokens` / `completion_tokens` only. Changelog notes a rename from `tokens_prompt` / `tokens_completion`. Mixed or old payloads would show **0 tokens** with non-zero cost.
- **Where:** `_fetch_activity` token fields.
- **To confirm:** Current OpenRouter `/activity` schema (docs or a live `mgmt_key` response). Fixture with only legacy names should currently yield `tokens == 0`.
- **Possible fix:** `g.get('prompt_tokens') or g.get('tokens_prompt')` (same for completion).

## Durability

### Atomic save without `fsync`
- **Why it might be real:** `save_config` writes a temp file and `os.replace`s it, so the file is no longer torn. Without `flush` + `fsync`, a power loss can still lose the *new* config and keep the previous one (or, on some filesystems, an empty new file). Lower risk than the old in-place truncate, still not crash-proof.
- **Where:** `save_config`.
- **To confirm:** Hard to unit-test honestly. Review Windows `os.replace` + NTFS behavior, or an integration test that mocks a crash after write-before-replace.
- **Possible fix:** `f.flush(); os.fsync(f.fileno())` before `replace`; optionally fsync the directory.

## Docs (valid mismatches, not crashes)

### Right-click menu vs README
- README Usage: “Settings / Refresh / Transparency / Pin / Exit”.
- `_ctx_menu`: Pin, Settings, Refresh, Exit — **no transparency**.
- Also: README is duplicated (two Quick Start / Features blocks). Changelog says Europe/Berlin dates are `12.08.2026`; `LOCALE_PATTERNS['eu']` is `DD/MM/YYYY` (`12/08/2026`). Tests match the slashes.

### `run.vbs` Python version
- Message still says “Install Python 3.9+”. App uses `float | None` (3.10+) and README/AGENTS say 3.10+. Cosmetic unless someone installs 3.9 from that prompt and hits `TypeError` on import.

## Out of scope / discarded
Do not reopen without new evidence:
- `resolve_tz("24")` / `"25"` — no crash; falls back to system local.
- `limit: 0` → “No Quota Limit” — current behavior, no crash.
- `_format_date_locale` `%-m` after `%m` — no current locale pattern uses unpadded forms.
