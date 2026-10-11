"""Render both designs without importing Anki or touching a collection."""
import ast
import html
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


class ReadyToGoWidgetDesignTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse((ROOT / "study_tools/ready_to_go.py").read_text())
        names = {"_buttons_html", "render_sidebar_html", "render_widget_html"}
        nodes = [node for node in source.body if
                 isinstance(node, ast.FunctionDef) and node.name in names or
                 isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "READY_ACTIONS"
                     for target in node.targets)]
        self.env = {
            "html": html,
            "localized_default": lambda value, keys: value,
            "tr": lambda key: {
                "ready_inbox": "Inbox", "ready_warm_up": "Warm up",
                "profile_sidebar_today": "Today", "ready_cool_down": "Cool-Down",
            }[key],
            "config": SimpleNamespace(themed_icon_color=lambda key: ""),
            "_setting": lambda key, default: default,
            "_color_setting": lambda key, default: default,
            "_icon_url": lambda key: "/icons/" + key + ".svg",
            "_appearance_style": lambda: "",
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "study_tools/ready_to_go.py", "exec"), self.env)

    def test_existing_and_unknown_designs_keep_labeled_shortcuts(self):
        render = self.env["render_widget_html"]
        for markup in (render(), render("squares"), render("unknown")):
            self.assertNotIn("is-circles", markup)
            self.assertEqual(markup.count('class="onigiri-ready-action '), 4)
            self.assertIn('<span>Inbox</span>', markup)
            self.assertIn('title="Inbox"', markup)

    def test_circles_keep_all_actions_and_accessible_names(self):
        markup = self.env["render_widget_html"]("circles")
        self.assertIn("is-circles", markup)
        self.assertEqual(markup.count('class="mag-skin"'), 4)
        self.assertEqual(markup.count('class="mag-label"'), 4)
        self.assertNotIn('title="Inbox"', markup)
        for key, action in self.env["READY_ACTIONS"].items():
            self.assertIn("pycmd('onigiri_ready:" + key + "')", markup)
            self.assertIn('aria-label="' + action["label"] + '"', markup)
            self.assertIn('/icons/' + key + '.svg', markup)

    def test_sidebar_keeps_its_existing_design(self):
        markup = self.env["render_sidebar_html"]()
        self.assertNotIn("mag-skin", markup)
        self.assertIn('<span>Inbox</span>', markup)

    def test_custom_tints_are_used_for_ready_icons(self):
        self.env["config"].themed_icon_color = lambda key: "#DDEEFF"
        markup = self.env["render_sidebar_html"]()
        self.assertEqual(markup.count("background-color:#DDEEFF"), 4)


if __name__ == "__main__":
    unittest.main()
