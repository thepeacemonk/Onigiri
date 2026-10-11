"""Upgrade persistence tests. Every write is confined to TemporaryDirectory."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
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

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_real_earlier_writers_survive_current_load_save_and_reload(self):
        for folder in ('Onigiri(Original)', 'Onigiri(Middle)'):
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
                original['achievements'][0]['legacy_metadata'] = {'keep': True}
                original['daily_specials'][0]['legacy_metadata'] = {'keep': True}
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

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_real_earlier_settings_writers_preserve_saved_progress(self):
        for folder in ('Onigiri(Original)', 'Onigiri(Middle)'):
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

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_all_earlier_game_state_fields_still_exist(self):
        def fields(path, name):
            tree = ast.parse(path.read_text())
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
            return {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)}
        for folder in ('Onigiri(Original)', 'Onigiri(Middle)'):
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
                payload = dict(payload, legacy_metadata={'keep': True})
                if prefix == 'onigimon':
                    payload.update(last_pet_day='2026-09-01', pets_used_today=4)
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
                    if hasattr(result, key):
                        self.assertEqual(getattr(result, key), value)
                if prefix == 'onigimon':
                    obj.save(immediate=True)
                else:
                    obj.save(result)
                saved = json.loads(Path(target).read_text())
                for key, value in payload.items():
                    self.assertEqual(saved[key], value)

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
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
                old_assignment, _ = nodes(ROOT / 'Onigiri(Middle)' / filename)
                assignment, reader = nodes(ROOT / 'study_tools' / filename)
                self.assertEqual(ast.literal_eval(old_assignment.value), ast.literal_eval(assignment.value))
                self.mw.col.conf[ast.literal_eval(old_assignment.value)] = copy.deepcopy(saved)
                namespace = {'mw': self.mw}
                exec(compile(ast.Module(body=[assignment, reader], type_ignores=[]), filename, 'exec'), namespace)
                self.assertEqual(namespace[function](), saved)

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_saved_palettes_are_preserved_even_when_equal_to_old_defaults(self):
        for folder in ('Onigiri(Original)', 'Onigiri(Middle)'):
            with self.subTest(version=folder):
                old = load_module('upgrade_test_addon.legacy_config', ROOT / folder / 'config.py')
                saved = copy.deepcopy(old.DEFAULTS)
                self.write('settings_Upgrade.json', saved)
                loaded = self.config._build_config()
                for key in ('colors', 'overview_style'):
                    if key not in saved:
                        continue
                    def check_values(source, target):
                        for name, value in source.items():
                            if isinstance(value, dict):
                                check_values(value, target[name])
                            else:
                                self.assertEqual(target[name], value, name)
                    check_values(saved[key], loaded[key])

    def test_empty_primary_is_an_intentional_clear_not_a_restore_trigger(self):
        for cleared, previous in (({}, {'coins': 90}), ([], [{'id': 'deleted'}])):
            with self.subTest(cleared=cleared):
                path = str(self.write('cleared.json', cleared))
                self.write('cleared.json.bak', previous)
                self.assertEqual(self.storage.read_json(path, default=cleared), cleared)

    def test_valid_but_wrong_json_type_recovers_the_backup(self):
        path = str(self.write('settings_Upgrade.json', ['wrong shape']))
        expected = {'userName': 'Existing learner'}
        self.write('settings_Upgrade.json.bak', expected)
        self.assertEqual(self.storage.read_json(path, default={}), expected)
        self.assertEqual(json.loads(Path(path).read_text()), expected)

    def test_empty_settings_do_not_import_another_legacy_setup(self):
        self.write('settings_Upgrade.json', {})
        self.mw.addonManager.getConfig = lambda _: {'userName': 'Stale shared setup'}
        self.assertEqual(self.config._build_config()['userName'], 'USER')

    def test_delayed_write_cannot_overwrite_an_immediate_purchase(self):
        self.mw.progress = types.SimpleNamespace(single_shot=lambda *args: None)
        path = str(self.files / 'gamification_Upgrade.json')
        data = {'coins': 90, 'owned': []}
        self.storage.schedule_write_json(path, data)
        data['coins'] = 0
        self.assertEqual(self.storage.pending_payload(path)['coins'], 90)
        self.storage.atomic_write_json(path, {'coins': 30, 'owned': ['purchase']})
        self.storage.flush_pending()
        self.assertEqual(json.loads(Path(path).read_text()), {'coins': 30, 'owned': ['purchase']})

    def test_failed_delayed_write_is_kept_until_a_successful_retry(self):
        self.mw.progress = types.SimpleNamespace(single_shot=lambda *args: None)
        path = str(self.files / 'gamification_Upgrade.json')
        data = {'coins': 91}
        self.storage.schedule_write_json(path, data)
        with patch.object(self.storage.os, 'replace', side_effect=OSError('disk unavailable')):
            self.assertFalse(self.storage.flush_pending())
        self.assertEqual(self.storage.pending_payload(path), data)
        self.assertTrue(self.storage.flush_pending())
        self.assertEqual(json.loads(Path(path).read_text()), data)

    def test_snapshot_identity_includes_the_parent_folder(self):
        for folder, data in (('prep_station', [{'id': 'plan'}]), ('pomodoro', [{'id': 'timer'}])):
            directory = self.files / folder
            directory.mkdir()
            path = str(directory / 'sessions.json')
            self.storage.atomic_write_json(path, data)
            Path(path).unlink()
            Path(path + '.bak').unlink()
        for folder, data in (('prep_station', [{'id': 'plan'}]), ('pomodoro', [{'id': 'timer'}])):
            self.assertEqual(self.storage.read_json(str(self.files / folder / 'sessions.json'), default=[]), data)

    def test_mirror_recovers_all_imported_assets_and_pending_redemptions(self):
        original = {}
        for relative in ('profile/avatar.png', 'profile_bg/cover.png', 'main_bg/wall.png',
                         'fonts/My Font.ttf', 'icons/custom.svg', 'pomodoro_sounds/custom.wav',
                         'prep_station_bg/exam.png', 'onigimon_backgrounds/scene.png',
                         'nested/user_themes/theme/asset.png', 'ankimon.db', 'redemption_requests.json'):
            path = self.files / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = b'{"code":"stable-id"}' if relative.endswith('.json') else relative.encode()
            path.write_bytes(data)
            original[relative] = data
        self.storage.mirror_all()
        shutil.rmtree(self.files)
        self.assertEqual(self.storage.restore_from_mirror(), len(original))
        for relative, data in original.items():
            self.assertEqual((self.files / relative).read_bytes(), data)

    def test_corrupt_file_never_overwrites_a_healthy_mirror(self):
        path = str(self.files / 'settings_Upgrade.json')
        self.storage.atomic_write_json(path, {'userName': 'Learner'})
        mirror = Path(self.storage._mirror_path_for(path))
        Path(path).write_text('{broken')
        self.storage.mirror_all()
        self.assertEqual(json.loads(mirror.read_text()), {'userName': 'Learner'})

    def test_collection_backup_is_immutable_and_separate_for_each_profile(self):
        self.mw.col.conf = {'onigiri_hashi_notes': [{'id': 'one', 'body_md': 'My notes'}],
                            'modern_menu_profile_bg_image': 'cover.png', 'unrelated': 42}
        self.storage.backup_before_upgrade({'old': True})
        self.mw.col.conf['onigiri_hashi_notes'] = []
        self.storage.backup_before_upgrade({})
        self.mw.pm.name = 'Second'
        self.mw.col.conf = {'onigiri_prep_station_plans': [{'id': 'two'}]}
        self.storage.backup_before_upgrade({})
        backups = [json.loads(path.read_text()) for path in Path(self.storage.external_backup_dir()).glob('before_progress_upgrade_v2_*.json')]
        by_profile = {data['profile']: data['collection_config'] for data in backups}
        self.assertEqual(by_profile['Upgrade']['onigiri_hashi_notes'][0]['body_md'], 'My notes')
        self.assertEqual(by_profile['Second']['onigiri_prep_station_plans'][0]['id'], 'two')

    def modern_collection(self, values):
        class ConfigManager:
            def __contains__(self, key):
                return key in values
            def get(self, key, default=None):
                return values.get(key, default)
            def __getitem__(self, key):
                if not isinstance(key, str):
                    raise TypeError('bad argument type for built-in operation')
                return values[key]
        return types.SimpleNamespace(conf=ConfigManager(), all_config=lambda: copy.deepcopy(values))

    def test_modern_anki_config_manager_backup_uses_all_config(self):
        values = {'onigiri_hashi_notes': [{'body_md': 'Keep my notes'}], 'unrelated': 42}
        self.mw.col = self.modern_collection(values)
        with self.assertRaisesRegex(TypeError, 'bad argument type'):
            dict(self.mw.col.conf)
        self.assertIsNotNone(self.storage.backup_before_upgrade())
        path = next(Path(self.storage.external_backup_dir()).glob('before_progress_upgrade_v2_*.json'))
        self.assertEqual(json.loads(path.read_text())['collection_config'], values)
        self.assertEqual(self.storage.take_notices(), [])

    def test_collection_export_is_detached_and_does_not_hide_bad_results(self):
        values = {'onigiri_hashi_notes': [{'body_md': 'Original'}]}
        collection = self.modern_collection(values)
        collection.all_config = lambda: values
        snapshot = self.storage.collection_config_snapshot(collection)
        snapshot['onigiri_hashi_notes'][0]['body_md'] = 'Changed'
        self.assertEqual(values['onigiri_hashi_notes'][0]['body_md'], 'Original')
        collection.all_config = lambda: []
        with self.assertRaises(TypeError):
            self.storage.collection_config_snapshot(collection)

    def test_failed_collection_backup_remains_retryable_and_identifies_onigiri(self):
        values = {'modern_menu_statsTitle': 'Saved title'}
        self.mw.col = self.modern_collection(values)
        with patch.object(self.mw.col, 'all_config', side_effect=RuntimeError('read unavailable')):
            self.assertIsNone(self.storage.backup_before_upgrade())
        self.assertFalse(list(Path(self.storage.external_backup_dir()).glob('before_progress_upgrade_v2_*.json')))
        self.assertIn('Onigiri', self.storage.take_notices()[0])
        self.assertIsNotNone(self.storage.backup_before_upgrade())
        self.assertEqual(self.mw.col.all_config(), values)

    def test_sync_includes_modern_collection_config_and_preserves_archive_on_read_failure(self):
        values = {'onigiri_hashi_notes': [{'body_md': 'Keep my notes'}],
                  'modern_menu_statsTitle': 'Saved title', 'unrelated': 42}
        self.mw.col = self.modern_collection(values)
        media = Path(self.temp.name) / 'collection.media'
        media.mkdir()
        self.mw.col.media = types.SimpleNamespace(dir=lambda: str(media))
        sync = load_module('upgrade_test_addon.core.sync', ROOT / 'core/sync.py')
        manager = sync.SyncManager()
        manager._user_files_dir = str(self.files)
        manager._state_file = str(self.files / 'sync_state.json')
        self.assertTrue(manager.pack_user_files(force=True))
        path = Path(manager.get_sync_file_path())
        before = path.read_bytes()
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read(sync.SYNC_MANIFEST))
        saved = {key: value for group in manifest['collection_config'].values() for key, value in group.items()}
        self.assertEqual(saved['onigiri_hashi_notes'], values['onigiri_hashi_notes'])
        self.assertEqual(saved['modern_menu_statsTitle'], values['modern_menu_statsTitle'])
        self.assertNotIn('unrelated', saved)
        with patch.object(self.mw.col, 'all_config', side_effect=RuntimeError('read unavailable')):
            self.assertFalse(manager.pack_user_files(force=True))
        self.assertEqual(path.read_bytes(), before)

    def test_baseline_archive_is_created_before_loading_migrates_coins(self):
        raw = {'restaurant_level': {'taiyaki_coins': 347, 'owned_items': ['onigiri_ii']}}
        self.write('settings_Upgrade.json', raw)
        self.config._build_config()
        with zipfile.ZipFile(self.storage.backup_before_upgrade()) as archive:
            self.assertEqual(json.loads(archive.read('user_files/settings_Upgrade.json')), raw)
            self.assertNotIn('user_files/gamification_Upgrade.json', archive.namelist())

    def test_shared_progress_adoption_keeps_the_original_file(self):
        legacy = self.write('gamification.json', {'restaurant_level': {'taiyaki_coins': 55}})
        before = legacy.read_bytes()
        manager = self.games.GamificationData(str(self.root))
        manager.save(immediate=True)
        self.assertEqual(legacy.read_bytes(), before)
        self.assertEqual(manager.get_restaurant_data()['taiyaki_coins'], 55)

    def test_profile_rename_does_not_mix_orphaned_game_owners(self):
        self.mw.pm.profiles = lambda: ['Upgrade']
        self.write('settings_Old.json', {'userName': 'Renamed learner'})
        self.write('gamification_Old.json', {'restaurant_level': {'taiyaki_coins': 55}})
        self.write('onigimon_Unrelated.json', {'inventory': {'berry': 100}})
        adopted = self.storage.adopt_orphaned_profile_files('Upgrade')
        self.assertEqual(set(adopted), {'settings_Old.json', 'gamification_Old.json'})
        self.assertFalse((self.files / 'onigimon_Upgrade.json').exists())
        self.assertTrue((self.files / 'settings_Old.json').exists())

    def test_multiple_profiles_and_default_settings_are_never_guessed_as_renames(self):
        self.write('settings_Old.json', {'userName': 'Old learner'})
        self.write('settings_default.json', {'userName': 'Startup default'})
        self.mw.pm.profiles = lambda: ['Upgrade', 'Second']
        self.assertEqual(self.storage.adopt_orphaned_profile_files('Upgrade'), [])
        self.assertFalse((self.files / 'settings_Upgrade.json').exists())

    def test_middle_full_sync_scope_stays_enabled_until_explicitly_changed(self):
        self.write('settings_Upgrade.json', {'ankiweb_sync_enabled': True})
        conf = self.config._build_config()
        self.assertTrue(conf['ankiweb_sync_layout'])
        self.config.write_config(dict(conf, ankiweb_sync_layout=False))
        self.assertFalse(self.config.get_config()['ankiweb_sync_layout'])

    def test_sparse_layout_and_sidebar_more_choices_survive(self):
        saved = {'onigiriWidgetLayout': {'grid': {'custom': {'pos': 12, 'row': 2, 'col': 2}},
                                        'archive': ['stats_title']},
                 'sidebarButtonLayout': {'visible': ['profile', 'more'], 'more': ['gamification'], 'archived': ['add']}}
        self.write('settings_Upgrade.json', saved)
        conf = self.config._build_config()
        self.assertEqual(conf['onigiriWidgetLayout']['grid'], saved['onigiriWidgetLayout']['grid'])
        self.assertEqual(conf['sidebarButtonLayout'], saved['sidebarButtonLayout'])

    def test_overview_slideshow_keeps_all_uploads_and_selects_first_image(self):
        saved = {'onigiri_overview_bg_mode': 'slideshow',
                 'onigiri_overview_slideshow_images': ['one.png', 'two.png'],
                 'onigiri_overview_slideshow_interval': 7}
        self.write('settings_Upgrade.json', saved)
        conf = self.config._build_config()
        self.assertEqual(conf['onigiri_overview_slideshow_images'], saved['onigiri_overview_slideshow_images'])
        self.assertEqual(conf['onigiri_overview_slideshow_interval'], 7)
        self.assertEqual(conf['onigiri_overview_bg_image_light'], 'one.png')
        self.assertEqual(conf['onigiri_overview_bg_image_dark'], 'one.png')

    def test_all_legacy_bundled_asset_paths_still_exist(self):
        for folder in ('Onigiri(Original)', 'Onigiri(Middle)'):
            source = ROOT / folder / 'system_files'
            for asset in source.rglob('*'):
                if not asset.is_file() or asset.name == '.DS_Store':
                    continue
                relative = asset.relative_to(source)
                self.assertTrue((ROOT / 'system_files' / relative).is_file(), str(relative))

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_all_purchased_ids_resolve_in_current_catalog(self):
        def dictionaries(path):
            tree = ast.parse(path.read_text())
            return {target.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Dict) for target in node.targets if isinstance(target, ast.Name)
                    and target.id in {'RESTAURANTS', 'EVOLUTIONS', 'SHOPS', 'DEVS', 'LEGACY_EVOLUTIONS'}}
        current = dictionaries(ROOT / 'gamification/nook_level.py')
        current_ids = set().union(*(group.keys() for group in current.values()))
        for path in (ROOT / 'Onigiri(Original)/gamification/restaurant_level.py', ROOT / 'Onigiri(Middle)/gamification/nook_level.py'):
            old = dictionaries(path)
            self.assertLessEqual(set().union(*(group.keys() for group in old.values())), current_ids)
        for item in current['LEGACY_EVOLUTIONS'].values():
            self.assertTrue((ROOT / 'system_files/gamification_images/nook_folder' / item['image']).is_file())

    def test_old_coin_checksum_does_not_zero_an_upgraded_balance(self):
        source = ast.parse((ROOT / '__init__.py').read_text())
        method = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'verify_coin_integrity')
        path = self.write('gamification_Upgrade.json', {'restaurant_level': {'taiyaki_coins': 739, '_security_token': 'older-writer-token'}})
        namespace = {'mw': self.mw, 'addon_path': str(self.root), 'addon_package': 'onigiri',
                     'os': os, 'safe_storage': self.storage, 'config': self.config}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '__init__.py', 'exec'), namespace)
        namespace['verify_coin_integrity']()
        saved = json.loads(path.read_text())['restaurant_level']
        self.assertEqual(saved['taiyaki_coins'], 739)
        self.assertEqual(saved['_security_token'], hashlib.sha256(b'739:onigiri_secret_salt_2024').hexdigest())

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_release_package_and_both_full_install_upgrades(self):
        builder = load_module('upgrade_release_builder', ROOT / 'tools/build_addon.py')
        release = builder.build_addon(Path(self.temp.name) / 'Current.ankiaddon')
        with zipfile.ZipFile(release) as archive:
            names = archive.namelist()
            self.assertEqual([name for name in names if name.startswith('user_files/')], ['user_files/README.txt'])
            self.assertNotIn('meta.json', names)
            self.assertNotIn('onigiri_layout.json', names)
            self.assertFalse(any(name.startswith(('Onigiri(', 'tests/', 'tools/')) for name in names))
            self.assertEqual(json.loads(archive.read('config.json')), {})
            self.assertEqual(json.loads(archive.read('manifest.json'))['package'], '1011095603')

        for folder in ('Onigiri(Original)', 'Onigiri(Middle)'):
            with self.subTest(version=folder):
                fixture = ProgressUpgradeTests()
                fixture.setUp()
                try:
                    shutil.copytree(ROOT / folder, fixture.root, dirs_exist_ok=True)
                    old_config = load_module('upgrade_test_addon.legacy_config', fixture.root / 'config.py')
                    saved = copy.deepcopy(old_config.DEFAULTS)
                    saved.update(userName='Existing learner', unknown_user_setting={'keep': [False, 0, '']})
                    saved.setdefault('onigiriProfile', {})['bio'] = 'Saved bio'
                    saved['restaurant_level'].update(total_xp=14723, level=17, name='My restaurant')
                    old_config.write_config(saved)
                    old_game = load_module('upgrade_test_addon.legacy_game', fixture.root / 'gamification/gamification.py')
                    manager = old_game.GamificationData(str(fixture.root))
                    manager.restaurant_data.total_xp = 14723
                    manager.restaurant_data.level = 17
                    manager.restaurant_data.taiyaki_coins = 739
                    manager.restaurant_data.owned_items = ['default', 'onigiri_ii', 'restaurant_evo_i']
                    manager.restaurant_data.current_theme_id = 'onigiri_ii'
                    manager.save()
                    fixture.write('settings_Second.json', {'userName': 'Other learner'})
                    fixture.write('gamification_Second.json', {'restaurant_level': {'taiyaki_coins': 123}})
                    for relative in ('profile/avatar.png', 'fonts/custom.ttf', 'main_bg/background.png', 'icons/choice.svg'):
                        path = fixture.files / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(relative.encode())
                    fixture.mw.col.conf.update(onigiri_hashi_notes=[{'id': 'note', 'body_md': 'My notes'}],
                                               onigiri_prep_station_plans=[{'id': 'plan', 'deck_ids': [123]}],
                                               onigiri_pomodoro_sessions=[{'id': 'session', 'actual_minutes': 25}],
                                               modern_menu_background_image='background.png')
                    collection = copy.deepcopy(fixture.mw.col.conf)
                    original_files = {path.relative_to(fixture.files).as_posix(): path.read_bytes()
                                      for path in fixture.files.rglob('*') if path.is_file()}
                    # Anki's documented installation contract: keep user_files,
                    # remove previous code, then install the new archive.
                    for path in fixture.root.iterdir():
                        if path.name == 'user_files':
                            continue
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                    with zipfile.ZipFile(release) as archive:
                        archive.extractall(fixture.root)
                    for relative, raw in original_files.items():
                        self.assertEqual((fixture.files / relative).read_bytes(), raw)
                    fixture.config = load_module('upgrade_test_addon.core.config', fixture.root / 'core/config.py')
                    fixture.games = load_module('upgrade_test_addon.games', fixture.root / 'gamification/gamification.py')
                    conf = fixture.config.get_config()
                    fixture.config.write_config(conf)
                    game = fixture.games.GamificationData(str(fixture.root))
                    game.save(immediate=True)
                    reloaded = fixture.config.get_config()
                    self.assertEqual(reloaded['userName'], 'Existing learner')
                    self.assertEqual(reloaded['onigiriProfile']['bio'], 'Saved bio')
                    self.assertEqual(reloaded['unknown_user_setting'], saved['unknown_user_setting'])
                    for mode, palette in saved['colors'].items():
                        for key, value in palette.items():
                            self.assertEqual(reloaded['colors'][mode][key], value)
                    state = fixture.games.GamificationData(str(fixture.root)).get_restaurant_data()
                    self.assertEqual(state['taiyaki_coins'], 739)
                    self.assertEqual(state['total_xp'], 14723)
                    self.assertEqual(state['owned_items'], ['default', 'onigiri_ii', 'restaurant_evo_i'])
                    self.assertEqual(state['current_theme_id'], 'onigiri_ii')
                    self.assertEqual(fixture.mw.col.conf, collection)
                    for relative, raw in original_files.items():
                        if relative not in ('settings_Upgrade.json', 'gamification_Upgrade.json'):
                            self.assertEqual((fixture.files / relative).read_bytes(), raw)
                    with zipfile.ZipFile(fixture.storage.backup_before_upgrade()) as archive:
                        for relative, raw in original_files.items():
                            self.assertEqual(archive.read('user_files/' + relative), raw)
                finally:
                    fixture.doCleanups()

    def test_first_sync_after_upgrade_cannot_overwrite_an_unresolved_archive(self):
        media = Path(self.temp.name) / 'collection.media'
        media.mkdir()
        self.mw.col.media = types.SimpleNamespace(dir=lambda: str(media))
        sync = load_module('upgrade_test_addon.core.sync', ROOT / 'core/sync.py')
        manager = sync.SyncManager()
        manager._user_files_dir = str(self.files)
        manager._state_file = str(self.files / 'sync_state.json')
        cloud = media / '_onigiri_sync_Upgrade.zip'
        with zipfile.ZipFile(cloud, 'w') as archive:
            archive.writestr('settings_Upgrade.json', json.dumps({'userName': 'Cloud learner'}))
        original = cloud.read_bytes()
        self.assertEqual(manager.check_conflict(), 'cloud_newer')
        self.assertFalse(manager.pack_user_files())
        self.assertEqual(cloud.read_bytes(), original)
        self.assertTrue(manager.pack_user_files(force=True))
        self.assertNotEqual(cloud.read_bytes(), original)
        self.assertEqual(manager.check_conflict(), 'none')

    def test_legacy_sync_import_keeps_other_files_and_full_saved_layout(self):
        media = Path(self.temp.name) / 'collection.media'
        media.mkdir()
        self.mw.col.media = types.SimpleNamespace(dir=lambda: str(media))
        self.write('settings_Upgrade.json', {'ankiweb_sync_enabled': True})
        sync = load_module('upgrade_test_addon.core.sync', ROOT / 'core/sync.py')
        manager = sync.SyncManager()
        manager._user_files_dir = str(self.files)
        manager._state_file = str(self.files / 'sync_state.json')
        local = self.files / 'profile' / 'local.png'
        local.parent.mkdir()
        local.write_bytes(b'local artwork')
        layout = {'grid': {'time': {'pos': 20, 'row': 1, 'col': 1}}, 'archive': ['stats_title']}
        with zipfile.ZipFile(media / '_onigiri_sync_Upgrade.zip', 'w') as archive:
            archive.writestr('settings_Upgrade.json', json.dumps({'userName': 'Cloud learner', 'onigiriWidgetLayout': layout}))
            archive.writestr('profile/cloud.png', b'cloud artwork')
            archive.writestr('gamification_Upgrade.json', json.dumps({'restaurant_level': {'taiyaki_coins': 444}}))
        self.assertTrue(manager.unpack_user_files())
        conf = self.config.get_config()
        self.assertEqual(conf['userName'], 'Cloud learner')
        self.assertEqual(conf['onigiriWidgetLayout']['grid']['time']['pos'], 20)
        self.assertEqual(local.read_bytes(), b'local artwork')
        self.assertEqual((local.parent / 'cloud.png').read_bytes(), b'cloud artwork')
        self.assertEqual(json.loads((self.files / 'gamification_Upgrade.json').read_text())['restaurant_level']['taiyaki_coins'], 444)

    def test_recovery_prefers_the_latest_mirrored_save_over_an_older_backup(self):
        path = str(self.files / 'gamification_Upgrade.json')
        self.storage.atomic_write_json(path, {'coins': 50})
        self.storage.atomic_write_json(path, {'coins': 75})
        Path(path).write_text('{broken')
        self.assertEqual(self.storage.read_json(path, default={}), {'coins': 75})

    def test_empty_save_can_be_rotated_and_recovered_after_later_edits(self):
        path = str(self.files / 'hashi.json')
        self.storage.atomic_write_json(path, [])
        self.storage.atomic_write_json(path, [{'id': 'new'}])
        self.assertEqual(json.loads(Path(path + '.bak').read_text()), [])

    def test_reload_applies_an_explicit_empty_game_reset(self):
        path = self.write('gamification_Upgrade.json', {'restaurant_level': {'taiyaki_coins': 50}})
        manager = self.games.GamificationData(str(self.root))
        path.write_text('{}')
        manager.reload()
        self.assertEqual(manager.get_restaurant_data()['taiyaki_coins'], 0)

    def test_sync_reloads_existing_game_managers_before_they_can_save(self):
        self.write('gamification_Upgrade.json', {'restaurant_level': {'taiyaki_coins': 50}})
        game = self.games.GamificationData(str(self.root))
        self.games._gamification_data = game
        self.write('gamification_Upgrade.json', {'restaurant_level': {'taiyaki_coins': 500}})
        onigimon = types.SimpleNamespace(manager=types.SimpleNamespace(_state={'old': True}))
        island = types.SimpleNamespace(manager=types.SimpleNamespace(_state_cache={'old': True}))
        mochi = types.SimpleNamespace(_HISTORY_CACHE=[{'old': True}])
        sync = load_module('upgrade_test_addon.core.sync', ROOT / 'core/sync.py')
        with patch.dict(sys.modules, {'upgrade_test_addon.gamification.gamification': self.games,
                                      'upgrade_test_addon.gamification.onigimon': onigimon,
                                      'upgrade_test_addon.gamification.hexagon_land': island,
                                      'upgrade_test_addon.gamification.mochi_messages': mochi}):
            sync.SyncManager._invalidate_loaded_state()
        self.assertEqual(game.get_restaurant_data()['taiyaki_coins'], 500)
        self.assertIsNone(onigimon.manager._state)
        self.assertIsNone(island.manager._state_cache)
        self.assertIsNone(mochi._HISTORY_CACHE)
        game.save(immediate=True)
        self.assertEqual(json.loads((self.files / 'gamification_Upgrade.json').read_text())['restaurant_level']['taiyaki_coins'], 500)

    def test_integrity_hook_registers_with_supported_api_before_game_imports(self):
        source = (ROOT / '__init__.py').read_text()
        registration = 'gui_hooks.profile_did_open.append(_storage_integrity_check)'
        self.assertEqual(source.count(registration), 1)
        self.assertLess(source.index(registration), source.index('from .rendering import onigiri_renderer'))
        self.assertNotIn('profile_did_open.insert(', source)

    def test_companion_and_island_caches_do_not_overwrite_another_profile(self):
        for filename, state_name, manager_name, prefix, key, methods in (
            ('onigimon.py', 'OnigimonState', 'OnigimonManager', 'onigimon', 'comet_shards', {'load', 'save', '_data_path', '_profile_name'}),
            ('hexagon_land.py', 'HexagonLandState', 'HexagonLandManager', 'hexagon_land', 'hex_coins', {'load', 'save', 'data_path'}),
        ):
            with self.subTest(game=prefix):
                tree = ast.parse((ROOT / 'gamification' / filename).read_text())
                state = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == state_name)
                original = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == manager_name)
                manager = ast.ClassDef(name='Manager', bases=[], keywords=[], decorator_list=[],
                                      body=[node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in methods])
                namespace = dict(globals(), safe_storage=self.storage, mw=self.mw, ITEMS={},
                                 RESOURCE_KEYS=('wood', 'stone', 'sand', 'crystal'),
                                 _normalize_tile_spots=lambda tile: None, _anki_today=date.today,
                                 _profile_name=lambda: self.mw.pm.name,
                                 __file__=str(self.root / 'gamification' / filename))
                exec(compile(ast.fix_missing_locations(ast.Module(body=[state, manager], type_ignores=[])), filename, 'exec'), namespace)
                extra = {'tiles': {'0,0': {'terrain': 'grass', 'height': 1, 'parts': []}}} if prefix == 'hexagon_land' else {}
                self.write(f'{prefix}_Upgrade.json', {key: 55, **extra})
                self.write(f'{prefix}_Second.json', {key: 99, **extra})
                obj = namespace['Manager']()
                obj._state = None
                obj._state_cache = None
                obj._data_path_cache = None
                self.mw.pm.name = 'Upgrade'
                self.assertEqual(getattr(obj.load(), key), 55)
                self.mw.pm.name = 'Second'
                loaded = obj.load()
                self.assertEqual(getattr(loaded, key), 99)
                if prefix == 'onigimon':
                    obj.save(immediate=True)
                else:
                    obj.save(loaded)
                self.assertEqual(json.loads((self.files / f'{prefix}_Upgrade.json').read_text())[key], 55)
                self.assertEqual(json.loads((self.files / f'{prefix}_Second.json').read_text())[key], 99)
                self.mw.pm.name = 'Upgrade'

    def test_mochi_history_cache_is_profile_specific(self):
        tree = ast.parse((ROOT / 'gamification/mochi_messages.py').read_text())
        methods = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('_load_history', '_save_history')]
        namespace = dict(globals(), config=self.config, _HISTORY_CACHE=None, _HISTORY_CACHE_PATH=None,
                         _history_path=lambda: str(self.files / f'mochi_history_{self.mw.pm.name}.json'),
                         __package__='upgrade_test_addon.gamification')
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'mochi_messages.py', 'exec'), namespace)
        self.write('mochi_history_Upgrade.json', {'history': [{'message': 'First learner'}]})
        self.write('mochi_history_Second.json', {'history': [{'message': 'Second learner'}]})
        self.assertEqual(namespace['_load_history'](), [{'message': 'First learner'}])
        self.mw.pm.name = 'Second'
        self.assertEqual(namespace['_load_history'](), [{'message': 'Second learner'}])
        namespace['_save_history']([{'message': 'Second learner new message'}])
        self.assertEqual(json.loads((self.files / 'mochi_history_Upgrade.json').read_text())['history'], [{'message': 'First learner'}])

    @unittest.skipUnless(all((ROOT / name).is_dir() for name in ("Onigiri(Original)", "Onigiri(Middle)")),
                         "Original and Middle attachment fixtures are not present")
    def test_original_stats_title_is_moved_to_a_free_tile(self):
        old = load_module('upgrade_test_addon.legacy_config', ROOT / 'Onigiri(Original)/config.py')
        self.write('settings_Upgrade.json', copy.deepcopy(old.DEFAULTS))
        conf = self.config._build_config()
        grid = conf['onigiriWidgetLayout']['grid']
        self.assertIn('stats_title', grid)
        for key, value in old.DEFAULTS['onigiriWidgetLayout']['grid'].items():
            self.assertEqual(grid[key], value)
        occupied = self.config._widget_layout_occupied_cells(grid, 4, skip_id='stats_title')
        title = grid['stats_title']
        row, col = divmod(title['pos'], 4)
        self.assertTrue(all((row, c) not in occupied for c in range(col, col + title['col'])))


if __name__ == '__main__':
    unittest.main()
