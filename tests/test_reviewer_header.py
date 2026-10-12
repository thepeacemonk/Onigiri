"""Reviewer header persistence, inheritance, and production CSS contracts."""
import ast
import json
import html
import math
import os
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(file, names, env):
    tree = ast.parse((ROOT / file).read_text())
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                                 and n.name in names], type_ignores=[]), file, 'exec'), env)


def header_schema(serialized=False):
    env = {'tr': lambda key, fallback='': fallback, '_current_simple_font_size': lambda role: 14,
           '_font_options': lambda: [{'value': 'system', 'label': 'Poppins', 'family': 'Poppins'},
                                    {'value': 'mono', 'label': 'Monospace', 'family': 'monospace'}],
           'COMPONENT_FONT_SIZE_DEFAULTS': {}}
    tree = ast.parse((ROOT / 'settings_web/schema.py').read_text())
    spec = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'ADVANCED_FONT_ROLES' for t in n.targets))
    env['ADVANCED_FONT_ROLES'] = ast.literal_eval(spec.value)
    load('settings_web/schema.py', {'_reviewer_header_fields', '_reviewer_progress_section', '_tool_visibility_section',
         '_color_pair_field', '_hidden_config_field', '_hidden_field', '_designer_preview_section',
         '_advanced_font_role', '_attach_compact_font_roles', '_attach_font_colors', 'iter_fields'}, env)
    section = env['_reviewer_progress_section']()
    env['_attach_font_colors']([{'sections': [section]}])
    if serialized:
        load('settings_web/render.py', {'_serialize_field', '_camel'}, env)
        store = types.SimpleNamespace(read=lambda id: next(f.get('default') for f in section['fields'] if f['id'] == id))
        section['fields'] = [env['_serialize_field'](store, f) for f in section['fields']]
        for key in ('font_roles', 'font_menu_label', 'color_groups', 'color_menu_label', 'mode_parity', 'header_customization'):
            section[env['_camel'](key)] = section.pop(key)
    return section


def runtime_env(conf=None, col=None):
    conf = conf or {}
    col = col or {}
    scripts = []
    env = {'os': os, 're': re, 'json': json, '__file__': str(ROOT / 'rendering/patcher.py'),
           '__package__': 'header_test.rendering',
           'config': types.SimpleNamespace(get_config_readonly=lambda: conf,
                    get_collection_config=lambda key, default=None: col.get(key, default)),
           'mw': types.SimpleNamespace(col=types.SimpleNamespace(conf=col), state='review',
                         reviewer=types.SimpleNamespace(web=types.SimpleNamespace(eval=scripts.append)))}
    load('rendering/patcher.py', {'generate_reviewer_header_css', 'refresh_reviewer_header_style',
         '_onigiri_int_style_value', '_onigiri_css_color_with_alpha', '_hex_to_rgba',
         'generate_scoped_main_font_css', 'generate_reviewer_top_bar_html_and_css'}, env)
    fonts = types.ModuleType('header_test.ui_kit.fonts')
    fonts.FONTS = {'system': {'family': 'Poppins', 'file': None}, 'mono': {'family': 'monospace', 'file': 'mono.ttf'}}
    fonts.get_all_fonts = lambda _: fonts.FONTS
    fonts.poppins_font_face_css = lambda _: ''
    env['font_module'] = fonts
    env['scripts'] = scripts
    return env


def runtime_css(conf=None, col=None):
    env = runtime_env(conf, col)
    with patch.dict(sys.modules, {env['font_module'].__name__: env['font_module']}):
        return env['generate_reviewer_header_css'](conf)


