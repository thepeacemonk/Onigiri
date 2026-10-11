"""Upgrade persistence tests. Every write is confined to TemporaryDirectory."""
import ast
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, source):
    if source.name == 'gamification.py':
        name = 'upgrade_test_addon.gamification.' + name.rsplit('.', 1)[-1]
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ProgressUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'addons21' / 'onigiri'
        self.files = self.root / 'user_files'
        self.files.mkdir(parents=True)
        self.mw = types.SimpleNamespace(
            pm=types.SimpleNamespace(name='Upgrade', base=self.temp.name),
            col=types.SimpleNamespace(conf={}),
            addonManager=types.SimpleNamespace(getConfig=lambda _: {}, addonFromModule=lambda _: 'onigiri'),
        )
        package = types.ModuleType('upgrade_test_addon')
        package.__path__ = [str(ROOT)]
        aqt = types.ModuleType('aqt')
        aqt.mw = self.mw
        aqt.gui_hooks = types.SimpleNamespace(profile_did_open=[])
        self.modules = patch.dict(sys.modules, {'aqt': aqt, 'upgrade_test_addon': package})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.storage = load_module('upgrade_test_addon.core.safe_storage', ROOT / 'core/safe_storage.py')
        self.storage.__file__ = str(self.root / 'core/safe_storage.py')
        self.config = load_module('upgrade_test_addon.core.config', ROOT / 'core/config.py')
        self.config.__file__ = str(self.root / 'core/config.py')
        self.games = load_module('upgrade_test_addon.games', ROOT / 'gamification/gamification.py')

    def write(self, filename, data):
        path = self.files / filename
        path.write_text(json.dumps(data))
        return path

    def test_real_earlier_writers_survive_current_load_save_and_reload(self):
        for folder in ('Onigiri (old version)', 'Onigiri (middle)'):
            with self.subTest(version=folder):
                old = load_module('upgrade_test_addon.legacy_game', ROOT / folder / 'gamification/gamification.py')
                manager = old.GamificationData(str(self.root))
                manager.restaurant_data = old.RestaurantLevelData(
                    daily_special={'current_progress': 73, 'completed': True},
                    total_xp=14723, level=18, taiyaki_coins=739,
                    owned_items=['default', 'sushi', 'focus_dango'],
                    current_theme_id='sushi', name='My restaurant', migrated=True,
                    enabled=True, notifications_enabled=False,
                )
                manager.achievements = {'earned': old.AchievementData(
                    id='earned', name='Earned', description='Completed', category='review',
                    unlocked=True, progress=1000, threshold=1000, count=3,
                )}
                manager.daily_specials = [old.DailySpecialData(
                    id='rush', name='Lunch', difficulty='hard', target_cards=100,
                    completed=True, cards_completed=100, xp_earned=300,
                )]
                manager.save()
                path = self.files / 'gamification_Upgrade.json'
                original = json.loads(path.read_text())
                original['extension'] = {'keep': True}
                original['restaurant_level']['_security_token'] = hashlib.sha256(b'739:onigiri_secret_salt_2024').hexdigest()
                original['restaurant_level']['legacy_metadata'] = 'keep'
                path.write_text(json.dumps(original))
                current = self.games.GamificationData(str(self.root))
                current.save(immediate=True)
                saved = json.loads(path.read_text())
                for key in ('achievements', 'daily_specials', 'restaurant_level', 'extension'):
                    self.assertEqual(saved[key], original[key])
                reloaded = self.games.GamificationData(str(self.root))
                self.assertEqual(reloaded.get_restaurant_data()['taiyaki_coins'], 739)
                current.update_restaurant_data({'taiyaki_coins': 800}, immediate=True)
                self.assertEqual(json.loads(path.read_text())['restaurant_level']['_security_token'],
                                 hashlib.sha256(b'800:onigiri_secret_salt_2024').hexdigest())

    def test_real_earlier_settings_writers_preserve_saved_progress(self):
        for folder in ('Onigiri (old version)', 'Onigiri (middle)'):
            with self.subTest(version=folder):
                old = load_module('upgrade_test_addon.legacy_config', ROOT / folder / 'config.py')
                old.__file__ = str(self.root / 'config.py')
                saved = copy.deepcopy(old.DEFAULTS)
                saved['restaurant_level'].update(total_xp=18000, level=23, name='My restaurant')
                saved['achievements']['earned'] = {'milestone': {'unlocked': True, 'count': 3}}
                saved['achievements']['history'] = [{'id': 'milestone', 'date': '2026-09-01'}]
                saved['achievements']['custom_goals']['daily']['completion_count'] = 17
                saved['userName'] = 'Existing learner'
                old.write_config(saved)
                self.config.invalidate_config_cache()
                loaded = self.config.get_config()
                for key in ('total_xp', 'level', 'name'):
                    self.assertEqual(loaded['restaurant_level'][key], saved['restaurant_level'][key])
                for key in ('earned', 'history', 'custom_goals'):
                    self.assertEqual(loaded['achievements'][key], saved['achievements'][key])
                self.assertEqual(loaded['userName'], 'Existing learner')
                self.config.write_config(loaded)
                self.assertEqual(self.config.get_config()['achievements']['earned'], saved['achievements']['earned'])

    def test_settings_coins_transfer_before_cleanup_and_current_zero_wins(self):
        for saved_coins in (None, 0, 99):
            with self.subTest(saved_coins=saved_coins):
                game_path = self.files / 'gamification_Upgrade.json'
                for file in self.files.glob('gamification*'):
                    file.unlink()
                self.write('settings_Upgrade.json', {'achievements': {'restaurant_level': {
                    'taiyaki_coins': 420, 'total_xp': 1234, 'owned_items': ['default', 'sushi'],
                }}})
                if saved_coins is not None:
                    self.write(game_path.name, {'restaurant_level': {'taiyaki_coins': saved_coins}})
                conf = self.config._build_config()
                self.assertNotIn('taiyaki_coins', conf['restaurant_level'])
                self.assertEqual(json.loads(game_path.read_text())['restaurant_level']['taiyaki_coins'],
                                 420 if saved_coins is None else saved_coins)
                self.assertEqual(conf['restaurant_level']['total_xp'], 1234)

    def test_legacy_shared_game_is_adopted_before_config_coin_transfer(self):
        self.write('gamification.json', {'restaurant_level': {'taiyaki_coins': 87, 'total_xp': 12345}})
        self.write('settings_Upgrade.json', {'restaurant_level': {'taiyaki_coins': 999}})
        self.config._build_config()
        saved = json.loads((self.files / 'gamification_Upgrade.json').read_text())
        self.assertEqual(saved['restaurant_level'], {'taiyaki_coins': 87, 'total_xp': 12345})

    def test_failed_coin_transfer_keeps_legacy_source(self):
        self.write('settings_Upgrade.json', {'restaurant_level': {'taiyaki_coins': 420}})
        with patch.object(self.storage, 'atomic_write_json', return_value=False):
            self.assertEqual(self.config._build_config()['restaurant_level']['taiyaki_coins'], 420)

    def test_explicit_current_settings_win_over_stale_nested_settings(self):
        self.write('settings_Upgrade.json', {
            'restaurant_level': {'total_xp': 900, 'enabled': False},
            'achievements': {'restaurant_level': {'total_xp': 800, 'enabled': True, 'owned_items': ['sushi']}},
        })
        conf = self.config._build_config()
        self.assertEqual(conf['restaurant_level']['total_xp'], 900)
        self.assertFalse(conf['restaurant_level']['enabled'])
        self.assertEqual(conf['restaurant_level']['owned_items'], ['sushi'])

    def test_purchase_and_theme_migration_does_not_require_higher_xp(self):
        tree = ast.parse((ROOT / 'gamification/nook_level.py').read_text())
        method = next(n for c in tree.body if isinstance(c, ast.ClassDef)
                      for n in c.body if isinstance(n, ast.FunctionDef) and n.name == 'get_progress')
        namespace = {'config': types.SimpleNamespace(get_config_readonly=lambda: {
            'restaurant_level': {'total_xp': 10, 'owned_items': ['sushi'],
                                 'current_theme_id': 'sushi', 'name': 'My restaurant'}}),
                     'tr': lambda key, default: default, 'LevelProgress': lambda **kw: kw}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'nook_level.py', 'exec'), namespace)
        state = {'total_xp': 1000, 'level': 5, 'owned_items': ['default'],
                 'current_theme_id': 'default', 'name': 'Nook Level', 'migrated': False}
        writes = []
        def update(changes, immediate=False):
            writes.append(immediate)
            state.update(changes)
        manager = types.SimpleNamespace(_get_gamification_state=lambda: state,
                    _update_gamification_data=update, _collapse_xp=lambda xp: (5, 1, 10))
        namespace['get_progress'](manager)
        self.assertEqual(state['total_xp'], 1000)
        self.assertEqual(state['owned_items'], ['default', 'sushi'])
        self.assertEqual(state['current_theme_id'], 'sushi')
        self.assertEqual(state['name'], 'My restaurant')
        namespace['get_progress'](manager)
        self.assertEqual(writes, [True])

    def test_baseline_archive_keeps_original_assets_and_all_profiles(self):
        self.write('gamification_Upgrade.json', {'restaurant_level': {'total_xp': 500}})
        self.write('gamification_Second.json', {'restaurant_level': {'total_xp': 700}})
        assets = self.files / 'profile'
        assets.mkdir()
        (assets / 'avatar.png').write_bytes(b'original avatar')
        archive_path = self.storage.backup_before_upgrade({'legacy': True})
        self.write('gamification_Upgrade.json', {'restaurant_level': {'total_xp': 999}})
        self.storage.backup_before_upgrade({})
        with zipfile.ZipFile(archive_path) as archive:
            self.assertEqual(json.loads(archive.read('user_files/gamification_Upgrade.json'))['restaurant_level']['total_xp'], 500)
            self.assertIn('user_files/gamification_Second.json', archive.namelist())
            self.assertEqual(archive.read('user_files/profile/avatar.png'), b'original avatar')
            self.assertEqual(json.loads(archive.read('legacy_addon_config.json')), {'legacy': True})

    def test_backup_recovery_for_corrupt_or_missing_game_saves(self):
        for filename in ('gamification_Upgrade.json', 'hexagon_land_Upgrade.json', 'onigimon_Upgrade.json'):
            with self.subTest(filename=filename):
                path = str(self.files / filename)
                original = {'coins': 800, 'inventory': {'item': 3}}
                self.storage.atomic_write_json(path, original)
                Path(path).write_text('{broken')
                self.assertEqual(self.storage.read_json(path), original)
                Path(path).unlink()
                self.assertEqual(self.storage.read_json(path), original)

    def test_all_earlier_game_state_fields_still_exist(self):
        def fields(path, name):
            tree = ast.parse(path.read_text())
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
            return {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)}
        for folder in ('Onigiri (old version)', 'Onigiri (middle)'):
            for filename, names in (
                ('gamification/gamification.py', ('AchievementData', 'DailySpecialData', 'RestaurantLevelData')),
                ('gamification/onigimon.py', ('OnigimonState',)),
                ('gamification/hexagon_land.py', ('HexagonLandState',)),
            ):
                old = ROOT / folder / filename
                if not old.exists():
                    continue
                for name in names:
                    with self.subTest(version=folder, state=name):
                        self.assertLessEqual(fields(old, name), fields(ROOT / filename, name))

    def test_middle_game_loaders_recover_and_keep_inventory_and_island(self):
        # Execute the production state classes and load/save methods while
        # omitting UI imports. Only Qt, profile lookup and tile rendering are
        # replaced; persistence goes through the real storage implementation.
        for filename, state_name, manager_name, payload, prefix in (
            ('onigimon.py', 'OnigimonState', 'OnigimonManager', {
                'active_companion_id': 'pokemon-123',
                'companions': {'pokemon-123': {'name': 'Partner', 'hp': 73}},
                'inventory': {'berry_oran': 17}, 'comet_shards': 870,
                'star_pieces': 23, 'current_streak': 8,
                'market_purchased': ['gift'], 'today_review_count': 91,
            }, 'onigimon'),
            ('hexagon_land.py', 'HexagonLandState', 'HexagonLandManager', {
                'hex_coins': 870, 'pending_hex_coins': 45, 'hex_coin_fraction': 0.7,
                'materials': {'wood': 25, 'stone': 19, 'sand': 9, 'crystal': 3},
                'pending_materials': {'wood': 3}, 'keys_of_the_island': True,
                'island_name': 'My island', 'lifetime_reviews': 10000,
                'tiles': {'0,0': {'terrain': 'grass', 'height': 2, 'parts': [{'id': 'tree_green'}]}},
                'current_streak': 8,
            }, 'hexagon_land'),
        ):
            with self.subTest(game=prefix):
                source = ast.parse((ROOT / 'gamification' / filename).read_text())
                state = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == state_name)
                manager = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == manager_name)
                methods = [n for n in manager.body if isinstance(n, ast.FunctionDef) and n.name in ('load', 'save')]
                manager = ast.ClassDef(name='Manager', bases=[], keywords=[], body=methods, decorator_list=[])
                namespace = dict(globals(), safe_storage=self.storage, ITEMS={}, RESOURCE_KEYS=('wood', 'stone', 'sand', 'crystal'),
                                 _normalize_tile_spots=lambda tile: None, _anki_today=date.today)
                exec(compile(ast.fix_missing_locations(ast.Module(body=[state, manager], type_ignores=[])), filename, 'exec'), namespace)
                path = self.write(f'{prefix}_Upgrade.json.bak', payload)
                target = str(path)[:-4]
                obj = namespace['Manager']()
                obj._state = None
                obj._state_cache = None
                obj._data_path_cache = None
                obj._data_path = lambda: target
                obj.data_path = lambda: target
                result = obj.load()
                for key, value in payload.items():
                    self.assertEqual(getattr(result, key), value)
                if prefix == 'onigimon':
                    obj.save(immediate=True)
                else:
                    obj.save(result)
                saved = json.loads(Path(target).read_text())
                for key, value in payload.items():
                    self.assertEqual(saved[key], value)

    def test_middle_study_tools_read_existing_collection_data(self):
        for filename, function, constant, saved in (
            ('prep_station.py', '_get_plans', 'PREP_STATION_CONF_KEY', [{'id': 'plan-1', 'name': 'Exam', 'deck_ids': [123]}]),
            ('hashi_notes.py', '_read_all', 'CONF_KEY', [{'id': 'note-1', 'body_md': 'Saved notes', 'created_at': '2026-09-01'}]),
            ('pomodoro.py', 'get_sessions', 'SESSIONS_CONF_KEY', [{'id': 'session-1', 'actual_minutes': 25, 'type': 'focus'}]),
        ):
            with self.subTest(tool=filename):
                def nodes(path):
                    tree = ast.parse(path.read_text())
                    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                                      and any(isinstance(t, ast.Name) and t.id == constant for t in n.targets))
                    reader = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
                    return assignment, reader
                old_assignment, _ = nodes(ROOT / 'Onigiri (middle)' / filename)
                assignment, reader = nodes(ROOT / 'study_tools' / filename)
                self.assertEqual(ast.literal_eval(old_assignment.value), ast.literal_eval(assignment.value))
                self.mw.col.conf[ast.literal_eval(old_assignment.value)] = copy.deepcopy(saved)
                namespace = {'mw': self.mw}
                exec(compile(ast.Module(body=[assignment, reader], type_ignores=[]), filename, 'exec'), namespace)
                self.assertEqual(namespace[function](), saved)


if __name__ == '__main__':
    unittest.main()
