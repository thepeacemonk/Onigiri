"""
Special Days engine for Onigiri.

Generalizes the original birthday popup into a small, reusable engine that
detects several "occasions" (birthday, study anniversary, New Year, lifetime
review milestones) and drives two independent kinds of celebration:

  1. ONE-SHOT notifications (the big birthday modal, or a toast) — fired once
     per occasion via a per-occasion guard stored in config.
  2. ALL-DAY "party mode" visuals (confetti drift, festive glow + emoji on
     today's heatmap cell, optional festive accent override) — injected on
     every deck-browser render while the occasion is active.

Performance note: the only cost is two cheap aggregate scalars on `revlog`,
run ONCE per profile open and cached (see `build_context`/`get_context`).
`get_party_state()` — called during every webview render in
`inject_menu_files()` — is pure cached-dict access and runs no SQL.
"""

import calendar
from datetime import datetime

from aqt import mw

from . import config
from . import birthday_dialog
from . import onigiri_notifications
from .translations import tr


# Lifetime-review thresholds that earn a celebration, ascending.
MILESTONE_THRESHOLDS = [10000, 25000, 50000, 100000, 250000, 500000, 1000000]

# Primary occasion wins the emoji/accent when several are active on one day.
_PRIMARY_PRIORITY = ["birthday", "review_milestone", "study_anniversary", "new_year"]

# Developer affordance: put occasion ids in here to force them active today
# (bypasses date/threshold detection) so the full inject + visual + toast path
# can be exercised without waiting for a real date. MUST be empty for release.
DEBUG_FORCE = set()


def _date_matches_today(month, day, today):
    """True if (month, day) is today, treating Feb-29 as Feb-28 in non-leap years."""
    if month == 2 and day == 29 and not calendar.isleap(today.year):
        month, day = 2, 28
    return today.month == month and today.day == day


class _DayContext:
    """Precomputed facts for "today", shared by every occasion's detect()."""

    def __init__(self, today, year_str, total_reviews, first_review_date, conf, sd_conf):
        self.today = today
        self.year_str = year_str
        self.total_reviews = total_reviews
        self.first_review_date = first_review_date
        self.conf = conf
        self.sd_conf = sd_conf
        self.active = []          # list of (Occasion, match dict)
        self.party_payload = None  # dict for party.js / accent CSS, or None


class Occasion:
    """Base occasion. Subclasses override detect() and the celebration bits."""

    id = ""
    uses_modal = False   # True -> celebrate() shows the big modal instead of a toast
    emoji = "🎉"
    accent = "#FFD700"   # festive accent used when this occasion is primary

    def detect(self, ctx):
        """Return a truthy "match" dict if active today, else None."""
        raise NotImplementedError

    def debug_match(self, ctx):
        """A plausible synthetic match used by DEBUG_FORCE."""
        return {"debug": True}

    # --- one-shot guard (default: once per calendar year) ---
    def already_fired(self, guard_val, match, ctx):
        return guard_val == ctx.year_str

    def new_guard_value(self, match, ctx):
        return ctx.year_str

    # --- celebration ---
    def celebrate(self, match, ctx):
        title, desc = self.toast_text(match, ctx)
        onigiri_notifications.notify(
            desc,
            title=title,
            icon=self.emoji,
            duration=7000,
            centered=True,
        )

    def toast_text(self, match, ctx):
        return ("Onigiri", "")


class BirthdayOccasion(Occasion):
    id = "birthday"
    uses_modal = True
    emoji = "🎂"
    accent = "#FF5FA2"

    def detect(self, ctx):
        birthday_str = ctx.conf.get("userBirthday", "")
        if not birthday_str:
            return None
        try:
            bdate = datetime.strptime(birthday_str, "%Y-%m-%d").date()
        except ValueError:
            return None
        if not _date_matches_today(bdate.month, bdate.day, ctx.today):
            return None
        return {"age": ctx.today.year - bdate.year}

    def debug_match(self, ctx):
        return {"age": 25}

    def celebrate(self, match, ctx):
        user_name = ctx.conf.get("userName", "User")
        birthday_dialog.show_birthday_dialog(user_name, match.get("age", 0))


class StudyAnniversaryOccasion(Occasion):
    id = "study_anniversary"
    emoji = "🎓"
    accent = "#5FC9FF"

    def detect(self, ctx):
        first = ctx.first_review_date
        if not first:
            return None
        if not _date_matches_today(first.month, first.day, ctx.today):
            return None
        years = ctx.today.year - first.year
        if years < 1:
            return None
        return {"years": years}

    def debug_match(self, ctx):
        return {"years": 3}

    def toast_text(self, match, ctx):
        years = match.get("years", 1)
        title = tr("anniversary_toast_title", "🎓 Study Anniversary!")
        desc = tr(
            "anniversary_toast_desc",
            "{years} years since your very first review. Look how far you've come!",
        ).format(years=years)
        return (title, desc)


class NewYearOccasion(Occasion):
    id = "new_year"
    emoji = "🎉"
    accent = "#FFD700"

    def detect(self, ctx):
        if ctx.today.month == 1 and ctx.today.day == 1:
            return {"year": ctx.today.year}
        return None

    def debug_match(self, ctx):
        return {"year": ctx.today.year}

    def toast_text(self, match, ctx):
        year = match.get("year", ctx.today.year)
        title = tr("new_year_toast_title", "🎉 Happy New Year!")
        desc = tr(
            "new_year_toast_desc",
            "Welcome to {year} — a fresh year of learning awaits!",
        ).format(year=year)
        return (title, desc)


