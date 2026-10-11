"""Reviewer sizing and border contracts without opening an Anki profile."""
import ast
import json
import os
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def reviewer_env(saved=None):
    saved = saved or {}
    cfg = types.SimpleNamespace(get_collection_config=lambda key, default=None: saved.get(key, default))
    env = {"config": cfg, "os": os, "json": json,
           "__file__": str(ROOT / "rendering/patcher.py"), "tr_at": lambda key: key}
    names = {"_reviewer_controls_font_size", "_reviewer_fixed_button_metrics", "_reviewer_bottom_bar_height_px",
             "generate_reviewer_buttons_css", "_onigiri_int_style_value"}
    tree = ast.parse((ROOT / "rendering/patcher.py").read_text())
    exec(compile(ast.Module(body=[node for node in tree.body
                                 if isinstance(node, ast.FunctionDef) and node.name in names],
                            type_ignores=[]), "patcher.py", "exec"), env)
    return env


def browser_fixtures():
    from test_localization import LocalizationTests
    case=LocalizationTests();case.setUp()
    fixtures=[]
    for lang, strings in case.translations.TRANSLATIONS.items():
     for dark in (False,True):
      for size in (14,28):
       conf={'onigiri_reviewer_stattxt_mode':'fixed','onigiri_font_size_reviewer_controls':size,'onigiri_reviewer_btn_border_size':2,'onigiri_reviewer_btn_height':40,'onigiri_reviewer_btn_radius':12,'onigiri_reviewer_btn_padding':5,'onigiri_reviewer_bar_height':60,'onigiri_reviewer_other_btn_bg_light':'#ffffff','onigiri_reviewer_other_btn_bg_dark':'#3a3a3a','onigiri_reviewer_good_border_light':'#123456'}
       env=reviewer_env(conf);env['tr_at']=lambda key:strings[key]
       fixtures.append({'lang':lang,'dark':dark,'size':size,'strings':{key:strings[key] for key in ('show_answer','bbar_edit','more','again','hard','good','easy')},'css':env['generate_reviewer_buttons_css'](conf),'height':env['_reviewer_bottom_bar_height_px'](conf)})
    case.doCleanups()
    return fixtures


class ReviewerBottomBarTests(unittest.TestCase):
    def test_every_border_control_has_persisted_light_and_dark_bindings(self):
        env = {"tr": lambda key, fallback: fallback,
               "_color_pair_field": lambda id, *args, **kwargs: {"id": id, "type": "color_pair"},
               "_image_field": lambda id, *args, **kwargs: {"id": id},
               "_hidden_config_field": lambda id, *args, **kwargs: {"id": id},
               "_designer_preview_section": lambda id, preview, **kwargs: dict(kwargs, id=id),
               "_attach_compact_font_roles": lambda section, *args: section}
        tree = ast.parse((ROOT / "settings_web/schema.py").read_text())
        exec(compile(ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)
                                     and node.name == "_reviewer_bottom_bar_section"], type_ignores=[]),
                     "schema.py", "exec"), env)
        section = env["_reviewer_bottom_bar_section"]()
        fields = {field["id"]: field for field in section["fields"]}
        self.assertEqual(fields["bbar_btn_border_size"]["bind"]["key"], "onigiri_reviewer_btn_border_size")
        for family in ("show_answer", "again", "hard", "good", "easy", "other", "timer"):
            for mode in ("light", "dark"):
                field = fields[f"bbar_{family}_border_{mode}"]
                self.assertEqual(field["bind"]["key"], f"onigiri_reviewer_{family}_border_{mode}")
            group = next(group for group in section["color_groups"] if group["id"] == "bbar_colors_" + family)
            self.assertIn("bbar_" + family + "_border", group["field_ids"])

    def test_fixed_bar_reserves_space_below_and_uses_collection_font(self):
        for size in (14, 28, 40):
            env = reviewer_env({"onigiri_font_size_reviewer_controls": size})
            conf = {"onigiri_reviewer_stattxt_mode": "fixed",
                    "onigiri_reviewer_bar_height": 20, "onigiri_reviewer_btn_border_size": 3}
            padding, counts, height = env["_reviewer_fixed_button_metrics"](conf)
            self.assertGreaterEqual(height, max(size * 1.25, counts) + 2 * (padding + 3))
            self.assertEqual(env["_reviewer_bottom_bar_height_px"](conf), height + 24)

    def test_border_width_and_independent_colours_reach_live_css(self):
        conf = {"onigiri_reviewer_btn_border_size": 3,
                "onigiri_reviewer_good_border_light": "#123456",
                "onigiri_reviewer_show_answer_border_dark": "#abcdef"}
        css = reviewer_env()["generate_reviewer_buttons_css"](conf)
        self.assertIn("border: 3px solid var(--onigiri-bbar-border", css)
        self.assertIn('#outer button[data-onigiri-ease="3"] { --onigiri-bbar-border: #123456; }', css)
        self.assertIn(".nightMode #outer button.onigiri-show-answer-btn { --onigiri-bbar-border: #abcdef; }", css)
        self.assertIn((ROOT / "web/reviewer_buttons_shared.css").read_text(), css)
        self.assertNotIn("tiny dot", css)

    def test_native_buttons_and_hidden_bar_keep_their_existing_paths(self):
        env = reviewer_env()
        self.assertEqual(env["generate_reviewer_buttons_css"]({"maxHide": True}),
                         "<style>#outer { display: none !important; }</style>")
        conf = {"onigiri_reviewer_btn_custom_enabled": False,
                "onigiri_reviewer_stattxt_mode": "fixed", "onigiri_reviewer_bar_height": 60}
        self.assertEqual(env["_reviewer_bottom_bar_height_px"](conf), 60)
        self.assertNotIn("--onigiri-bbar-fixed-height", env["generate_reviewer_buttons_css"](conf))


if __name__ == "__main__":
    unittest.main()
