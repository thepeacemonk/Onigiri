import unittest
from pathlib import Path


HTML = (
    Path(__file__).resolve().parents[1] / "web" / "prep_station.html"
).read_text(encoding="utf-8")


class PrepStationWebTests(unittest.TestCase):
    def test_native_color_and_confirmation_controls_are_not_used(self):
        self.assertNotIn('type="color"', HTML)
        self.assertNotIn("confirm(", HTML)
        self.assertIn("openWebColorPicker", HTML)
        self.assertIn("openDeleteDialog", HTML)

    def test_icon_color_is_limited_to_icons_tab(self):
        self.assertIn("$('icon-color-foot').hidden = active !== 1", HTML)

    def test_anki_button_effects_are_neutralized(self):
        self.assertIn("box-shadow: none !important", HTML)
        self.assertIn("transition: none !important", HTML)
        self.assertIn("border: 0 !important", HTML)

    def test_empty_state_has_guided_onboarding(self):
        self.assertIn("prep_empty_exam_step", HTML)
        self.assertIn("prep_empty_decks_step", HTML)
        self.assertIn("prep_empty_goal_step", HTML)
        self.assertIn('class="empty-mark"><svg', HTML)


if __name__ == "__main__":
    unittest.main()
