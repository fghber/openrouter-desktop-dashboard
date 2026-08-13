# Plan: Locale-aware date formatting (zero new deps)

**TL;DR** — Add locale-aware **short** date formatting for the daily-breakdown popup (and any other visible date labels) using **only the Python standard library**. No `babel`, no `PyICU`. Strategy: a small built-in mapping of IANA timezone to BCP-47 locale (e.g. `Asia/Shanghai` to `zh_CN`), a curated per-locale short pattern table (e.g. `dd.MM.yyyy` / `M/d/yy` / `yyyy年M月d日`), and `time.strftime` to render. Provides a deterministic default, a graceful English fallback.

## Steps

1. **Discovery / mapping table** — author a small `LOCALE_PATTERNS` dict covering the locales needed by the timezones already in `COMMON_TIMEZONES` in `main.py` (en, de, fr, ja, zh-CN, zh-TW, ko, es, pt, ru, it, nl, sv, da, no, fi, pl, tr, vi, th, id, hi, ar, he, uk, cs, el, hu, ro, bg). For each, hardcode only `date_short` (e.g. `dd.MM.yyyy`, `M/d/yy`, `yyyy年M月d日`). Use POSIX `%` codes because we render with `datetime.strftime` (no need for CLDR patterns). For locales without written month names in the C runtime (zh, ja, ko, ar, he, th), pre-translate month/weekday names in the dict and render via a small helper (string-substitution) instead. *depends on: nothing — pure data*

2. **Timezone to locale mapping** — author a small `TZ_TO_LOCALE` dict covering the same timezones: e.g. `Asia/Shanghai` to `zh_CN`, `Asia/Tokyo` to `ja_JP`, `Europe/Berlin` to `de_DE`, `America/Los_Angeles` to `en_US`, `America/Sao_Paulo` to `pt_BR`, `Europe/Moscow` to `ru_RU`, `Asia/Dubai` to `ar_AE`, `Asia/Jerusalem` to `he_IL`, `Asia/Bangkok` to `th_TH`, etc. Always default to `en_US` when the IANA zone is not in the map or the IANA is empty (system local). *depends on: nothing — pure data*

3. **`_format_date_locale(dt, locale=None)` helper** — pure stdlib, no side effects, no `setlocale` calls. Take a `datetime` (or `date`) and an optional BCP-47 locale string. Resolve locale: explicit arg to `TZ_TO_LOCALE[tz]` to `en_US`. If locale has a pre-translated months/days dict (e.g. `zh_CN`), substitute month/day names into the pattern manually; otherwise use `dt.strftime(pattern)`. The function **must not** mutate the process locale. Always uses short format. *depends on: 1, 2*

4. **Plumb into UI** — replace `tk.Label(row, text=day, ...)` in `_open_daily_popup` (around `main.py:1502`) with `_format_date_locale(self._now(), locale=<derived from configured timezone>)`. The "Date" column header should be localized too. *depends on: 3*

5. **Config integration** — extend `config.example.json` (mirrors `load_config` defaults) with a new `date_format` key (values: `system|short`, default `system`). Add a `ttk.Combobox` in the settings dialog alongside the existing timezone combo. Apply the chosen style inside `_format_date_locale` (when `system` or empty, infer from IANA timezone mapping or fall back to `en_US`/`short`). *depends on: 3*

6. **Tests** — add `tests/test_locale_dates.py` covering: (a) `_format_date_locale` returns expected short-format strings for `en_US`, `de_DE`, `zh_CN`, `ja_JP`, `fr_FR`; (b) the timezone to locale map resolves all entries in `COMMON_TIMEZONES` to a known locale; (c) the helper leaves `locale.getlocale()` unchanged before/after (i.e. no process-locale mutation); (d) the daily-popup row formatter is locale-aware (snapshot the row string for each sample). *depends on: 3, 4, 5*

## Relevant files
- `main.py` — add `LOCALE_PATTERNS`, `TZ_TO_LOCALE`, `_format_date_locale` near the top (after `COMMON_TIMEZONES`/`CURRENCIES` blocks around line ~30–80); modify `_open_daily_popup` (around line 1502) to use it; add `date_format` row to the settings dialog; update `load_config` defaults.
- `config.example.json` — add `"date_format": "system"` field.
- `tests/test_locale_dates.py` (new) — unit tests for the formatter, mapping completeness, locale side-effect test, and the popup row.

