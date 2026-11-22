"""Tests for the Motion-inspired Reviewer 'More' menu override."""

import importlib
import json
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    pkg = types.ModuleType("onigiri_test_pkg")
    pkg.__path__ = [str(ROOT)]
    core_pkg = types.ModuleType("onigiri_test_pkg.core")
    core_pkg.__path__ = [str(ROOT / "core")]
    rendering_pkg = types.ModuleType("onigiri_test_pkg.rendering")
    rendering_pkg.__path__ = [str(ROOT / "rendering")]
    fake_config = types.SimpleNamespace(
        effective_night_mode=lambda *_: True,
        get_collection_config=lambda *_: "system",
    )
    core_pkg.config = fake_config
    with patch.dict(
        sys.modules,
        {
            "onigiri_test_pkg": pkg,
            "onigiri_test_pkg.core": core_pkg,
            "onigiri_test_pkg.core.config": fake_config,
            "onigiri_test_pkg.rendering": rendering_pkg,
        },
    ):
        return importlib.import_module("onigiri_test_pkg.rendering.reviewer_more_menu")


class _FakeAction:
    def __init__(self, text="", shortcut="", checkable=False, checked=False, enabled=True, separator=False, menu=None):
        self._text = text
        self._shortcut = shortcut
        self._checkable = checkable
        self._checked = checked
        self._enabled = enabled
        self._separator = separator
        self._menu = menu
        self.triggered_count = 0

    def text(self):
        return self._text

    def isSeparator(self):
        return self._separator

    def menu(self):
        return self._menu

    def isCheckable(self):
        return self._checkable

    def isChecked(self):
        return self._checked

    def isEnabled(self):
        return self._enabled

    def shortcut(self):
        if not self._shortcut:
            return None
        return types.SimpleNamespace(
            isEmpty=lambda: False,
            toString=lambda *_: self._shortcut,
        )

    def trigger(self):
        self.triggered_count += 1


class _FakeQMenu:
    def __init__(self, actions):
        self._actions = list(actions)

    def actions(self):
        return list(self._actions)


class ReviewerMoreMenuTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_mnemonic_and_shortcut_formatting(self):
        self.assertEqual(self.mod._strip_mnemonic("&Flag Card"), "Flag Card")
        self.assertEqual(self.mod._strip_mnemonic("Save && &Exit"), "Save & Exit")
        self.assertEqual(self.mod._strip_trailing_ellipsis("Set Due Date..."), "Set Due Date")
        self.assertEqual(self.mod._strip_trailing_ellipsis("Reset Card…"), "Reset Card")
        self.assertEqual(self.mod._strip_trailing_ellipsis("Delete Note"), "Delete Note")
        self.assertEqual(self.mod._format_shortcut("Ctrl+Alt+N", is_mac=True), "⌥⌘N")
        self.assertEqual(self.mod._format_shortcut("Ctrl+Shift+D", is_mac=True), "⇧⌘D")
        self.assertEqual(self.mod._format_shortcut("Ctrl+Backspace", is_mac=True), "⌘⌫")
        self.assertEqual(self.mod._format_shortcut("Shift+A", is_mac=True), "⇧A")
        self.assertEqual(self.mod._format_shortcut("Ctrl+Alt+N", is_mac=False), "Ctrl+Alt+N")

    def test_build_menu_payload_reads_card_and_flags(self):
        note = types.SimpleNamespace(has_tag=lambda tag: tag == "marked")
        card = types.SimpleNamespace(user_flag=lambda: 4, note=lambda: note)
        reviewer = types.SimpleNamespace(
            card=card,
            auto_advance_enabled=True,
            previous_card=object(),
        )
        fake_flags = [
            types.SimpleNamespace(index=i, label=f"Flag {i}") for i in range(1, 8)
        ]
        mw_ref = types.SimpleNamespace(
            flags=types.SimpleNamespace(all=lambda: fake_flags),
            addonManager=types.SimpleNamespace(addonFromModule=lambda *_: "1011095603"),
        )

        with patch.object(
            self.mod.config,
            "get_config_readonly",
            lambda: {"onigiri_reviewer_flag_icons": {"1": "system:heart.svg"}},
            create=True,
        ):
            payload = self.mod.build_menu_payload(reviewer, mw_ref=mw_ref)
        self.assertEqual(payload["flag"], 4)
        self.assertTrue(payload["marked"])
        self.assertTrue(payload["autoAdvance"])
        self.assertTrue(payload["hasPreviousCard"])
        self.assertEqual(len(payload["flags"]), 7)
        self.assertEqual(payload["flags"][3]["label"], "Flag 4")
        self.assertIn("heart.svg", payload["flags"][0]["iconUrl"])
        self.assertIn("flag.svg", payload["flags"][1]["iconUrl"])
        self.assertIn("buryCard", payload["shortcuts"])
        self.assertIn("deleteNote", payload["shortcuts"])
        self.assertEqual(payload["labels"]["setDueDate"], "Set Due Date")
        self.assertEqual(payload["labels"]["resetCard"], "Reset Card")
        self.assertEqual(payload["labels"]["createCopy"], "Create Copy")
        self.assertEqual(payload["labels"]["recordShort"], "Record")
        self.assertEqual(payload["labels"]["playVoiceShort"], "Replay")

    def test_bottom_bar_assets_includes_lucide_chevron(self):
        assets = self.mod.bottom_bar_assets()
        self.assertIn("lucide-chevron-down", assets)
        self.assertIn("m6 9 6 6 6-6", assets)
        self.assertIn("onigiri-more-chevron", assets)

    def test_extract_custom_items_ignores_builtins_and_preserves_submenus(self):
        builtin_1 = _FakeAction("Bury Card")
        builtin_sep = _FakeAction(separator=True)
        custom_sep_lead = _FakeAction(separator=True)
        custom_toggle = _FakeAction("Toggle &Ankimon", shortcut="Shift+M", checkable=True, checked=True)
        sub_child = _FakeAction("Heal Team")
        sub_menu = _FakeQMenu([sub_child])
        custom_sub = _FakeAction("Ankimon &Tools", menu=sub_menu)
        trailing_sep = _FakeAction(separator=True)

        qmenu = _FakeQMenu([
            builtin_1,
            builtin_sep,
            custom_sep_lead,
            custom_toggle,
            custom_sub,
            trailing_sep,
        ])
        items, action_map = self.mod._extract_custom_items(qmenu, {builtin_1, builtin_sep})
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["type"], "action")
        self.assertEqual(items[0]["label"], "Toggle Ankimon")
        self.assertTrue(items[0]["checkable"])
        self.assertTrue(items[0]["checked"])
        self.assertEqual(items[1]["type"], "submenu")
        self.assertEqual(items[1]["label"], "Ankimon Tools")
        self.assertEqual(items[1]["items"][0]["label"], "Heal Team")
        self.assertEqual(len(action_map), 2)

        self.mod._custom_action_map = action_map
        self.assertTrue(self.mod.handle_command(f"onigiri_more_menu:custom:{items[1]['items'][0]['id']}"))
        self.assertEqual(sub_child.triggered_count, 1)

    def test_action_dispatch_routes_every_reviewer_method(self):
        reviewer = MagicMock()
        reviewer.card = types.SimpleNamespace(user_flag=lambda: 2, note=lambda: types.SimpleNamespace(has_tag=lambda *_: False))
        fake_mw = types.SimpleNamespace(reviewer=reviewer, bottomWeb=MagicMock(), state="review")

        with patch.object(self.mod, "mw", fake_mw):
            for cmd_id, attr in [
                ("mark", "toggle_mark_on_current_note"),
                ("auto_advance", "toggle_auto_advance"),
                ("options", "onOptions"),
                ("card_info", "on_card_info"),
                ("prev_card_info", "on_previous_card_info"),
                ("bury_card", "bury_current_card"),
                ("bury_note", "bury_current_note"),
                ("suspend_card", "suspend_current_card"),
                ("suspend_note", "suspend_current_note"),
                ("set_due", "on_set_due"),
                ("reset_card", "forget_current_card"),
                ("create_copy", "on_create_copy"),
                ("delete_note", "delete_current_note"),
                ("replay_audio", "replayAudio"),
                ("pause_audio", "on_pause_audio"),
                ("seek_back", "on_seek_backward"),
                ("seek_fwd", "on_seek_forward"),
                ("record_voice", "onRecordVoice"),
                ("replay_voice", "onReplayRecorded"),
            ]:
                self.assertTrue(self.mod.handle_command(f"onigiri_more_menu:act:{cmd_id}"))
                getattr(reviewer, attr).assert_called_once()

            self.assertTrue(self.mod.handle_command("onigiri_more_menu:act:flag:5"))
            reviewer.set_flag_on_current_card.assert_called_with(5)
            self.assertTrue(self.mod.handle_command("onigiri_more_menu:act:flag:0"))
            reviewer.set_flag_on_current_card.assert_called_with(0)

    def test_open_toggles_closed_when_already_open(self):
        note = types.SimpleNamespace(has_tag=lambda *_: False)
        card = types.SimpleNamespace(user_flag=lambda: 0, note=lambda: note)
        r_web = MagicMock()
        b_web = MagicMock()
        fake_mw = types.SimpleNamespace(
            state="review",
            bottomWeb=b_web,
            flags=types.SimpleNamespace(all=lambda: []),
        )
        reviewer = types.SimpleNamespace(
            card=card,
            auto_advance_enabled=False,
            previous_card=None,
            mw=fake_mw,
            web=r_web,
        )
        fake_mw.reviewer = reviewer

        with patch.object(self.mod, "mw", fake_mw):
            self.mod.close_menu(from_js=True, immediate=True)
            self.mod.open_menu(reviewer)
            self.assertTrue(self.mod._is_open)
            self.assertIn("OnigiriReviewerMoreMenu.open(", r_web.eval.call_args[0][0])
            b_web.eval.assert_called_with("window.onigiriSetMoreMenuOpen && window.onigiriSetMoreMenuOpen(true);")

            # Calling open_menu while open toggles closed
            self.mod.open_menu(reviewer)
            self.assertFalse(self.mod._is_open)
            self.assertIn("OnigiriReviewerMoreMenu.close()", r_web.eval.call_args[0][0])
            b_web.eval.assert_called_with("window.onigiriSetMoreMenuOpen && window.onigiriSetMoreMenuOpen(false);")

    def test_css_contains_motion_spring_and_reduced_motion(self):
        css = (ROOT / "web/reviewer_more_menu.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("backdrop-filter:", css)
        self.assertIn("box-shadow: none;", css)
        self.assertIn(":host(.night-mode)", css)
        self.assertIn("linear(", css)

    def test_js_runtime_mounts_shadow_renders_and_dispatches(self):
        script = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

function makeElement(tag) {
  const attrs = {};
  const listeners = {};
  const styleMap = {};
  const classSet = new Set();
  const el = {
    tagName: tag.toUpperCase(),
    id: '',
    children: [],
    parentNode: null,
    hidden: false,
    disabled: false,
    title: '',
    offsetParent: {},
    offsetWidth: 100,
    _text: '',
    style: {
      cssText: '',
      setProperty(k, v) { styleMap[k] = v; },
      removeProperty(k) { delete styleMap[k]; },
      getPropertyValue(k) { return styleMap[k] || ''; }
    },
    classList: {
      add(...names) { names.forEach(n => classSet.add(n)); },
      remove(...names) { names.forEach(n => classSet.delete(n)); },
      toggle(n, force) {
        if (force === undefined) {
          if (classSet.has(n)) { classSet.delete(n); return false; }
          classSet.add(n); return true;
        }
        if (force) classSet.add(n); else classSet.delete(n);
        return !!force;
      },
      contains(n) { return classSet.has(n); }
    },
    set className(val) {
      classSet.clear();
      String(val || '').split(/\s+/).filter(Boolean).forEach(n => classSet.add(n));
    },
    get className() { return Array.from(classSet).join(' '); },
    set textContent(v) {
      this._text = String(v || '');
      if (v === '') this.children = [];
    },
    get textContent() {
      if (this.children.length) return this.children.map(c => c.textContent).join('');
      return this._text;
    },
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null; },
    appendChild(child) { child.parentNode = this; this.children.push(child); return child; },
    append(...nodes) { nodes.forEach(n => { if (n) this.appendChild(n); }); },
    replaceChild(next, old) {
      const idx = this.children.indexOf(old);
      if (idx >= 0) { next.parentNode = this; this.children[idx] = next; }
    },
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    dispatchEvent(ev) { (listeners[ev.type] || []).forEach(fn => fn(ev)); },
    click() { this.dispatchEvent({ type: 'click', preventDefault() {}, stopPropagation() {} }); },
    focus() { if (el._shadowRoot) el._shadowRoot.activeElement = el; },
    querySelectorAll(sel) {
      const out = [];
      function walk(node) {
        for (const c of node.children || []) {
          if (sel.includes('button') && c.tagName === 'BUTTON') out.push(c);
          walk(c);
        }
      }
      walk(this);
      return out;
    },
    attachShadow() {
      const sr = {
        activeElement: null,
        children: [],
        appendChild(c) { c._shadowRoot = sr; sr.children.push(c); return c; }
      };
      this.shadowRoot = sr;
      return sr;
    }
  };
  return el;
}

