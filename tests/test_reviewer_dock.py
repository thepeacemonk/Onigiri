"""Tests for Reviewer Dock modes (Static, Minimal, Island) and Settings wiring."""

import ast
import importlib
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load_dock_module(test_case, conf=None):
    conf = conf or {"hideNativeHeaderAndBottomBar": True}
    pkg = types.ModuleType("onigiri_dock_test")
    pkg.__path__ = [str(ROOT)]
    core_pkg = types.ModuleType("onigiri_dock_test.core")
    core_pkg.__path__ = [str(ROOT / "core")]
    rendering_pkg = types.ModuleType("onigiri_dock_test.rendering")
    rendering_pkg.__path__ = [str(ROOT / "rendering")]
    api_pkg = types.ModuleType("onigiri_dock_test.api")
    api_pkg.__path__ = [str(ROOT / "api")]

    fake_config = types.SimpleNamespace(
        get_config_readonly=lambda: dict(conf),
        get_collection_config=lambda _k, default=None: default,
    )
    fake_translations = types.SimpleNamespace(tr=lambda key, fallback=None: fallback or key.title())
    fake_visibility = types.SimpleNamespace(reviewer_button_visible=lambda tool, _c: tool == "pomodoro")
    fake_sidebar = types.SimpleNamespace(render_reviewer_toolbar_entries=lambda: "")
    fake_patcher = types.SimpleNamespace(
        generate_reviewer_top_bar_html_and_css=lambda include_overview_class=False: (
            '<div id="onigiri-reviewer-header" class="header"><div class="onigiri-reviewer-header-buttons">static</div></div>',
            "<style>/* static */</style>",
        ),
        _get_reviewer_nook_level_chip_html=lambda: '<div class="restaurant-level-chip">Lv 8</div>',
        _reviewer_progress_settings=lambda _c, force=False: {"enabled": True, "position": "right"},
        reset_reviewer_progress_session=lambda: None,
        _reviewer_progress_html=lambda _s: '<div id="onigiri-reviewer-progress">2/20</div>',
        generate_scoped_main_font_css=lambda *_a: "<style></style>",
        generate_box_effect_button_vars_css=lambda *_a, **_kw: "<style></style>",
    )
    core_pkg.config = fake_config
    core_pkg.translations = fake_translations
    core_pkg.study_tool_visibility = fake_visibility
    api_pkg.sidebar = fake_sidebar
    rendering_pkg.patcher = fake_patcher

    patcher_ctx = patch.dict(
        sys.modules,
        {
            "onigiri_dock_test": pkg,
            "onigiri_dock_test.core": core_pkg,
            "onigiri_dock_test.core.config": fake_config,
            "onigiri_dock_test.core.translations": fake_translations,
            "onigiri_dock_test.core.study_tool_visibility": fake_visibility,
            "onigiri_dock_test.api": api_pkg,
            "onigiri_dock_test.api.sidebar": fake_sidebar,
            "onigiri_dock_test.rendering": rendering_pkg,
            "onigiri_dock_test.rendering.patcher": fake_patcher,
        },
    )
    patcher_ctx.start()
    test_case.addCleanup(patcher_ctx.stop)
    return importlib.import_module("onigiri_dock_test.rendering.reviewer_dock")


