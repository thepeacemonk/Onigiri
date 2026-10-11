"""Native Kome surface for the optional advanced analytics data.

The data calculations live in :mod:`things_stats`; this module is the narrow
bridge that serializes them into the deck-browser WebView. Keeping the bridge
here makes the ownership explicit: Kome supplies the shell and assets, and
the attachment supplies collection analysis only.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from aqt import mw


PERIODS = ("today", "7d", "30d", "90d", "12m", "all")
DEFAULT_PERIOD = "30d"


def _safe_period(period: str) -> str:
    return period if period in PERIODS else DEFAULT_PERIOD


def dashboard_data(period: str = DEFAULT_PERIOD) -> Dict[str, Any]:
    """Build one validated dashboard payload from the current collection."""
    from ..things_stats import build_dashboard_data

    if mw is None or getattr(mw, "col", None) is None:
        return {}
    return build_dashboard_data(mw.col, _safe_period(period))


def _json_for_script(value: Any) -> str:
    """Serialize data without allowing a value to close the script element."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def build_html(period: str = DEFAULT_PERIOD) -> str:
    """Return a dormant mount point; data is fetched only after user reveal."""
    safe_period = _safe_period(period)
    return (
        "<script>window.__baAdvancedStatsData=null;"
        "window.__baAdvancedStatsPeriod="
        + json.dumps(safe_period)
        + ";</script>"
        + '<section class="ba-advanced-stats is-collapsed" '
        'data-ba-advanced-stats aria-label="Kome insights"></section>'
    )


def push_period(period: str = DEFAULT_PERIOD) -> None:
    """Recompute a selected period and hand it to the mounted dashboard."""
    safe_period = _safe_period(period)
    web = getattr(mw, "web", None)
    if web is None:
        return
    try:
        data = dashboard_data(safe_period)
        web.eval(
            "window.__baSetAdvancedStats&&window.__baSetAdvancedStats("
            + _json_for_script(data)
            + ","
            + json.dumps(safe_period)
            + ");"
        )
    except Exception as exc:  # noqa: BLE001 - surface a local inline error
        web.eval(
            "window.__baAdvancedStatsError&&window.__baAdvancedStatsError("
            + json.dumps(str(exc))
            + ");"
        )
