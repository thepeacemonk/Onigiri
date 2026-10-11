"""Execute Kome's heatmap and dashboard hook without starting Anki."""
import ast
import datetime
import html
import math
import sys
import types
import unittest
from pathlib import Path
from typing import Dict
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class ThingsHeatmapRenderTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / "things_theme/__init__.py").read_text())
        names = {"_heatmap_level_fn", "build_heatmap_html",
                 "on_deck_browser_will_render_content"}
        functions = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
        self.today = int(datetime.datetime(
            2026, 10, 11, 12, tzinfo=datetime.timezone.utc
        ).timestamp() // 86400)
        self.counts = {self.today: 12, self.today - 1: 4}
        self.language = "en"
        self.month_calls = []
        self.day_calls = []
        def month_name(month, form):
            self.month_calls.append(month)
            return f"{self.language}-month-{month}"
        def day_name(day, form):
            self.day_calls.append(day)
            return f"{self.language}-day-{day}"
        locale = types.SimpleNamespace(monthName=month_name, dayName=day_name)
        qt = types.ModuleType("aqt.qt")
        qt.QLocale = types.SimpleNamespace(
            FormatType=types.SimpleNamespace(ShortFormat=0)
        )
        self.modules = patch.dict(sys.modules, {"aqt.qt": qt})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        translations = {
            "kome_review_activity": "Review activity",
            "today": "today", "hashi_yesterday": "yesterday",
            "kome_streak_days": "{n} day streak",
            "kome_reviews_weeks": "{total} reviews in {weeks} weeks",
        }
        class FixedDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(2026, 10, 11)

        self.namespace = dict(
            datetime=types.SimpleNamespace(date=FixedDate, timedelta=datetime.timedelta),
            html=html, math=math, Dict=Dict,
            time=types.SimpleNamespace(time=lambda: self.today * 86400 + 43200),
            mw=types.SimpleNamespace(col=object()),
            current_locale=lambda: locale, tr=translations.__getitem__,
            _counts_by_day=lambda: self.counts, _day_shift_seconds=lambda: 0,
            _config=lambda: {"heatmap_weeks": 8},
            build_review_chart_html=lambda days: '<section class="ba-review-chart"></section>',
            DeckBrowser=object, DeckBrowserContent=object,
        )
        exec(compile(ast.Module(body=functions, type_ignores=[]),
                     str(ROOT / "things_theme/__init__.py"), "exec"), self.namespace)

    def dashboard(self):
        content = types.SimpleNamespace(stats="")
        self.namespace["on_deck_browser_will_render_content"](None, content)
        return content.stats

    def test_dashboard_contains_review_cells_and_summary(self):
        output = self.dashboard()
        self.assertNotIn("heatmap error", output)
        self.assertIn('class="ba-heatmap-card"', output)
        self.assertIn('data-count="12"', output)
        self.assertIn("Review activity", output)
        self.assertIn("16 reviews in 8 weeks", output)
        self.assertIn("2 day streak", output)
        self.assertEqual(output.count("data-count="), 56)

    def test_empty_history_still_renders_calendar(self):
        self.counts.clear()
        output = self.dashboard()
        self.assertNotIn("heatmap error", output)
        self.assertEqual(output.count('data-count="0"'), 56)
        self.assertIn("0 reviews in 8 weeks", output)
        self.assertIn("0 day streak", output)

    def test_date_labels_follow_language_on_each_render(self):
        self.assertIn("en-month-10", self.dashboard())
        self.assertEqual(self.month_calls, list(range(1, 13)))
        self.assertEqual(self.day_calls, [7, 1, 2, 3, 4, 5, 6])
        self.language = "pt"
        output = self.dashboard()
        self.assertIn("pt-month-10", output)
        self.assertIn("pt-day-7", output)
        self.assertNotIn("en-month-", output)


if __name__ == "__main__":
    unittest.main()
