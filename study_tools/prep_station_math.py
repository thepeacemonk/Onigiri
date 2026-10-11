"""Pure projection math for Prep Station.

The planner deliberately lives outside the Anki/PyQt integration module so the
calculation can be exercised with ordinary Python.  A card is considered
``mature`` when its scheduled interval reaches 21 days, matching Anki's stats
and the convention used by Anki Simulator.

The FSRS equations below follow the public FSRS-6 model.  The implementation is
independent and deterministic: it follows the expected Good-answer path, while
charging ``1 / desired_retention`` reviews for each successful review.  This
keeps the result stable enough to be a daily goal rather than a Monte Carlo
number that changes each time the dialog opens.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


MATURE_INTERVAL_DAYS = 21
DEFAULT_DESIRED_RETENTION = 0.90
DEFAULT_FSRS_DECAY = 0.1542

# FSRS-6 defaults used when a preset has not been optimized.  Anki represents
# an unoptimized preset with an empty parameter array, so a local fallback is
# required for projecting cards that do not exist yet.
DEFAULT_FSRS_PARAMETERS = (
    0.212,
    1.2931,
    2.3065,
    8.2956,
    6.4133,
    0.8334,
    3.0194,
    0.001,
    1.8722,
    0.1666,
    0.796,
    1.4835,
    0.0614,
    0.2629,
    1.6483,
    0.6014,
    1.8729,
    0.5425,
    0.0912,
    0.0658,
    DEFAULT_FSRS_DECAY,
)


@dataclass(frozen=True)
class FsrsSettings:
    """Scheduling inputs shared by a group of cards."""

    desired_retention: float = DEFAULT_DESIRED_RETENTION
    parameters: tuple[float, ...] = DEFAULT_FSRS_PARAMETERS
    learning_steps: tuple[float, ...] = (1.0, 10.0)
    maximum_interval: int = 36500


@dataclass(frozen=True)
class ProjectionCard:
    """Small, serializable card snapshot needed by the projection."""

    interval: int = 0
    due_day: int = 0
    stability: float | None = None
    difficulty: float | None = None
    last_review_day: int | None = None
    is_new: bool = False
    learning_steps_remaining: int = 0
    settings: FsrsSettings = FsrsSettings()


@dataclass(frozen=True)
class CardPath:
    matures_on: int | None
    reviews_to_mature: float
    reviews_through_exam: float


def clamp_retention(value: float) -> float:
    """Keep the model inside Anki's supported desired-retention range."""

    return max(0.70, min(0.99, float(value or DEFAULT_DESIRED_RETENTION)))


def normalized_settings(settings: FsrsSettings) -> FsrsSettings:
    params = tuple(float(value) for value in settings.parameters)
    if len(params) != 21 or any(not math.isfinite(value) for value in params):
        params = DEFAULT_FSRS_PARAMETERS
    return FsrsSettings(
        desired_retention=clamp_retention(settings.desired_retention),
        parameters=params,
        learning_steps=tuple(max(0.0, float(step)) for step in settings.learning_steps),
        maximum_interval=max(1, int(settings.maximum_interval or 36500)),
    )


def _factor(decay: float) -> float:
    decay = max(0.01, float(decay or DEFAULT_FSRS_DECAY))
    return (0.9 ** (-1.0 / decay)) - 1.0


def interval_for_stability(
    stability: float,
    desired_retention: float,
    decay: float,
    maximum_interval: int,
) -> int:
    """Return FSRS's unfuzzed interval for a memory stability value."""

    decay = max(0.01, float(decay or DEFAULT_FSRS_DECAY))
    retention = clamp_retention(desired_retention)
    interval = (max(0.001, stability) / _factor(decay)) * (
        retention ** (-1.0 / decay) - 1.0
    )
    return max(1, min(int(maximum_interval), round(interval)))


def stability_for_interval(
    interval: int,
    desired_retention: float,
    decay: float,
) -> float:
    """Estimate missing stability by inverting FSRS's interval equation."""

    decay = max(0.01, float(decay or DEFAULT_FSRS_DECAY))
    denominator = clamp_retention(desired_retention) ** (-1.0 / decay) - 1.0
    if denominator <= 0:
        return max(0.001, float(interval))
    return max(0.001, max(1, int(interval)) * _factor(decay) / denominator)


