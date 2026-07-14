# Onigiri v2 — Peace v1.0 feature port onto Louie base

Branch: `louie/v2-peace-port`. Base = Louie `louie/improvements` (sidebar/heatmap/dialogs kept).
Peace reference tree: `C:/Users/Louie/OneDrive/Documents/Anki/Onigiri-merge` (pristine upstream/main v1.0).

## Verified facts driving decisions
- Peace `translations.py` is a strict superset of Louie's (0 Louie-only keys). → adopt wholesale.
- Peace gamification package depends only on `config`, `onigiri_notifications`, `translations`. → clean adopt.
- Peace `nook_level` still uses `restaurant_*` storage keys → user progress carries over.
- Live user data rescued from emptied 1011095603 install: hashi_notes/, hexagon_land json,
  `*.peace-backup.json` for gamification/settings saves (user_files, gitignored).
- Louie-only gamification (restaurant_level*, shop_handler) is the older ancestor of Peace's
  (nook_level*, reward_redemption) → superseded, remove after call-site fixes.

## Waves
1. **Support modules** (no deps): onigiri_notifications, emoji_sprites, onigiri_color_picker,
   onigiri_date_picker, refresh, ui_widgets.py (FlowLayout/AnimatedToggleButton/
   MainBackgroundEffectSlider extracted from Peace settings pkg), bento_api (flattened,
   de-hardcoded addon id). Web: adopt Peace notifications.css/js. system_files: emojis/, sounds/,
   peace_logos/ + additive diffs of gamification_images/pokesprite/system_icons.
2. **Shared-file merges**: translations.py (adopt Peace's), config.py DEFAULTS merge.
3. **Features**: pomodoro, hashi_notes (+2 html), prep_station(+ui), learner_stats_widget,
   guide_dialog, donations_dialog (import adaptations: settings pkg → ui_widgets).
4. **Gamification stack**: adopt Peace `gamification/` package + `gamification_settings.py` +
   web/gamification; remove restaurant_level*/shop_handler; fix Louie call sites
   (menu_buttons, onigiri_renderer profile chip, patcher, settings.py, config.py, __init__.py,
   translations refs, manual_reset tool).
5. **Wiring**: menu_buttons rebuild (Study Tools + Games menus), webview_handlers dispatch
   additions, __init__ hooks (notifications css/js injection, hashi purge, learner_stats init,
   bento register), patcher touchpoints (togglePomodoro/openHashiNotes).
6. **Profile panel** (click-to-expand in sidebar) — port from Peace renderer/injector/css.
7. **Settings redesign** — new design system, search, one design language. gamification_settings
   restyle included.
8. **Design-language pass + static verification sweep** (py_compile all, node --check all,
   pycmd cross-ref, icon/asset existence check).

## Decisions log
- Heatmap: Louie's stays (user preference).
- themes.py: Louie's stays (verify THEMES keys used by adopted code exist).
- sync.py / sync_ui.py: Louie's stays.
- webview_handlers.py / patcher.py / __init__.py: Louie's stay as base; additive merges only.
- "Nook" naming adopted (comes with Peace translations; matches ported game stack).
- find_returns.py (dev lint script): not ported.
- icon_modal.js / rename_modal.js (Peace dialogs): not ported — Louie's dialogs are better.
