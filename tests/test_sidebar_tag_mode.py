import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "core/config.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
RENDERER = (ROOT / "rendering/onigiri_renderer.py").read_text(encoding="utf-8")
TREE_UPDATER = (ROOT / "decks" / "tree_updater.py").read_text(encoding="utf-8")
HANDLERS = (ROOT / "rendering/webview_handlers.py").read_text(encoding="utf-8")
ENGINE = (ROOT / "web" / "engine.js").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "rendering/templates.py").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "core/translations.py").read_text(encoding="utf-8")
READY_TO_GO = (ROOT / "study_tools/ready_to_go.py").read_text(encoding="utf-8")


class SidebarTagModeContractTests(unittest.TestCase):
    def test_sidebar_mode_defaults_to_decks_and_is_configurable(self):
        self.assertIn('"sidebarContentMode": "decks"', CONFIG)
        self.assertIn('"id": "sidebarContentMode"', SCHEMA)
        self.assertIn('{"value": "tags", "label": tr("tags", "Tags")}', SCHEMA)

    def test_renderer_switches_between_deck_and_tag_trees(self):
        self.assertIn('_render_tag_tree_html(self)', RENDERER)
        self.assertIn('"sidebarContentMode": sidebar_content_mode', RENDERER)
        self.assertIn('is-tags-mode', RENDERER)
        self.assertIn('onigiri-tag-table', TEMPLATE)

    def test_tag_rows_are_hierarchical_searchable_and_safe(self):
        self.assertIn('tree = deck_browser.mw.col.tags.tree()', TREE_UPDATER)
        self.assertIn('margin-inline-start: calc(var(--tag-depth, 0) * 16px)', TEMPLATE)
        self.assertIn('encoded_tag = quote(full_name, safe="")', TREE_UPDATER)
        self.assertIn('onigiri_tag_search:', ENGINE)
        self.assertIn('onigiri_tag_collapse:', HANDLERS)
        self.assertIn('_render_active_sidebar_list(deck_browser)', TREE_UPDATER)
        self.assertIn('"search_tags": "Search tags"', TRANSLATIONS)
        self.assertIn('desired_state = "1" if expanded else "0"', TREE_UPDATER)

    def test_tag_click_starts_a_reusable_filtered_deck(self):
        self.assertIn('onigiri_study_tag:', TREE_UPDATER)
        self.assertIn('ready_to_go.study_tag(tag)', HANDLERS)
        self.assertIn('TAG_STUDY_DECK_NAME = "Onigiri Ready — Tags"', READY_TO_GO)
        self.assertIn('SearchNode(tag=tag)', READY_TO_GO)
        self.assertIn('_build_and_study({', READY_TO_GO)

    def test_each_tag_can_open_the_existing_icon_picker(self):
        self.assertIn('lucide-tags.svg', TREE_UPDATER)
        self.assertIn('showTagContextMenu', ENGINE)
        self.assertIn('onigiri_tag_change_icon:', HANDLERS)
        self.assertIn('"onigiri_custom_tag_icons"', HANDLERS)


if __name__ == "__main__":
    unittest.main()
