# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Locale-aware short date formatting**: Dates in the Monthly Details popup are now formatted according to the user's configured IANA timezone, using a built-in timezone-to-locale mapping (e.g., `Asia/Shanghai` → `2026年08月12日`, `Europe/Berlin` → `12.08.2026`, `America/Los_Angeles` → `08/12/2026`). Uses only the Python standard library — no `setlocale` calls, no new dependencies.
- **Multi-currency support**: Replaced hardcoded CNY/USD toggle with a generic currency system supporting 20 currencies (USD, CNY, EUR, GBP, JPY, CAD, AUD, CHF, INR, KRW, BRL, RUB, TRY, ZAR, SGD, HKD, TWD, MYR, THB, IDR).
- **Currency combobox in Settings**: Users can select any supported currency from a dropdown.
- **Exchange rate fetching**: Added "↻ Fetch" button in Settings to auto-fetch live USD→selected currency rates from exchangerate-api.com (with exchangerate.host fallback).
- **Currency toggle button**: Left-side title-bar button toggles USD ↔ the last non-USD currency chosen in Settings, with live symbol display.
- **Timezone configuration**: Users can set timezone via IANA name (e.g., `Asia/Shanghai`), numeric offset (e.g., `8`, `-3.5`), or empty for system local.
- **Timezone combobox in Settings**: Dropdown with 35 common IANA timezone names.
- **`resolve_tz()` function**: Resolves timezone specs to `tzinfo` objects with fallback to system local.
- **Machine-specific encryption**: API keys (`api_key`, `extra_keys`, `mgmt_key`) are encrypted using Fernet (AES) with a machine-derived key based on MAC address.
- **Encryption toggle in Settings**: Lock button (🔒) in Settings allows users to toggle encryption on/off.
- **Auto-migration**: Plaintext keys in existing config are automatically encrypted on first load.

### Changed
- **Windows launcher**: Removed redundant `run.bat`. `run.vbs` no longer silently `pip install`s on every start; it resolves `pythonw`/`python` on PATH, checks for `main.py`, and shows a clear error if Python is missing.
- **Removed stale `plan.md`**: Locale-aware date formatting plan was already implemented; kept history in `changelog.md`.
- **Currency defaults are currency-agnostic**: CNY is no longer the implicit alternate for `last_currency` or the title-bar toggle. `last_currency` is only set from a real non-USD choice; an invalid or missing alternate keeps the display on USD. Renamed `_cny_btn` → `_currency_btn`.
- **Config migration**: Old `cny_mode`/`cny_rate` config fields automatically migrate to new `currency`/`currency_rate` fields.
- **`_fmt()` and `_fmt2()` methods**: Now format amounts according to the selected currency's symbol, decimal places, and exchange rate.
- **`load_config()`**: Decrypts sensitive fields on load; re-saves config to encrypt any plaintext keys.
- **`save_config()`**: Encrypts sensitive fields before writing to disk.
- **Config field**: Added `encrypt_keys` boolean (default `True`).
- **Config field**: Added `timezone` string field.
- **`_now()` method**: Returns current time in the configured timezone.
- **Time display**: All time labels now use the configured timezone.
- **Dynamic Island capsule height**: Reduced from 36px to 32px for a more compact capsule.
- **Expanded dashboard height**: Increased from 185px to 200px for more content space.
- **Hover effects**: Island capsule background brightens on hover with coordinated child widget updates.
- **Currency toggle position**: Moved to left side of title bar for visibility when collapsed.

### Fixed
- **Title-bar currency toggle reused a stale FX rate**: Cycling currencies kept one `currency_rate`, so amounts were wrong after USD→CNY/EUR. Toggle is now USD ↔ last Settings currency and preserves the rate.
- **Legacy `cny_mode` migration never applied**: Defaults filled `currency`/`currency_rate` before the migrate check. `load_config()` now detects raw `cny_*` keys and migrates to `currency`/`currency_rate`.
- **Overlapping refreshes scheduled duplicate timers**: Concurrent fetches each called `after()` without cancelling the previous job. Added a refresh generation token and cancel-before-reschedule.
- **Island capsule could not be dragged**: Capsule `<Button-1>` always toggled expand. Click-vs-drag: small movement toggles; larger movement snaps/saves.
- **Monthly spend used delayed activity totals**: Headline monthly card now always uses real-time `usage_monthly` sum; activity remains for TOP 3 / daily popup only.
- **Main key usage re-fetched and sometimes dropped**: Seed daily/monthly from the first `/auth/key` response; fetch only distinct extra keys.
- **Settings “Fetch” rate blocked the UI thread**: Exchange-rate HTTP now runs on a background thread.
- **Title-bar action clicks started a window drag**: Handlers return `'break'` so close/pin/settings/refresh do not propagate to drag.
- **Credits failure showed `$0.00` total**: Total card shows `——` when the credits API fails (same as balance).
- **Encryption lock claimed encryption when Fernet missing**: Settings shows “Encryption unavailable” when `cryptography` is not installed.
- **Window could not be moved to second monitor**: `winfo_screenwidth()` and `winfo_screenheight()` return primary monitor dimensions on some Windows configurations, preventing the window from being dragged beyond the primary monitor. Added `_get_virtual_screen()` method using Windows API `GetSystemMetrics` (`SM_CXVIRTUALSCREEN`/`SM_CYVIRTUALSCREEN`) to get true virtual desktop dimensions across all monitors. Updated `_drag_start`, `_drag_move`, `_drag_end`, and initial window positioning to use virtual screen coordinates.
- **Column alignment in Monthly Details popup**: Header column widths now exactly match row column widths. Previously, headers used `w // 8` (e.g., `60 // 8 = 7` for Share) while rows used hardcoded widths (e.g., `5` for Share), causing misalignment. Headers now use the same fixed widths as rows: `11, 13, 10, 5`.
- **Font mismatch between headers and rows**: Headers used `('Segoe UI', 8, 'bold')` while rows used `('Consolas', 8)`. Different fonts have different character widths, causing pixel-level misalignment even with matching `width` values. Rows now use `('Segoe UI', 8, 'bold')` to match headers exactly.
- **Activity API field name changes**: Updated `tokens_prompt` → `prompt_tokens` and `tokens_completion` → `completion_tokens` to match current OpenRouter API response format.
- **Removed `date_min` parameter**: The activity API no longer accepts `date_min`; removed it from the request params.
- **Tkinter close button binding error**: Fixed `pack().bind()` returning `None` by separating the `pack()` and `bind()` calls onto separate lines.
