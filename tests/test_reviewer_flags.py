"""Flag icon persistence, asset fallback, and Anki's live flag transitions."""

import ast
import copy
import importlib.util
import os
import subprocess
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reviewer_flags", ROOT / "rendering/reviewer_flags.py")
flags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flags)


def load_nodes(filename, names, env):
    tree = ast.parse((ROOT / filename).read_text())
    body = [node for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), filename, "exec"), env)


class ReviewerFlagTests(unittest.TestCase):
    def test_independent_choices_persist_and_reset_without_resetting_other_flags(self):
        writes = []
        env = {"tr": lambda key, fallback: fallback, "copy": copy, "os": os,
               "config": types.SimpleNamespace(get_config=lambda: {}, write_config=lambda conf: writes.append(copy.deepcopy(conf)))}
        load_nodes("settings_web/schema.py", {"_reviewer_flags_section"}, env)
        load_nodes("settings_web/store.py", {"Store", "MissingBinding"}, env)
        fields = env["_reviewer_flags_section"]()["fields"]
        store = env["Store"]()
        self.assertEqual(len(fields), 7)
        for field in fields:
            store.register(field["id"], field["bind"], field["default"])
        self.assertEqual(store.apply_now({field["id"]: "system:star.svg" for field in fields})[1], [])
        reloaded = env["Store"]()
        reloaded.config = writes[-1]
        for field in fields:
            reloaded.register(field["id"], field["bind"], field["default"])
            self.assertEqual(reloaded.read(field["id"]), "system:star.svg")
        reloaded.apply_now({fields[0]["id"]: ""})
        saved = writes[-1]["onigiri_reviewer_flag_icons"]
        self.assertEqual(saved["1"], "")
        self.assertEqual(saved["7"], "system:star.svg")

    def test_bundled_svg_and_uploaded_png_resolve_and_deleted_assets_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system = root / "system_files/system_icons/available_for_users/star.svg"
            custom = root / "user_files/icons/my icon.png"
            for path in (system, custom):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"icon")
            conf = {"onigiri_reviewer_flag_icons": {"1": "system:star.svg", "7": "my icon.png", "3": "missing.svg"}}
            urls = flags.icon_urls(conf, root, "1011095603")
            self.assertEqual(set(urls), {str(number) for number in range(1, 8)})
            self.assertIn("/available_for_users/star.svg?v=", urls["1"])
            self.assertIn("/user_files/icons/my%20icon.png?v=", urls["7"])
            self.assertTrue(urls["3"].endswith("/available_for_users/flag.svg"))
            custom.unlink()
            self.assertTrue(flags.icon_urls(conf, root, "1011095603")["7"].endswith("/available_for_users/flag.svg"))

    def test_empty_and_invalid_values_use_onigiri_for_all_seven_flags(self):
        default = flags.icon_urls({}, ROOT, "test")
        self.assertEqual(len(default), 7)
        self.assertTrue(all("/available_for_users/flag.svg?v=" in url for url in default.values()))
        for value in (None, [], "invalid", {"1": "../star.svg", "2": 3, "3": "system:../../star.svg", "4": "file.html", "8": "system:star.svg"}):
            self.assertEqual(flags.icon_urls({"onigiri_reviewer_flag_icons": value}, ROOT, "test"), default)

    def test_serialized_choices_keep_preview_and_default_metadata(self):
        env = {"tr": lambda key, fallback: fallback}
        load_nodes("settings_web/schema.py", {"_reviewer_flags_section"}, env)
        fields = env["_reviewer_flags_section"]()["fields"]
        env.update(store=types.SimpleNamespace(read=lambda _: ""))
        load_nodes("settings_web/render.py", {"_serialize_field", "_camel"}, env)
        for field in fields:
            serialized = env["_serialize_field"](env["store"], field)
            self.assertEqual(serialized["defaultIcon"], "system:flag.svg")
            self.assertEqual(serialized["iconTint"], field["icon_tint"])
            self.assertFalse(serialized["advanced"])

    def test_runtime_tracks_all_flag_colours_hidden_state_and_live_reset(self):
        script = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const props = {};
let callback;
let pending = false;
const flag = {
  hidden: true, textContent: '⚑',
  style: {color: '', getPropertyValue: key => props[key] || '',
    setProperty: (key, value) => {props[key] = value; pending = true;},
    removeProperty: key => {delete props[key]; pending = true;}}
};
function settle() {
  let count = 0;
  do {pending = false; callback(); assert.ok(++count < 5, 'observer must settle');} while(pending);
}
const icons = Object.fromEntries(Array.from({length: 7}, (_, i) => [String(i+1), '/icon-'+(i+1)+'.svg']));
const context = {window: {onigiriReviewerFlagIcons: icons},
  document: {readyState: 'complete', getElementById: id => id === '_flag' ? flag : null},
  MutationObserver: class {constructor(fn) {callback = fn;} disconnect() {} observe() {}}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
for (let i = 1; i <= 7; i++) {
  flag.hidden = false; flag.style.color = 'var(--flag-'+i+')'; settle();
  assert.equal(props['--onigiri-flag-icon'], 'url("/icon-'+i+'.svg")');
  assert.equal(flag.textContent, '⚑');
  assert.equal(flag.style.color, 'var(--flag-'+i+')');
}
flag.hidden = true; flag.style.color = 'var(--flag-0)'; settle();
assert.ok(flag.hidden);
flag.hidden = false; flag.style.color = 'var(--flag-2)'; settle();
context.window.OnigiriReviewerFlags.setIcons({}); settle();
assert.equal(props['--onigiri-flag-icon'], undefined);
assert.equal(flag.textContent, '⚑');
assert.equal(flag.style.color, 'var(--flag-2)');
'''
        result = subprocess.run(["node", "-e", script, str(ROOT / "web/reviewer_flags.js")],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
