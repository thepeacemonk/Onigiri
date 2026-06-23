# AGENTS.md

## 1. Project Manifesto & Core Directives
Onigiri is an experimental Anki add-on that completely revamps the user interface to be modern, customizable, and motivating through gamification elements. Its primary design philosophy is "Calm defaults, powerful options"—enhancing user motivation without breaking Anki's core study paradigms.
The core tech stack consists of Python (3.9+) utilizing PyQt6 (Anki's default UI framework), alongside standard web technologies (HTML, CSS, JavaScript) for WebView injections.

## 2. Directory Architecture & Navigation Map
Below is a tree diagram of the essential files and directories, and what logic lives where:

```text
.
├── __init__.py           - Main entry point that sets up global hooks and initializes the add-on.
├── config.py             - Manages reading, writing, and migrating user preferences.
├── constants.py          - Centralized list of constants and static file paths.
├── onigiri_renderer.py   - Replaces Anki's default deck browser rendering with Onigiri's custom UI.
├── patcher.py            - Monkey-patches Anki's core UI components and intercepts webview loads.
├── heatmap.py            - Parses review data and generates the study heatmap data structure.
├── sync.py / sync_ui.py  - Handles syncing custom Onigiri config data across devices via AnkiWeb.
├── webview_handlers.py   - Bridges JavaScript events from the web UI to the Python backend.
├── gamification/         - Contains logic for gamified study elements (Onigimon, restaurant levels, currency).
├── settings/             - Houses the PyQt6 infrastructure for Onigiri's custom settings dialog and tabs.
├── system_files/         - Stores static UI assets including fonts, base icons, and profile defaults.
└── web/                  - Frontend web stack (HTML/CSS/JS) injected into Anki's webviews.
```

## 3. Workflow & State Management
1. Check Anki version compatibility (currently targeted for 25.07.5 and 25.09).
2. Review `__init__.py` and `patcher.py` to understand where hooks and UI overrides are currently applied.
3. Verify asset dependencies in `/system_files` before adding any new graphical elements.
To test and run the project, the code must be loaded as an add-on directly within a local Anki installation (typically placed in the `%APPDATA%\Anki2\addons21` folder or equivalent), as there is no standalone build command or test suite.

## 5. Formatting & Commit Standards
Follow strict Python PEP 8 style guidelines and ensure all web assets are clean and heavily commented.
Always use the conventional commit format for summarizing work (e.g., `feat: implement new Onigimon animation`, `fix: resolve CSS conflict on profile page`).