class ReviewerDockTests(unittest.TestCase):
    def test_config_and_settings_schema_expose_merged_dock_designer(self):
        cfg_text = (ROOT / "core/config.py").read_text(encoding="utf-8")
        for key in (
            '"onigiri_reviewer_dock_mode": "static"',
            '"onigiri_reviewer_dock_icons": {}',
            '"onigiri_reviewer_dock_icon_colors_light": {}',
            '"onigiri_reviewer_dock_icon_colors_dark": {}',
            '"onigiri_reviewer_dock_goo_color_light": "#17181a"',
            '"onigiri_reviewer_dock_goo_color_dark": "#ffffff"',
            '"onigiri_web_rdock_goo_theme_mode": "separate"',
        ):
            self.assertIn(key, cfg_text)

        env = {
            "tr": lambda _key, fallback=None: fallback or _key,
            "_reviewer_background_section": lambda: {"id": "reviewer_background"},
            "_reviewer_bottom_bar_section": lambda: {"id": "reviewer_bottom_bar"},
            "_reviewer_flags_section": lambda: {"id": "reviewer_flags"},
        }
        tree = ast.parse((ROOT / "settings_web/schema.py").read_text(encoding="utf-8"))
        wanted_defs = {
            "_hidden_config_field",
            "_color_pair_field",
            "_designer_preview_section",
            "_dock_icon_tint_fields",
            "_reviewer_progress_fields",
            "_reviewer_dock_section",
            "_reviewer_page",
        }
        nodes = [
            node
            for node in tree.body
            if (isinstance(node, ast.FunctionDef) and node.name in wanted_defs)
            or (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_DOCK_BUTTON_SPECS" for t in node.targets)
            )
        ]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "schema.py", "exec"), env)

        page = env["_reviewer_page"]()
        self.assertIn("reviewer_dock", page["post_save"])
        section_ids = [sec["id"] for sec in page["sections"]]
        self.assertIn("reviewer_dock", section_ids)
        self.assertNotIn("reviewer_progress", section_ids)

        dock_section = next(sec for sec in page["sections"] if sec["id"] == "reviewer_dock")
        self.assertEqual(dock_section["layout"], "designer_preview")
        self.assertEqual(dock_section["preview_kind"], "reviewer_dock")
        self.assertTrue(dock_section["icon_colors_inline"])
        self.assertTrue(dock_section["head_to_deck"])
        self.assertIn("rdock_goo_color_theme_mode", dock_section["dynamic_keys"])

        fields_by_id = {f["id"]: f for f in dock_section["fields"]}
        mode_field = fields_by_id["reviewer_dock_mode"]
        self.assertEqual(mode_field["bind"]["key"], "onigiri_reviewer_dock_mode")
        self.assertEqual(mode_field["default"], "static")
        self.assertEqual([opt["value"] for opt in mode_field["options"]], ["static", "minimal", "island"])

        goo_field = fields_by_id["rdock_goo_color"]
        self.assertEqual(goo_field["type"], "color_pair")
        self.assertEqual(goo_field["show_when"], {"field": "reviewer_dock_mode", "values": ["island"]})

        # Contiguous block of all 7 dock icons + companions + merged progress controls
        dock_icon_indices = [
            idx for idx, f in enumerate(dock_section["fields"]) if f["id"].startswith("rdock_icon_") and f["type"] == "icon"
        ]
        self.assertEqual(len(dock_icon_indices), 7)
        self.assertEqual(dock_icon_indices, list(range(dock_icon_indices[0], dock_icon_indices[0] + 7)))

        for key in ("decks", "add", "browse", "stats", "sync", "hashi_notes", "pomodoro"):
            icon_f = fields_by_id[f"rdock_icon_{key}"]
            self.assertEqual(icon_f["icon_group"], "dock_icons")
            self.assertEqual(icon_f["bind"], {"kind": "config", "path": ["onigiri_reviewer_dock_icons", key]})
            svg_name = icon_f["default_icon"].split("system:", 1)[1]
            self.assertTrue(
                any(
                    (ROOT / folder / svg_name).is_file()
                    for folder in (
                        "system_files/system_icons/available_for_users",
                        "system_files/system_icons/unavailable_for_users",
                        "system_files/system_icons",
                    )
                ),
                f"Missing default icon {svg_name}",
            )
            color_f = fields_by_id[f"rdock_icon_color_{key}"]
            self.assertEqual(color_f["type"], "color_pair")
            self.assertTrue(color_f["always_split"])

        for merged_prog_id in ("rprog_enabled", "rprog_style", "rprog_chrome", "rprog_fill"):
            self.assertIn(merged_prog_id, fields_by_id)
        self.assertEqual(fields_by_id["rprog_enabled"].get("head_label"), "Progress Bar")

        # Declarative subsections clearly separate shared Dock/Island/Icon
        # controls (Reviewer & Overview) from Reviewer-only Progress Bar controls.
        subsections = dock_section.get("subsections") or []
        sub_by_id = {sub["id"]: sub for sub in subsections}
        self.assertEqual(
            [sub["id"] for sub in subsections],
            [
                "dock_style",
                "dock_island",
                "dock_icons",
                "progress_bar",
                "progress_bar_shape",
                "progress_bar_colors",
            ],
        )
        for shared_id in ("dock_style", "dock_island", "dock_icons"):
            self.assertEqual(sub_by_id[shared_id]["band"], "top")
            self.assertEqual(sub_by_id[shared_id]["badge_tone"], "shared")
            self.assertTrue(sub_by_id[shared_id]["badge"])
            self.assertFalse(sub_by_id[shared_id].get("desc"))
        self.assertTrue(sub_by_id["dock_icons"].get("icon_grid"))
        for rev_id in ("progress_bar", "progress_bar_shape", "progress_bar_colors"):
            self.assertEqual(sub_by_id[rev_id]["badge_tone"], "reviewer")
            self.assertTrue(sub_by_id[rev_id]["badge"])
            self.assertFalse(sub_by_id[rev_id].get("desc"))

        assigned_ids = {fid for sub in subsections for fid in sub["fields"]}
        companion_color_ids = {f"rdock_icon_color_{key}" for key in ("decks", "add", "browse", "stats", "sync", "hashi_notes", "pomodoro")}
        visible_field_ids = {
            f["id"]
            for f in dock_section["fields"]
            if f["type"] != "hidden" and f["id"] not in companion_color_ids
        }
        self.assertEqual(assigned_ids, visible_field_ids)

        side_effects = (ROOT / "settings_web/side_effects.py").read_text(encoding="utf-8")
        self.assertIn('"reviewer_dock": _reviewer_dock', side_effects)

    def test_dock_mode_icons_colors_goo_and_html_variants(self):
        mod = _load_dock_module(self)
        self.assertEqual(mod.dock_mode({"onigiri_reviewer_dock_mode": "static"}), "static")
        self.assertEqual(mod.dock_mode({"onigiri_reviewer_dock_mode": "minimal"}), "minimal")
        self.assertEqual(mod.dock_mode({"onigiri_reviewer_dock_mode": "ISLAND"}), "island")
        self.assertEqual(mod.dock_mode({"onigiri_reviewer_dock_mode": "unknown"}), "static")

        base_conf = {
            "hideNativeHeaderAndBottomBar": True,
            "restaurant_level": {"enabled": True, "show_reviewer_header": True},
            "onigiri_reviewer_dock_icons": {
                "decks": "emoji:🍙",
                "add": "../../etc/passwd",
            },
            "onigiri_reviewer_dock_icon_colors_light": {"decks": "#123456"},
            "onigiri_reviewer_dock_icon_colors_dark": {"decks": "#abcdef"},
            "onigiri_reviewer_dock_goo_color_light": "#ffd23f",
            "onigiri_reviewer_dock_goo_color_dark": "#112233",
            "onigiri_web_rdock_goo_theme_mode": "separate",
        }
        html_static, _ = mod.generate_top_bar_html_and_css(
            {**base_conf, "onigiri_reviewer_dock_mode": "static"}
        )
        self.assertNotIn("is-minimal", html_static)
        self.assertNotIn("is-island", html_static)

        html_min, css_min = mod.generate_top_bar_html_and_css(
            {**base_conf, "onigiri_reviewer_dock_mode": "minimal"}
        )
        self.assertIn("is-minimal", html_min)
        self.assertIn("is-icon-only", html_min)
        self.assertIn("onigiri-pomodoro-button", html_min)
        self.assertNotIn("onigiri-hashi-notes-button", html_min)
        self.assertIn("onigiri-dock-glyph is-emoji", html_min)
        self.assertIn("🍙", html_min)
        self.assertNotIn("/etc/passwd", html_min)
        self.assertIn("data:image/svg+xml;base64,", html_min)
        self.assertIn("--rd-icon-color-light: #123456;", html_min)
        self.assertIn("--rd-icon-color-dark: #abcdef;", html_min)
        self.assertIn("restaurant-level-chip", html_min)
        self.assertIn("onigiri-reviewer-progress", html_min)
        self.assertIn("onigiri-reviewer-dock-style", css_min)

        html_island, _ = mod.generate_top_bar_html_and_css(
            {**base_conf, "onigiri_reviewer_dock_mode": "island"}
        )
        self.assertIn("is-island", html_island)
        self.assertIn("--rd-goo-light: #ffd23f;", html_island)
        self.assertIn("--rd-goo-ink-light: #0e0f11;", html_island)
        self.assertIn("--rd-goo-dark: #112233;", html_island)
        self.assertIn("--rd-goo-ink-dark: #ffffff;", html_island)
        self.assertIn("onigiri-island-shell", html_island)
        self.assertIn("onigiri-island-surface", html_island)
        self.assertIn("onigiri-rubber-dock", html_island)
        self.assertIn("onigiri-dock-indicator", html_island)
        self.assertIn("onigiri-dock-ink", html_island)
        self.assertIn("onigiri-island-notice", html_island)
        self.assertIn("restaurant-level-chip", html_island)
        self.assertIn("onigiri-reviewer-progress", html_island)

        # Overview / Congrats dock shares the exact same dock style, icons,
        # icon colors, and goo palette, without Progress Bar or Level chip.
        html_ov_min, _ = mod.generate_top_bar_html_and_css(
            {**base_conf, "onigiri_reviewer_dock_mode": "minimal"},
            include_overview_class=True,
        )
        self.assertIn("is-minimal", html_ov_min)
        self.assertIn("onigiri-pomodoro-button", html_ov_min)
        self.assertIn("--rd-icon-color-light: #123456;", html_ov_min)
        self.assertNotIn("restaurant-level-chip", html_ov_min)
        self.assertNotIn("onigiri-reviewer-progress", html_ov_min)

        html_ov_island, _ = mod.generate_top_bar_html_and_css(
            {**base_conf, "onigiri_reviewer_dock_mode": "island"},
            include_overview_class=True,
        )
        self.assertIn("is-island", html_ov_island)
        self.assertIn("--rd-goo-light: #ffd23f;", html_ov_island)
        self.assertIn("onigiri-rubber-dock", html_ov_island)
        self.assertNotIn("restaurant-level-chip", html_ov_island)
        self.assertNotIn("onigiri-reviewer-progress", html_ov_island)
        self.assertNotIn("onigiri-dock-divider", html_ov_island)
        self.assertNotIn("onigiri-island-info", html_ov_island)

    def test_island_js_mounts_rubber_dock_and_expands_downward_for_notifications(self):
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
    parentElement: null,
    dataset: {},
    _text: '',
    offsetLeft: 0,
    offsetTop: 0,
    offsetWidth: 280,
    offsetHeight: 42,
    clientWidth: 280,
    clientHeight: 42,
    style: {
      cssText: '',
      width: '',
      height: '',
      left: '',
      top: '',
      borderRadius: '',
      clipPath: '',
      transform: '',
      setProperty(k, v) { styleMap[k] = String(v); },
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
    removeAttribute(k) { delete attrs[k]; },
    appendChild(child) {
      child.parentNode = this;
      child.parentElement = this;
      this.children.push(child);
      return child;
    },
    append(...nodes) { nodes.forEach(n => { if (n) this.appendChild(n); }); },
    prepend(child) { child.parentNode = this; child.parentElement = this; this.children.unshift(child); },
    remove() {
      if (this.parentNode) {
        this.parentNode.children = this.parentNode.children.filter(c => c !== this);
        this.parentNode = null;
        this.parentElement = null;
      }
    },
    cloneNode() {
      const c = makeElement(tag);
      c.className = this.className;
      c.offsetWidth = this.offsetWidth;
      c.offsetHeight = this.offsetHeight;
      c.clientWidth = this.clientWidth;
      c.clientHeight = this.clientHeight;
      return c;
    },
    matches() { return false; },
    closest() { return null; },
    getBoundingClientRect() { return { left: 0, top: 0, width: this.offsetWidth, height: this.offsetHeight }; },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    dispatchEvent(ev) { (listeners[ev.type] || []).forEach(fn => fn(ev)); },
    querySelector(sel) {
      return this.querySelectorAll(sel)[0] || null;
    },
    querySelectorAll(sel) {
      const out = [];
      const cls = sel.startsWith('.') ? sel.slice(1).split(',')[0].trim() : null;
      const id = sel.startsWith('#') ? sel.slice(1) : null;
      function walk(node) {
        for (const c of node.children || []) {
          if ((cls && c.classList.contains(cls)) ||
              (id && c.id === id) ||
              (sel.includes('svg') && c.tagName === 'SVG')) {
            out.push(c);
          }
          walk(c);
        }
      }
      walk(this);
      return out;
    }
  };
  return el;
}

