"""The native runner must not accept partial or empty suite coverage."""
import json
from pathlib import Path
import sys
import shutil
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from test_runtime import collect_reports
from test_live_minimax import RinxUI


class RuntimeReportTests(unittest.TestCase):
    def setUp(self):
        state = (ROOT / '.test-state').resolve()
        state.mkdir(exist_ok=True)
        directory = state / ('reports-' + uuid4().hex)
        directory.mkdir()
        def cleanup():
            if directory.resolve().parent != state or not directory.name.startswith('reports-'):
                raise RuntimeError('Unsafe report test cleanup target')
            shutil.rmtree(directory)
        self.addCleanup(cleanup)
        self.paths = {name: directory / (name + '.json') for name in ('news', 'weather', 'holiday', 'fx')}
        for path in self.paths.values():
            path.write_text(json.dumps({'passed': 3, 'failed': 0, 'stage': 'complete'}), encoding='utf-8')

    def test_all_suites_required(self):
        self.assertEqual(collect_reports(self.paths)['passed'], 12)
        self.paths['news'].unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required reports: news'):
            collect_reports(self.paths)

    def test_incomplete_and_malformed_reports_rejected(self):
        for content in ('not json', '[]', '{"passed": 3, "failed": 0, "stage": "running"}'):
            with self.subTest(content=content):
                self.paths['fx'].write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    collect_reports(self.paths)

    def test_invalid_or_empty_counts_rejected(self):
        for passed, failed in ((0, 0), (True, 0), (-1, 0), (3, None)):
            with self.subTest(passed=passed, failed=failed):
                self.paths['fx'].write_text(json.dumps({'passed': passed, 'failed': failed, 'stage': 'complete'}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    collect_reports(self.paths)

    def test_failures_are_aggregated_with_details(self):
        part = {'passed': 1, 'failed': 2, 'stage': 'complete', 'failure_detail': 'fixed-input failures'}
        self.paths['weather'].write_text(json.dumps(part), encoding='utf-8')
        report = collect_reports(self.paths)
        self.assertEqual((report['passed'], report['failed']), (10, 2))
        self.assertEqual(report['stages']['weather']['failure_detail'], 'fixed-input failures')

    def test_agent_mode_does_not_require_data_reports(self):
        self.assertEqual(set(collect_reports({'agent': self.paths['news']})['stages']), {'agent'})


class LiveRuntimeDiagnosticsTests(unittest.TestCase):
    def test_control_wait_uses_settled_geometry(self):
        ui = RinxUI(1234)
        old = {'ty': 'Button', 'i': 'run', 'r': [10, 10, 40, 30]}
        new = dict(old, r=[10, 70, 40, 30])
        ui.widgets = Mock(side_effect=[[old], [new], [new]])
        with patch('test_live_minimax.time.sleep'):
            self.assertEqual(ui.wait(lambda w: w['i'] == 'run')['r'], new['r'])
        self.assertEqual(ui.widgets.call_count, 3)

    def test_missing_control_reports_live_host_and_expected_input(self):
        process = Mock(returncode=None)
        process.poll.return_value = None
        ui = RinxUI(1234, process)
        ui.widgets = Mock(return_value=[])
        with patch('test_live_minimax.time.monotonic', side_effect=[0, 0, 2]), patch('test_live_minimax.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, r'waiting for intent_input.*Rinx is still running'):
                ui.wait(lambda w: False, seconds=1, expected='intent_input')

    def test_native_exit_is_not_reported_as_control_timeout(self):
        process = Mock(returncode=-11)
        process.poll.return_value = -11
        ui = RinxUI(1234, process)
        with self.assertRaisesRegex(RuntimeError, r'Rinx exited.*signal 11'):
            ui.wait(lambda w: False)

    def test_diagnostics_omit_credentials_and_private_widget_text(self):
        ui = RinxUI(1234)
        ui.last_widgets = [{'ty': 'TextInput', 'i': 'local_key', 't': 'PRIVATE_KEY', 'r': [0, 0, 10, 10]},
                           {'ty': 'Label', 'i': 'draft', 't': 'PRIVATE_DRAFT'},
                           {'ty': 'Splash', 't': 'PRIVATE_SCRIPT_CONTENT'}]
        data = json.dumps(ui.diagnostics())
        self.assertIn('local_key', data)
        self.assertNotIn('PRIVATE_', data)


if __name__ == '__main__':
    unittest.main()
