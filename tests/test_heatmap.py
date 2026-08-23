"""Tests for heatmap.get_heatmap_data(): streaks, due mapping, averages.

Uses a real in-memory SQLite database seeded relative to 'today' as the
production code computes it, so date math is verified end-to-end
(including the SQL STRFTIME grouping).
"""

import sqlite3

import pytest

from conftest import (
    FakeCol,
    FakeDb,
    FakeMw,
    FakeSched,
    load_module,
    local_midnight,
    revlog_rows_at_local_noon,
)


@pytest.fixture()
def heatmap_mod():
    return load_module("heatmap")


def _seed_reviews(db: FakeDb, day_offsets_with_counts):
    """Seed revlog rows at local noon for each (day_offset, count)."""
    rows = []
    for offset, count in day_offsets_with_counts:
        base_id = (local_midnight(offset) + 12 * 3600) * 1000
        for i in range(count):
            # Spread within the afternoon to keep unique ids per review.
            rows.append((base_id + i * 60_000, 1, 0))
    db.conn.executemany("INSERT INTO revlog (id, cid, type) VALUES (?, ?, ?)", rows)
    db.conn.commit()


def _seed_due_cards(db: FakeDb, due_day_to_count):
    """Seed queue=2 cards with relative due day numbers."""
    rows = [(2, due) for due, count in due_day_to_count.items() for _ in range(count)]
    db.conn.executemany("INSERT INTO cards (queue, due) VALUES (?, ?)", rows)
    db.conn.commit()


def test_empty_collection_returns_zeroed_payload(heatmap_mod, heatmap_clock):
    mw = FakeMw()  # empty db
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    # Today is always present in the calendar (count may be zero).
    assert data["calendar"] == {heatmap_clock.key(0): 0}
    assert data["streak"] == 0
    assert data["longest_streak"] == 0
    assert data["due_calendar"] == {}
    assert data["daily_average"] == 0


def test_no_col_short_circuits(heatmap_mod):
    mw = FakeMw()
    mw.col = None
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data == {"calendar": {}, "streak": 0, "due_calendar": {}}


def test_streak_counts_today_and_yesterday(heatmap_mod, heatmap_clock):
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    _seed_reviews(mw.col.db, [(0, 5), (-1, 3)])
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["streak"] == 2
    assert data["longest_streak"] == 2
    assert data["calendar"][heatmap_clock.key(0)] == 5
    assert data["calendar"][heatmap_clock.key(-1)] == 3


def test_streak_survives_when_today_missing(heatmap_mod, heatmap_clock):
    """Reviewed yesterday only -> streak of 1 starting from yesterday."""
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    _seed_reviews(mw.col.db, [(-1, 4)])
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["streak"] == 1


def test_gap_breaks_current_streak_but_not_longest(heatmap_mod, heatmap_clock):
    """Today+yes (2), gap yesterday-1, then a 10-day run ending -40."""
    runs = [(d, 1) for d in range(-40, -30)]  # 10 consecutive days
    runs += [(0, 2), (-1, 2)]
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    _seed_reviews(mw.col.db, runs)
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["streak"] == 2
    assert data["longest_streak"] == 10


def test_manual_rescheduling_rows_are_ignored(heatmap_mod, heatmap_clock):
    """type=4 rows are manual operations and must not count as reviews."""
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    _seed_reviews(mw.col.db, [(0, 1)])
    manual_id = local_midnight(0) + 15 * 3600 * 1000
    mw.col.db.conn.execute("INSERT INTO revlog (id, cid, type) VALUES (?, 1, 4)", (manual_id,))
    mw.col.db.conn.commit()
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["calendar"][heatmap_clock.key(0)] == 1
    assert data["streak"] == 1


def test_future_due_days_map_to_local_dates(heatmap_mod, heatmap_clock):
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    _seed_due_cards(mw.col.db, {1: 4, 2: 2, 5: 7})
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["due_calendar"] == {
        heatmap_clock.key(1): 4,
        heatmap_clock.key(2): 2,
        heatmap_clock.key(5): 7,
    }


def test_daily_average_divides_by_days_since_first_review(heatmap_mod, heatmap_clock):
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    _seed_reviews(mw.col.db, [(-9, 30), (0, 10)])  # first review 9 days ago
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    # days_elapsed = 9 + 1 = 10 -> (30 + 10) / 10
    assert data["daily_average"] == pytest.approx(4.0)


def test_first_year_reflects_first_review(heatmap_mod, heatmap_clock):
    mw = FakeMw(col=FakeCol(sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    old_year = datetime_from_timestamp(local_midnight(-400)).year
    _seed_reviews(mw.col.db, [(-400, 1), (0, 1)])
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["firstYear"] == old_year


def datetime_from_timestamp(ts_seconds):
    from datetime import datetime

    return datetime.fromtimestamp(ts_seconds)


def test_rollover_hour_is_reported_not_applied(heatmap_mod, heatmap_clock):
    """The rollover setting is surfaced to JS; cutoff comes from sched."""
    conf = {"rollover": 7}
    mw = FakeMw(col=FakeCol(conf=conf, sched=FakeSched(day_cutoff=heatmap_clock.day_cutoff)))
    heatmap_mod.mw = mw

    data = heatmap_mod.get_heatmap_data()

    assert data["rollover_hour"] == 7
