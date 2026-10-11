# Changelog

All notable changes to Anki Design are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versioning is semver-ish.

## [0.4.2] — 2026-09-05
### Changed
- Settings window footer no longer shows the "Anki Design vX.Y.Z" wordmark.
- Reviewer header now shows only the current deck/subdeck's own name
  instead of the full "Parent::Child::Grandchild" path (still available
  as a tooltip on hover).

## [0.4.1] — 2026-09-04
### Changed
- Removed the sidebar's "Progress" block entirely (the 14-day review bar
  chart + streak flame). The `sidebar_progress_chart` setting is gone with
  it. Active cards legend and Tasks now sit back-to-back where it used to
  be.

## [0.4.0] — 2026-09-04
### Changed
- Sidebar "Active cards" lost its donut ring — it's just the legend now,
  centered in the row where the ring used to sit. The running total moved
  up into the section heading instead of the ring's hollow center.
- Deck list (home page) now has a column header — Deck / Due / Progress /
  New — and each row shows a Due count, a per-deck "studied today" progress
  bar, and a New count, instead of the New/Learning/Review count cluster.
  The current deck's row gets a quiet accent highlight and a flag icon in
  place of its chevron spacer. The congrats "Keep going" list keeps its
  original compact layout (no header, no progress bar).

## [0.3.0] — 2026-09-02
### Fixed
- Sub-decks now open the way you left them. The deck list reads Anki's own
  per-deck collapse flag (the one that syncs), and the chevrons write it
  back — so decks you minimised stay minimised after a restart instead of
  everything expanding on launch. The old behaviour is still available as
  **Sub-decks on startup: Expanded**; there is also **Collapsed**.
- Single-deck home page: a lone top-level deck (e.g. `All::…`) hid all of
  its sub-decks behind the hero card. They now list underneath it, with
  their own chevrons and gears. The hero itself can be switched off.
- Turning the sidebar off left the deck list empty (the tree payload was
  only injected alongside the sidebar).
- Inline rename works again on the redesigned deck rows (it had fallen
  back to Anki's rename prompt after the shared-list refactor).
- The "Show streak counter" setting is wired up; it was a no-op.

### Added
- Move decks without renaming: drag a deck onto another deck to nest it,
  drop it on the top-level zone to un-nest it, or pick **Move to…** from
  the deck's gear menu for a searchable list of destinations. Both drive
  Anki's own reparent operation.
- Settings → **Appearance → Background**: Paper / White / custom colour
  for light mode and Ink / Black / custom for dark mode.
- Settings → **Reviewer → Style card content** — off keeps your note
  type's own CSS (fonts, colours, background) exactly as stock Anki
  renders it; the header and answer keys stay.
- Settings → **Reviewer → Answer buttons** — interval chips (default) or
  Anki's labelled Again / Hard / Good / Easy bar.
- Every opinionated feature now has its own switch, all defaulting to the
  current behaviour: today panel, click-to-reveal, press feedback, inline
  editing, click-a-deck-to-study (vs. Anki's overview page), drag-to-move,
  the command palette, inline Add / Browse / Stats / Preferences windows,
  the redesigned Add window, the redesigned finished-deck page, and quiet
  sync. `config.md` documents each key.
- "Restore Anki Design defaults" now reads the shipped `config.json`, so
  it can never drift from the real defaults.

### Changed
- Default for sub-decks on startup is **Remember** (Anki's synced state)
  rather than always expanded.
- Settings page regrouped into Appearance · Home page · Deck list ·
  Reviewer · Windows · Heatmap · Typography.

## [0.2.0] — 2026-05-24
### Added
- Cmd-K command palette: searches actions, decks, cards, and tags from
  anywhere (deck browser, overview, reviewer). Opens via the sidebar's
  "Search anything…" pill, ⌘K / Ctrl-K, or Cmd-Shift-P.
- Press-feedback animation on ease grading — soft radial bloom expands
  from the pressed key and the interval text fades in place.
- Redesigned congrats page (deck-finished): editorial header, single-
  sentence result, proportional accuracy bar with legend.
- Shared deck-list component: the home tree and the congrats "keep going"
  list render through the same module (`web/decklist.{js,css}`).
- `min_point_version: 250900` in `manifest.json` so older Ankis don't try
  to install a build they can't run.

### Fixed
- Ease-interval chips (`10 min`, `1 day`, etc.) now appear on Image
  Occlusion, Cloze, and any non-FrontSide card types — previously they
  only showed up when the back template included `{{FrontSide}}`.
- Deck-browser single-deck mode no longer renders the deck twice (the
  shared deck-list bails when the hero card owns the page).
- "Search anything…" pill renders with its background and border on the
  congrats page; Anki's Svelte/Bootstrap reset was wiping them.
- "Try custom study" link no longer duplicates on the congrats page when
  there are no other decks with work due.

## [0.1.0]
Initial AnkiWeb release.
### Added
- Base theme injected into the deck browser, overview, and reviewer.
- Contribution-style review-activity heatmap on the deck list, with
  today / streak / total summary.
- Reviewer progress bar with a `done / total` label.
- Themed Add Card, Browse, Stats, Preferences windows.
- Inline rename and a custom deck-options menu on multi-deck rows.
- Inline field editing in the reviewer (in place of the EditCurrent dialog).
- Config: `accent`, `show_heatmap`, `show_progress`, `heatmap_weeks`,
  `theme`, `density`, `sidebar_nav`, `heatmap_palette`,
  `reviewer_card_width`, `reviewer_font_size`, `font_serif`, `font_sans`.
- Declares conflicts with Onigiri, Review Heatmap, and the Progress Bar
  add-on so Anki warns users instead of silently fighting them.

### Known issues
- Anki 25.09's deck-list DOM differs from the classic selectors; some rows
  are low-contrast until the theme selectors are tuned.
- Qt chrome (menus, native dialogs, sidebar) is not themed yet.
