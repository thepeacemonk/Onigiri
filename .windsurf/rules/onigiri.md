---
trigger: always_on
---

This file provides guidance to AI coding agents working with code in this repository.

## What This Is

Onigiri is an Anki add-on (package ID: 1011095603) that replaces Anki's native UI with a modern, customizable dashboard. It includes gamification (restaurant progression, coins, achievements), extensive theming, and profile customization. Beta release targeting Anki 25.07.5 and 25.09 only. Licensed AGPL-3.0.

## Development Environment

This is an Anki add-on — there is no build system, test suite, or CI pipeline. The best way to verify changes is to ask the user to load the add-on in Anki and test manually. No linter or formatter is configured.

**To test:** Copy/symlink the repo into Anki's add-ons folder (`~/.local/share/Anki2/addons21/` on Linux, `%APPDATA%\Anki2\addons21\` on Windows) and restart Anki.

## Architecture

### Three-Layer Design

**Configuration (`config.py`)** — Profile-specific JSON files in `user_files/settings_{profile}.json`. The `DEFAULTS` dict (~250 keys) covers all settings. `get_config()` deep-merges saved config onto defaults; `write_config()` saves atomically. Legacy migration from Anki's shared config happens on first run per profile.

**Rendering & Patching (`patcher.py` + `onigiri_renderer.py`)** — `patcher.py` (4,600+ lines) is the engine: it patches Anki's DeckBrowser, Reviewer, Overview, and Toolbar classes, generates all dynamic CSS, and handles webview command routing. `onigiri_renderer.py` replaces `DeckBrowser._renderPage` with the Onigiri deck browser, using templates from `templates.py`.

**Web Layer (`web/`)** — JavaScript and CSS injected into Anki's webviews. Key files:
- `engine.js` (229KB) — High-performance deck list rendering with scroll preservation
- `injector.js` — Static UI elements (sidebar, resize handle, focus button)
- `heatmap.js`, `heatmap.css` — Heatmap visualization
- `icon_chooser.js`, `icon_chooser.html`, `icon_chooser.css` — Icon picker interface
- `notifications.js`, `notifications.css` — Notification system
- `profile.css`, `profile_page.js` — Profile page styling and logic
- `menu.css` — Menu styling
- `overview.css` — Overview page styling
- `congrats.css` — Congratulations screen styling
- `birthday.html`, `credits.html`, `welcome.html` — Special popup pages
- `gamification/mr_taiyaki_store/` — Store CSS/JS
- `gamification/restaurant_level/` — Restaurant level CSS/JS (including special_dishes.js)

CSS is mostly generated in Python and injected; the `.css` files in `web/` handle structure that doesn't change with config.

### Hook Registration Order Matters

In `__init__.py`, Anki hooks are registered in a specific order that prevents conflicts with other add-ons. Key constraints:
- `DeckBrowser._renderPage` and `_render_deck_node` are patched **at module load time** (before other add-ons) to prevent an unstyled flash
- `sidebar_api.ensure_capture_hook_is_last()` must run after all other add-ons register their hooks
- Profile-dependent setup (coins, shop, welcome dialogs) runs in `on_profile_did_open` with `QTimer.singleShot` delays to avoid race conditions

### Two Config Storage Backends

- **`user_files/settings_{profile}.json`** — Primary. All Onigiri config lives here.
- **`mw.col.conf`** — Anki's built-in per-collection config. Used for transient per-view state (selected background images, icon filenames, reviewer button colors). These are keyed with `modern_menu_` or `onigiri_` prefixes.

Config that affects rendering is split between these two stores. Settings dialog reads/writes both. When confused about where a setting lives, grep for its key name — if it starts with `modern_menu_` or `onigiri_`, it's in `mw.col.conf`.

### Settings Dialog (`settings.py`)

The settings dialog is a monolithic file (12,512 lines) containing:
- `SettingsDialog` class — Main dialog with screen-proportional sizing, navigation, and save orchestrator
- `FlowLayout` class — Custom layout for wrapping widgets
- `ModernColorPickerDialog` class — Color picker dialog
- `IconPickerDialog` class — Icon picker dialog
- `DonationDialog` class — Donation dialog
- Nested layout editor classes: `SidebarLayoutEditor`, `OnigiriLayoutEditor`, `MainMenuLayoutEditor`, `UnifiedLayoutEditor` — Drag-and-drop widget layout editors
- Page creation methods: `create_search_page`, `create_hide_modes_page`, `create_fonts_page`, `create_themes_page`, `create_main_menu_page`, `create_sidebar_page`, `create_overviews_page`, etc.

Page creation methods are lazy-loaded via `self.pages` dict. The `open_settings()` function is the entry point for opening the dialog.

### Gamification (`gamification/`)

