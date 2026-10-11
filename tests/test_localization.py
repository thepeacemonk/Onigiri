"""Language switching and notification payloads without opening Anki."""
import ast
import importlib.util
import json
import re
import string
import subprocess
import shutil
import sys
import types
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.settings = {}
        self.profile = {"onigiri_language": "en"}
        self.scripts = []
        self.mw = types.SimpleNamespace(
            pm=types.SimpleNamespace(profile=self.profile), state="review",
            reviewer=types.SimpleNamespace(web=types.SimpleNamespace(eval=self.scripts.append)),
        )
        package = types.ModuleType("_onigiri_locale_tests")
        package.__path__ = [str(ROOT / "core")]
        config = types.ModuleType(package.__name__ + ".config")
        config.get_config_readonly = lambda: self.settings
        aqt = types.ModuleType("aqt")
        aqt.mw = self.mw
        spec = importlib.util.spec_from_file_location(
            package.__name__ + ".translations", ROOT / "core/translations.py"
        )
        self.translations = importlib.util.module_from_spec(spec)
        self.modules = patch.dict(sys.modules, {
            "aqt": aqt, package.__name__: package, config.__name__: config,
            spec.name: self.translations,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec.loader.exec_module(self.translations)

    def test_all_eight_catalogues_cover_every_english_key(self):
        catalogues = self.translations.TRANSLATIONS
        self.assertEqual(len(self.translations.LANGUAGES), 8)
        for language in self.translations.LANGUAGES.values():
            with self.subTest(language=language):
                self.assertFalse(set(catalogues["en"]) - set(catalogues[language]))
                self.assertTrue(all(isinstance(text, str) for text in catalogues[language].values()))

    def test_referenced_python_keys_exist(self):
        catalogue = self.translations.TRANSLATIONS["en"]
        missing = []
        for path in ROOT.rglob("*.py"):
            if any(part in path.parts for part in ("tests", "user_files", "__pycache__")):
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "tr" and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    key = node.args[0].value
                    if key not in catalogue:
                        missing.append((str(path.relative_to(ROOT)), node.lineno, key))
        self.assertEqual(missing, [])

    def test_translated_format_fields_are_valid(self):
        formatter = string.Formatter()
        catalogues = self.translations.TRANSLATIONS
        for key, source in catalogues["en"].items():
            required = {field for _, field, _, _ in formatter.parse(source) if field is not None}
            for language in self.translations.LANGUAGES.values():
                with self.subTest(language=language, key=key):
                    used = {field for _, field, _, _ in formatter.parse(catalogues[language][key]) if field is not None}
                    # A language can omit a name, but cannot request a value
                    # that the event producer never provides.
                    self.assertFalse(used - required)

    def test_literal_aliases_and_bundled_defaults_have_catalogue_entries(self):
        source = self.translations.TRANSLATIONS["en"]
        self.assertFalse(set(self.translations._LITERAL_ALIASES.values()) - set(source))
        tree = ast.parse((ROOT / "core/config.py").read_text())
        default_messages = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "messages" and isinstance(value, ast.List):
                    default_messages.extend(ast.literal_eval(value))
        known = [source[f"mochi_default_{n}"] for n in range(1, 8)] + [source["fd_default_message"]]
        self.assertTrue(default_messages)
        self.assertFalse(set(default_messages) - set(known))
        for label in self.translations._HEXAGON_PART_LABELS:
            key = "hexland_" + label.lower().replace(" ", "_").replace("-", "_")
            for language, entries in self.translations.TRANSLATIONS.items():
                self.assertTrue(entries[key])
                if language != "en":
                    self.assertNotEqual(entries[key], label)
        emoji_tree = ast.parse((ROOT / "ui_kit/emoji_sprites.py").read_text())
        emojis = next(ast.literal_eval(node.value) for node in emoji_tree.body
                      if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                      and target.id == "EMOJI_SPRITES" for target in node.targets))
        literals = self.translations.literal_strings()
        self.assertFalse({item["label"] for item in emojis} - set(literals) - {"Onigiri", "Dango"})

    def test_saved_language_wins_over_stale_profile_mirror(self):
        for name, code in self.translations.LANGUAGES.items():
            self.settings["language"] = name
            self.profile["onigiri_language"] = "en" if code != "en" else "ja-JP"
            self.assertEqual(self.translations.current_language(), code)
            self.assertEqual(self.translations.tr("settings_title"), self.translations.TRANSLATIONS[code]["settings_title"])
        self.settings["language"] = "unknown"
        self.profile["onigiri_language"] = "ja-JP"
        self.assertEqual(self.translations.current_language(), "ja-JP")

    def test_recovery_notices_translate_only_when_displayed(self):
        spec = importlib.util.spec_from_file_location(
            self.translations.__package__ + ".safe_storage", ROOT / "core/safe_storage.py")
        storage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(storage)
        self.settings["language"] = "English (Default)"
        original = "Your Onigiri progress was restored from backup file."
        storage._note(original, key="storage_restored", label="Your Onigiri progress", source="backup file")
        self.settings["language"] = "Português (Brasil)"
        expected = self.translations.TRANSLATIONS["pt-BR"]
        self.assertEqual(storage.take_notices(), [expected["storage_restored"].format(
            label=expected["storage_progress_label"], source=expected["storage_backup_file"])])
        self.assertEqual(storage.take_notices(), [])

    def test_explicit_empty_fallback_is_respected(self):
        self.assertEqual(self.translations.tr("unknown-key", ""), "")

    def test_mochi_dispatch_changes_language_without_recreating_messenger(self):
        tree = ast.parse((ROOT / "gamification/mochi_messages.py").read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MochiMessenger")
        keys = tuple(f"mochi_default_{index}" for index in range(1, 8))
        self.settings["mochi_messages"] = {
            "messages": [self.translations.TRANSLATIONS["en"][key] for key in keys]
        }
        env = {
            "List": List, "Dict": Dict, "Any": Any, "Optional": Optional,
            "config": types.SimpleNamespace(get_config_readonly=lambda: self.settings),
            "DEFAULT_MESSAGE_KEYS": keys, "mw": self.mw, "json": json,
            "localized_default": self.translations.localized_default,
            "tr": self.translations.tr, "trigger_haptic": lambda *args: None,
        }
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "mochi_messages.py", "exec"), env)
        messenger = env["MochiMessenger"]()
        for name, code in self.translations.LANGUAGES.items():
            with self.subTest(language=code):
                self.settings["language"] = name
                expected = self.translations.TRANSLATIONS[code]
                messages = messenger._messages()
                self.assertEqual(messages, [expected[key] for key in keys])
                messenger._dispatch_notification(self.translations.TRANSLATIONS["en"][keys[0]])
                payload = json.loads(re.search(r"Notifications.show\((.*?)\);", self.scripts[-1]).group(1))
                self.assertEqual(payload["description"], expected[keys[0]])
                self.assertEqual(payload["name"], expected["mochi_title_placeholder"])
        self.settings["mochi_messages"].update(messages=["My handwritten message"], title_name="My mascot")
        self.assertEqual(messenger._messages(), ["My handwritten message"])
        messenger._dispatch_notification("My handwritten message")
        self.assertIn('"name": "My mascot"', self.scripts[-1])
        # Localization never rewrites the persisted default message list.
        self.assertEqual(self.settings["mochi_messages"]["messages"], ["My handwritten message"])

    def test_defaults_saved_in_other_languages_translate_back(self):
        for code in self.translations.LANGUAGES.values():
            source = self.translations.TRANSLATIONS[code]["mochi_default_1"]
            self.settings["language"] = "Português (Brasil)"
            self.assertEqual(self.translations.localized_default(source, ("mochi_default_1",)),
                             self.translations.TRANSLATIONS["pt-BR"]["mochi_default_1"])
        self.assertEqual(self.translations.localized_default("My deck called Today", ("ready_to_go",)), "My deck called Today")

    def test_nook_notifications_follow_each_language(self):
        tree = ast.parse((ROOT / "gamification/nook_level.py").read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "NookLevelManager")
        cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                    and node.name.startswith("_create_") and "notification" in node.name]
        env = {"Dict": Dict, "List": List, "Any": Any, "tr": self.translations.tr}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "nook_level.py", "exec"), env)
        nook = env["NookLevelManager"]()
        nook._addon_prefix = "/_addons/1011095603"
        nook.get_current_theme_image = lambda: "test.webp"
        for name, code in self.translations.LANGUAGES.items():
            self.settings["language"] = name
            expected = self.translations.TRANSLATIONS[code]
            checks = [
                (nook._create_level_up_notification(3), "level_unlocked_msg", "level_unlocked_desc", {"level": 3}),
                (nook._create_half_level_notification(3, 5, 10), "level_progress_msg", "level_progress_desc", {"level": 3, "percent": 50, "next_level": 4}),
                (nook._create_daily_special_complete_notification(), "daily_special_complete_msg", "daily_special_complete_desc", {}),
                (nook._create_daily_special_75_notification(100, 75), "daily_special_progress_msg", "daily_special_75_desc", {"remaining": 25}),
                (nook._create_daily_special_50_notification(100, 50), "daily_special_progress_msg", "daily_special_50_desc", {"remaining": 50}),
            ]
            for payloads, title_key, body_key, args in checks:
                self.assertEqual(payloads[0]["name"], expected[title_key].format(**args))
                self.assertEqual(payloads[0]["description"], expected[body_key].format(**args))

    def test_onigimon_reward_item_names_and_effects_have_translations(self):
        tree = ast.parse((ROOT / "gamification/onigimon.py").read_text())
        catalogue = self.translations.TRANSLATIONS["en"]
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else ""
            if name not in {"ITEMS", "BERRY_ITEMS", "ONIGIMON_EXTRA_ITEMS"}:
                continue
            for item_key, item in ast.literal_eval(node.value).items():
                self.assertIn("onigimon_item_" + item_key, catalogue)
                if item.get("effect"):
                    key = re.sub(r"[^a-z0-9]+", "_", item["effect"].lower()).strip("_")
                    self.assertIn("onigimon_effect_" + key, catalogue)

    def test_hexagon_notification_uses_language_at_timer_fire(self):
        tree = ast.parse((ROOT / "gamification/hexagon_land.py").read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HexagonLandManager")
        wanted = {"_notify_session_rewards", "_material_label", "_material_rewards_text"}
        cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        callbacks = []
        env = {"Dict": Dict, "HexagonLandState": Any, "tr": self.translations.tr,
               "json": json, "mw": self.mw, "_addon_package": lambda: "1011095603",
               "QTimer": types.SimpleNamespace(singleShot=lambda delay, callback: callbacks.append(callback))}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "hexagon_land.py", "exec"), env)
        island = env["HexagonLandManager"]()
        for name, code in self.translations.LANGUAGES.items():
            island._last_session_notification_signature = None
            state = types.SimpleNamespace(last_study_day="2026-10-11", today_reviews=10)
            self.settings["language"] = "English (Default)"
            island._notify_session_rewards(state, 3, {"wood": 2, "stone": 1})
            self.settings["language"] = name
            callbacks.pop()()
            payload = json.loads(re.search(r"Notifications.show\((.*?)\);", self.scripts[-1]).group(1))
            expected = self.translations.TRANSLATIONS[code]
            self.assertEqual(payload["description"], expected["hexland_earned_session_ui"])
            self.assertEqual(payload["rewardItems"][0]["iconAlt"], expected["hexland_hex_coins"])
            self.assertEqual(payload["rewardItems"][1]["value"], "2 " + expected["hexland_wood"])
            self.assertEqual(payload["rewardItems"][2]["value"], "1 " + expected["hexland_material_stone"])

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the frontend runtime")
    def test_frontend_templates_translate_and_keep_user_content_untouched(self):
        data = {}
        for name, code in self.translations.LANGUAGES.items():
            self.settings["language"] = name
            data[code] = self.translations.literal_strings()
        script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const maps = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
