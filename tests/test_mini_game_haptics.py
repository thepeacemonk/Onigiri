"""Static contracts for macOS haptics across every bundled mini-game."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MiniGameHapticsTests(unittest.TestCase):
    def test_settings_web_has_a_native_haptic_bridge(self):
        dialog = (ROOT / "settings_web" / "dialog.py").read_text(encoding="utf-8")
        settings = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
        self.assertIn("def _cmd_haptic", dialog)
        self.assertIn("def _trigger_mac_haptic_native", dialog)
        self.assertIn('bridge("osw:haptic:1")', settings)

    def test_every_mini_game_routes_feedback_to_the_shared_bridge(self):
        game_sources = {
            "Nook Level": ROOT / "gamification" / "nook_web_ui.py",
            "Onigimon": ROOT / "gamification" / "onigimon_web_ui.py",
            "Hexagon Land": ROOT / "gamification" / "hexagon_land.py",
            "Focus Dango": ROOT / "gamification" / "focus_dango.py",
            "Mochi Messages": ROOT / "gamification" / "mochi_messages.py",
        }
        helper = (ROOT / "gamification" / "haptics.py").read_text(encoding="utf-8")
        self.assertIn("_trigger_mac_haptic_native", helper)
        for game, path in game_sources.items():
            with self.subTest(game=game):
                source = path.read_text(encoding="utf-8")
                self.assertIn("trigger_haptic", source)

    def test_web_games_request_feedback_for_user_actions(self):
        sources = {
            "Nook Level": ROOT / "web" / "gamification" / "nook_level" / "nook_level.js",
            "Mr. Taiyaki Store": ROOT / "web" / "gamification" / "mr_taiyaki_store" / "mr_taiyaki_store.js",
            "Onigimon": ROOT / "web" / "gamification" / "onigimon" / "onigimon.js",
            "Hexagon Land": ROOT / "gamification" / "hexagon_land.py",
        }
        for game, path in sources.items():
            with self.subTest(game=game):
                self.assertIn("haptic", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
