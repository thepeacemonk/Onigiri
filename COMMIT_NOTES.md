# Commit Notes — Heatmap Improvements

## Files Changed

- `web/heatmap.css`
- `web/heatmap.js`
- `templates.py` (whitespace only)

---

## 1. Header Layout — Absolute Positioning

**Problem:** The heatmap header (year label, nav arrows, streak counter, filter buttons) shifted position depending on the active view (year/month/week). It looked janky because different views have different grid heights.

**Fix:** Changed `.onigiri-heatmap-header` to `position: absolute; top: 15px; left: 15px; right: 15px;` so it stays fixed relative to the container padding across all views.

**CSS changes:**
- Removed redundant properties: `margin-bottom: 0`, `flex-wrap: nowrap`, `width: 100%`, `min-width: 0`, `padding-top: 0`, `margin-left: auto`
- Header no longer participates in normal document flow — the grid sits below it naturally via a `.heatmap-viewport` wrapper with `margin-top: 40px`

---

## 2. Heatmap Viewport Wrapper

**New CSS class:** `.heatmap-viewport`

```css
.heatmap-viewport {
    margin-top: 40px;
    overflow: hidden;
    position: relative;
    width: 100%;
}
```

This wrapper:
- Pushes grid content below the absolute-positioned header
- Provides `overflow: hidden` + `position: relative` so sliding grids are clipped correctly during transitions
- Replaced the old `.heatmap-grid { margin-top: 22px; }` approach

---

## 3. Slide Transitions — Year/Month/Week Navigation

**Problem:** Clicking prev/next arrows instantly swapped grid content with no visual feedback.

**Fix:** Implemented a full carousel-style slide transition. Old grid slides out while new grid slides in simultaneously.

### Architecture

- **`isTransitioning` flag** — prevents overlapping transitions
- **Transition constants:**
  - `TRANSITION_DURATION_MS = 500`
  - `TRANSITION_FALLBACK_MS = 700` (duration + 200ms safety margin)

### How it works

1. Capture `oldGrid.getBoundingClientRect()` to freeze its exact pixel position and size
2. Clone those `top`, `left`, `width`, `height` values onto both `oldGrid` and `newGrid` via inline styles
3. `newGrid` starts off-screen: `translate3d(±viewportWidth, 0, 0)`
4. `requestAnimationFrame` ensures the browser paints the initial state before applying transitions
5. Force reflow via `void oldGrid.offsetHeight`
6. Apply `will-change: transform` + `transition: transform 500ms cubic-bezier(0.3, 0.3, 0.2, 1)` to both grids
7. Animate:
   - Click **right arrow** (next period): old slides left (`-100vw`), new enters from right (`0`)
   - Click **left arrow** (previous period): old slides right (`+100vw`), new enters from left (`0`)
8. Cleanup on `transitionend` (with `setTimeout` fallback):
   - Remove `oldGrid` from DOM
   - Strip all inline styles from `newGrid`
   - Clear `viewport.style.height`
   - Reset `isTransitioning = false`

### Robustness

- `transitionend` listener checks `e.target === newGrid && e.propertyName === 'transform'` to avoid firing on child element transitions
- `setTimeout` fallback ensures cleanup even if `transitionend` doesn't fire (rare browser edge case)
- `cleanedUp` boolean prevents double-cleanup
- Null guards on `viewport` and `oldGrid` — falls back to instant re-render if elements are missing

### Key JS additions

- `renderCurrentView(direction)` now has three paths:
  1. **No existing header** → full DOM build (initial render)
  2. **No direction** → filter click, in-place header update (see below)
  3. **Direction provided** → nav click, slide transition
- `renderGrid(gridContainer)` — extracted into a reusable helper
- `resetGridStyles(grid)` — strips all 8 inline transition styles in one call

---

## 4. Sliding Filter Button Indicator

**Problem:** Filter buttons (Year / Month / Week) snapped instantly between active states with no visual movement.

**Fix:** Added a sliding "pill" indicator behind the buttons that physically animates its position and width to the newly active button.

### CSS

```css
.heatmap-filters {
    position: relative;
}

.filter-indicator {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: calc(var(--heatmap-control-height) - 8px);
    background-color: rgba(128, 128, 128, 0.18);
    border-radius: 6px;
    pointer-events: none;
    transition: left 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 0;
}

.filter-btn {
    position: relative;
    z-index: 1;
    background-color: transparent; /* removed old solid bg */
}
```

### JS

- `positionIndicator()` — measures the active button's `getBoundingClientRect()` relative to the `.heatmap-filters` container and sets the indicator's `left` and `width` inline styles
- Called on:
  - Initial render (double `requestAnimationFrame` to ensure layout is settled)
  - Every filter click after toggling `.active` classes

### Button behaviour changes

- Buttons now have transparent backgrounds — the pill provides the active highlight
- Hover state also uses `background-color: transparent` (no clash with the pill)
- `.filter-btn.active` no longer sets its own background-color; only sets `color` and `font-weight: 600`

---

## 5. Filter Click Refactor — In-Place Header Update

