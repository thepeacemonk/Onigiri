"""Study Tool visibility, persistence, and entry points without opening Anki."""
import ast
import copy
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_study_visibility_tests"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(selected) == len(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), path, "exec"), namespace)
    return namespace


class StudyToolVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.conf = {
            "hashi_notes": {"show_in_reviewer_header": False, "font_size": 19},
            "prep_station": {"plans": [{"id": "exam", "target": 120}]},
            "onigiri_pomodoro_show_in_reviewer_header": True,
            "onigiriWidgetLayout": {"grid": {"hashi_notes": {"pos": 6}}, "archive": ["prep_station"]},
        }
        self.collection = {"onigiri_hashi_notes": [{"id": "note", "body_md": "Keep this"}],
                           "onigiri_pomodoro_sessions": [{"actual_minutes": 25}]}
        self.config = types.ModuleType(PACKAGE + ".core.config")
        self.config.get_config = lambda: copy.deepcopy(self.conf)
        self.config.get_config_readonly = lambda: self.conf
        self.config.write_config = lambda conf: self.conf.update(copy.deepcopy(conf))
        modules = {"aqt": types.SimpleNamespace(mw=types.SimpleNamespace(col=types.SimpleNamespace(conf=self.collection))),
                   self.config.__name__: self.config}
        for suffix in ("", ".core", ".settings_web", ".study_tools", ".rendering"):
            name = PACKAGE + suffix
            modules[name] = types.ModuleType(name)
            modules[name].__path__ = []
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.visibility = load_module(PACKAGE + ".core.study_tool_visibility", "core/study_tool_visibility.py")

    def test_existing_profiles_keep_tools_visible(self):
        for conf in ({}, {"study_tools_visibility": None}, {"study_tools_visibility": []}):
            for tool in self.visibility.TOOL_IDS:
                self.assertTrue(self.visibility.tool_visible(tool, conf))

    def test_header_preferences_survive_hiding_and_showing(self):
        before = copy.deepcopy(self.conf)
        self.assertFalse(self.visibility.reviewer_button_visible("hashi_notes", self.conf))
        self.assertTrue(self.visibility.reviewer_button_visible("pomodoro", self.conf))
        self.conf["study_tools_visibility"] = {"pomodoro": False}
        self.assertFalse(self.visibility.reviewer_button_visible("pomodoro", self.conf))
        self.conf["study_tools_visibility"]["pomodoro"] = True
        self.assertTrue(self.visibility.reviewer_button_visible("pomodoro", self.conf))
        self.assertFalse(self.visibility.reviewer_button_visible("prep_station", self.conf))
        del self.conf["study_tools_visibility"]
        self.assertEqual(self.conf, before)

    def test_settings_round_trip_preserves_data_layout_and_header_preferences(self):
        before, collection_before = copy.deepcopy(self.conf), copy.deepcopy(self.collection)
        store_module = load_module(PACKAGE + ".settings_web.store", "settings_web/store.py")
        store = store_module.Store()
        for tool in self.visibility.TOOL_IDS:
            store.register(tool, {"kind": "config", "path": ["study_tools_visibility", tool]}, True)
        self.assertEqual([store.read(tool) for tool in self.visibility.TOOL_IDS], [True] * 3)
        _, failures = store.apply_now(dict.fromkeys(self.visibility.TOOL_IDS, False))
        self.assertEqual(failures, [])
        self.assertTrue(all(not self.visibility.tool_visible(tool, self.conf) for tool in self.visibility.TOOL_IDS))
        reopened = store_module.Store()
        for tool in self.visibility.TOOL_IDS:
            reopened.register(tool, {"kind": "config", "path": ["study_tools_visibility", tool]}, True)
        self.assertEqual([reopened.read(tool) for tool in self.visibility.TOOL_IDS], [False] * 3)
        reopened.apply_now(dict.fromkeys(self.visibility.TOOL_IDS, True))
        self.assertEqual({key: self.conf[key] for key in before}, before)
        self.assertEqual(self.collection, collection_before)

    def test_controls_are_visible_and_keep_legacy_header_bindings(self):
        namespace = load_functions("settings_web/schema.py", ["_tool_visibility_section"],
                                   {"tr": lambda key, fallback="": fallback or key})
        for tool, title, header in (("prep_station", "Prep Station", None),
                                    ("hashi_notes", "Hashi Notes", "hashi_show_header"),
                                    ("pomodoro", "Pomodoro", "pomodoro_show_header")):
            section = namespace["_tool_visibility_section"](tool, title, header)
            master = section["fields"][0]
            self.assertEqual(master["label"], "Show " + title)
            self.assertNotIn("show_when", master)
            self.assertFalse(master.get("advanced", False))
            if header:
                button = section["fields"][1]
                self.assertEqual(button["show_when"], {"field": tool + "_visible", "values": [True]})
                binding = button["bind"]
                self.assertEqual(binding.get("path", binding.get("key")),
                                 ["hashi_notes", "show_in_reviewer_header"] if tool == "hashi_notes"
                                 else "onigiri_pomodoro_show_in_reviewer_header")

    def test_each_tool_page_leads_with_reachable_visibility_controls(self):
        tree = ast.parse((ROOT / "settings_web/schema.py").read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        namespace = {
            "__package__": PACKAGE + ".settings_web",
            "tr": lambda key, fallback="": fallback or key,
            "config": types.SimpleNamespace(DEFAULT_ACCENT_COLOR="#00a982"),
            "TONE_PAIRS": [],
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), "schema.py", "exec"), namespace)
        # Appearance helpers are independent of the visibility controls under test.
        namespace["_designer_preview_section"] = lambda section_id, *args, **kwargs: {
            "id": section_id, "fields": kwargs.get("fields", []),
        }
        namespace["_color_pair_field"] = lambda field_id, *args, **kwargs: {"id": field_id}
        for function, tool in (("_prep_station_page", "prep_station"),
                               ("_hashi_notes_page", "hashi_notes"), ("_pomodoro_page", "pomodoro")):
            page = namespace[function]()
            self.assertNotIn("show_when", page)
            self.assertEqual(page["sections"][0]["fields"][0]["id"], tool + "_visible")
            self.assertIn("study_tool_visibility", page["post_save"])
            ids = [field["id"] for section in page["sections"] for field in section.get("fields", [])]
            self.assertEqual(len(ids), len(set(ids)))

    def test_hidden_entry_points_do_not_create_windows_or_notes(self):
        self.conf["study_tools_visibility"] = dict.fromkeys(self.visibility.TOOL_IDS, False)
        before = copy.deepcopy(self.conf)
        for filename, names in (("prep_station", ["open_prep_station"]),
                                ("hashi_notes", ["open_hashi_note_popup", "open_hashi_gallery"]),
                                ("pomodoro", ["toggle_widget", "open_stats_dialog"])):
            namespace = load_functions("study_tools/" + filename + ".py", names,
                                       {"__package__": PACKAGE + ".study_tools"})
            for name in names:
                self.assertIsNone(namespace[name]())
        self.assertEqual(self.conf, before)

    def test_hiding_pauses_timer_and_closes_only_hidden_loaded_tools(self):
        events = []
        self.conf["study_tools_visibility"] = {"prep_station": False, "pomodoro": False}
        for tool in self.visibility.TOOL_IDS:
            module = types.ModuleType(PACKAGE + ".study_tools." + tool)
            for attribute in ("_dialog", "_popup", "_gallery", "_widget", "_stats_dialog"):
                setattr(module, attribute, types.SimpleNamespace(close=lambda t=tool, a=attribute: events.append((t, a))))
            module._timer = types.SimpleNamespace(pause=lambda: events.append(("pomodoro", "pause")))
            sys.modules[module.__name__] = module
        self.visibility.hide_open_tools(self.conf)
        self.assertEqual(events, [("prep_station", "_dialog"), ("pomodoro", "pause"),
                                  ("pomodoro", "_widget"), ("pomodoro", "_stats_dialog")])

    def test_dashboard_hides_tools_without_changing_saved_widget_placement(self):
        tree = ast.parse((ROOT / "rendering/onigiri_renderer.py").read_text())
        loop = next(node for node in ast.walk(tree) if isinstance(node, ast.For)
                    and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute)
                    and isinstance(node.iter.func.value, ast.Name) and node.iter.func.value.id == "onigiri_layout")
        layout = {"hashi_notes": {"pos": 6, "row": 2, "col": 2},
                  "prep_station": {"pos": 8, "row": 1, "col": 2}}
        before = copy.deepcopy(layout)
        calls = []
        render = lambda tool: types.SimpleNamespace(render_widget_html=lambda **kwargs: calls.append(tool) or tool)
        namespace = {
            "TOOL_IDS": self.visibility.TOOL_IDS, "tool_visible": self.visibility.tool_visible,
            "conf": {"study_tools_visibility": {"hashi_notes": False, "prep_station": False}},
            "onigiri_layout": layout, "col_count": 4, "onigiri_grid_html": "",
            "widget_generators": dict.fromkeys(layout), "_is_deck_stats_widget_id": lambda tool: False,
            "render_widget_safely": lambda tool, renderer: renderer(),
            "_hashi_notes": lambda: render("hashi_notes"), "_prep_station": lambda: render("prep_station"),
        }
        code = compile(ast.Module(body=[loop], type_ignores=[]), "onigiri_renderer.py", "exec")
        exec(code, namespace)
        self.assertEqual(calls, [])
        self.assertEqual(namespace["onigiri_grid_html"], "")
        namespace["conf"]["study_tools_visibility"]["hashi_notes"] = True
        exec(code, namespace)
        self.assertEqual(calls, ["hashi_notes"])
        self.assertIn("hashi_notes", namespace["onigiri_grid_html"])
        self.assertNotIn("prep_station", namespace["onigiri_grid_html"])
        self.assertEqual(layout, before)

    def test_native_menu_and_shortcut_follow_each_tool(self):
        class Action:
            def setVisible(self, visible):
                self.visible = visible

            def setEnabled(self, enabled):
                self.enabled = enabled

        actions = [(tool, Action()) for tool in self.visibility.TOOL_IDS]
        submenu, shortcut = Action(), Action()
        namespace = load_functions("ui_kit/menu_buttons.py", ["refresh_study_tool_visibility"], {
            "__package__": PACKAGE + ".ui_kit", "tool_visible": self.visibility.tool_visible,
            "_study_tool_actions": actions, "_study_tools_menu": types.SimpleNamespace(menuAction=lambda: submenu),
            "_pomodoro_shortcut": shortcut,
        })
        self.conf["study_tools_visibility"] = dict.fromkeys(self.visibility.TOOL_IDS, False)
        namespace["refresh_study_tool_visibility"]()
        self.assertFalse(submenu.visible)
        self.assertFalse(shortcut.enabled)
        self.assertFalse(any(action.visible for _, action in actions))
        self.conf["study_tools_visibility"]["hashi_notes"] = True
        namespace["refresh_study_tool_visibility"]()
        self.assertTrue(submenu.visible)
        self.assertEqual([action.visible for _, action in actions], [False, True, False])

    def test_reviewer_generation_respects_both_visibility_layers(self):
        namespace = load_functions("rendering/patcher.py", ["_study_tool_header_buttons"], {
            "__package__": PACKAGE + ".rendering", "tr_at": lambda key: key,
        })
        generate = namespace["_study_tool_header_buttons"]
        self.assertEqual(generate(self.conf)[0], "")
        self.assertIn("togglePomodoro", generate(self.conf)[1])
        self.conf["study_tools_visibility"] = {"hashi_notes": False, "pomodoro": False}
        self.assertEqual(generate(self.conf), ("", ""))
        self.conf["hashi_notes"]["show_in_reviewer_header"] = True
        self.conf["study_tools_visibility"]["hashi_notes"] = True
        self.assertIn("openHashiNotes:reviewer", generate(self.conf)[0])


if __name__ == "__main__":
    unittest.main()
