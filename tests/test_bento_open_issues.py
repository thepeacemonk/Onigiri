"""Behavioral regressions for open Bento issues; no live profile is loaded."""
import ast
import html
import json
import os
import re
import sys
import types
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def functions(file, names, env):
    tree = ast.parse((ROOT / file).read_text())
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    body.insert(0, ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0))
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, file, 'exec'), env)


class OpenBentoIssueTests(unittest.TestCase):
    def handler_env(self):
        class DeckBrowser:
            def __init__(self):
                self.refreshes = 0
                self.menus = []
            def show(self):
                self.refreshes += 1
            def _showOptions(self, did):
                self.menus.append(did)
        saved = {'onigiri_custom_deck_icons': {'old': {'icon': 'star.svg'}}}
        errors = []
        cfg = types.SimpleNamespace(get_collection_config=lambda k, default: saved.get(k, default),
                                    set_collection_config=lambda k, v: saved.update({k: v}))
        env = dict(config=cfg, json=json, DeckBrowser=DeckBrowser, tooltip=errors.append,
                   tr=lambda k: '{}', _refresh_deck_browser=lambda _: None,
                   unquote=__import__('urllib.parse', fromlist=['unquote']).unquote)
        functions('rendering/webview_handlers.py', {'handle_webview_cmd', '_icon_store_target'}, env)
        return env, DeckBrowser(), saved, errors

    def test_icon_save_then_reset_preserves_other_decks_and_dark_color(self):
        env, db, saved, errors = self.handler_env()
        payload = {'icon': 'system:folder.svg', 'color': '#123456', 'colorDark': '#abcdef'}
        result = env['handle_webview_cmd']((False, None), 'onigiri_icon_chooser_save:42:' + json.dumps(payload), db)
        self.assertEqual(result, (True, None))
        self.assertEqual(saved['onigiri_custom_deck_icons']['42'], {'icon': payload['icon'], 'color': '#123456', 'colorDark': '#abcdef'})
        self.assertEqual(saved['onigiri_custom_deck_icons']['old'], {'icon': 'star.svg'})
        env['handle_webview_cmd']((False, None), 'onigiri_icon_chooser_reset:42', db)
        self.assertEqual(saved['onigiri_custom_deck_icons'], {'old': {'icon': 'star.svg'}})
        self.assertEqual(errors, [])
        self.assertEqual(db.refreshes, 2)

    def test_tag_icon_save_keeps_encoded_colons_out_of_command_target(self):
        env, db, saved, errors = self.handler_env()
        cmd = 'onigiri_icon_chooser_save:tag~a%3Ab:' + json.dumps({'icon': 'emoji:🍙', 'color': '#123456'})
        env['handle_webview_cmd']((False, None), cmd, db)
        self.assertEqual(saved['onigiri_custom_tag_icons']['a:b'], {'icon': 'emoji:🍙', 'color': '#123456'})
        self.assertEqual(errors, [])

    def test_addon_actions_use_native_deck_menu_and_exact_deck(self):
        env, db, _, _ = self.handler_env()
        self.assertEqual(env['handle_webview_cmd']((False, None), 'onigiri_ctx_addon_actions:42', db), (True, None))
        self.assertEqual(db.menus, ['42'])

    def test_hidden_cached_and_deleted_editors_do_not_dim_dashboard(self):
        visible = types.SimpleNamespace(isVisible=lambda: True)
        hidden = types.SimpleNamespace(isVisible=lambda: False)
        class Editor:
            def isVisible(self):
                raise RuntimeError('wrapped object deleted')
        dialogs = types.SimpleNamespace(_dialogs={'AddCards': (None, hidden)})
        aqt = types.ModuleType('aqt'); aqt.dialogs = dialogs
        env = {'_active_card_editors': {Editor()}}
        functions('__init__.py', {'_is_card_editing_active'}, env)
        with patch.dict(sys.modules, {'aqt': aqt}):
            self.assertFalse(env['_is_card_editing_active']())
            dialogs._dialogs['AddCards'] = (None, visible)
            self.assertTrue(env['_is_card_editing_active']())
        css = (ROOT / 'web/menu.css').read_text()
        self.assertNotRegex(css, r'is-card-editing[^{}]*\{[^{}]*pointer-events:\s*none')

    def toolbar_env(self):
        class Entry:
            def __init__(self, **kw): self.__dict__.update(kw)
        env = dict(_registry={}, _toolbar_entry_ids=set(), _toolbar_cmds=set(),
                   _TOOLBAR_ENTRY_PREFIX='toolbar.', _TOOLBAR_CMD_BLACKLIST={'decks','add','browse','stats','sync'},
                   html=html, json=json, re=re, urllib=__import__('urllib.parse', fromlist=['parse']),
                   _ensure_layout_entry=lambda _: None, SidebarEntry=Entry,
                   _extract_icon_svg_from_html=lambda _: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>',
                   _refresh_reviewer_toolbar_entries=lambda: None)
        # urllib.parse is referenced by production.
        env['urllib'] = __import__('urllib'); __import__('urllib.parse')
        functions('api/sidebar.py', {'_extract_attr', '_extract_pycmd', '_label_from_html',
                  'register_sidebar_action', '_reset_toolbar_entries', '_capture_toolbar_links',
                  'render_reviewer_toolbar_entries', '_dispatch_toolbar_cmd'}, env)
        return env

    def test_external_toolbar_button_renders_and_dispatches_from_reviewer(self):
        env = self.toolbar_env()
        env['_capture_toolbar_links'](["<a onclick=\"return pycmd('decks')\">Decks</a>",
                     "<a title=\"AI Assistant\" onclick=\"return pycmd('ankiterminator')\">AI</a>"], None)
        rendered = env['render_reviewer_toolbar_entries']()
        self.assertIn('ankiterminator', rendered)
        self.assertIn('aria-label="AI Assistant"', rendered)
        self.assertNotIn('Decks', rendered)
        calls = []
        aqt = types.ModuleType('aqt')
        aqt.mw = types.SimpleNamespace(toolbar=types.SimpleNamespace(link_handlers={'ankiterminator': lambda: calls.append('AI')}))
        with patch.dict(sys.modules, {'aqt': aqt}):
            self.assertEqual(env['_dispatch_toolbar_cmd']((False, None), 'ankiterminator', object()), (True, None))
            env['_dispatch_toolbar_cmd']((True, None), 'ankiterminator', object())
        self.assertEqual(calls, ['AI'])
        env['_capture_toolbar_links']([], None)
        self.assertEqual(env['render_reviewer_toolbar_entries'](), '')

    def progression_manager(self, state, multiplier=4, backups=()):
        cfg = {'restaurant_level': {'enabled': True}, 'daily_special': {'enabled': False}}
        env = dict(config=types.SimpleNamespace(get_config_readonly=lambda: cfg),
                   tr=lambda key, fallback: fallback, XP_PER_REVIEW=5,
                   LevelProgress=lambda **kw: types.SimpleNamespace(**kw))
        tree = ast.parse((ROOT / 'gamification/nook_level.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and any(isinstance(m, ast.FunctionDef) and m.name == '_add_xp' for m in n.body))
        names = {'get_progress', '_ensure_progression_curve', '_collapse_xp', '_add_xp', '_xp_for_next'}
        body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        mini = ast.ClassDef(name='Manager', bases=[], keywords=[], body=body, decorator_list=[])
        mod = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), mini], type_ignores=[])
        ast.fix_missing_locations(mod)
        functions('gamification/nook_level.py', {'_curve_loss_recovery'}, env)
        exec(compile(mod, 'nook_level.py', 'exec'), env)
        manager = env['Manager']()
        writes = []
        def update(changes, immediate=False):
            state.update(changes); writes.append(dict(changes))
        manager._get_gamification_state = lambda: state
        manager._update_gamification_data = update
        manager._get_difficulty_multiplier = lambda: multiplier
        manager._get_coins_from_json = lambda: state['taiyaki_coins']
        manager._restaurant_conf_readonly = lambda: cfg['restaurant_level']
        manager._gamification_manager = types.SimpleNamespace(progression_backups=lambda: iter(backups))
        manager._create_level_up_notification = lambda _: []
        manager._addon_prefix = '/addon'
        return manager, writes

    def test_upgrade_keeps_level_98_and_coins_without_repeat_conversion(self):
        state = {'total_xp': 50 * 98 ** 2 + 150, 'level': 98, 'taiyaki_coins': 3500, 'migrated': True}
        manager, writes = self.progression_manager(state)
        self.assertEqual(manager.get_progress().level, 98)
        self.assertEqual(state['taiyaki_coins'], 3500)
        self.assertEqual(state['total_xp'], (50 * 98 ** 2 + 150) * 4)
        manager.get_progress()
        self.assertEqual(len(writes), 2)  # visibility defaults, then curve migration
        manager._add_xp(5, reason='review')
        self.assertEqual(state['level'], 98)
        self.assertEqual(state['taiyaki_coins'], 3500)

    def test_positive_xp_never_debits_coins_for_a_stale_level(self):
        state = {'total_xp': 480205, 'level': 98, 'taiyaki_coins': 3500, 'migrated': True, 'xp_multiplier': 4}
        manager, _ = self.progression_manager(state)
        manager._add_xp(5, reason='review')
        self.assertEqual(state['taiyaki_coins'], 3500)
        self.assertEqual(state['level'], 49)

    def test_real_level_up_and_undo_still_award_and_reverse_same_coins(self):
        state = {'total_xp': 195, 'level': 0, 'taiyaki_coins': 100, 'migrated': True, 'xp_multiplier': 4}
        manager, _ = self.progression_manager(state)
        manager._add_xp(5, reason='review')
        self.assertEqual((state['level'], state['taiyaki_coins']), (1, 105))
        manager._add_xp(-5, reason='undo')
        self.assertEqual((state['level'], state['taiyaki_coins']), (0, 100))

    def test_verified_snapshot_recovers_exact_curve_debt_and_keeps_other_data(self):
        previous = {'total_xp': 480200, 'level': 98, 'taiyaki_coins': 3500, 'owned_items': ['default','sushi']}
        deduction = 5 * (98 * 99 - 49 * 50) // 2
        state = dict(previous, total_xp=480205, level=49, taiyaki_coins=3500-deduction,
                     migrated=True, current_theme_id='sushi', daily_special={'completed': True})
        manager, writes = self.progression_manager(state, backups=[previous])
        self.assertEqual(manager.get_progress().level, 98)
        self.assertEqual(state['taiyaki_coins'], 3500)
        self.assertEqual(state['daily_special'], {'completed': True})
        self.assertEqual(state['owned_items'], ['default','sushi'])
        manager.get_progress()
        self.assertEqual(len(writes), 2)

    def test_multi_review_and_easy_curve_loss_recover_from_verified_snapshot(self):
        old = {'total_xp': 480200, 'level': 98, 'taiyaki_coins': 3500, 'owned_items': ['default']}
        deduction_49 = 5 * (98 * 99 - 49 * 50) // 2
        deduction_50 = 5 * (98 * 99 - 50 * 51) // 2
        # Case 1: Easy review (+10 XP) on first card.
        easy_state = dict(old, total_xp=480210, level=49, taiyaki_coins=3500 - deduction_49)
        manager, _ = self.progression_manager(easy_state, backups=[old])
        self.assertEqual(manager.get_progress().level, 98)
        self.assertEqual(easy_state['taiyaki_coins'], 3500)
        # Case 2: Multiple reviews after the downgrade that even leveled 49 -> 50,
        # and an earlier build already stamped xp_multiplier=4 while leaving negative coins.
        post_level_state = dict(old, total_xp=500000, level=50, taiyaki_coins=3500 - deduction_50, xp_multiplier=4)
        manager, _ = self.progression_manager(post_level_state, backups=[old])
        self.assertEqual(manager.get_progress().level, 98)
        self.assertEqual(post_level_state['taiyaki_coins'], 3500)

    def test_ambiguous_spending_or_review_history_is_not_recovered(self):
        old = {'total_xp': 480200, 'level': 98, 'taiyaki_coins': 3500, 'owned_items': ['default']}
        deduction = 5 * (98 * 99 - 49 * 50) // 2
        cases = [dict(old, total_xp=480205, level=49, taiyaki_coins=3500-deduction-50),
                 dict(old, total_xp=480205, level=49, taiyaki_coins=3500-deduction, owned_items=['default','sushi'])]
        for state in cases:
            with self.subTest(state=state):
                manager, _ = self.progression_manager(state, backups=[old])
                self.assertEqual(manager.get_progress().level, 49)
                # Ambiguous cases do not restore the old level/3500 balance,
                # and unrecoverable negative debt is clamped to 0.
                self.assertEqual(state['taiyaki_coins'], 0)

    def test_scoped_fonts_read_supported_config_and_keep_poppins_faces(self):
        saved = {'onigiri_font_main': 'custom', 'onigiri_font_size_main': 23}
        module = types.ModuleType('bento_test.ui_kit.fonts')
        module.FONTS = {'system': {'family': 'Poppins', 'file': None}, 'custom': {'family': 'Custom Font', 'file': 'custom.ttf', 'user': True}}
        module.get_all_fonts = lambda _: module.FONTS
        module.poppins_font_face_css = lambda _: "@font-face {font-family:'Poppins';src:url('poppins.ttf');}"
        env = dict(__package__='bento_test.rendering', __file__=str(ROOT / 'rendering/patcher.py'), os=os,
                   config=types.SimpleNamespace(get_collection_config=lambda k, d: saved.get(k,d)))
        functions('rendering/patcher.py', {'generate_scoped_main_font_css', 'generate_reviewer_font_css'}, env)
        with patch.dict(sys.modules, {module.__name__: module}):
            css = env['generate_scoped_main_font_css']('test', '#header')
            bottom = env['generate_reviewer_font_css']('test')
        self.assertIn('Poppins', css)
        self.assertIn('/user_files/fonts/custom.ttf', css)
        self.assertIn('--font-size-main: 23px', css)
        self.assertIn('font-size: 23px', bottom)

    def test_independent_sidebar_runtime_keeps_images_when_effects_are_synced(self):
        from test_background_matching import BackgroundMatchingTests
        fixture = BackgroundMatchingTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for palette in fixture.env['config'].DEFAULTS['colors'].values():
            palette['--profile-page-bg'] = '#aaaaaa'
        functions('rendering/patcher.py', {'generate_deck_browser_backgrounds', '_hex_to_rgba', '_mix_colors', '_render_background_css'}, fixture.env)
        for mode in ('image', 'image_color'):
            for sync in (True, False):
                with self.subTest(mode=mode, sync=sync):
                    fixture.main.update(modern_menu_sidebar_bg_mode='independent', modern_menu_sidebar_bg_type=mode,
                                        modern_menu_sidebar_sync_box_effect=sync,
                                        modern_menu_sidebar_bg_image_theme_mode='single',
                                        modern_menu_sidebar_bg_image='sidebar.png')
                    css = fixture.env['generate_deck_browser_backgrounds'](str(ROOT))
                    self.assertIn('/sidebar_bg/sidebar.png', css)
                    style = re.search(r"<style id=['\"]modern-menu-sidebar-background-style['\"]>(.*?)</style>", css, re.S).group(1)
                    if mode == 'image':
                        self.assertIn('background: transparent', style)
                        self.assertNotIn('background-color:', style)
        fixture.main.update(modern_menu_sidebar_bg_image_theme_mode='separate',
                            modern_menu_sidebar_bg_image_light='', modern_menu_sidebar_bg_image_dark='')
        css = fixture.env['generate_deck_browser_backgrounds'](str(ROOT))
        self.assertIn('/sidebar_bg/sidebar.png', css)

    def test_profile_backup_evidence_and_curve_marker_survive_reload(self):
        from test_progress_upgrade import ProgressUpgradeTests
        fixture = ProgressUpgradeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        old = {'total_xp': 480200, 'level': 98, 'taiyaki_coins': 3500, 'metadata': 'keep'}
        fixture.write('gamification_Upgrade.json', {'restaurant_level': old, 'extension': {'keep': True}})
        data = fixture.games.GamificationData(str(fixture.root))
        data.update_restaurant_data({'level': 49, 'total_xp': 480205, 'taiyaki_coins': -14630}, immediate=True)
        self.assertIn(old, list(data.progression_backups()))
        data.update_restaurant_data({'level': 98, 'total_xp': 1920820, 'taiyaki_coins': 3500, 'xp_multiplier': 4}, immediate=True)
        reloaded = fixture.games.GamificationData(str(fixture.root))
        self.assertEqual(reloaded.get_restaurant_data()['xp_multiplier'], 4)
        saved = json.loads((fixture.files / 'gamification_Upgrade.json').read_text())
        self.assertEqual(saved['restaurant_level']['metadata'], 'keep')
        self.assertEqual(saved['extension'], {'keep': True})


if __name__ == '__main__': unittest.main()
