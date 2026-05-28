# Feature Branch Summary

This branch significantly expands Onigiri’s custom deck browser and settings experience. The main focus is a redesigned interactive sidebar, improved deck organisation tools, modern web-based dialogs, better heatmap visibility, and a broader settings refresh.

The changes are intended to be backwards-compatible and should not deliberately alter or remove existing user data.

---

## Main Changes

### Custom Deck Browser / Sidebar

The stock deck browser experience has been replaced with a more interactive custom sidebar UI.

Key additions include:

- Clicking the `DECKS` header now cycles between the normal dashboard, existing focus mode, central sidebar-only mode, and central sidebar with profile/buttons restored, without permanently changing saved widget/layout settings.
- Double-click a deck to start studying immediately.
- Sidebar display modes: full, compact, minimal, and fully collapsed.
- Smooth scrolling, thinner scrollbar, and fade indicators for overflowing deck lists.
- Reduced flicker during sidebar refreshes, including preserved hover state.
- Optimised deck row hover responsiveness so the background highlight snaps instantly even during very fast cursor movement (GPU layer priming via `will-change`).
- Circular collapse/expand control on the sidebar edge.
- Expand control in the main menu when the sidebar is fully collapsed.
- Resize handle for sidebar changed to have a fixed position (doesn't follow cursor)
- Chevron rotation for deck expand/collapse, including while searching.
- Removed the selected/open deck state since it was redundant and served no purpose.
- Changed overflowing deck names to fade out instead of using ellipsis.
- Sync status indicator:
  - Red = local upload needed.
  - Blue = remote changes available.

### Deck Actions

Deck actions have been expanded and moved into a cleaner right-click/context menu flow.

Supported actions include:

- Add subdeck using a modern web-based dialog.
- Create deck using a searchable modern web-based dialog
- Rename deck using a modern web-based dialog.
- Move deck using drag-and-drop.
- Move deck using a searchable modern web-based destination dialog.
- Edit deck icon using a modern icon picker.
- Mark decks with coloured dots.
- Favourite decks, with the favourite limit increased to 10.
- Archive decks (potential use case: User want to delete deck without losing heatmap history)
- Copy deck ID.
- Export deck (uses native Anki dialog at present)
- Delete deck.

### Deck Organisation

The Organise menu now supports sorting, filtering, and searching directly from the sidebar.

Added organisation tools:

- Sort by alphabetical order.
- Sort by most due.
- Sort by custom order.
- Filter archived decks.
- Filter marked decks.
- Filter favourited decks.
- Search decks from the sidebar.
- Search bar to search deck names

### Multi-Select Deck Editing

The sidebar now supports multi-deck selection and bulk interaction.

Implemented behaviour:

- Ctrl-click selects individual decks.
- Shift-click selects deck ranges.
- Ctrl+A to select all decks.
- Selected decks can be dragged together.
- Multi-drag supports reordering and reparenting.
- A stacked drag preview appears with a selected-count badge.
- Insertion lines show reorder position.
- Hovering near deck chevron during drag shows spinner instead of chevron - indicates pending expansion.
- Accent border indicates the current reparenting target.
- Esc key or empty-space click or dragging outside the sidebar clears selection.
- The selected-count badge can be clicked to cancel selection.
- Selected rows use a vertical accent pill indicator.

### Modern Web Dialogs

Several deck-management flows now use custom web-based dialogs instead of native-looking dialogs.

Added or updated dialogs:

- Move deck dialog with search and destination list.
- Rename deck dialog with full-path / leaf-name toggle.
- Edit icon dialog with:
  - SVG import.
  - PNG import.
  - Emoji picker.
  - Lazy loading.
  - Keyword search.
  - Colour picker.

### Ellipsis / More Menu

The old action-button style has been replaced or supplemented with a cleaner ellipsis menu.

The ellipsis menu appears in:

- Minimal sidebar mode.
- Collapsed sidebar mode.
- Full sidebar mode as a list item (as it did before)

---

## Icon System

All interface icons have been moved into the `system_icons` folder rather than being hardcoded inline.

Changes include:

- New shared icon system.
- 45+ interface icons added or updated.
- Mix of copied, adapted, and custom-made icons.
- Reduced reliance on inline SVG markup.

---

## Loading Experience

Added a native Qt startup overlay to hide Anki’s broken state during initial load.

Behaviour:

- Uses the main menu background colour.
- Shows a spinner while the webview loads.
- Automatically dismisses when the webview is ready.
- Fallback auto-dismiss after 4.5 seconds.

---

## Heatmap Improvements

The heatmap has been updated for better visual clarity, especially for low-activity and high-activity days.

Changes include:

- General layout improvements (absolute positioning of header etc.)
- Increased activity intensity levels from 5 to 12.
- Added a power curve for better low-activity visibility.
- Improved tooltip readability in both light and dark mode.
- Normalised header button corner radius and padding
- Modernised heatmap background styling (see settings overhaul...)
- Simplified streak display to show fire icon + day count.
- Moved longest streak information into the tooltip.
- Added smooth transitions between viewing heatmaps for different Years, Months and Days
- Added a sliding "pill" indicator behind the buttons that physically animates its position and width to the newly active button
- Navigation arrows now have a tactile `translateY(1px)` press effect on click

---

## Overview Page

The deck overview page has been visually cleaned up and made quicker to access.

Changes include:

- Removed native Anki styling from the Study button.
- Normalised Study button border radius and text sizing
- Normalised Click to reveal/hide description button.
- Study button and reveal/hide button now share the same tactile `translateY(1px)`
- Moved study options, description, and deck options into plain top-corner icon buttons.
- Optimised deck left-click behaviour so opening the overview feels faster.

---

## Settings Overhaul

The settings UI has been substantially modernised.

General settings changes:

- Refreshed layout with clearer grouping.
- Added icons across settings sections.
- Improved spacing and border-radius consistency.
- Recoded colour picker layout so cleaner visually with "Cancel" and "Apply" changes buttons
- Added opacity slider so all colours support

Sidebar settings:

- Toggle for showing/hiding the collapse/expand sidebar button (appears on hover by default).
- Configurable right-click highlight background.
- Fixed SVG icon previews not appearing correctly.

Profile settings:

- Added profile bar gradient option.
- Updated username text colour to automatically switch between black and white based on background luminance for optimal contrast.
- Added initials-as-profile-picture option.
- Renamed “Username” to “Name”.
- Added profile picture size presets.
- Reworked backend handling to prevent image clipping and improve scaling.
- Live preview of profile bar changes (top left corner)

Palette / main menu settings:

- Removed separate boxes background colour setting.
- Moved widget background control into the main menu settings.
- Added widget background styles:
  - Glassmorphism.
  - Colour overlay.
  - Solid colour.

---

## Compatibility and Data Safety

These changes are intended to preserve existing user data and settings.

No deliberate migration has been added that should delete or overwrite existing deck data, user progress, icons, profile data, or Anki collection content.

---

## Manual Testing

Tested manually on:

- Anki 24.x
- Qt6
- Windows 11

Areas tested include:

- Sidebar display modes.
- Deck searching, sorting, and filtering.
- Single-deck and multi-deck drag-and-drop.
- Right-click deck actions.
- Move, rename, create deck, add subdeck and edit-icon dialogs.
- Heatmap display.
- Overview page controls.
- Settings layout and colour/profile/sidebar options
- `DECKS` header cycling between normal dashboard, focus mode, central sidebar-only mode, and central sidebar with profile/buttons restored.