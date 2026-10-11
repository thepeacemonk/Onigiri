"""Compact deck-wide statistics for Onigiri's overview surfaces.

The feature is inspired by More Overview Stats 2.1, but keeps data collection
separate from presentation so Onigiri can render the same calm summary on the
regular overview and on the finished-deck screen.
"""

import html
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, List, Optional


MATURE_INTERVAL_DAYS = 21


@dataclass(frozen=True)
class DeckOverviewStats:
    """Deck-wide card states and a conservative new-card forecast."""

    total: int
    mature: int
    young: int
    unseen: int
    buried: int
    suspended: int
    new_per_day: int

    @property
    def learned(self) -> int:
        return self.mature + self.young

    @property
    def learning_pool(self) -> int:
        """Cards that currently participate in the deck's learning path."""
        return max(0, self.total - self.buried - self.suspended)

    @property
    def progress_percent(self) -> int:
        if self.learning_pool <= 0:
            return 0
        return max(
            0,
            min(100, round((self.learned / self.learning_pool) * 100)),
        )

    @property
    def days_until_introduced(self) -> Optional[int]:
        if self.unseen <= 0 or self.new_per_day <= 0:
            return None
        return math.ceil(self.unseen / self.new_per_day)

    @property
    def estimated_finish(self) -> Optional[date]:
        days = self.days_until_introduced
        if days is None:
            return None
        return date.today() + timedelta(days=days)


def _selected_deck_ids(col: Any) -> List[int]:
    """Return the current deck ID and all of its descendants."""
    deck_id = int(col.decks.current()["id"])
    deck_ids = [deck_id]
    try:
        deck_ids.extend(int(child_id) for child_id in col.decks.child_ids(deck_id))
    except Exception:
        # Keep the selected deck useful on Anki versions where the child-deck
        # helper has moved or an add-on has wrapped it incompatibly.
        pass
    return list(dict.fromkeys(deck_ids))


