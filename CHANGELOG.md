# Changelog

## Unreleased

- feat: make deck opening from the sidebar feel more immediate with instant selected-row feedback, a dedicated fast-open path, delayed native busy cursor handling, and asynchronous overview-only due-later counts
- feat: preload context-menu and ellipsis-menu SVG mask icons so menu icons appear immediately on first open
- feat: make the `D` shortcut match the Decks toolbar action from overview/reviewer contexts, plus local deck-tree refresh helpers so sidebar state can update without full page reloads
- feat: improve deck expand/collapse animations with smoother child fade and lower-row FLIP transitions
- feat: refresh dynamic deck icon CSS and icon chooser results in place, including clearing deleted custom deck icons from the live deck view
- feat: update the startup overlay and loading handoff so the native splash uses the configured deck-browser background, improved spinner styling, and a safer dismissal flow
- feat: expand the system icon set, normalize icon filenames to underscore variants, and switch more UI surfaces to shared SVG assets instead of inline icon data
- feat: add deck, subdeck, filtered-deck, gamification, and drag-handle icon defaults plus related settings support
- fix: align sidebar sync status dot closer to the Sync label
- fix: keep deck counts, collapse slots, drag handles, and collapsed-sidebar layout aligned more consistently across deck row states
- fix: preserve deck name ellipsis behavior in the sidebar so long names truncate gracefully
- fix: keep ellipsis menu selection state in sync for focus mode, sort mode, favorites, and marked filters after local refreshes
- fix: make right-click deck highlight color follow the configured light/dark mode scheme
- fix: soften selected deck highlight in light mode while keeping a theme-aware dark mode variant
- fix: position ellipsis-menu tick indicators consistently closer to the option label
- fix: restyle profile and overview action buttons to use the shared icon treatment and cleaner light/dark theme behavior
- fix: clean up heatmap and icon chooser asset/theme updates, including refreshed shape icons
- fix: stop the main menu from refreshing when the settings dialog is closed without clicking Save
- fix: make the settings dialog save/close flow more robust by only persisting window size on close and keeping the save guard recoverable on errors
