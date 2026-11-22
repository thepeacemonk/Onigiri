"""Release resolution and staging tests; all writes use temporary storage."""
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('version_manager_service_test', ROOT / 'version_manager/service.py')
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


def release(version, **changes):
    result = {'tag_name': 'v.' + version, 'draft': False, 'prerelease': False,
              'assets': [{'name': 'Onigiri.ankiaddon', 'state': 'uploaded',
                          'digest': 'sha256:' + 'a' * 64, 'size': 100}]}
    result.update(changes)
    return result


def metadata(releases):
    return io.BytesIO(json.dumps(releases).encode())


class LatestBentoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'addons21' / service.PACKAGE
        (self.root / 'user_files').mkdir(parents=True)
        service.write_json(self.root / 'manifest.json', {'package': service.PACKAGE, 'version': '1.0-Sake-Nigiri'})
        service.write_json(self.root / 'meta.json', {'update_enabled': True, 'config': {'keep': 42}})
        self.personal = self.root / 'user_files' / 'settings.json'
        self.personal.write_bytes(b'{"progress":73,"name":"Study"}\n')

    def archive(self, version='2.0.2-Bento'):
        path = Path(self.temp.name) / 'release.ankiaddon'
        with zipfile.ZipFile(path, 'w') as package:
            package.writestr('manifest.json', json.dumps({'package': service.PACKAGE, 'version': version}))
            package.writestr('__init__.py', service.BOOT + '\n# release entry\n')
            package.writestr('ui_kit/menu_buttons.py', 'def setup():\n    mw.form.menubar.addMenu(onigiri_menu)\n')
            package.writestr('version_manager/service.py', '# older bundled manager\n')
            package.writestr('version_manager/obsolete.py', '# must not survive overlay\n')
            package.writestr('user_files/settings.json', '{"progress":0}')
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_bento_selects_highest_stable_numeric_version(self):
        releases = [release('2.0.2-Bento'), release('2.0-Bento'), release('2.0.10-Bento'),
                    release('3.0-Bento', draft=True), release('4.0-Bento', prerelease=True),
                    release('9.0-Other'), release('5.0-Bento-beta')]
        with patch.object(service.urllib.request, 'urlopen', return_value=metadata(releases)):
            self.assertEqual(service.resolve_release('2.0-Bento'), ('v.2.0.10-Bento', 'a' * 64, '2.0.10-Bento'))

    def test_bento_refreshes_when_a_new_release_is_published(self):
        with patch.object(service.urllib.request, 'urlopen', side_effect=[
                metadata([release('2.0.2-Bento')]), metadata([release('2.0.3-Bento')])]):
            self.assertEqual(service.resolve_release('2.0-Bento')[2], '2.0.2-Bento')
            self.assertEqual(service.resolve_release('2.0-Bento')[2], '2.0.3-Bento')

    def test_release_resolution_follows_pagination(self):
        with patch.object(service.urllib.request, 'urlopen', side_effect=[
                metadata([release('1.0-Other')] * 100), metadata([release('2.0.2-Bento')])]) as fetch:
            self.assertEqual(service.resolve_release('2.0-Bento')[2], '2.0.2-Bento')
            self.assertIn('page=2', fetch.call_args[0][0].full_url)

    def test_latest_release_missing_asset_or_digest_does_not_fall_back(self):
        for assets in ([], [{'name': 'Onigiri.ankiaddon', 'state': 'uploaded'}]):
            with self.subTest(assets=assets), patch.object(service.urllib.request, 'urlopen',
                    return_value=metadata([release('2.0-Bento'), release('2.0.2-Bento', assets=assets)])):
                with self.assertRaises(ValueError):
                    service.resolve_release('2.0-Bento')

    def test_historical_releases_remain_pinned_without_network_lookup(self):
        with patch.object(service.urllib.request, 'urlopen') as fetch:
            for target, expected in (('1.0-Sake-Nigiri', '1.0 - Sake nigiri'), ('0.9-legacy', '1.0.9-beta')):
                tag, digest, version = service.resolve_release(target)
                self.assertEqual((tag, digest), service.RELEASES[target])
                self.assertEqual(version, expected)
            fetch.assert_not_called()

    def test_staging_and_commit_keep_exact_bento_version_and_personal_data(self):
        archive, digest = self.archive()
        original = self.personal.read_bytes()
        with patch.object(service, 'resolve_release', return_value=('v.2.0.2-Bento', digest, '2.0.2-Bento')):
            stage = service.prepare_release(self.root, '2.0-Bento', archive=archive)
        self.assertEqual(service.installed_version(stage), '2.0.2-Bento')
        self.assertEqual(service.installed_release(stage), '2.0-Bento')
        self.assertEqual((stage / 'version_manager/service.py').read_bytes(), (ROOT / 'version_manager/service.py').read_bytes())
        self.assertIn('QByteArray', (stage / 'version_manager/__init__.py').read_text())
        self.assertFalse((stage / 'version_manager/obsolete.py').exists())
        self.assertFalse((stage / 'user_files').exists())
        self.assertEqual((stage / '__init__.py').read_text().count(service.BOOT_MARKER), 1)
        self.assertEqual(self.personal.read_bytes(), original)
        self.assertEqual(service.installed_version(self.root), '1.0-Sake-Nigiri')
        context = {'profile': 'Study', 'profile_config': {}, 'collection_config': {'keep': 73}}
        service.queue_switch(self.root, '2.0-Bento', stage, context)
        self.assertEqual(service.pending_switch(self.root)['target_version'], '2.0.2-Bento')
        backup = service.commit_switch(self.root, context)
        self.assertEqual(service.installed_version(self.root), '2.0.2-Bento')
        self.assertEqual(service.read_json(self.root / 'meta.json')['human_version'], '2.0.2-Bento')
        self.assertEqual(service.read_json(self.root / 'meta.json')['config'], {'keep': 42})
        self.assertEqual(service.read_json(backup / 'switch.json')['to'], '2.0.2-Bento')
        self.assertEqual(service.read_json(backup / 'context.json'), context)
        self.assertEqual(self.personal.read_bytes(), original)
        self.assertEqual((backup / 'installation/user_files/settings.json').read_bytes(), original)
        self.assertIsNone(service.pending_switch(self.root))

    def test_download_url_and_digest_use_resolved_release(self):
        archive, digest = self.archive()
        published = release('2.0.2-Bento')
        published['assets'][0]['digest'] = 'sha256:' + digest
        with patch.object(service.urllib.request, 'urlopen', side_effect=[
                metadata([published]), io.BytesIO(archive.read_bytes())]) as fetch:
            stage = service.prepare_release(self.root, '2.0-Bento')
        self.assertEqual(fetch.call_args[0][0].full_url,
                         'https://github.com/thepeacemonk/Onigiri/releases/download/v.2.0.2-Bento/Onigiri.ankiaddon')
        self.assertEqual(service.installed_version(stage), '2.0.2-Bento')

    def test_bad_checksum_or_mismatched_manifest_cancels_before_queue(self):
        archive, digest = self.archive('2.0-Bento')
        for checksum in ('0' * 64, digest):
            with self.subTest(checksum=checksum), patch.object(service, 'resolve_release',
                    return_value=('v.2.0.2-Bento', checksum, '2.0.2-Bento')):
                with self.assertRaises(ValueError):
                    service.prepare_release(self.root, '2.0-Bento', archive=archive)
                self.assertEqual(list(service.control_dir(self.root).glob('staged-*')), [])
                self.assertEqual(service.installed_version(self.root), '1.0-Sake-Nigiri')
                self.assertTrue(service.updates_enabled(self.root))
                self.assertIsNone(service.pending_switch(self.root))

    def test_lookup_failure_does_not_download_original_bento(self):
        with patch.object(service.urllib.request, 'urlopen', side_effect=URLError('offline')) as fetch:
            with self.assertRaises(URLError):
                service.prepare_release(self.root, '2.0-Bento')
            self.assertEqual(fetch.call_count, 1)
        self.assertEqual(list(service.control_dir(self.root).glob('staged-*')), [])
        self.assertTrue(service.updates_enabled(self.root))


if __name__ == '__main__':
    unittest.main()
