# AI Agent Instructions: OpenRouter Dashboard

## Project purpose
This is a small Windows desktop dashboard built with `tkinter` for monitoring OpenRouter usage and spend. The app runs from a single Python entrypoint, `main.py`, and uses `requests` to fetch OpenRouter API data.

## Key files
- `main.py` — single-source application logic, UI, config handling, API integration, refresh scheduling, and tray-like behavior.
- `config.example.json` — reference config schema for runtime settings.
- `requirements.txt` — dependency list containing `requests`.
- `README.md` — user-facing usage and packaging instructions.

## Recommended agent behavior
- Treat `main.py` as the authoritative source of app behavior, not as a library package.
- Preserve the single-file structure unless the user explicitly asks to refactor into modules.
- Keep Windows-specific UI code intact: `enable_window_effects`, `sys.frozen` handling, and `tkinter` window attributes are central to the UX.
- When changing config behavior, update both `config.example.json` and runtime handling in `main.py`.
- Avoid introducing new runtime dependencies unless the user explicitly requests them.

## Runtime and development
- Run locally with `python main.py` after installing dependencies from `requirements.txt`.
- The app requires Python 3.9+ and targets Windows.
- Packaging is done with PyInstaller, e.g.:
  ```bash
  pip install pyinstaller
  pyinstaller --onefile --windowed --name OpenRouter-Dashboard main.py
  ```

## Important app behavior
- Important: The `config.json` contains user API keys and should not be read or output in any way.
- The app stores config in `config.json` next to the script or executable.
- Config fields include: `api_key`, `refresh_sec`, `x`, `y`, `alpha`, `timezone`, `extra_keys`, `pinned`, `cny_mode`, `cny_rate`, `mgmt_key`, and `island_state`.
- API endpoints used:
  - `https://openrouter.ai/api/v1/auth/key`
  - `https://openrouter.ai/api/v1/credits`
  - `https://openrouter.ai/api/v1/activity`
- `extra_keys` are aggregated for daily/monthly usage; `mgmt_key` is optional and used only for monthly model TOP 3 and daily breakdown.
- The app refreshes automatically on a timer and uses a background thread for network requests.

## UI conventions
- Two main states: `island` (collapsed capsule) and `expanded` (full dashboard).
- Right-click menu offers pin, settings, refresh, and exit.
- Window drag supports edge snapping and position persistence.
- Currency toggle supports USD/CNY display.

## Notes for change proposals
- If adding features, keep the visible dashboard minimal and preserve the compact capsule style.
- If modifying refresh behavior, maintain `root.after` scheduling and thread safety for UI updates.
- Do not hardcode API keys or secrets in source control.

## References
- `README.md` for user-facing setup and feature summary.
- `config.example.json` for current config schema.
- `changelog.md` for recent changes and version history.
