# agents.md

This file provides guidance to AI coding agents working with code in this repository.

## What This Is

Onigiri is an Anki add-on (package ID: 1011095603) that replaces Anki's native UI with a modern, customizable dashboard. It includes gamification (restaurant progression, coins, achievements), extensive theming, and profile customization. Beta release targeting Anki 25.07.5 and 25.09 only. Licensed AGPL-3.0.

## Development Environment

This is an Anki add-on — there is no build system, test suite, or CI pipeline. The only way to verify changes is to load the add-on in Anki and test manually. No linter or formatter is configured.

**To test:** Copy/symlink the repo into Anki's add-ons folder (`~/.local/share/Anki2/addons21/` on Linux, `%APPDATA%\Anki2\addons21\` on Windows) and restart Anki.

## Architecture

### Three-Layer Design

**Configuration (`config.py`)** — Profile-specific JSON files in `user_files/settings_{profile}.json`. The `DEFAULTS` dict (~300 keys) covers all settings. `get_config()` deep-merges saved config onto defaults; `write_config()` saves atomically. Legacy migration from Anki's shared config happens on first run per profile.

**Rendering & Patching (`patcher.py` + `onigiri_renderer.py`)** — `patcher.py` (4,100+ lines) is the engine: it patches Anki's DeckBrowser, Reviewer, Overview, and Toolbar classes, generates all dynamic CSS, and handles webview command routing. `onigiri_renderer.py` replaces `DeckBrowser._renderPage` with the Onigiri deck browser, using templates from `templates.py`.

**Web Layer (`web/`)** — JavaScript and CSS injected into Anki's webviews. `engine.js` handles high-performance deck list rendering with scroll preservation. `injector.js` sets up the sidebar and static UI. CSS is mostly generated in Python and injected; the `.css` files in `web/` handle structure that doesn't change with config.

### Hook Registration Order Matters

In `__init__.py`, Anki hooks are registered in a specific order that prevents conflicts with other add-ons. Key constraints:
- `DeckBrowser._renderPage` and `_render_deck_node` are patched **at module load time** (before other add-ons) to prevent an unstyled flash
- `sidebar_api.ensure_capture_hook_is_last()` must run after all other add-ons register their hooks
- Profile-dependent setup (coins, shop, welcome dialogs) runs in `on_profile_did_open` with `QTimer.singleShot` delays to avoid race conditions

### Two Config Storage Backends

- **`user_files/settings_{profile}.json`** — Primary. All Onigiri config lives here.
- **`mw.col.conf`** — Anki's built-in per-collection config. Used for transient per-view state (selected background images, icon filenames, reviewer button colors). These are keyed with `modern_menu_` or `onigiri_` prefixes.

Config that affects rendering is split between these two stores. Settings dialog reads/writes both. When confused about where a setting lives, grep for its key name — if it starts with `modern_menu_` or `onigiri_`, it's in `mw.col.conf`.

### Settings Package (`settings/`)

The settings dialog is split into a package using Python mixins:
- `_dialog_core.py` — `SettingsDialog` class with `__init__`, navigation, save orchestrator
- `_infra.py` — Gallery, icon management, stylesheet (mixin)
- `_page_*.py` — One mixin per settings page (10 files)
- `_widgets.py` — Reusable widgets (toggles, cards, overlays)
- `_color_picker.py`, `_icon_picker.py` — Picker dialogs
- `_layout_base.py`, `_layout_main.py`, `_layout_sidebar.py` — Drag-and-drop layout editors

`SettingsDialog` inherits from all mixins plus `QDialog`. Page creation methods are lazy-loaded via `self.pages` dict. External files import from `settings/__init__.py` which re-exports `SettingsDialog`, `open_settings`, and `FlowLayout`.

### Gamification (`gamification/`)

Isolated subsystem with its own data file (`user_files/gamification_{profile}.json`, separate from config for security). Key pieces:
- `restaurant_level.py` — XP/progression system (13 themed restaurants)
- `taiyaki_store.py` — Coin shop with anti-tampering (security token verified on startup via `verify_coin_integrity()` in `__init__.py`)
- `focus_dango.py` — Focus session tracking

Coins have anti-cheat: a security token is stored alongside the coin count. `__init__.py` verifies this on startup; tampering resets coins to 0.

### Webview Command Bridge

JavaScript calls `pycmd('command_name')` which routes through `patcher.on_webview_js_message()`. Commands include deck operations (`onigiri_collapse:`, `onigiri_toggle_favorite:`), navigation (`openOnigiriSettings`, `openProfile`), and gamification triggers.

### Sync System (`sync.py`, `sync_ui.py`)

Zips `user_files/` into `_onigiri_sync_{profile}.zip` in Anki's media folder. AnkiWeb syncs this as a media file. On sync finish, compares local vs cloud timestamps and shows a conflict dialog if both sides changed.

## Key Conventions

- **PyQt6 only** — no PyQt5 fallback needed (Anki 25.07+ requirement)
- **Profile isolation** — all user data is per-profile via `{profile_name}` in filenames
- **CSS variables** — themes use 50+ CSS custom properties (`--accent-color`, `--bg`, `--fg`, etc.) with separate light/dark palettes
- **Dynamic CSS generation** — most CSS is built as Python strings in `patcher.py` functions like `generate_dynamic_css()`, `generate_deck_browser_backgrounds()`, `generate_reviewer_background_css()`, etc.
- **Atomic file writes** — sync uses tmp-then-rename pattern; config writes directly (JSON)
- **`QTimer.singleShot`** — used throughout for delayed initialization to avoid Anki startup race conditions
