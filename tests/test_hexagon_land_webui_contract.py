import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEXAGON = (ROOT / "gamification" / "hexagon_land.py").read_text(
    encoding="utf-8"
)
REDEMPTION = (ROOT / "gamification" / "reward_redemption.py").read_text(
    encoding="utf-8"
)
PATCHER = (ROOT / "patcher.py").read_text(encoding="utf-8")


class HexagonLandWebUiContractTests(unittest.TestCase):
    def test_hex_coin_flow_opens_inside_hexagon_land(self):
        self.assertIn("open_hexagon_land_dialog(open_redeem=True)", HEXAGON)
        self.assertIn('class="redeem-overlay"', HEXAGON)
        self.assertIn("pycmd('hex_land_redeem:'", HEXAGON)
        self.assertNotIn('open_reward_redeem_dialog(context="hex")', PATCHER)

    def test_redemption_network_call_has_background_safe_entry_point(self):
        self.assertIn("def fetch_reward_code(", REDEMPTION)
        self.assertIn("QueryOp(", HEXAGON)
        self.assertIn(".without_collection()", HEXAGON)

    def test_sidebar_navigation_uses_targeted_webui_updates(self):
        self.assertIn("function renderCatalog()", HEXAGON)
        self.assertIn("onclick=\"selectTab('${id}')\"", HEXAGON)
        self.assertIn("app.classList.toggle('side-collapsed'", HEXAGON)

    def test_sidebar_collapse_is_animated_and_accessible(self):
        self.assertIn(".app.side-transitioning .stage", HEXAGON)
        self.assertIn("transform 280ms cubic-bezier(.22, 1, .36, 1)", HEXAGON)
        self.assertIn("@media (prefers-reduced-motion: reduce)", HEXAGON)
        self.assertNotIn(".app.side-collapsed .side {\n    display: none;", HEXAGON)

    def test_dark_sidebar_toggle_hover_keeps_a_dark_surface(self):
        self.assertIn("body.nightMode .app .side-toggle:hover", HEXAGON)
        self.assertIn("background: rgba(52,52,54,.98);", HEXAGON)


if __name__ == "__main__":
    unittest.main()
