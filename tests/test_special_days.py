"""
Tier 1 unit tests for the Special Days engine — pure logic only, no Anki.

These cover the parts where the bugs actually live: the Feb-29 leap-year fix,
the "celebrate a milestone exactly once" guard, occasion detection, and the
party-payload priority merge. Every test builds a plain _DayContext by hand and
calls the engine directly, so the whole suite runs in milliseconds with no
collection, no Qt and no display.
"""

from datetime import date

from onigiri import special_days as sd


def make_ctx(today, *, total_reviews=0, first_review_date=None, conf=None, sd_conf=None):
    """Build a _DayContext the way build_context() would, but from plain data."""
    conf = conf or {}
    if sd_conf is None:
        sd_conf = conf.get("special_days", {})
    return sd._DayContext(
        today=today,
        year_str=str(today.year),
        total_reviews=total_reviews,
        first_review_date=first_review_date,
        conf=conf,
        sd_conf=sd_conf,
    )


# Occasions are stateless, so a single shared instance per type is fine.
BIRTHDAY = sd.BirthdayOccasion()
ANNIVERSARY = sd.StudyAnniversaryOccasion()
NEW_YEAR = sd.NewYearOccasion()
MILESTONE = sd.ReviewMilestoneOccasion()


# --- _date_matches_today: the headline Feb-29 leap-year fix -------------------

def test_date_matches_exact_day():
    assert sd._date_matches_today(6, 23, date(2026, 6, 23)) is True


def test_date_does_not_match_other_day():
    assert sd._date_matches_today(6, 23, date(2026, 6, 24)) is False


def test_feb29_celebrated_on_feb28_in_non_leap_year():
    # 2027 is not a leap year -> a Feb-29 occasion should fall back to Feb-28.
    assert sd._date_matches_today(2, 29, date(2027, 2, 28)) is True


def test_feb29_not_matched_on_feb27_in_non_leap_year():
    assert sd._date_matches_today(2, 29, date(2027, 2, 27)) is False


def test_feb29_matches_real_feb29_in_leap_year():
    # 2028 *is* a leap year -> the real Feb-29 still matches.
    assert sd._date_matches_today(2, 29, date(2028, 2, 29)) is True


def test_feb29_not_remapped_in_leap_year():
    # In a leap year there is no fallback, so Feb-28 must not match Feb-29.
    assert sd._date_matches_today(2, 29, date(2028, 2, 28)) is False


# --- BirthdayOccasion.detect --------------------------------------------------

def test_birthday_today_returns_age():
    ctx = make_ctx(date(2026, 6, 23), conf={"userBirthday": "2000-06-23"})
    assert BIRTHDAY.detect(ctx) == {"age": 26}


def test_birthday_absent_returns_none():
    assert BIRTHDAY.detect(make_ctx(date(2026, 6, 23), conf={})) is None


def test_birthday_malformed_returns_none():
    ctx = make_ctx(date(2026, 6, 23), conf={"userBirthday": "nonsense"})
    assert BIRTHDAY.detect(ctx) is None


def test_birthday_feb29_fires_on_feb28_in_non_leap_year():
    # The regression the commit fixed: Feb-29 birthdays were missed in 2027.
    ctx = make_ctx(date(2027, 2, 28), conf={"userBirthday": "2000-02-29"})
    assert BIRTHDAY.detect(ctx) == {"age": 27}


# --- ReviewMilestoneOccasion: detection + "celebrate exactly once" guard ------

def test_milestone_detects_highest_threshold_crossed():
    ctx = make_ctx(date(2026, 6, 23), total_reviews=30000, sd_conf={"last_shown": {}})
    assert MILESTONE.detect(ctx) == {"milestone": 25000}


def test_milestone_none_below_first_threshold():
    ctx = make_ctx(date(2026, 6, 23), total_reviews=9000, sd_conf={"last_shown": {}})
    assert MILESTONE.detect(ctx) is None


def test_milestone_suppressed_after_being_celebrated():
    ctx = make_ctx(
        date(2026, 6, 23),
        total_reviews=30000,
        sd_conf={"last_shown": {"review_milestone": 25000}},
    )
    assert MILESTONE.detect(ctx) is None


def test_milestone_reactivates_at_next_tier():
    ctx = make_ctx(
        date(2026, 6, 23),
        total_reviews=60000,
        sd_conf={"last_shown": {"review_milestone": 25000}},
    )
    assert MILESTONE.detect(ctx) == {"milestone": 50000}


def test_milestone_already_fired_guard():
    ctx = make_ctx(date(2026, 6, 23))
    assert MILESTONE.already_fired("25000", {"milestone": 25000}, ctx) is True
    assert MILESTONE.already_fired("10000", {"milestone": 25000}, ctx) is False
    assert MILESTONE.already_fired(None, {"milestone": 10000}, ctx) is False


def test_milestone_new_guard_value_is_the_milestone():
    ctx = make_ctx(date(2026, 6, 23))
    assert MILESTONE.new_guard_value({"milestone": 50000}, ctx) == 50000


# --- StudyAnniversaryOccasion.detect ------------------------------------------

def test_anniversary_today_returns_years():
    ctx = make_ctx(date(2026, 6, 23), first_review_date=date(2023, 6, 23))
    assert ANNIVERSARY.detect(ctx) == {"years": 3}


def test_anniversary_same_year_is_not_an_anniversary():
    ctx = make_ctx(date(2023, 6, 23), first_review_date=date(2023, 6, 23))
    assert ANNIVERSARY.detect(ctx) is None


def test_anniversary_without_first_review_returns_none():
    assert ANNIVERSARY.detect(make_ctx(date(2026, 6, 23))) is None


# --- NewYearOccasion.detect ---------------------------------------------------

def test_new_year_fires_on_jan_1():
    assert NEW_YEAR.detect(make_ctx(date(2026, 1, 1))) == {"year": 2026}


def test_new_year_silent_on_other_days():
    assert NEW_YEAR.detect(make_ctx(date(2026, 1, 2))) is None


# --- _build_party_payload: priority resolution + flag plumbing ----------------

def test_payload_is_none_when_nothing_active():
    assert sd._build_party_payload([], {}) is None


def test_payload_birthday_wins_priority_over_new_year():
    active = [
        (NEW_YEAR, {"year": 2026}),
        (BIRTHDAY, {"age": 26}),
    ]
    payload = sd._build_party_payload(active, {})
    assert payload["emoji"] == "🎂"          # birthday's emoji
    assert payload["accent"] == "#FF5FA2"     # birthday's accent
    assert set(payload["occasions"]) == {"new_year", "birthday"}


def test_payload_single_occasion_uses_its_own_emoji():
    payload = sd._build_party_payload([(NEW_YEAR, {"year": 2026})], {})
    assert payload["emoji"] == "🎉"


def test_payload_flags_default_on_and_can_be_disabled():
    on = sd._build_party_payload([(NEW_YEAR, {})], {})
    assert on["confetti"] is True
    assert on["heatmap_effect"] is True

    off = sd._build_party_payload(
        [(NEW_YEAR, {})], {"confetti": False, "heatmap_effect": False}
    )
    assert off["confetti"] is False
    assert off["heatmap_effect"] is False


# --- generate_party_accent_css ------------------------------------------------

def test_accent_css_injects_color_under_override_id():
    css = sd.generate_party_accent_css("#ABCDEF")
    assert "#ABCDEF" in css
    assert "onigiri-party-mode-override" in css
    assert "!important" in css


# --- release safety: the debug override must never ship enabled ---------------

def test_debug_force_is_empty_for_release():
    assert sd.DEBUG_FORCE == set()