class ReviewMilestoneOccasion(Occasion):
    id = "review_milestone"
    emoji = "🏆"
    accent = "#FFB000"

    def _last_celebrated(self, ctx):
        try:
            return int(ctx.sd_conf.get("last_shown", {}).get("review_milestone", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def detect(self, ctx):
        crossed = [t for t in MILESTONE_THRESHOLDS if t <= ctx.total_reviews]
        if not crossed:
            return None
        highest = max(crossed)
        # Unlike date occasions, a milestone has no natural day boundary, so the
        # guard is consulted here: it stays active only until celebrated.
        if highest <= self._last_celebrated(ctx):
            return None
        return {"milestone": highest}

    def debug_match(self, ctx):
        return {"milestone": 10000}

    def already_fired(self, guard_val, match, ctx):
        try:
            last = int(guard_val or 0)
        except (TypeError, ValueError):
            last = 0
        return last >= match.get("milestone", 0)

    def new_guard_value(self, match, ctx):
        return match.get("milestone", 0)

    def toast_text(self, match, ctx):
        count = match.get("milestone", 0)
        title = tr("milestone_toast_title", "🏆 Milestone reached!")
        desc = tr(
            "milestone_toast_desc",
            "{count} lifetime reviews — incredible dedication!",
        ).format(count=f"{count:,}")
        return (title, desc)


REGISTRY = [
    BirthdayOccasion(),
    StudyAnniversaryOccasion(),
    NewYearOccasion(),
    ReviewMilestoneOccasion(),
]

_OCCASIONS_BY_ID = {occ.id: occ for occ in REGISTRY}


def _build_party_payload(active, sd_conf):
    """Merge the active occasions into one descriptor for party.js + accent CSS."""
    if not active:
        return None
    active_by_id = {occ.id: occ for occ, _ in active}
    primary_id = next((pid for pid in _PRIMARY_PRIORITY if pid in active_by_id), None)
    primary = active_by_id.get(primary_id) or active[0][0]
    return {
        "occasions": [occ.id for occ, _ in active],
        "emoji": primary.emoji,
        "accent": primary.accent,
        "confetti": bool(sd_conf.get("confetti", True)),
        "heatmap_effect": bool(sd_conf.get("heatmap_effect", True)),
    }


# --- Per-profile-open cache ----------------------------------------------------
_CACHE = None
_CACHE_DAY = None


def build_context():
    """Compute today's occasions. Runs the two revlog scalars (once per open)."""
    conf = config.get_config()
    sd_conf = conf.get("special_days", {})
    today = datetime.now().date()

    total_reviews = 0
    first_review_date = None
    try:
        if mw.col:
            total_reviews = mw.col.db.scalar(
                "SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3)"
            ) or 0
            first_ts = mw.col.db.scalar(
                "SELECT min(id) FROM revlog WHERE type IN (0,1,2,3)"
            )
            if first_ts:
                first_review_date = datetime.fromtimestamp(first_ts / 1000).date()
    except Exception as exc:
        print(f"Onigiri special_days: could not read revlog stats: {exc}")

    ctx = _DayContext(today, str(today.year), total_reviews, first_review_date, conf, sd_conf)

    if sd_conf.get("enabled", True):
        for occ in REGISTRY:
            try:
                match = occ.detect(ctx)
            except Exception as exc:
                print(f"Onigiri special_days: detect({occ.id}) failed: {exc}")
                match = None
            if match is None and occ.id in DEBUG_FORCE:
                match = occ.debug_match(ctx)
            if match is not None:
                ctx.active.append((occ, match))

    ctx.party_payload = _build_party_payload(ctx.active, sd_conf)
    return ctx


def get_context():
    """Cached context, rebuilt on first use, profile open, or date rollover."""
    global _CACHE, _CACHE_DAY
    today = datetime.now().date()
    if _CACHE is None or _CACHE_DAY != today:
        _CACHE = build_context()
        _CACHE_DAY = today
    return _CACHE


def invalidate_cache():
    """Drop the cache (call on profile close or after settings change)."""
    global _CACHE, _CACHE_DAY
    _CACHE = None
    _CACHE_DAY = None


# --- Public API ----------------------------------------------------------------
def get_party_state():
    """Cheap accessor for inject_menu_files(): the merged party payload, or None.

    After the first build (profile open) this is pure dict access — no SQL.
    """
    conf = config.get_config()
    if not conf.get("special_days", {}).get("enabled", True):
        return None
    try:
        return get_context().party_payload
    except Exception as exc:
        print(f"Onigiri special_days: get_party_state failed: {exc}")
        return None


def generate_party_accent_css(accent):
    """A standalone, high-specificity accent override.

    It auto-reverts simply by NOT being injected on the next non-special render,
    so the user's saved theme in config is never mutated.
    """
    return (
        '<style id="onigiri-party-mode-override">'
        f":root {{ --accent-color: {accent} !important; --button-primary-bg: {accent} !important; }}"
        f".night-mode {{ --accent-color: {accent} !important; --button-primary-bg: {accent} !important; }}"
        "</style>"
    )


def check_and_celebrate():
    """One-shot path (run on a QTimer after profile open).

    Fires each active occasion's modal/toast at most once per guard, then
    persists the updated guards in a single config write.
    """
    conf = config.get_config()
    if not conf.get("special_days", {}).get("enabled", True):
        return

    ctx = get_context()
    if not ctx.active:
        return

    special_days_conf = conf.setdefault("special_days", {})
    last_shown = special_days_conf.setdefault("last_shown", {})

    changed = False
    for occ, match in ctx.active:
        guard_val = last_shown.get(occ.id)
        if occ.already_fired(guard_val, match, ctx):
            continue
        try:
            occ.celebrate(match, ctx)
        except Exception as exc:
            print(f"Onigiri special_days: celebrate({occ.id}) failed: {exc}")
            continue
        last_shown[occ.id] = occ.new_guard_value(match, ctx)
        changed = True

    if changed:
        config.write_config(conf)