def live_refresh_fixture():
    conf = {"onigiri_reviewer_header_mode": "custom", "onigiri_reviewer_header_radius": 7}
    env = runtime_env(conf)
    env.update(html=html, math=math, tr=lambda key, fallback: fallback,
               _PROGRESS_STYLES=("bar", "segments", "ring", "text"),
               _PROGRESS_LABELS=("fraction", "percent", "remaining", "done", "none"),
               _progress_settings_cache={"key": None, "settings": None},
               _reviewer_progress_counts=lambda: {"done": 12, "left": 28, "total": 40, "pct": 30,
                                                 "new": 8, "learn": 4, "review": 16})
    load('rendering/patcher.py', {'_reviewer_progress_settings', '_reviewer_progress_css',
         '_reviewer_progress_html', '_reviewer_progress_inner_html', '_reviewer_progress_classes',
         '_reviewer_progress_label_text', '_reviewer_progress_tooltip'}, env)
    with patch.dict(sys.modules, {env['font_module'].__name__: env['font_module']}):
        for change in ({}, {"onigiri_reviewer_progress_position": "left", "onigiri_reviewer_progress_style": "ring"},
                       {"onigiri_reviewer_progress_enabled": False},
                       {"onigiri_reviewer_progress_enabled": True, "onigiri_reviewer_header_mode": "widgets"}):
            conf.update(change)
            env['refresh_reviewer_header_style'](conf)
    return env['scripts']


def tool_visibility_fixture():
    env = {'tr': lambda key, fallback='': fallback}
    load('settings_web/schema.py', {'_tool_visibility_section'}, env)
    load('settings_web/render.py', {'_serialize_field', '_camel'}, env)
    pages = []
    for tool, title, header in (('hashi_notes', 'Hashi Notes', 'hashi_show_header'),
                                ('pomodoro', 'Pomodoro', 'pomodoro_show_header')):
        section = env['_tool_visibility_section'](tool, title, header)
        defaults = {f['id']: f.get('default') for f in section['fields']}
        store = types.SimpleNamespace(read=lambda id: defaults[id])
        section['fields'] = [env['_serialize_field'](store, f) for f in section['fields']]
        pages.append({'id': tool, 'title': title, 'sections': [section]})
    runtime = runtime_env()
    runtime['tr_at'] = lambda key: key
    load('rendering/patcher.py', {'_study_tool_header_buttons', 'refresh_study_tool_reviewer_buttons'}, runtime)
    visibility = types.ModuleType('header_test.core.study_tool_visibility')
    exec((ROOT / 'core/study_tool_visibility.py').read_text(), visibility.__dict__)
    with patch.dict(sys.modules, {visibility.__name__: visibility}):
        for hashi, pomodoro in ((True, True), (False, True), (False, False), (True, True)):
            runtime['refresh_study_tool_reviewer_buttons']({
                'hashi_notes': {'show_in_reviewer_header': hashi},
                'onigiri_pomodoro_show_in_reviewer_header': pomodoro})
    return {'pages': pages, 'scripts': runtime['scripts']}


