## Other

**Icons**
- Migrated all icons to use `system_icons` folder (no inline/hardcoded SVGs)
- New icon set with 44+ custom icons across the interface

**Loading Overlay**
- Native Qt startup overlay with spinner hides Anki's native "(---)" during initial load
- Uses deck browser background color
- Auto-dismisses after 4.5 seconds or when webview is ready

## Sidebar

**Layout**
- Added sidebar action modes: full, compact, minimal
- Thinner, modern scrollbar with momentum/smooth scroll
- Top and bottom fade-out for overflowing content
- Profile bar reduced from 50px to 48px
- Hover state preserved during DOM refresh (reduced flicker)

**Deck Functions** (right-click menu)
- Add Subdeck
- Move decks via drag-and-drop handle
- Move decks via right-click menu (modern web dialog)
- Rename deck (modern web dialog with full path/leaf name toggle)
- Edit icon (modern web dialog with SVG/PNG import, emoji picker with lazy-loading and keyword search)
- Mark decks with colored dots (red, yellow, blue, green)
- Favorite decks (filled accent when favorited, outline when not; cap increased to 10)
- Archive decks
- Copy deck ID
- Export deck
- Delete deck

**Organization** (organize button)
- Sort by: alphabetical, most due, most new, custom order
- Filter by: archived, marked, favorited
- Search bar for decks

**Multi-Select** (Ctrl+click for single, Shift+click for range)
- Drag-and-drop to reparent or reorder (custom sort)
- Selected decks appear stacked with count badge in top-right
- Clicking empty space or dragging outside sidebar cancels selection
- Insertion lines indicate reordering (accent color)
- Deck row border indicates reparenting target (accent color)
- Count badge ("* selected") in top-right cancels selection
- Vertical accent pill indicator for selected deck

**Other**
- Circular collapse/expand button on right edge; expand button in main menu top-left
- Sidebar now closes completely instead of staying partially visible
- Chevron rotates 90° on expand/collapse (works during search)
- Sync status indicator (red = upload needed, blue = remote newer)

**Dialogs**
- Ellipsis/more menu appears in minimal mode (top-right), collapsed mode (bottom-right), and full mode (as list item)
- Move deck dialog: modern web-based dialog with search and destination list
- Rename deck dialog: modern web-based dialog with full path/leaf name toggle
- Edit icon dialog: modern web-based dialog with icon picker and color picker

## Heatmap

**Cells**
- Expanded from 5 to 12 intensity levels with power curve (exponent 0.5) for better low-activity visibility
- Tooltips adapt to light/dark mode with proper background for readability

**Layout**
- Normalized corner radius on header buttons, modernized background
- Streak container shows fire icon + day count only; longest streak in tooltip

## Overviewer

**General**
- Study button: removed native Anki styling, normalized border radius and text size
- Study options, description, and deck options buttons: plain icons in top corner

## Settings

**General**
- Revamped modern layout with icons and consistent border radius
- Revamped color picker with opacity slider and cleaner layout

**Sidebar**
- Toggle to show/hide collapsed sidebar
- Right-click highlight background configuration

**Profile**
- Profile bar gradient option
- Initials as profile picture
- Renamed "Username" to "Name"
- Profile picture size presets
- Backend recoded to prevent image clipping and ensure proper scaling

**Palette**
- Removed boxes background color, migrated to main menu as widget background

**Main Menu**
- Widget background configuration options: glassmorphism, color overlay, solid color
