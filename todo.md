# Reviewed follow-ups

The previously listed candidates have been reviewed. Reproduced issues and documentation corrections have been addressed and recorded in `changelog.md`.

Confirmed/fixed issues live in `changelog.md` (`## [Unreleased]` → `### Fixed`).

## Out of scope / discarded
Do not reopen without new evidence:
- Activity analytics use the UTC calendar month; the UI and README now identify this period explicitly.
- `resolve_tz("24")` / `"25"` — no crash; falls back to system local.
- `limit: 0` → “No Quota Limit” — current behavior, no crash.
- `_format_date_locale` `%-m` after `%m` — no current locale pattern uses unpadded forms.