const body = makeElement('body');
const docEl = makeElement('html');
docEl.classList.add('night-mode');
const cmds = [];
const context = {
  window: {
    onigiriMoreMenuCssText: '/* css */',
    pycmd(cmd) { cmds.push(cmd); }
  },
  document: {
    readyState: 'complete',
    documentElement: docEl,
    body,
    createElement: tag => makeElement(tag),
    createElementNS: (_ns, tag) => makeElement(tag),
    getElementById(id) {
      return body.children.find(c => c.id === id) || null;
    }
  },
  MutationObserver: class { constructor() {} observe() {} disconnect() {} },
  setTimeout,
  clearTimeout
};
context.window.window = context.window;

vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const api = context.window.OnigiriReviewerMoreMenu;
assert.ok(api, 'API attached');

const payload = {
  flag: 2,
  marked: false,
  autoAdvance: false,
  hasPreviousCard: true,
  dark: true,
  flags: Array.from({length: 7}, (_, i) => ({ index: i + 1, label: 'Flag ' + (i + 1), color: '#fff', shortcut: '⌘' + (i + 1), iconUrl: i === 0 ? '/_addons/1011095603/heart.svg' : '' })),
  labels: { markNote: 'Mark Note', autoAdvance: 'Auto Advance', setDueDate: 'Set Due Date...', deleteNote: 'Delete Note' },
  shortcuts: { mark: '*', autoAdvance: '⇧A', deleteNote: '⌘⌫' },
  customItems: [
    { type: 'action', id: 0, label: 'Custom Action', shortcut: '', checkable: false, checked: false, disabled: false },
    { type: 'submenu', label: 'Submenu', disabled: false, items: [{ type: 'action', id: 1, label: 'Nested', shortcut: '', checkable: false, checked: false, disabled: false }] }
  ]
};