for (const [locale, literals] of Object.entries(maps)) {
  context.window.ONIGIRI_LOCALIZATION = {locale, literals};
  assert.equal(context.window.onigiriText('  Settings '), '  ' + literals.Settings + ' ');
  const template = context.window.onigiriTemplate('<button title="Open Anki\'s full editor">Settings</button>');
  const escape = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[c]);
  assert(template.includes('>' + escape(literals.Settings) + '</button>'));
  assert(template.includes('title="' + escape(literals["Open Anki\'s full editor"]) + '"'));
  // User content is interpolated after source translation, never scanned.
  const userContent = 'Settings';
  assert.equal(context.window.onigiriTemplate('<div>') + userContent + '</div>', '<div>Settings</div>');
}
context.window.ONIGIRI_LOCALIZATION = {literals: {'Settings': 'A < B & C "D"'}};
assert.equal(context.window.onigiriTemplate('<b>Settings</b>'), '<b>A &lt; B &amp; C &quot;D&quot;</b>');
"""
        result = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "web/localization.js")],
                                input=json.dumps(data), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the frontend runtime")
    def test_open_settings_switch_copy_and_preserve_pending_edits(self):
        script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('  function applyLocalization(context)');
const end = source.indexOf('  function setStatus(', start);
const oldPages = [{id: 'games'}], oldStrings = {title: 'old'};
const env = {CTX: {}, STRINGS: oldStrings, PAGES: oldPages, pageById: {old: {}}, fieldById: {old: {}},
  pending: {custom: 'unsaved'}, values: {custom: 'unsaved', mochi: ['English default']},
  document: {documentElement: {}}, window: {}, currentPage: 'games',
  rebuildSearchIndex(){}, paintChromeLanguage(){}, buildNav(){}, showPage(id){assert.equal(id, 'games');}};
vm.runInNewContext(source.slice(start, end), env);
const context = {heatmapLocale: 'ja-JP', strings: {title: 'translated'},
  localization: {locale: 'ja-JP', literals: {Settings: 'translated'}},
  pages: [{id:'games', sections:[{fields:[{id:'mochi', type:'message_list', value:['translated default']},
    {id:'custom', type:'message_list', value:['persisted custom']}]}]}]};
env.applyLocalization(context);
assert.equal(oldStrings.title, 'translated');
assert.equal(oldPages[0].id, 'games');
assert.equal(env.document.documentElement.lang, 'ja-JP');
assert.equal(env.window.ONIGIRI_LOCALIZATION.locale, 'ja-JP');
assert.equal(env.values.mochi[0], 'translated default');
assert.equal(env.values.custom, 'unsaved');
assert(!env.fieldById.old && !env.pageById.old);
"""
        result = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "web/settings.js")],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_settings_javascript_keys_are_supplied(self):
        catalogue = self.translations.TRANSLATIONS["en"]
        source = (ROOT / "web/settings.js").read_text()
        refs = set(re.findall(r'\bstr\(\s*[\'"]([\w]+)[\'"]', source))
        # These UI aliases are explicitly set in settings_web/render.py.
        aliases = {"advanced", "simple", "collapse_sidebar", "expand_sidebar", "lstats_title", "gallery_import", "gallery_none", "onigimon_streak", "rows"}
        self.assertFalse(refs - set(catalogue) - aliases - {"lstats_view_", "ready_"})


if __name__ == "__main__":
    unittest.main()
