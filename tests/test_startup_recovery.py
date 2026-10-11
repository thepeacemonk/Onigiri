"""Exercise profile hook ordering with real recovery files in temporary storage."""
import ast
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import test_progress_upgrade as upgrade_fixture

ROOT = upgrade_fixture.ROOT


class StartupRecoveryTests(unittest.TestCase):
    # Reuse the isolated host/storage fixture, without rerunning its test cases.
    setUp = upgrade_fixture.ProgressUpgradeTests.setUp
    write = upgrade_fixture.ProgressUpgradeTests.write

    def startup_hook(self):
        self.callbacks = []
        self.warnings = []
        notifications = types.ModuleType('upgrade_test_addon.ui_kit.onigiri_notifications')
        notifications.notify_warning = lambda message, **kw: self.warnings.append((message, kw))
        ui = types.ModuleType('upgrade_test_addon.ui_kit')
        ui.__path__ = []
        modules = patch.dict('sys.modules', {
            ui.__name__: ui, notifications.__name__: notifications,
        })
        modules.start()
        self.addCleanup(modules.stop)
        tree = ast.parse((ROOT / '__init__.py').read_text())
        hook = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_storage_integrity_check')
        namespace = dict(__package__='upgrade_test_addon', mw=self.mw,
                         addon_package='onigiri', safe_storage=self.storage,
                         config=self.config, tr=lambda key: key,
                         QTimer=types.SimpleNamespace(singleShot=lambda delay, fn: self.callbacks.append(fn)))
        exec(compile(ast.Module(body=[hook], type_ignores=[]), '__init__.py', 'exec'), namespace)
        return namespace['_storage_integrity_check']

    def damaged_settings(self):
        path = str(self.files / 'settings_Upgrade.json')
        saved = {'userName': 'Existing learner', 'extension': {'keep': True}}
        self.storage.atomic_write_json(path, saved)
        # Force the precise recovery source named in the user's screenshot.
        mirror = self.storage._mirror_path_for(path)
        Path(mirror).unlink()
        Path(path).write_text('{broken')
        return path, saved

    def test_recovery_warning_returns_before_remaining_profile_hooks(self):
        path, saved = self.damaged_settings()
        self.assertEqual(self.storage.read_json(path, default={}, label='Your Onigiri settings'), saved)
        hook = self.startup_hook()
        hook()
        self.assertEqual(self.warnings, [])
        self.assertEqual(len(self.callbacks), 1)
        self.assertEqual(self.config.get_config()['userName'], saved['userName'])
        self.callbacks.pop()()
        message, options = self.warnings[0]
        self.assertIn('dated snapshot', message)
        self.assertIs(options['blocking'], False)
        self.assertEqual(self.storage._try_load(path)[0], saved)

    def test_recovery_during_later_profile_hook_is_also_reported(self):
        self.damaged_settings()
        self.startup_hook()()
        self.config.get_config()  # Simulate a later profile loader.
        self.assertEqual(self.warnings, [])
        self.callbacks.pop()()
        self.assertEqual(len(self.warnings), 1)
        self.assertIn('dated snapshot', self.warnings[0][0])

    def test_profile_switch_does_not_display_the_previous_profiles_notice(self):
        self.storage._note('Recovered old profile')
        self.startup_hook()()
        self.mw.col = types.SimpleNamespace(conf={})
        self.mw.pm.name = 'Second'
        self.callbacks.pop()()
        self.assertEqual(self.warnings, [])

    def test_clean_startup_does_not_display_a_warning(self):
        self.write('settings_Upgrade.json', {'userName': 'Existing learner'})
        self.startup_hook()()
        self.callbacks.pop()()
        self.assertEqual(self.warnings, [])

