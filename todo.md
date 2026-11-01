# Unproven follow-ups

Candidates from the 2026-09-15 repro-gate review that were **not** confirmed with a failing production-path test, but still look plausible. Do not treat these as findings until they reproduce.

Confirmed/fixed issues live in `changelog.md` (`## [Unreleased]` → `### Fixed`).

## Product / data

### Activity list truncated at 1000 rows
- **Why it might be real:** `_fetch_activity` requests `params={'limit': 1000}` with no pagination. Heavy accounts could undercount TOP 3 and the daily popup.
- **Where:** `Dashboard._fetch_activity`.
- **To confirm:** Live OpenRouter `/activity` (or a fixture with `>1000` rows plus documented paging). Check whether the API supports `offset` / cursor / extra pages.
- **Possible fix:** Page until a short page, or document the cap in the UI/README.

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
- Activity analytics use the UTC calendar month; the UI and README now identify this period explicitly.
- `resolve_tz("24")` / `"25"` — no crash; falls back to system local.
- `limit: 0` → “No Quota Limit” — current behavior, no crash.
- `_format_date_locale` `%-m` after `%m` — no current locale pattern uses unpadded forms.
