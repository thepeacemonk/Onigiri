"""Server-side validation for the widget-layout payload.

The HTML5 grid editor already prevents invalid layouts during normal use, but a
JS bug must never be able to corrupt the config file (one write_config() call
overwrites the whole thing). This module re-validates every layout before it can
reach disk: scalar ranges, widget-id allow-list, per-widget span clamps, and a
full overlap/bounds replay — misplaced widgets are archived, not silently lost.

The grid algorithm mirrors settings/_layout_base.py (is_region_free) so behavior
matches the native editor exactly.
"""

from . import config

ONIGIRI_WIDGET_IDS = {
    "studied", "time", "pace", "retention", "heatmap", "favorites",
    "restaurant_level", "onigimon", "hexagon_land", "deck_stats", "prep_station",
}

# Per-widget span bounds (ported from OnigiriDraggableItem.contextMenuEvent).
SPAN_RULES = {
    "heatmap":          {"col_min": 2, "col_max": 4, "row_min": 2, "row_max": 2},
    "restaurant_level": {"col_min": 1, "col_max": 2, "row_min": 1, "row_max": 2},
    "deck_stats":       {"col_min": 1, "col_max": 2, "row_min": 1, "row_max": 2},
    "onigimon":         {"col_min": 1, "col_max": 4, "row_min": 1, "row_max": 2},
    "hexagon_land":     {"col_min": 1, "col_max": 4, "row_min": 1, "row_max": 4},
    "prep_station":     {"col_min": 1, "col_max": 4, "row_min": 2, "row_max": 2},
    "favorites":        {"col_min": 1, "col_max": 4, "row_min": 1, "row_max": 3},
}
DEFAULT_ONIGIRI_RULE = {"col_min": 1, "col_max": 4, "row_min": 1, "row_max": 1}
DEFAULT_EXTERNAL_RULE = {"col_min": 1, "col_max": 4, "row_min": 2, "row_max": 2}


def _clamp_int(value, lo, hi, fallback):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(lo, min(hi, v))


def _external_hook_ids():
    try:
        from . import patcher
        return {patcher._get_hook_name(h) for h in patcher._get_external_hooks()}
    except Exception:
        return set()


def _rule_for(widget_id, is_external):
    if is_external:
        return DEFAULT_EXTERNAL_RULE
    return SPAN_RULES.get(widget_id, DEFAULT_ONIGIRI_RULE)


def _is_region_free(cells, pos, row_span, col_span, cols, rows):
    row, col = divmod(pos, cols) if cols else (0, 0)
    if cols <= 0 or rows <= 0:
        return False
    if col + col_span > cols or row + row_span > rows:
        return False
    for r in range(row, row + row_span):
        for c in range(col, col + col_span):
            if cells.get(r * cols + c) is not None:
                return False
    return True


def _fill_cells(cells, widget_id, pos, row_span, col_span, cols):
    row, col = divmod(pos, cols)
    for r in range(row, row + row_span):
        for c in range(col, col + col_span):
            cells[r * cols + c] = widget_id


def _default_layout():
    d = config.DEFAULTS.get("onigiriWidgetLayout", {})
    import copy
    return copy.deepcopy(d)