## Verification
1. Run `pytest tests/` (or `python -m pytest tests/test_locale_dates.py -v`) — all new tests pass.
2. Run `python main.py`, open settings, set timezone to `Asia/Shanghai`, set date_format to `medium`, save, click "Monthly Details" — daily-breakup date column should show `8月12日 2026年` style (or our closest representation; see decisions below).
3. With timezone `Europe/Berlin`, dates should read `12.08.2026`.
4. With timezone `America/Los_Angeles`, dates should read `Aug 12, 2026`.
5. Run `python -c "import locale; print(locale.getlocale())"` before and after invoking `_format_date_locale` — must be identical (proves we don't call `setlocale`).
6. Smoke-test the existing test suite to ensure no regressions (`pytest tests/test_formatting.py tests/test_update_ui.py`).

## Decisions
- **Zero new dependencies.** Confirmed by the user. AGENTS.md already says avoid new deps unless explicitly requested.
- **Do not use `locale.setlocale`.** It is unreliable on Windows (BSD-style names vs Windows names), is process-global (breaks other threads and the rest of the app), and is the very thing we are trying to avoid. Document this decision in a code comment in `main.py` near the helper.
- **IANA timezone to locale by hardcoded table** (option chosen in the research). We do not need a runtime library because the user's timezone is one of ~35 known IANA zones from `COMMON_TIMEZONES`. Anything outside the table falls back to `en_US`.
- **Render with `time.strftime`/string substitution** — for Latin/Cyrillic/Greek locales, plain `dt.strftime(pattern)` works because Windows provides translated month names for these via the C runtime. For CJK and RTL locales, we cannot rely on the C runtime for translated month names, so we pre-translate them in the data table and substitute manually.
- **Style semantics:** `short` = numeric (e.g. `08/12/26`), `medium` = abbreviated month name + day + year (e.g. `Aug 12, 2026` / `12.08.2026`).
- **Out of scope:** translating weekday/month names in the time-of-day label in the footer; that is a separate i18n pass. Currency strings are already handled.
- **`date_format` config key** added; default `system` (derive from timezone).

## Further considerations
1. **CJK/RTL accuracy vs. effort.** For zh_CN the medium format using a hardcoded pattern `yyyy年M月d日` plus a manual month substitution is feasible, but month names (一月, 二月 …) are not used in numeric-date styles so we can mostly avoid them. RTL output is currently not needed (the app is LTR). If the user later wants native CJK month names, we extend the data table.
2. **`en_US` for everything is acceptable as a baseline** but the user picked zero-deps, so the hardcoded table is the path. If we discover the table is too sparse, we can extend it case-by-case.

## Research findings (summary)

### 1. Windows locale name format (`locale.setlocale`)
- POSIX: `language[_territory][.charset][@modifier]` (e.g. `en_US.UTF-8`, `de_DE.UTF-8`).
- Windows: accepts both IETF BCP-47 (`en-US`, `de-DE`, `zh-CN`) **and** legacy `Language_Country.Codepage` (`English_United States.1252`, `German_Germany.1252`, `Chinese_China.936`).
- The C runtime / UCRT on Windows is documented to accept BOTH forms. See Microsoft "Locale Names, Languages, and Country/Region Strings" and "Language Strings" (linked in the research notes).
- **However**, `time.strftime('%x', ...)` is what actually renders, and `%x` is governed by the **process's LC_TIME** category. `setlocale(LC_TIME, 'de_DE')` is *supposed* to work but historically has bugs in UCRT and in the Python `_locale` extension on Windows, especially with UTF-8 codes, and is not thread-safe (the docstring explicitly warns about this).
- **Verdict:** not reliable enough for an app that runs on a single process with a background fetch thread.

### 2. `setlocale` reliability on Windows
- Documented as **not thread-safe** in `locale.py`'s own docs.
- Documented as "expensive" and with side effects on the entire process.
- On Windows, `LC_TIME` accepts BCP-47 (`en-US`) but the behavior of `%x`/`%X` after a `setlocale` call depends on the Windows NLS data the user has installed; for many users it works, but edge cases (missing locale packs, mismatched code pages) are common.
- Pitfall: must call `setlocale(LC_ALL, '')` first to initialize properly, then `setlocale(LC_TIME, target)` — but doing so changes every other module's number formatting too.
- **Verdict:** unsafe for a single-process tkinter app with a refresh thread.

### 3. Alternative approaches
- **`babel`** (https://babel.pocoo.org): pure Python, ~10 MB install (CLDR locale data for ~500 locales; one `.dat` file per locale in `babel/locale-data/`). Provides `format_date`, `format_datetime`, `format_time`, `Locale.parse`, `get_timezone_name`, `get_timezone_location`. Used by Flask, Sphinx, Anki, Jupyter, ~400k GitHub dependents. **No C extensions** — pure-Python install is a single wheel. **There is no PyInstaller hook for babel** in `pyinstaller-hooks-contrib/stdhooks`, so we'd need to write our own `datas` entry to bundle `babel/locale-data/*.dat` files. **Disqualified by user choice** (zero new deps).
- **`PyICU`**: thin Python wrapper over IBM's ICU C++ library. Windows wheels are provided via Christoph Gohlke's unofficial builds and `conda-forge`, but **no official PyPI wheels for PyPI 3.12+ on Windows**; install requires building ICU. Heavy, hundreds of MB. **Disqualified.**
- **Manual IANA to locale mapping + pattern table**: pure stdlib. Reliable, deterministic, small (~200 LOC). Adopted.
- **stdlib `locale` with Windows names**: would still call `setlocale`, so it has all the same problems.

### 4. Mapping IANA timezone to locale
- Babel exposes `get_global('zone_territories')` (e.g. `Europe/Berlin` to `DE`) but only if you use Babel.
- Without Babel, the most reliable mapping is a **hand-curated table** because the IANA tz database contains ~600 zones and the CLDR mapping isn't always 1:1 (e.g. `Asia/Shanghai` to `CN` to `zh_Hans_CN`). For our ~35 supported zones, hand-curating is trivial and 100% correct.

### 5. `strftime` codes
- `%x` is "locale's appropriate date representation" (e.g. `08/12/2026` or `12.08.2026`). Its content depends entirely on the **process's LC_TIME**, which is what we want to avoid controlling.
- `%B` (full month name), `%b` (abbreviated), `%A` (full weekday), `%a` (abbreviated) — these read from the same locale.
- Custom format examples: `Aug 12, 2026` approx `%-d %b %Y` (POSIX), or `"%b %-d, %Y"` cross-platform.
- `12.08.2026` approx `%d.%m.%Y`. `2026年8月12日` requires manual substitution because POSIX `strftime` won't produce CJK month names unless the system locale supports them (and most don't).

### 7. Fallback when IANA is missing
- For our app, the IANA timezone is set by the user in Settings (or empty = system local).
- Reasonable default chain: `TZ_TO_LOCALE[configured_tz]` to `en_US` (English, US) to `medium` style.

### 8. Testing locale-dependent code in pytest on Windows
- `pytest`'s `monkeypatch` fixture can replace `locale.setlocale`, `time.strftime`, `babel.dates.format_date` etc.
- The cleanest pattern: **do not call `setlocale` at all** in the code under test (which is our plan), and use snapshot-style assertions against a fixed `_format_date_locale(d, 'medium', 'de_DE')` to `'12.08.2026'`.
- For the popup, snapshot the label string and assert equality.

### 9. PyInstaller compatibility
- Stdlib only — no issues.

---

Q: How should we determine the user's locale for date formatting?
A: Stdlib-only (recommended) - No new dependencies. A built-in IANA→locale map (Asia/Shanghai→zh_CN, Europe/Berlin→de_DE, etc.) plus a curated per-locale pattern table. Renders via datetime.strftime. Honors AGENTS.md 'avoid new deps'.
Q: How should the locale be selected — auto from IANA timezone, or a new explicit setting?
A: Auto from timezone (recommended) - When user picks Asia/Shanghai in Timezone, dates automatically show in zh_CN format. No extra setting. Uses built-in TZ→locale map.
Q: Should the date format style be configurable?
A: Fixed (very) short style
Q: Which date strings should be localized?
A: Both visible dates (recommended) - Localize both the TOP 3 title and the Date column in the Monthly Details popup. Matches your example `f'Monthly TOP 3 ({latest_date})'`.