Isolated subsystem with its own data file (`user_files/gamification_{profile}.json`, separate from config for security). Key pieces:
- `gamification.py` — Data classes (AchievementData, DailySpecialData, RestaurantLevelData, GamificationData)
- `restaurant_level.py` — XP/progression system (11 themed restaurants)
- `restaurant_level_ui.py` — UI widget for restaurant level display
- `taiyaki_store.py` — Coin shop with anti-tampering (security token verified on startup via `verify_coin_integrity()` in `__init__.py`)
- `shop_handler.py` — Store window class for external shop API
- `focus_dango.py` — Focus session tracking
- `mochi_messages.py` — Mochi encouragement messages during reviews
- `mod_transfer_window.py` — Deck transfer window for moving decks

Coins have anti-cheat: a security token is stored alongside the coin count. `__init__.py` verifies this on startup; tampering resets coins to 0.

### Webview Command Bridge

JavaScript calls `pycmd('command_name')` which routes through `patcher.on_webview_js_message()`. Commands include deck operations (`onigiri_collapse:`, `onigiri_toggle_favorite:`), navigation (`open_settings`, `open_profile`), and gamification triggers. The hook is registered in `__init__.py`. Note: `sidebar_api.py` also registers its own webview hook for toolbar commands.

### Key Standalone Modules

Beyond the three-layer architecture, these modules handle specific functionality:
- `webview_handlers.py` — Webview command handling, deck tree updates, and refresh logic
- `deck_tree_updater.py` — Deck tree state management without full page reloads
- `sidebar_api.py` — API for external add-ons to register sidebar actions
- `constants.py` — Constants including ICON_DEFAULTS, COLOR_LABELS, theme keys
- `themes.py` — Theme management and theme switching logic
- `color_utils.py` — Color normalization, parsing, and contrast utilities
- `fonts.py` — Font management and font discovery
- `heatmap.py` — Heatmap generation and configuration
- `icon_chooser.py` — Icon chooser dialog (AnkiWebView-based)
- `coloris_picker.py` — Color picker using Coloris library
- `create_deck_dialog.py` — Custom deck creation dialog
- `rename_dialog.py` — Deck rename dialog
- `sort_dialog.py` — Deck sort dialog with drag-drop reordering
- `favorites_cleanup.py` — Favorites management and cleanup
- `welcome_dialog.py` — Welcome popup dialog
- `credits_dialog.py` — Credits display dialog
- `birthday_dialog.py` — Birthday popup dialog
- `gamification_settings.py` — Separate gamification settings dialog (1,069 lines)
- `settings_helpers.py` — Settings helper functions
- `menu_buttons.py` — Menu button setup and profile action
- `templates.py` — HTML templates for deck browser and profile page
- `check_icons.py` — Utility script to check icon references in codebase
- `manual_reset_restaurant_level.py` — Debug console script to reset restaurant level

### Dialog Classes in patcher.py

The patcher.py file also contains several dialog classes for gamification features:
- `ProfileDialog` — Profile page dialog
- `RestaurantLevelDialog` — Restaurant level display dialog
- `MrTaiyakiStoreDialog` — Taiyaki store dialog

## Key Conventions

- **PyQt6 with PyQt5 fallback** — Primary target is PyQt6 (Anki 25.07+), but PyQt5 fallback code exists in `__init__.py`, `sidebar_api.py`, and `taiyaki_store.py` for compatibility
- **Profile isolation** — all user data is per-profile via `{profile_name}` in filenames
- **CSS variables** — themes use 50+ CSS custom properties (`--accent-color`, `--bg`, `--fg`, etc.) with separate light/dark palettes
- **Dynamic CSS generation** — most CSS is built as Python strings in `patcher.py` functions: `generate_dynamic_css()`, `generate_deck_browser_backgrounds()`, `generate_reviewer_background_css()`, `generate_profile_page_background_css()`, `generate_overview_background_css()`, `generate_toolbar_background_css()`, `generate_reviewer_bottom_bar_background_css()`, and helper functions `_render_background_css()`, `_generate_outer_background_css()`
- **Atomic file writes** — config writes directly (JSON); theme import/export uses zip files (.onigiri format)
- **`QTimer.singleShot`** — used throughout for delayed initialization to avoid Anki startup race conditions
- **Sync hooks** — `sync_did_finish` and `sync_will_start` hooks update sync status indicators in the UI (no file syncing via AnkiWeb)
- **Icon usage** — All icons must source from SVG files in `system_files/system_icons/` (UI icons) or `system_files/heatmap_system_icons/` (heatmap shapes). Never hardcode inline SVG markup or SVG data URIs directly in code. Instead:
  - CSS: `mask-image: url("../system_files/system_icons/icon.svg")` or `mask-image: url("/_addons/{pkg}/system_files/system_icons/icon.svg")`
  - JS: `url('/_addons/${pkg}/system_files/system_icons/icon.svg')`
  - Python templates: `{system_icon_base}icon.svg` (replaced in `onigiri_renderer.py`)
  - Python code: `os.path.join(addon_dir, "system_files", "system_icons", f"{name}.svg")`
  - The `ICON_DEFAULTS` dict in `constants.py` maps icon keys to filenames
  - Converting SVG files to data URIs dynamically is acceptable for CSS/JS injection, but the source must always be an SVG file from the system_icons folders
  - Exception: `sidebar_api.py` allows external add-ons to provide inline SVGs which are converted to data URIs for the sidebar API