def retrievability(stability: float, elapsed_days: int, decay: float) -> float:
    decay = max(0.01, float(decay or DEFAULT_FSRS_DECAY))
    return (
        1.0 + _factor(decay) * max(0, elapsed_days) / max(0.001, stability)
    ) ** (-decay)


def _initial_difficulty(params: Sequence[float]) -> float:
    value = params[4] - math.exp(params[5] * 2.0) + 1.0
    return max(1.0, min(10.0, value))


def _next_difficulty(difficulty: float, params: Sequence[float]) -> float:
    initial_easy = params[4] - math.exp(params[5] * 3.0) + 1.0
    delta = (10.0 - difficulty) * 0.0 / 9.0  # Good has zero difficulty delta.
    value = params[7] * initial_easy + (1.0 - params[7]) * (difficulty + delta)
    return max(1.0, min(10.0, value))


def _next_good_stability(
    difficulty: float,
    stability: float,
    recall_probability: float,
    params: Sequence[float],
) -> float:
    increase = (
        math.exp(params[8])
        * (11.0 - difficulty)
        * (max(0.001, stability) ** -params[9])
        * (math.exp((1.0 - recall_probability) * params[10]) - 1.0)
    )
    return max(0.001, stability * (1.0 + increase))


def _short_term_good_stability(stability: float, params: Sequence[float]) -> float:
    increase = math.exp(params[17] * params[18]) * (
        max(0.001, stability) ** -params[19]
    )
    return max(0.001, stability * max(1.0, increase))