def validate_layout(onigiri_layout, external_layout, unified_grid_rows):
    """Return a sanitized {onigiriWidgetLayout, externalWidgetLayout,
    unifiedGridRows}. Never raises for bad data — clamps / archives instead.
    (The caller's save path still wraps everything so a truly unexpected error
    fails closed without writing.)"""
    if not isinstance(onigiri_layout, dict):
        onigiri_layout = _default_layout()
    if not isinstance(external_layout, dict):
        external_layout = {}

    rows = _clamp_int(unified_grid_rows, 0, 200, 6)
    cols = _clamp_int(onigiri_layout.get("column_count"), 0, 6, 4)
    grid_width = _clamp_int(onigiri_layout.get("grid_width"), 200, 340, 230)
    widget_height = _clamp_int(onigiri_layout.get("widget_height"), 120, 320, 120)
    alignment = onigiri_layout.get("grid_alignment")
    if alignment not in ("left", "center", "right"):
        alignment = "center"

    external_ids = _external_hook_ids()

    # Collect placed widgets from both grids into a unified, ordered list.
    placed = []  # (pos, widget_id, is_external, row_span, col_span, extra)

    onigiri_grid = onigiri_layout.get("grid", {}) or {}
    for wid, cfg in onigiri_grid.items():
        if wid not in ONIGIRI_WIDGET_IDS or not isinstance(cfg, dict):
            continue
        rule = _rule_for(wid, False)
        col_span = _clamp_int(cfg.get("col"), rule["col_min"], rule["col_max"], rule["col_min"])
        row_span = _clamp_int(cfg.get("row"), rule["row_min"], rule["row_max"], rule["row_min"])
        pos = _clamp_int(cfg.get("pos"), 0, max(0, rows * cols - 1), 0)
        extra = {}
        if "display_name" in cfg:
            extra["display_name"] = cfg["display_name"]
        if wid == "restaurant_level" and cfg.get("orientation") in ("horizontal", "vertical"):
            extra["orientation"] = cfg["orientation"]
        placed.append((pos, wid, False, row_span, col_span, extra))

    external_grid = external_layout.get("grid", {}) or {}
    for hid, cfg in external_grid.items():
        if hid not in external_ids or not isinstance(cfg, dict):
            continue
        rule = _rule_for(hid, True)
        col_span = _clamp_int(cfg.get("column_span"), rule["col_min"], rule["col_max"], rule["col_min"])
        row_span = _clamp_int(cfg.get("row_span"), rule["row_min"], rule["row_max"], rule["row_min"])
        pos = _clamp_int(cfg.get("grid_position"), 0, max(0, rows * cols - 1), 0)
        extra = {}
        if "display_name" in cfg:
            extra["display_name"] = cfg["display_name"]
        placed.append((pos, hid, True, row_span, col_span, extra))

    # Replay placement in pos order; keep widgets that fit, archive the rest.
    placed.sort(key=lambda x: x[0])
    cells = {}
    kept_onigiri = {}
    kept_external = {}
    archived_onigiri = []
    archived_external = []

    for pos, wid, is_external, row_span, col_span, extra in placed:
        if _is_region_free(cells, pos, row_span, col_span, cols, rows):
            _fill_cells(cells, wid, pos, row_span, col_span, cols)
            if is_external:
                entry = {"grid_position": pos, "row_span": row_span, "column_span": col_span}
                entry.update(extra)
                kept_external[wid] = entry
            else:
                entry = {"pos": pos, "row": row_span, "col": col_span}
                entry.update(extra)
                kept_onigiri[wid] = entry
        else:
            (archived_external if is_external else archived_onigiri).append((wid, extra))

    # Merge existing archives (from the payload) with widgets bumped here.
    def _merge_archive(raw_archive, bumped):
        result = {}
        if isinstance(raw_archive, dict):
            for k, v in raw_archive.items():
                result[k] = v if isinstance(v, dict) else {}
        elif isinstance(raw_archive, list):
            for k in raw_archive:
                result[k] = {}
        for wid, extra in bumped:
            result[wid] = dict(extra)
        return result

    onigiri_archive = _merge_archive(onigiri_layout.get("archive"), archived_onigiri)
    external_archive = _merge_archive(external_layout.get("archive"), archived_external)

    # Archive/grid exclusivity: an id can't be in both.
    for wid in list(onigiri_archive.keys()):
        kept_onigiri.pop(wid, None)
    for wid in list(external_archive.keys()):
        kept_external.pop(wid, None)

    # Drop unknown / uninstalled external ids from the archive too.
    external_archive = {k: v for k, v in external_archive.items() if k in external_ids}

    return {
        "onigiriWidgetLayout": {
            "grid": kept_onigiri,
            "archive": onigiri_archive,
            "column_count": cols,
            "grid_width": grid_width,
            "grid_alignment": alignment,
            "widget_height": widget_height,
        },
        "externalWidgetLayout": {
            "grid": kept_external,
            "archive": external_archive,
        },
        "unifiedGridRows": rows,
    }
