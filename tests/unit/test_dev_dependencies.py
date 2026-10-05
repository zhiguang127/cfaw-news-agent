"""Check that the recorded lock correction preserves other checkout changes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_dev_dependencies as dependencies


class DependencyPreparationTests(unittest.TestCase):
    def setUp(self):
        state = ROOT / '.test-state'
        state.mkdir(exist_ok=True)
        self.work = tempfile.TemporaryDirectory(prefix='dependencies-', dir=state)
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.checkout = self.root / 'vendor/tool'
        self.checkout.mkdir(parents=True)
        self.git('init', '--quiet')
        self.original = 'version = 4\n'
        self.corrected = self.original + '# Recorded local dependency correction\n'
        (self.checkout / 'Cargo.lock').write_text(self.original)
        self.git('add', 'Cargo.lock')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.org', 'commit', '--quiet', '-m', 'Fixture')
        revision = self.git('rev-parse', 'HEAD').strip()
        (self.checkout / 'Cargo.lock').write_text(self.corrected)
        correction = self.git('diff', '--binary', '--no-ext-diff', 'HEAD', '--', 'Cargo.lock')
        self.git('restore', 'Cargo.lock')
        (self.root / 'correction.patch').write_text(correction)
        self.repo = {'name': 'tool', 'relative_checkout': 'vendor/tool', 'commit': revision,
                     'cargo_lock_patch': {'path': 'correction.patch',
                                         'patch_sha256_normalized': hashlib.sha256(correction.encode()).hexdigest(),
                                         'patched_sha256_normalized': hashlib.sha256(self.corrected.encode()).hexdigest()}}
        (self.root / 'dev-dependencies.lock.json').write_text(json.dumps({'repositories': [self.repo]}))
        self.root_patch = patch.object(dependencies, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.checkout), *args], text=True)

    def test_correction_is_applied_once(self):
        dependencies.prepare()
        dependencies.prepare()
        self.assertEqual((self.checkout / 'Cargo.lock').read_text(), self.corrected)
        self.assertTrue(dependencies.verify_checkout(self.checkout, self.repo))

    def test_unrelated_user_file_is_preserved(self):
        user_file = self.checkout / 'user-work.txt'
        user_file.write_text('Keep this work')
        with self.assertRaises(SystemExit):
            dependencies.prepare()
        self.assertEqual(user_file.read_text(), 'Keep this work')
        self.assertEqual((self.checkout / 'Cargo.lock').read_text(), self.original)

    def test_modified_corrected_lock_is_preserved(self):
        dependencies.prepare()
        user_lock = self.corrected + '# User change\n'
        (self.checkout / 'Cargo.lock').write_text(user_lock)
        with self.assertRaises(SystemExit):
            dependencies.prepare()
        self.assertEqual((self.checkout / 'Cargo.lock').read_text(), user_lock)

    def test_changed_patch_is_refused(self):
        (self.root / 'correction.patch').write_text('Unexpected patch')
        with self.assertRaises(SystemExit):
            dependencies.prepare()
        self.assertEqual((self.checkout / 'Cargo.lock').read_text(), self.original)

    def test_unprepared_checkout_cannot_be_used(self):
        with self.assertRaises(SystemExit):
            dependencies.verify_checkout(self.checkout, self.repo)


if __name__ == '__main__':
    unittest.main()