def _learning_review_days(steps: Sequence[float], remaining: int) -> list[int]:
    """Return day offsets for the expected Good learning sequence.

    Learning steps are stored as minutes.  Sub-day steps remain on the same
    projection day; interday steps move the next answer to a later day.
    """

    if remaining <= 0:
        remaining = max(1, len(steps))
    relevant = list(steps[-remaining:]) if steps else [0.0]
    offsets = []
    day = 0
    for index in range(max(1, remaining)):
        offsets.append(day)
        if index < len(relevant) - 1:
            day += int(max(0.0, relevant[index + 1]) // 1440.0)
    return offsets


def project_card(card: ProjectionCard, horizon_days: int) -> CardPath:
    """Project one card along its expected FSRS Good-answer path."""

    horizon = max(0, int(horizon_days))
    settings = normalized_settings(card.settings)
    params = settings.parameters
    retention = settings.desired_retention
    decay = max(0.01, float(params[20]))
    day = max(0, int(card.due_day))
    stability = card.stability
    difficulty = card.difficulty
    interval = max(0, int(card.interval))
    reviews = 0.0
    matures_on = 0 if interval >= MATURE_INTERVAL_DAYS else None

    if matures_on is not None:
        # Existing mature cards still create maintenance work before the exam.
        first_review = True
        while day < horizon:
            elapsed = interval
            if card.last_review_day is not None and first_review:
                elapsed = max(0, day - card.last_review_day)
            stability = stability or stability_for_interval(interval, retention, decay)
            difficulty = difficulty or _initial_difficulty(params)
            recall = retrievability(stability, elapsed, decay)
            reviews += 1.0 / max(0.05, recall)
            stability = _next_good_stability(difficulty, stability, recall, params)
            difficulty = _next_difficulty(difficulty, params)
            interval = interval_for_stability(
                stability, retention, decay, settings.maximum_interval
            )
            day += interval
            first_review = False
        return CardPath(0, 0.0, reviews)

    if card.is_new or card.learning_steps_remaining:
        learning_days = _learning_review_days(
            settings.learning_steps,
            card.learning_steps_remaining,
        )
        for index, offset in enumerate(learning_days):
            review_day = day + offset
            if review_day >= horizon:
                return CardPath(None, reviews, reviews)
            reviews += 1.0
            if stability is None:
                stability = max(0.001, params[2])
                difficulty = _initial_difficulty(params)
            elif index:
                stability = _short_term_good_stability(stability, params)
                difficulty = _next_difficulty(
                    difficulty or _initial_difficulty(params), params
                )
        day += learning_days[-1]
        interval = interval_for_stability(
            stability or params[2], retention, decay, settings.maximum_interval
        )
        if interval >= MATURE_INTERVAL_DAYS:
            matures_on = day
        day += interval
    else:
        stability = stability or stability_for_interval(
            max(1, interval), retention, decay
        )
        difficulty = difficulty or _initial_difficulty(params)

    reviews_to_mature = reviews
    first_review = True
    while day < horizon:
        if card.last_review_day is not None and first_review:
            recall = retrievability(
                stability or params[2],
                max(0, day - card.last_review_day),
                decay,
            )
        else:
            recall = retention
        reviews += 1.0 / max(0.05, recall)
        stability = _next_good_stability(
            difficulty or _initial_difficulty(params),
            stability or params[2],
            recall,
            params,
        )
        difficulty = _next_difficulty(
            difficulty or _initial_difficulty(params), params
        )
        interval = interval_for_stability(
            stability, retention, decay, settings.maximum_interval
        )
        if matures_on is None and interval >= MATURE_INTERVAL_DAYS:
            matures_on = day
            reviews_to_mature = reviews
        day += interval
        first_review = False

    if matures_on is None:
        reviews_to_mature = reviews
    return CardPath(matures_on, reviews_to_mature, reviews)


def evenly_spaced_arrival_days(count: int, horizon_days: int) -> list[int]:
    """Spread user-entered future cards across the remaining study days."""

    count = max(0, int(count))
    horizon = max(1, int(horizon_days))
    return [
        min(horizon - 1, (index * horizon) // max(1, count))
        for index in range(count)
    ]


def calculate_plan_projection(
    cards: Iterable[ProjectionCard],
    future_cards: Iterable[ProjectionCard],
    horizon_days: int,
    target_percent: int,
) -> dict:
    """Calculate the minimum average daily workload for a maturity target."""

    current = list(cards)
    future = list(future_cards)
    horizon = max(1, int(horizon_days))
    target = max(1, min(100, int(target_percent)))
    current_mature = sum(
        1 for card in current if card.interval >= MATURE_INTERVAL_DAYS
    )
    projected_total = len(current) + len(future)
    target_mature = math.ceil(projected_total * target / 100.0)
    mature_gap = max(0, target_mature - current_mature)

    required_existing_reviews = 0.0
    expected_mature = current_mature
    candidates: list[CardPath] = []
    for card in current:
        path = project_card(card, horizon)
        if card.interval >= MATURE_INTERVAL_DAYS:
            required_existing_reviews += path.reviews_through_exam
        elif card.is_new:
            if path.matures_on is not None:
                candidates.append(path)
        else:
            # Scheduled young/learning cards remain part of the deck's normal
            # FSRS workload even when the maturity target is already met.
            required_existing_reviews += path.reviews_through_exam
            if path.matures_on is not None:
                expected_mature += 1
    for card in future:
        path = project_card(card, horizon)
        if path.matures_on is not None:
            candidates.append(path)

    candidates.sort(
        key=lambda item: (
            item.reviews_through_exam,
            item.matures_on if item.matures_on is not None else horizon + 1,
        )
    )
    introductions_needed = max(0, target_mature - expected_mature)
    selected = candidates[:introductions_needed]
    achievable_mature = expected_mature + len(candidates)
    projected_mature = expected_mature + len(selected)
    achievable_percent = (
        (achievable_mature / projected_total * 100.0) if projected_total else 100.0
    )
    total_reviews = required_existing_reviews + sum(
        item.reviews_through_exam for item in selected
    )
    required_per_day = total_reviews / horizon

    return {
        "current_total": len(current),
        "future_new_cards": len(future),
        "projected_total": projected_total,
        "current_mature": current_mature,
        "current_mature_percent": (
            current_mature / len(current) * 100.0 if current else 0.0
        ),
        "target_mature": target_mature,
        "target_mature_percent": target,
        "mature_gap": mature_gap,
        "projected_mature": projected_mature,
        "achievable_mature": achievable_mature,
        "achievable_percent": min(100.0, achievable_percent),
        "feasible": len(candidates) >= introductions_needed,
        "expected_mature_from_scheduled": expected_mature,
        "cards_to_introduce": introductions_needed,
        "maintenance_reviews": required_existing_reviews,
        "workload_reviews": total_reviews,
        "required_per_day": required_per_day,
    }
