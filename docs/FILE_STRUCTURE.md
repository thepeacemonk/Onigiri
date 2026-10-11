# File structure

The add-on entry point remains `../__init__.py`. Internal modules are grouped
by responsibility:

| Folder | Contents |
| --- | --- |
| `core/` | Configuration, safe storage, sync, translations, constants and refresh scheduling |
| `rendering/` | Anki patches, webview handlers, dashboard renderers, widget statistics, templates and themes |
| `study_tools/` | Hashi Notes, Pomodoro, Prep Station and Ready-to-go |
| `dialogs/` | Birthday, credits, donations and sync conflict dialogs |
| `integrations/` | FSRS Helper and macOS title bar integration |
| `integrations/apps_script/` | Google Apps Script database and webhook sources |
| `ui_kit/` | Native widgets, pickers, fonts, emoji assets, notifications and menu actions |
| `api/` | Public sidebar and Bento integration APIs |
| `decks/` | Deck tree, move and drag-and-drop operations |
| `gamification/` | Games, rewards and companion logic |
| `settings_web/` | Settings schema, state, rendering and commands |
| `things_theme/`, `things_stats/` | Kome and its statistics |
| `web/` | Webview HTML, CSS and JavaScript |
| `system_files/` | Bundled artwork, fonts, icons, sounds and the Onigiri logo |
| `tools/`, `tests/`, `docs/` | Maintenance utilities, regression checks and setup documentation |

The root retains Anki's `config.json`, `manifest.json` and `meta.json`, the
existing `onigiri_layout.json`, the README, license, and `sidebar_api.py` as a
compatibility entry point for the public Sidebar API.

Saved profile data continues to use the original root-level `user_files/`
directory. Moving Python modules does not move that data, change configuration
keys, or change the add-on package ID. Asset paths are resolved against the
add-on root rather than an individual module's folder.

Internal imports should use the module's grouped location, for example
`from ..core import config` or `from ..study_tools import prep_station`.
Package initializers keep feature loading lazy; the root entry point retains
the existing startup order and hook registration.

The database setup guides are available here:

- [Communications](ONIGIRI_DATABASE_COMMUNICATIONS_SETUP.md)
- [Developer Nooks](ONIGIRI_DATABASE_DEV_SHOPS_SETUP.md)
