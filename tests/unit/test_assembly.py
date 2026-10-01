"""Checks for source assembly, source mapping and network admission consistency."""
import json
from pathlib import Path
import sys
from contextlib import contextmanager
import shutil
import unittest
from uuid import uuid4
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from assemble import ORDER, assemble, build, source_catalog


@contextmanager
def temporary_workspace():
    parent = (ROOT / '.test-state').resolve()
    parent.mkdir(exist_ok=True)
    root = parent / ('assembly-' + uuid4().hex)
    root.mkdir()
    try:
        yield str(root)
    finally:
        # Only remove the fresh test directory inside this workspace.
        if root.resolve().parent != parent or not root.name.startswith('assembly-'):
            raise RuntimeError('Unsafe test cleanup target')
        shutil.rmtree(root)


class AssemblyTests(unittest.TestCase):
    def test_generated_entry_and_source_map(self):
        output, spans = assemble()
        self.assertEqual(output, (ROOT / 'bundle/main.splash').read_text(encoding='utf-8'))
        lines = output.splitlines()
        self.assertEqual([span['source'] for span in spans], ORDER)
        for span in spans:
            self.assertEqual(lines[span['generated_start'] - 2], '// BEGIN ' + span['source'])
            self.assertEqual(lines[span['generated_end']], '// END ' + span['source'])
            if not span['generated_catalog']:
                actual = '\n'.join(lines[span['generated_start'] - 1:span['generated_end']])
                expected = (ROOT / span['source']).read_text(encoding='utf-8').rstrip()
                self.assertEqual(actual, expected)

    def test_source_hosts_admitted(self):
        catalog = source_catalog()
        allowed = set(json.loads((ROOT / 'bundle/manifest.json').read_text())['network']['hosts'])
        requested = {urlsplit(source['url']).hostname for source in catalog['sources']}
        self.assertTrue((requested | set(catalog['redirect_hosts'])).issubset(allowed))

    def test_invalid_catalog_refused(self):
        catalog = source_catalog()
        for mutation in ('duplicate', 'http', 'credentials'):
            with self.subTest(mutation=mutation), temporary_workspace() as directory:
                root = Path(directory)
                data = json.loads(json.dumps(catalog))
                if mutation == 'duplicate':
                    data['sources'].append(data['sources'][0].copy())
                else:
                    data['sources'][0]['url'] = 'http://example.org/rss' if mutation == 'http' else 'https://user:secret@example.org/rss'
                path = root / 'src/data/ingestion/sources.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(ValueError):
                    source_catalog(root)

    def test_stale_bundle_refused(self):
        with temporary_workspace() as directory:
            root = Path(directory)
            (root / 'bundle').mkdir()
            (root / 'bundle/main.splash').write_text('outdated', encoding='utf-8')
            for relative in ORDER:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text((ROOT / relative).read_text(encoding='utf-8'), encoding='utf-8')
            with self.assertRaises(SystemExit):
                build(root, check=True)


if __name__ == '__main__':
    unittest.main()
