# Unproven follow-ups

Candidates from the 2026-09-15 repro-gate review that were **not** confirmed with a failing production-path test, but still look plausible. Do not treat these as findings until they reproduce.

Confirmed/fixed issues live in `findings-log.md`.

## Product / data

### Stale FX rate when changing currency in Settings
- **Why it might be real:** Saving Settings writes `currency` from the combobox and `currency_rate` from the rate field as-is. Changing CNY → EUR does not clear or refetch the rate, so a leftover `7.2` can be applied to euros.
- **Where:** `_open_settings` → nested `_save` in `main.py` (currency / `rate_var`); rate field is only updated by “↻ Fetch” or by hand.
- **To confirm:** UI test or extract `_save`: start CNY @ 7.2, switch combobox to EUR, Save without Fetch, assert displayed amounts (or stored `currency_rate`) are not still 7.2.
- **Possible fix:** On currency change, set USD rate to `1.0`; for any other currency reset the field and/or auto-fetch.

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
- **Why it might be real:** `_fetch_credits` and `_fetch_extra_key_usage` retry only on exceptions. Non-200 (including 500/429) `break`s immediately. Transient OpenRouter errors then show `——` balance or silently drop an extra key’s usage.
- **Where:** `_fetch_credits` (3 attempts), `_fetch_extra_key_usage` (2 attempts). Main `/auth/key` is the same pattern for HTTP errors.
- **To confirm:** Mock 500 then 200 on `/credits` or an extra `/auth/key`; today the 200 is never used.
- **Possible fix:** Retry 429/5xx with the existing backoff; still fail fast on 401.

### `alpha` not clamped and not in Settings
- **Why it might be real:** `_setup_window` applies `self.cfg.get('alpha', 0.95)` with no 0.1–1.0 clamp. `alpha: 0` would make the window invisible. README still describes a right-click transparency control; `_ctx_menu` has none.
- **Where:** `_setup_window`, `_ctx_menu`; README Usage table.
- **To confirm:** Load `alpha: 0` / `alpha: 1.5` and see window + Tk errors. Decide whether missing menu is a docs bug or a missing feature.
- **Possible fix:** Clamp on load; restore a simple transparency entry, or drop the README claim.

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

## Partial (code path real; encrypt round-trip not run here)

### `encrypt_keys: null` rewriting ciphertext as plaintext
- **Proven:** `load_config` now coerces non-boolean `encrypt_keys` to `true` (`test_null_encrypt_keys_coerced_to_true`).
- **Unproven here:** `test_null_encrypt_keys_does_not_plaintext_resave` skipped — `cryptography` was not installed, so the old “decrypt then save plaintext” path was not re-run with a live Fernet token.
- **To confirm:** `pip install cryptography` and run that test.

## Out of scope / discarded
Do not reopen without new evidence:
- `resolve_tz("24")` / `"25"` — no crash; falls back to system local.
- `limit: 0` → “No Quota Limit” — current behavior, no crash.
- `_format_date_locale` `%-m` after `%m` — no current locale pattern uses unpadded forms.