def _positive_limit(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _new_cards_per_day(col: Any, deck: dict) -> int:
    """Resolve today's deck override, deck override, then preset limit."""
    if deck.get("dyn"):
        return 0

    today_limit = deck.get("newLimitToday")
    if isinstance(today_limit, dict) and today_limit.get("today") == 2:
        return _positive_limit(today_limit.get("limit"))

    if deck.get("newLimit") is not None:
        return _positive_limit(deck.get("newLimit"))

    try:
        deck_config = col.decks.config_dict_for_deck_id(int(deck["id"]))
        return _positive_limit(deck_config.get("new", {}).get("perDay"))
    except Exception:
        return 0


def collect_deck_overview_stats(col: Any) -> DeckOverviewStats:
    """Collect card-state totals for the current deck and its subdecks."""
    deck = col.decks.current()
    deck_ids = _selected_deck_ids(col)
    deck_ids_sql = ",".join(str(deck_id) for deck_id in deck_ids)

    row = col.db.first(
        f"""
        select
            count(),
            coalesce(sum(case when queue = 2 and ivl >= ? then 1 else 0 end), 0),
            coalesce(sum(case when queue in (1, 3)
                or (queue = 2 and ivl < ?) then 1 else 0 end), 0),
            coalesce(sum(case when queue = 0 then 1 else 0 end), 0),
            coalesce(sum(case when queue in (-2, -3) then 1 else 0 end), 0),
            coalesce(sum(case when queue = -1 then 1 else 0 end), 0)
        from cards
        where did in ({deck_ids_sql})
        """,
        MATURE_INTERVAL_DAYS,
        MATURE_INTERVAL_DAYS,
    )
    total, mature, young, unseen, buried, suspended = row or (0, 0, 0, 0, 0, 0)

    return DeckOverviewStats(
        total=max(0, int(total or 0)),
        mature=max(0, int(mature or 0)),
        young=max(0, int(young or 0)),
        unseen=max(0, int(unseen or 0)),
        buried=max(0, int(buried or 0)),
        suspended=max(0, int(suspended or 0)),
        new_per_day=_new_cards_per_day(col, deck),
    )


def _format_date(value: date) -> str:
    """Format with Onigiri's selected locale, with an ISO fallback."""
    try:
        from PyQt6.QtCore import QDate, QLocale

        from ..core.translations import current_locale

        qdate = QDate(value.year, value.month, value.day)
        return current_locale().toString(qdate, QLocale.FormatType.ShortFormat)
    except Exception:
        return value.isoformat()


def _detail_item(label: str, value: int) -> str:
    return (
        '<div class="onigiri-deck-progress-detail">'
        f"<span>{html.escape(str(label))}</span>"
        f"<strong>{int(value)}</strong>"
        "</div>"
    )


def render_deck_overview_stats(col: Any, surface: str = "overview") -> str:
    """Render a minimal summary; return nothing if collection access fails."""
    try:
        stats = collect_deck_overview_stats(col)
        if stats.total <= 0:
            return ""

        from ..core.translations import tr

        progress_label = tr("overview_deck_progress", "Deck progress")
        learned_text = tr(
            "overview_learned_of_total",
            "{learned} of {total} learned",
        ).format(learned=stats.learned, total=stats.learning_pool)

        forecast_html = ""
        if stats.estimated_finish is not None:
            days = stats.days_until_introduced or 0
            forecast_key = (
                "overview_finish_estimate_one"
                if days == 1
                else "overview_finish_estimate_many"
            )
            forecast_default = (
                "≈ 1 day · {date}"
                if days == 1
                else "≈ {days} days · {date}"
            )
            forecast_text = tr(forecast_key, forecast_default).format(
                days=days,
                date=_format_date(stats.estimated_finish),
            )
            forecast_title = tr(
                "overview_finish_estimate_basis",
                "Based on {count} new cards/day",
            ).format(count=stats.new_per_day)
            forecast_html = (
                '<span class="onigiri-deck-progress-forecast" '
                f'title="{html.escape(forecast_title, quote=True)}">'
                f"{html.escape(forecast_text)}"
                "</span>"
            )

        labels = {
            "mature": tr("lstats_mature", "Mature"),
            "young": tr("lstats_young", "Young"),
            "unseen": tr("lstats_unseen", "Unseen"),
            "buried": tr("lstats_buried", "Buried"),
            "suspended": tr("lstats_suspended", "Suspended"),
            "total": tr("lstats_total", "Total"),
        }
        detail_html = "".join(
            (
                _detail_item(labels["mature"], stats.mature),
                _detail_item(labels["young"], stats.young),
                _detail_item(labels["unseen"], stats.unseen),
                _detail_item(labels["buried"], stats.buried),
                _detail_item(labels["suspended"], stats.suspended),
                _detail_item(labels["total"], stats.total),
            )
        )
        details_label = tr("overview_deck_details", "Deck details")
        safe_surface = "congrats" if surface == "congrats" else "overview"

        return f"""
        <section class="onigiri-deck-progress onigiri-deck-progress-{safe_surface}"
                 aria-label="{html.escape(progress_label, quote=True)}">
            <div class="onigiri-deck-progress-heading">
                <span>{html.escape(progress_label)}</span>
                <strong>{stats.progress_percent}%</strong>
            </div>
            <div class="onigiri-deck-progress-track" role="progressbar"
                 aria-valuemin="0" aria-valuemax="100"
                 aria-valuenow="{stats.progress_percent}">
                <span style="width: {stats.progress_percent}%"></span>
            </div>
            <div class="onigiri-deck-progress-meta">
                <span>{html.escape(learned_text)}</span>
                {forecast_html}
            </div>
            <details class="onigiri-deck-progress-details">
                <summary>{html.escape(details_label)}</summary>
                <div class="onigiri-deck-progress-grid">{detail_html}</div>
            </details>
        </section>
        """
    except Exception as exc:
        print(f"Onigiri: failed to render overview deck stats: {exc}")
        return ""
