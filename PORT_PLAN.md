# Onigiri v2 — status

Branch: `louie/v2-peace-port` (base: Louie `louie/improvements`).
Peace v1.0 reference tree: `C:/Users/Louie/OneDrive/Documents/Anki/Onigiri-merge`.

## Completed
- **Support modules**: onigiri_notifications (rich in-app toasts, used addon-wide),
  emoji_sprites, onigiri_color_picker, onigiri_date_picker, refresh, assets.py,
  ui_widgets.py (FlowLayout/AnimatedToggle/EffectSlider), icon_picker.py, bento_api.py
  (external add-on API, dynamic addon id).
- **Shared merges**: translations.py (superset, adds current_locale + all feature strings),
  config.py (+27 feature defaults, effective_night_mode, fossil cleanup).
- **Features**: Pomodoro (+Shift+P, stats), Hashi Notes (+gallery, reviewer popup,
  expiry purge), Prep Station (+widget), Learner Stats widget (+deck picker cmds),
  guide/donations dialogs.
- **Gamification**: full upstream stack adopted (nook_level keeps restaurant_* storage
  keys → progress preserved), Onigimon care dialog, Hexagon Land (+widget +pan persist),
  reward redemption, richer onigimon toasts. restaurant_level*/shop_handler removed,
  all call sites renamed.
- **Dashboard widgets**: hexagon_land / deck_stats / prep_station generators with span
  clamps; learner-stats external hooks.
- **Profile panel**: click profile bar → slides profile (avatar/status/bio/music embed)
  into sidebar; back button returns. Full profile page still in Onigiri menu.
- **Settings**: modular settings/ package adopted (search built in, pages for every
  feature). Monolith settings.py removed. Reconciliation:
  - Widget Background section (glassmorphism/overlay/solid → onigiri_widget_bg_*)
  - Sidebar Behaviour (collapse-button visibility, ellipsis toggle)
  - Profile Avatar & Sections (size presets, initials colours, section visibility)
  - Reviewer Notifications (6-way position, silent toggle)
  - Profile name colour renderer block ported (upstream page controls now live)
  - Dead upstream sidebar position selector (left/center/right) removed — runtime
    is left-anchored with Louie DECKS-header display modes
  - All new sections indexed in settings search
- **Menu**: Games / Study Tools / Info submenus, translations, version footer.
- **Verification**: every .py compiles; every .js syntax-checked; import graph
  statically verified (caught + fixed 2 breaks); all 34 sent pycmds have handlers;
  system-icon references exist; no hardcoded upstream addon ids in live code paths.
- **Hygiene**: __MACOSX junk, css_history, temp_old_engine, stray dev files removed.
- **Data**: live hashi notes + hexagon land saves rescued from the wiped 1011095603
  install into user_files; ambiguous saves kept as *.peace-backup.json.

## Known items for live testing
- Settings dialog visual pass: functional consistency done by construction (shared
  SectionGroup/toggle/segment widgets); subjective styling tweaks need eyes on screen.
- hexagon_land.py has a pre-existing upstream SyntaxWarning (JS regex in a plain
  string at ~line 2540) — harmless.
- Reviewer top-bar buttons for Hashi/Pomodoro (upstream had them in its shadow-DOM
  top bar; Louie top bar kept) — tools reachable via menu + Shift+P; decide placement later.
- Peace's onigiri_color_picker favourites use a new storage key; old favourites list
  (onigiri_favorites) not migrated.
