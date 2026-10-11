import ast
import runpy
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOOK_LEVEL = ROOT / "gamification" / "nook_level.py"
TRANSLATIONS = ROOT / "core/translations.py"
ASSET_ROOT = ROOT / "system_files" / "gamification_images" / "nook_folder"


def _literal_assignment(name):
    tree = ast.parse(NOOK_LEVEL.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment: {name}")


def _loaded_translations():
    original_aqt = sys.modules.get("aqt")
    aqt = types.ModuleType("aqt")
    aqt.mw = types.SimpleNamespace(
        pm=types.SimpleNamespace(profile={"onigiri_language": "en"})
    )
    sys.modules["aqt"] = aqt
    try:
        namespace = runpy.run_path(str(TRANSLATIONS))
        return namespace["LANGUAGES"], namespace["TRANSLATIONS"]
    finally:
        if original_aqt is None:
            sys.modules.pop("aqt", None)
        else:
            sys.modules["aqt"] = original_aqt


class DeveloperNookCatalogTest(unittest.TestCase):
    def test_all_developer_nooks_have_real_art_and_theme_colors(self):
        devs = _literal_assignment("DEVS")
        self.assertEqual(
            set(devs),
            {
                "koeni_nook",
                "dyzur_sushi",
                "max_udon_recoin",
                "maxims_shop",
                "mochi_girl_shop",
                "nitro_nook",
                "royal_kulfi",
            },
        )
        for item in devs.values():
            self.assertRegex(item["theme"], r"^#[0-9A-F]{6}$")
            self.assertTrue((ASSET_ROOT / item["image"]).is_file(), item["image"])

    def test_new_shop_art_is_connected(self):
        shops = _literal_assignment("SHOPS")
        expected = {
            "wizard_shop": "shops/wizard_shop.webp",
            "paws_whiskers": "shops/paws_and_whiskers.webp",
            "dino_shop": "shops/dino_shop.webp",
        }
        for item_id, image in expected.items():
            self.assertEqual(shops[item_id]["image"], image)
            self.assertTrue((ASSET_ROOT / image).is_file(), image)

    def test_every_store_item_is_translated_in_every_available_language(self):
        languages, translations = _loaded_translations()
        groups = (
            _literal_assignment("RESTAURANTS"),
            _literal_assignment("EVOLUTIONS"),
            _literal_assignment("SHOPS"),
            _literal_assignment("DEVS"),
        )
        keys = {
            item[field]
            for group in groups
            for item in group.values()
            for field in ("name", "description")
        }

        for language_code in languages.values():
            self.assertIn(language_code, translations)
            for key in keys:
                self.assertIn(key, translations[language_code], (language_code, key))
                self.assertTrue(translations[language_code][key].strip())

        english = translations["en"]
        description_keys = {
            item["description"] for group in groups for item in group.values()
        }
        for language_code in languages.values():
            if language_code == "en":
                continue
            for key in description_keys:
                self.assertNotEqual(
                    translations[language_code][key],
                    english[key],
                    (language_code, key),
                )

    def test_both_webviews_expose_the_developer_category(self):
        files = (
            ROOT / "web" / "gamification" / "nook_level" / "nook_level.html",
            ROOT / "web" / "gamification" / "mr_taiyaki_store" / "mr_taiyaki_store.html",
        )
        for path in files:
            self.assertIn('data-group="devs"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