api.open(payload, true);
assert.equal(api.isOpen(), true);
const host = context.document.getElementById('onigiri-reviewer-more-menu-host');
assert.ok(host.classList.contains('night-mode'));

const panel = host.shadowRoot.children[1].children[1];
const buttons = panel.querySelectorAll('button');
// Clear + 7 flags + Mark + Auto + Options + Info + Prev + 2 Bury + 2 Suspend + 4 single + 6 media + Custom + Submenu toggle + Nested = 30 buttons
assert.equal(buttons.length, 30);

// First flag uses custom icon glyph mask; Set Due Date strips trailing ellipsis
const flag1Btn = buttons.find(b => b.getAttribute('aria-label') === 'Flag 1');
assert.equal(flag1Btn.children[0].className, 'rm-flag-glyph');
assert.ok(flag1Btn.children[0].style.getPropertyValue('--rm-flag-mask').includes('heart.svg'));
const setDueBtn = buttons.find(b => b.textContent.includes('Set Due Date'));
assert.ok(setDueBtn && !setDueBtn.textContent.includes('...'));

// Clicking Replay keeps menu open
const replayBtn = buttons.find(b => b.textContent.includes('Replay'));
replayBtn.click();
assert.equal(api.isOpen(), true);
assert.equal(cmds[cmds.length - 1], 'onigiri_more_menu:act:replay_audio');

// Clicking Delete Note closes menu immediately and sends act:delete_note
const deleteBtn = buttons.find(b => b.textContent.includes('Delete Note'));
deleteBtn.click();
assert.equal(api.isOpen(), false);
assert.equal(cmds[cmds.length - 1], 'onigiri_more_menu:act:delete_note');

// Reopen, open custom submenu, click nested item
api.open(payload, false);
assert.equal(api.isOpen(), true);
const subToggle = panel.querySelectorAll('button').find(b => b.textContent.includes('Submenu'));
subToggle.click();
assert.equal(subToggle.getAttribute('aria-expanded'), 'true');
const nestedBtn = panel.querySelectorAll('button').find(b => b.textContent.includes('Nested'));
nestedBtn.click();
assert.equal(cmds[cmds.length - 1], 'onigiri_more_menu:custom:1');
assert.equal(api.isOpen(), false);
'''
        env = dict(os.environ)
        env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
        result = subprocess.run(
            ["node", "-e", script, str(ROOT / "web/reviewer_more_menu.js")],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
