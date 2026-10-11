import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = (ROOT / "onigiri_renderer.py").read_text(encoding="utf-8")
ONIGIMON = (ROOT / "gamification" / "onigimon.py").read_text(encoding="utf-8")
HEXAGON = (ROOT / "gamification" / "hexagon_land.py").read_text(encoding="utf-8")


class GameWidgetRootContractTests(unittest.TestCase):
    def test_game_widgets_receive_grid_position_directly(self):
        self.assertIn('widget_id in ("onigimon", "hexagon_land")', RENDERER)
        self.assertIn('grid_style=style', RENDERER)

    def test_onigimon_card_is_the_root_widget_without_a_title(self):
        self.assertIn('class="onigimon-card onigimon-card-compact', ONIGIMON)
        self.assertIn('root_class = card_class if companion', ONIGIMON)
        self.assertNotIn('class="onigimon-widget', ONIGIMON)
        self.assertNotIn('<h3>Onigimon</h3>', ONIGIMON)

    def test_hexagon_preview_is_the_root_widget_without_a_title(self):
        self.assertIn('class="hex-land-preview disabled"', HEXAGON)
        self.assertIn('class="hex-land-preview" style="{grid_style}', HEXAGON)
        self.assertNotIn('class="hex-land-widget', HEXAGON)


if __name__ == "__main__":
    unittest.main()
