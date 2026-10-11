import unittest

from prep_station_math import (
    FsrsSettings,
    ProjectionCard,
    calculate_plan_projection,
    evenly_spaced_arrival_days,
    project_card,
)


class PrepStationMathTests(unittest.TestCase):
    def test_future_cards_are_part_of_target_denominator(self):
        cards = [ProjectionCard(interval=30, due_day=40) for _ in range(8)]
        future = [ProjectionCard(is_new=True) for _ in range(2)]

        result = calculate_plan_projection(cards, future, 14, 80)

        self.assertEqual(result["projected_total"], 10)
        self.assertEqual(result["target_mature"], 8)
        self.assertTrue(result["feasible"])

    def test_higher_retention_requires_more_reviews_to_mature(self):
        low = project_card(
            ProjectionCard(
                is_new=True,
                settings=FsrsSettings(desired_retention=0.80),
            ),
            60,
        )
        high = project_card(
            ProjectionCard(
                is_new=True,
                settings=FsrsSettings(desired_retention=0.95),
            ),
            60,
        )

        self.assertGreater(high.reviews_to_mature, low.reviews_to_mature)
        self.assertGreater(high.matures_on, low.matures_on)

    def test_late_future_cards_can_make_target_unreachable(self):
        future = [
            ProjectionCard(is_new=True, due_day=day)
            for day in evenly_spaced_arrival_days(10, 21)
        ]

        result = calculate_plan_projection([], future, 21, 80)

        self.assertFalse(result["feasible"])
        self.assertLess(result["achievable_percent"], 80)

    def test_scheduled_young_cards_remain_in_daily_workload(self):
        cards = [
            ProjectionCard(interval=30, due_day=40),
            ProjectionCard(interval=5, due_day=0),
        ]

        result = calculate_plan_projection(cards, [], 30, 50)

        self.assertTrue(result["feasible"])
        self.assertGreater(result["workload_reviews"], 0)
        self.assertGreater(result["expected_mature_from_scheduled"], 1)


if __name__ == "__main__":
    unittest.main()
