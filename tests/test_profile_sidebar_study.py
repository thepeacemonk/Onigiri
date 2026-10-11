import ast
import html
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def renderer(states, reviews=42, seconds=3900, streak=3):
    source = ast.parse((ROOT / 'rendering/onigiri_renderer.py').read_text())
    function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == '_profile_study_summary_html')
    things = types.ModuleType('profile_fixture.things_theme')
    things._card_state_counts = lambda: states
    things._standing = lambda: {'streak': streak}
    query_calls = []
    def query(sql, cutoff):
        query_calls.append((sql, cutoff))
        return reviews, seconds
    colors = dict(new='#55a8ee', learning='#ffd33d', relearning='#eb3f70', young='#6fc66f', mature='#78b8b4')
    namespace = dict(__package__='profile_fixture.rendering', html=html, tr=lambda key, fallback: fallback,
                     config=types.SimpleNamespace(get_config_readonly=lambda: {}, DEFAULTS={'things_theme': {'active_cards_colors': colors}}),
                     mw=types.SimpleNamespace(col=types.SimpleNamespace(sched=types.SimpleNamespace(day_cutoff=100000), db=types.SimpleNamespace(first=query))))
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'profile_sidebar', 'exec'), namespace)
    def render(options):
        with patch.dict(sys.modules, {'profile_fixture': types.ModuleType('profile_fixture'), 'profile_fixture.things_theme': things}):
            return namespace['_profile_study_summary_html'](options)
    return render, query_calls


class ProfileSidebarStudyTests(unittest.TestCase):
    def test_collection_counts_duration_and_browse_actions(self):
        render, queries = renderer(dict(new=10, learning=2, relearning=1, young=20, mature=67))
        output = render({})
        self.assertIn('<strong>100</strong>', output)
        self.assertIn('1h 5m', output)
        self.assertIn('3 days', output)
        self.assertEqual(output.count('ba:donut-open:'), 5)
        self.assertEqual(queries[0][1], (100000 - 86400) * 1000)
        self.assertIn('type IN (0,1,2,3)', queries[0][0])

    def test_zero_collection_has_an_empty_ring_and_real_zeroes(self):
        render, _ = renderer({}, reviews=0, seconds=0, streak=0)
        output = render({})
        self.assertIn('<strong>0</strong>', output)
        self.assertEqual(output.count('opacity: 0;'), 5)
        self.assertIn('0m', output)

    def test_visibility_toggles_omit_sections_and_stats_query(self):
        render, queries = renderer({})
        self.assertEqual(render({'show_active_cards': False, 'show_today_stats': False}), '')
        self.assertEqual(queries, [])


if __name__ == '__main__':
    unittest.main()