**Problem:** Filter clicks used to do `container.innerHTML = ...` which destroyed and recreated the entire heatmap DOM including buttons. This killed any chance of CSS transitions on the buttons.

**Fix:** Filter clicks now only update the header and grid in-place:

1. Rebuild nav content (`navEl.innerHTML = buildNavContent(config)`) and rebind nav buttons
2. Toggle `.active` class on existing filter buttons (preserving DOM elements)
3. Call `positionIndicator()` to animate the pill
4. Re-render the grid for the new view

The button DOM elements are never destroyed on filter clicks, so the CSS `transition` on the sliding pill works perfectly.

**Guard:** Filter clicks check `if (isTransitioning) return;` to prevent corruption if a user clicks a filter button during an active nav slide transition.

---

## 6. Removed / Cleaned Up

### CSS removed
- `.filter-btn` `transition: color 0.35s ease` (remnant from earlier misunderstanding — the pill provides the visual transition, not the button itself)
- `.filter-btn:hover` `opacity: 1` (redundant)
- `.filter-btn.active` `background-color: rgba(128, 128, 128, 0.18)` (now handled by pill)
- `.filter-btn:hover` `background-color: rgba(128, 128, 128, 0.18)` (now transparent to avoid clashing with pill)
- Various redundant `.onigiri-heatmap-header` properties

### JS removed
- Old inline header HTML generation mixed with grid rendering — now cleanly separated into `buildHeaderHTML()` and `renderGrid()`

---

## 7. templates.py

- Whitespace-only change (blank line added inside a CSS block) — no functional impact

---

## 8. Deck Browser Hover Responsiveness

**Problem:** Quickly dragging the cursor across the deck list produced a sluggish visual "stream" because each row took 200 ms to transition into and out of the hover state.

**Fix:** Removed the `transition` declarations on `tr.deck` in `web/menu.css` so hover/unhover snaps instantly in a single frame.

**CSS changes in `web/menu.css`:**
- `tr.deck` — removed `transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;`
- `.deck-table tr.deck:not(:hover)` — removed entire ruleset (it only duplicated the same transition)

No JavaScript logic was touched. Other row states (multi-select, drag-over, context-menu highlight) already override transitions and are unaffected.

---

## 9. Search Bar Padding & Close Icon

**Files changed:** `templates.py`

### Search bar padding
- Changed `#onigiri-deck-search-bar` padding from `6px 6px 6px 8px` to `6px 12px 6px 12px`

### Search close icon
- Swapped `.search-close-icon` mask source from `cancel_circle.svg` to `cancel.svg`
- Both `-webkit-mask-image` and `mask-image` updated

---

## 10. Deck Row Hover — Paint Lag Fix

**File changed:** `web/menu.css`

**Problem:** When moving the cursor very quickly across deck rows, the hover background change felt slightly delayed — not caused by CSS `transition` or JS, but by the browser's paint pipeline lagging behind rapid `background-color` changes on rounded shapes.

**Fix:** Added `will-change: background-color` to `tr.deck`.

**CSS change in `web/menu.css`:**
- `tr.deck` — added `will-change: background-color;`

This keeps the background-color layer primed in GPU memory, eliminating the per-frame paint lag and making hover feel instant even during very fast cursor movement.

---

## 11. Search Bar Padding Tweak

**File changed:** `templates.py`

- Changed `#onigiri-deck-search-bar` padding from `6px 12px 6px 12px` to `6px 6px 6px 12px`

---

## 12. Unified Button Press Effect

**Reference:** The `* selected` badge (`#onigiri-multiselect-badge`) has a satisfying `translateY(1px)` press effect on `:active`. This change replicates that identical feel across three other interactive elements.

**Pattern used everywhere:**
- `transition: opacity 0.12s ease, box-shadow 0.12s ease, transform 0.12s ease` on the base element
- `:active { transform: translateY(1px); }` — only the property that changes, inherited from base/hover for everything else

### 12a. Heatmap navigation arrows

**File changed:** `web/heatmap.css`

- `.nav-btn` — added `transition: background-color 0.12s ease, box-shadow 0.12s ease, transform 0.12s ease`
- `.nav-btn:hover, .nav-btn:focus, .nav-btn:focus-visible, .nav-btn:active` — merged into one shared block (same visual state: hover bg)
- `.nav-btn:active` — added `transform: translateY(1px)` (single-property override)

### 12b. Overview "Click to reveal / Click to hide" button

**File changed:** `patcher.py`

- `#onigiri-reveal-btn` — updated `transition` to include `transform 0.12s ease`
- `#onigiri-reveal-btn:active` — added `opacity: 0.65` and `transform: translateY(1px)` (removed redundant `box-shadow` / `border` resets already in base)

### 12c. Overview "Study Now" button

**File changed:** `web/overview.css`

- `.add-button-dashed` — updated `transition` to include `transform 0.12s ease`
- `.add-button-dashed:active` — added `opacity: 0.65` and `transform: translateY(1px)` (removed 6 redundant `!important` declarations already covered by base/hover)
- Fixed two pre-existing lint warnings: added standard `appearance: none` alongside `-webkit-appearance: none` on both `.add-button-dashed` and `#study`