class ReviewerHeaderTests(unittest.TestCase):
    def test_old_progress_fields_and_saved_keys_are_preserved(self):
        section = header_schema()
        self.assertEqual(section['id'], 'reviewer_progress')
        self.assertEqual(section['title'], 'Header Customization')
        fields = {f['id']: f for f in section['fields']}
        self.assertEqual(len(fields), len(section['fields']))
        self.assertEqual(fields['rprog_enabled']['bind']['key'], 'onigiri_reviewer_progress_enabled')
        self.assertEqual(fields['rprog_style']['default'], 'bar')
        self.assertEqual(fields['rheader_mode']['default'], 'widgets')
        self.assertEqual(fields['onigiri_font_reviewer_header']['bind']['key'], 'onigiri_font_reviewer_header')
        self.assertNotIn('onigiri_font_reviewer_controls', fields)
        self.assertEqual(fields['hashi_show_header']['bind']['path'], ['hashi_notes', 'show_in_reviewer_header'])
        self.assertEqual(fields['pomodoro_show_header']['bind']['key'], 'onigiri_pomodoro_show_in_reviewer_header')
        self.assertFalse(fields['hashi_show_header']['head'])
        self.assertFalse(fields['pomodoro_show_header']['head'])
        self.assertEqual(len(section['color_groups']), 1)
        self.assertEqual(section['color_groups'][0]['field_ids'],
                         ['rheader_bg', 'rheader_text', 'rheader_hover_bg', 'rheader_hover_text', 'rheader_border'])
        for family in ('decks', 'add', 'browse', 'stats', 'sync', 'hashi', 'pomodoro'):
            self.assertFalse(any(id.startswith('rheader_' + family + '_') for id in fields))
        for color in ('bg', 'text', 'hover_bg', 'hover_text', 'border'):
            for mode in ('light', 'dark'):
                self.assertEqual(fields[f'rheader_{color}_{mode}']['bind']['path'],
                                 [f'onigiri_reviewer_header_{color}_{mode}'])

    def test_opacity_zero_keeps_text_and_rgba_alpha_is_preserved(self):
        css = runtime_css({'onigiri_reviewer_header_mode': 'custom', 'onigiri_reviewer_header_opacity': 0,
                           'onigiri_reviewer_header_radius': 0, 'onigiri_reviewer_header_padding': 0})
        self.assertIn('--rh-bg: rgba(255, 255, 255, 0.0)', css)
        self.assertIn('--rh-text: #2c2c2c', css)
        self.assertIn('--rh-radius: 0px', css)
        self.assertNotIn('opacity: 0', css)
        css = runtime_css({'onigiri_reviewer_header_mode': 'custom', 'onigiri_reviewer_header_opacity': 50,
                           'onigiri_reviewer_header_bg_light': 'rgba(100, 120, 140, 0.4)'})
        self.assertIn('--rh-bg: rgba(100, 120, 140, 0.2)', css)

    def test_shared_theme_link_ignores_saved_individual_overrides(self):
        conf = {'onigiri_reviewer_header_mode': 'custom',
                'onigiri_reviewer_header_bg_light': '#123456',
                'onigiri_web_rheader_bg_theme_mode': 'single',
                'onigiri_reviewer_header_decks_bg_light': '#abcdef',
                'onigiri_reviewer_header_decks_bg_dark': '#fedcba',
                'onigiri_reviewer_header_add_hover_bg_light': '#abcdef',
                'onigiri_web_rheader_add_bg_theme_mode': 'single'}
        css = runtime_css(conf)
        self.assertEqual(css.count('--rh-bg: rgba(18, 52, 86, 1.0)'), 2)
        self.assertNotIn('--rh-button-', css)
        self.assertNotIn('171, 205, 239', css)
        self.assertNotIn('#abcdef', css)
        self.assertEqual(conf['onigiri_reviewer_header_decks_bg_light'], '#abcdef')
        css = runtime_css({'onigiri_reviewer_header_mode': 'widgets'})
        self.assertNotIn('--rh-bg:', css)

    def test_header_font_is_independent_and_missing_font_falls_back(self):
        css = runtime_css({}, {'onigiri_font_reviewer_header': 'mono', 'onigiri_font_size_reviewer_header': 23,
                              'onigiri_font_reviewer_controls': 'system', 'onigiri_font_size_reviewer_controls': 40,
                              'onigiri_font_reviewer_header_color_dark': '#123456'})
        self.assertIn('--rh-font-family: monospace; --rh-font-size: 23px;', css)
        self.assertIn('system_files/fonts/system_fonts/mono.ttf', css)
        self.assertIn('--rh-text: #123456', css)
        self.assertNotIn('40px', css)
        self.assertIn('--rh-font-family: Poppins', runtime_css({}, {'onigiri_font_reviewer_header': 'deleted'}))

    def test_header_customization_is_only_in_reviewer_and_keeps_actions(self):
        conf = {'hideNativeHeaderAndBottomBar': True}
        env = runtime_env(conf)
        env.update(_study_tool_header_buttons=lambda _: ('', ''),
                   _reviewer_progress_settings=lambda *a, **k: {'enabled': False, 'position': 'right'})
        with patch.dict(sys.modules, {env['font_module'].__name__: env['font_module']}):
            env['tr_at'] = lambda key: key
            reviewer, css = env['generate_reviewer_top_bar_html_and_css'](False)
            overview, ov_css = env['generate_reviewer_top_bar_html_and_css'](True)
        for action in ('decks', 'add', 'browse', 'stats', 'sync'):
            self.assertIn(f'data-header-button="{action}"', reviewer)
            self.assertIn(f"pycmd('{action}')", reviewer)
        self.assertIn('onigiri-reviewer-header-customization', css)
        self.assertNotIn('onigiri-header-customization', overview)
        self.assertNotIn('onigiri-reviewer-header-customization', ov_css)


if __name__ == '__main__':
    if '--visibility-fixture' in sys.argv:
        print(json.dumps(tool_visibility_fixture()))
    elif '--refresh-fixture' in sys.argv:
        print(json.dumps(live_refresh_fixture()))
    elif '--fixture' in sys.argv:
        print(json.dumps(header_schema(True)))
    else:
        unittest.main()