const header = makeElement('div');
header.id = 'onigiri-reviewer-header';
header.className = 'header is-island';

const shell = makeElement('div'); shell.className = 'onigiri-island-shell';
const surface = makeElement('span'); surface.className = 'onigiri-island-surface';
const bar = makeElement('div'); bar.className = 'onigiri-island-bar'; bar.offsetWidth = 280; bar.offsetHeight = 42;
const dock = makeElement('nav'); dock.className = 'onigiri-rubber-dock'; dock.clientWidth = 180; dock.clientHeight = 34;
const ind = makeElement('i'); ind.className = 'onigiri-dock-indicator';
const ink = makeElement('div'); ink.className = 'onigiri-dock-ink'; ink.clientWidth = 180; ink.clientHeight = 34;
const tip = makeElement('span'); tip.className = 'onigiri-dock-tip';

const dockBtn1 = makeElement('a'); dockBtn1.className = 'onigiri-dock-item'; dockBtn1.setAttribute('data-tip', 'Decks');
dockBtn1.offsetLeft = 0; dockBtn1.offsetWidth = 34; dockBtn1.offsetHeight = 34;
const svg1 = makeElement('svg'); svg1.clientWidth = 17; svg1.clientHeight = 17;
dockBtn1.appendChild(svg1);

const dockBtn2 = makeElement('a'); dockBtn2.className = 'onigiri-dock-item'; dockBtn2.setAttribute('data-tip', 'Add');
dockBtn2.offsetLeft = 36; dockBtn2.offsetWidth = 34; dockBtn2.offsetHeight = 34;
const svg2 = makeElement('svg'); svg2.clientWidth = 17; svg2.clientHeight = 17;
dockBtn2.appendChild(svg2);

