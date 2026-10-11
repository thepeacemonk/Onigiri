# Anki Design configuration

Every option here is also in **Tools → Anki Design Settings…** (or the
sidebar's Settings row), which is the recommended way to change them. Values
in this file are the raw form the settings page writes.

## Appearance
- **theme** — `"system"`, `"light"`, or `"dark"`.
- **accent** — hex colour for links, the progress bar, and other accents.
  Example: `"#6c8cff"`.
- **background_light** / **background_dark** — page colour override per
  theme. `""` keeps the default paper (light) / ink (dark); a hex such as
  `"#ffffff"` replaces it.
- **sidebar_background_light** / **sidebar_background_dark** — optional
  sidebar-only colours. `""` inherits the corresponding main background.
- **density** — fixed to `"comfortable"` by the integrated Kome layout.
- **font_serif** / **font_sans** — optional display fonts prepended to the
  built-in stacks (e.g. `"Iowan Old Style"`). `""` uses the defaults.

## Home page
- **sidebar_nav** — the left rail replaces Anki's top toolbar. The inline
  windows below need it.
- **sidebar_hero** — the big "Due Today / N cards" number at the top of the
  sidebar (sum of due + new + learning across every deck).
- **sidebar_hero_stat** — which single stat the hero number shows:
  `"due"`, `"new"`, or `"learn"`.
- **sidebar_donut** — the "Active cards" breakdown below the nav, breaking
  every non-suspended card into New / Learning / Relearning / Young (< 21 day
  interval) / Mature (≥ 21 days). Hover a legend row for the count, click to
  open Browse filtered to that state.
- **sidebar_tasks** — a free-form checklist in the sidebar, unrelated to
  cards. Synced with the collection, so it travels with AnkiWeb sync like
  deck config does.
- **sidebar_progress** — the recent-review bars at the bottom of the sidebar.
- **show_review_chart** — the cards-reviewed chart below the deck list.
- **active_cards_colors** — colours for the New, Learning, Relearning, Young,
  and Mature segments in the Active Cards chart.
- **show_today** — the today panel (cards · minutes + per-hour bars).
- **show_streak** — the streak counter above the heatmap.
- **show_heatmap**, **heatmap_weeks**, **heatmap_palette** — the review
  heatmap, its date range in weeks (`53` ≈ a year), and its colour
  (`"accent"`, `"green"`, `"teal"`, `"violet"`, `"rose"`, `"amber"`).
- **hide_bottom_on_decks** / **hide_bottom_on_overview** — hide Anki's
  native bottom strip on those screens.

## Deck list
- **deck_tree_startup** — `"remember"` keeps each deck's own open/closed
  state (Anki's synced flag), `"expanded"` opens everything on launch,
  `"collapsed"` closes every parent on launch.
- **deck_drag_move** — drag a deck onto another to nest it (or onto the
  top-level zone). "Move to…" in the deck menu is always available.
- **single_deck_hero** — with one top-level deck, show it as a big card with
  its sub-decks listed beneath.
- **skip_overview** — clicking a deck starts studying right away. `false`
  opens Anki's overview page first.

## Reviewer
- **reviewer_card_width** — `"narrow"`, `"medium"`, `"wide"`, or `"full"`.
- **reviewer_font_size** — `"small"`, `"medium"`, `"large"`, or `"x-large"`.
- **reviewer_card_styling** — apply Anki Design typography and colours to
  the card body. `false` keeps your note type's own CSS untouched.
- **reviewer_answer_buttons** — `"intervals"` (interval chips under the
  answer) or `"native"` (Anki's Again / Hard / Good / Easy bar).
- **show_progress** — progress strip across the top of the reviewer.
- **click_to_reveal** — clicking the card shows the answer.
- **press_feedback** — the bloom animation when grading.
- **inline_edit** — `E` edits fields in place; `false` opens Anki's editor.

## Windows
- **cmdk** — the ⌘K / Ctrl+K command palette.
- **embed_add**, **embed_browse**, **embed_stats**, **embed_settings** — open
  those inside the main window (needs `sidebar_nav`); `false` uses Anki's
  separate windows.
- **restyle_addcard** — the redesigned Add window. `false` restores Anki's
  stock Add window.
- **congrats_redesign** — the redesigned finished-deck page.
- **silent_sync** — sync progress in the sidebar instead of a dialog.

Changes take effect the next time the relevant screen is drawn (return to
the deck list / start a review). Restarting Anki is never required.
