# Onigiri redesign brief — single source of truth

User mandate (verbatim intent): full redesign, light/clean/flat/minimal like a modern
settings app (reference: Claude desktop settings — quiet left nav, generous whitespace,
bold section headers, description text under each row title, right-aligned controls,
thin separators between rows, NO card-in-card nesting, subdued surfaces). One design
language across EVERY surface: settings dialog, gamification hub, all Qt dialogs
(pomodoro/hashi/prep/pickers), web dashboard widgets, overview, sidebar. User trusts
executor to make all design decisions.

## Design tokens (authoritative)
- Radius: 10px controls/inputs/buttons, 14px preview surfaces, 18px window shell. No pills
  except toggles/avatars.
- Row anatomy (settings): title 13px/600 fg + optional description 12px muted below;
  control right-aligned; rows separated by 1px hairline (border at ~8% fg alpha);
  NO boxed sub-panels. Section header: 15px/700, 28px top spacing, description under.
- Buttons: primary = accent bg, white text, 32px, radius 10. Secondary = 1px hairline
  border, transparent bg. Ghost = no border, hover surface. One height per context.
- Surfaces: window bg = palette --bg; content = --canvas elevated one step; NO nested
  contrasting boxes. Hairlines over borders wherever possible.
- Typography: page title 20/650; section 15/700; row 13/600; desc/meta 12 muted.
- Scrollbars everywhere (Qt + web): 6px thumb, rounded, transparent track, hover darkens
  — match the deck-sidebar's thin scrollbar. Overflowing text: fade-out mask, not ellipsis
  (deck-name fade pattern from web/menu.css `.is-overflowing`).
- Icons: Hugeicons (iconify set "hugeicons", MIT-free tier) — stroke style, 1.5px,
  fetched as SVGs into system_files/system_icons/hugeicons/. Replace ALL nav/action
  icons addon-wide. Specific: Languages = hugeicons:globe-02, Donate = hugeicons:favourite
  (heart), Search = hugeicons:search-01, Fonts = hugeicons:text-font, Themes =
  hugeicons:paint-board, Gallery = hugeicons:album-02, Sync = hugeicons:refresh,
  Modes = hugeicons:dashboard-square-01, Main Menu = hugeicons:home-01, Sidebar =
  hugeicons:sidebar-left, Overviewer = hugeicons:analytics-01, Reviewer =
  hugeicons:cards-01 (verify names against API; fetch via
  https://api.iconify.design/hugeicons/<name>.svg).
- Color pickers/swatches: keep onigiri picker; swatches already alpha-safe.

## Required feature changes
1. Remove the WELCOME <h2 class="sidebar-welcome-heading"> from sidebar template
   (templates.py) + strip related CSS. DONE? (verify)
2. Donate icon → heart (settings nav + anywhere else).
3. Profile background GRADIENT option restore (Louie feature: profile bar gradient —
   check `profile_page_bg_gradient_radio` exists in adopted _page_profile; if the
   gradient MODE for profile bar/page was dropped in adoption, port from old settings.py
   in git history: `git show a7dd0f1~1:settings.py`, search gradient).
4. Widgets (web dashboard): restyle nook/onigimon/hexland/prep/stats/favorites cards to
   the same flat language: one surface, hairline border, 14px radius, consistent title
   row (11px/700 uppercase muted), consistent paddings (14px), no mixed fonts. The
   Silkscreen pixel font stays ONLY inside onigimon scene, not its card chrome.
5. Performance: settings dialog lag — profile pages build eagerly? Ensure pages lazy
   (tabs_loaded), avoid repeated preview pixmap renders on every signal; defer
   translations term expansion (already deferred). Investigate `_update_modern_background_preview`
   spam via signal storms (buttonToggled lambdas firing during construction).
   Dashboard: keep Louie fast-path rendering.

## Execution order (work through; keep each step compiling + committed)
A. Fetch hugeicons SVG batch → system_files/system_icons/hugeicons/. Map + replace
   settings nav icons (`_dialog_core.py` nav list ~line 456 (tr(...), "Page", "icon.svg")),
   Donate/Report/Search icons, sidebar toolbar icons (web side uses masks — png/svg url).
B. Settings QSS rewrite in _dialog_core.py around the tokens above (kill boxed
   organizeCompactPanel look: restyle #organizeCompactPanel + SectionGroup in _widgets.py
   to flat rows with hairlines; remove inner QFrame borders).
C. Scrollbar QSS (QScrollBar:vertical 6px, transparent track) global in dialog QSS +
   web overview/settings-like surfaces.
D. Welcome heading removal; heart donate; globe languages (part of A).
E. Web widget CSS pass in onigiri_renderer._PORTED_WIDGET_CSS + Louie's stats-block CSS:
   normalize all widget cards (radius 14, hairline, padding 14, title style).
F. Gradient profile bg restore.
G. Perf pass (signal storms, preview renders, uncached pixmaps).
H. Full verify sweep (compile all, node --check, unresolved names) + commit.

## Status log (update as steps land)
- [2026-07-14] Crashes fixed: tr shadow (deck open), --highlight-bg KeyError (sidebar page),
  nook name in gamification save. Committed 189939e.
- Steps A–H: pending.