dock.append(ind, dockBtn1, dockBtn2, ink, tip);
bar.appendChild(dock);

const notice = makeElement('div'); notice.className = 'onigiri-island-notice';
notice.offsetHeight = 64;
const noticeInner = makeElement('div'); noticeInner.className = 'onigiri-island-notice-inner';
notice.appendChild(noticeInner);

shell.append(surface, bar, notice);
header.appendChild(shell);

const shadow = {
  getElementById(id) { return id === 'onigiri-reviewer-header' ? header : null; }
};
const host = makeElement('div'); host.id = 'onigiri-reviewer-ui-host'; host.shadowRoot = shadow;

const body = makeElement('body');
body.appendChild(host);
const docEl = makeElement('html');

const timeouts = [];
const context = {
  window: {
    innerWidth: 1000,
    onigiriIsReviewerCardWebview: true,
    onigiriReviewerDockMode: 'island',
    onigiriNotificationDuration: 5000,
    matchMedia: () => ({ matches: true }),
    requestAnimationFrame: cb => { cb(16); return 1; },
    cancelAnimationFrame: () => {},
    setTimeout: (fn, ms) => { timeouts.push(fn); return timeouts.length; },
    clearTimeout: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {}
  },
  document: {
    readyState: 'complete',
    documentElement: docEl,
    body,
    createElement: tag => makeElement(tag),
    getElementById(id) { return id === 'onigiri-reviewer-ui-host' ? host : null; },
    addEventListener: () => {}
  },
  performance: { now: () => 100 },
  setTimeout: (fn, ms) => { timeouts.push(fn); return timeouts.length; },
  clearTimeout: () => {}
};
context.window.window = context.window;

vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), context);

context.window.OnigiriReviewerDock.mount(shadow);
assert.ok(context.window.OnigiriReviewerIsland, 'Island API mounted');
assert.equal(ink.children.length, 2, 'Ink layer cloned both dock icons');

// Hovering second item moves rubber indicator and shows tooltip
dockBtn2.dispatchEvent({ type: 'pointerenter', pointerType: 'mouse' });
assert.ok(dock.classList.contains('has-selection'));
assert.equal(tip.textContent, 'Add');
assert.ok(ink.style.clipPath.includes('inset('));

// Sending notification expands island downward (reduced motion snaps to target immediately)
context.window.OnigiriNotifications.show({
  name: 'Level Up',
  description: 'Reached Lv 9',
  rewardItems: [{ value: '+25' }]
});
assert.ok(context.window.OnigiriReviewerIsland.isExpanded());
assert.ok(shell.classList.contains('island-notice'));
assert.equal(noticeInner.children.length, 1);
assert.equal(surface.style.height, '106.00px'); // 42px bar + 64px notice

// Clicking notice item dismisses and shrinks back to bar height (42px)
noticeInner.children[0].dispatchEvent({ type: 'click', stopPropagation() {} });
assert.equal(context.window.OnigiriReviewerIsland.isExpanded(), false);
assert.equal(surface.style.height, '42.00px');
assert.equal(noticeInner.children.length, 0);
'''
        env = dict(os.environ)
        env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
        result = subprocess.run(
            [
                "node",
                "-e",
                script,
                str(ROOT / "web/reviewer_dock.js"),
                str(ROOT / "web/notifications.js"),
            ],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pill_background_parity_and_settings_preview_syntax(self):
        dock_css = (ROOT / "web/reviewer_dock.css").read_text(encoding="utf-8")
        self.assertIn("#onigiri-reviewer-header.is-island .onigiri-reviewer-progress,\n#onigiri-reviewer-header.is-island .onigiri-reviewer-progress.is-bare", dock_css)
        self.assertIn("#onigiri-reviewer-header.is-minimal .restaurant-level-chip,\n#onigiri-reviewer-header.is-minimal .onigiri-reviewer-progress", dock_css)

        patcher_src = (ROOT / "rendering/patcher.py").read_text(encoding="utf-8")
        self.assertIn("#onigiri-reviewer-header:not(.is-island):has(.onigiri-reviewer-progress.is-bare) .restaurant-level-chip", patcher_src)

        settings_js = (ROOT / "web/settings.js").read_text(encoding="utf-8")
        self.assertIn('ICON_POPUP_COMPANIONS["rdock_icon_" + key] = ["rdock_icon_color_" + key]', settings_js)
        self.assertIn("PREVIEW_PAINTERS.reviewer_dock =", settings_js)
        self.assertIn("osw-rdock-notify-test-btn", settings_js)

        env = dict(os.environ)
        env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
        syntax_result = subprocess.run(
            ["node", "--check", str(ROOT / "web/settings.js")],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(syntax_result.returncode, 0, syntax_result.stderr)

        painter_script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const src = fs.readFileSync(process.argv[1], 'utf8');
const start = src.indexOf('  const RDOCK_PREVIEW_BUTTONS =');
const end = src.indexOf('\n  // ── Sidebar previews', start);
assert.ok(start > 0 && end > start, 'Could not slice reviewer_dock preview block');

function makeNode(tag, className, text = '') {
  const attrs = {};
  const classSet = new Set(String(className || '').split(/\s+/).filter(Boolean));
  const styleMap = {};
  const listeners = {};
  const node = {
    tag,
    isConnected: true,
    children: [],
    textContent: text === undefined ? '' : String(text),
    scrollHeight: 62,
    attrs,
    listeners,
    style: {
      setProperty(k, v) { styleMap[k] = String(v); },
      getPropertyValue(k) { return styleMap[k] || ''; },
    },
    classList: {
      add(...xs) { xs.forEach(x => classSet.add(x)); },
      remove(...xs) { xs.forEach(x => classSet.delete(x)); },
      contains(x) { return classSet.has(x); },
    },
    appendChild(child) { this.children.push(child); return child; },
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return attrs[k]; },
    addEventListener(ev, fn) { (listeners[ev] ||= []).push(fn); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 220, height: 34, right: 220, bottom: 34 }; },
    set innerHTML(val) { this.children = []; this._html = val; },
    cloneNode(deep) {
      const copy = makeNode(this.tag, Array.from(classSet).join(' '), this.textContent);
      Object.assign(copy.style, this.style);
      return deep ? copy : copy;
    },
  };
  return node;
}

const sandbox = {
  PREVIEW_PAINTERS: {},
  REVIEWER_BG_KEYS: [],
  str: (_k, fb) => fb || _k,
  el: makeNode,
  paintResolvedBackdropState() {},
  designerBgSourceState: () => ({}),
  rprogSample: () => ({ done: 2, total: 20, pct: 10 }),
  rprogChip: (_v, _d, _data) => makeNode('div', 'osw-preview-rprog-chip'),
  designerPairValue: (vals, lk, dk, _tk, isDark) => (isDark ? vals[dk] : vals[lk]),
  designerIconGlyph: (val, color) => {
    const g = makeNode('span', 'osw-sbprev-glyph');
    g.dataset = { val };
    g.style.background = color;
    return g;
  },
  performance: { now: () => 0 },
  window: {
    setTimeout: () => 1,
    clearTimeout() {},
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
  },
};

vm.createContext(sandbox);
vm.runInContext(src.slice(start, end), sandbox);

const stage = makeNode('div', 'osw-designer-preview-stage');
const vals = {
  reviewer_dock_mode: 'static',
  rprog_enabled: true,
  rprog_chrome: false,
  rdock_goo_color_light: '#ffd23f',
  rdock_goo_color_dark: '#112233',
  rdock_icon_decks: 'emoji:🍙',
  rdock_icon_color_decks_light: '#ff5500',
  rdock_icon_color_decks_dark: '#00ffaa',
};

sandbox.PREVIEW_PAINTERS.reviewer_dock(stage, vals, false);
assert.equal(stage.children[0].children[0].children.find(n => n.classList.contains('osw-preview-rdock-level')).classList.contains('is-bare'), true);

vals.reviewer_dock_mode = 'minimal';
sandbox.PREVIEW_PAINTERS.reviewer_dock(stage, vals, false);
const minBtn = stage.children[0].children[0].children.find(n => n.classList.contains('osw-preview-rdock-minbtn'));
assert.ok(minBtn, 'Minimal button rendered');
assert.equal(minBtn.children[0].style.background, '#ff5500');

vals.reviewer_dock_mode = 'island';
sandbox.PREVIEW_PAINTERS.reviewer_dock(stage, vals, false);
assert.equal(typeof stage._triggerDockNotice, 'function');
const island = stage.children[0].children[0].children[0];
const bar = island.children[1];
const strip = bar.children[0];
const indicator = strip.children[0];
const ink = strip.children[strip.children.length - 2];
assert.equal(indicator.style.background, '#ffd23f');
assert.equal(ink.children[0].style.background, '#0e0f11'); // high-contrast dark ink on #ffd23f goo

stage._triggerDockNotice();
assert.ok(island.classList.contains('island-notice'));
assert.ok(island.children[2].classList.contains('has-message'));
'''
        painter_res = subprocess.run(
            ["node", "-e", painter_script, str(ROOT / "web/settings.js")],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(painter_res.returncode, 0, painter_res.stderr)


if __name__ == "__main__":
    unittest.main()
