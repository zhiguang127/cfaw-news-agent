#!/usr/bin/env python3
"""Run actual OctoScript data tests in an isolated native card-host storage jail."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen
from uuid import uuid4
from assemble import ROOT, ORDER, assemble


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, help='Pinned card-host executable')
    parser.add_argument('--agent-only', action='store_true', help='Run isolated agent validation tests')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    checkout = ROOT / next(r['relative_checkout'] for r in lock['repositories'] if r['name'] == 'OctoSense-App-Hub')
    host = (args.host or checkout / 'target/release' / ('card-host.exe' if os.name == 'nt' else 'card-host')).resolve()
    if not host.is_file():
        raise SystemExit('Pinned card-host missing; supply --host. A graphical session is required.')
    work = ROOT / '.test-state' / ('runtime-' + uuid4().hex[:12])
    bundle = work / 'bundle'
    bundle.mkdir(parents=True)
    data_modules = [p for p in ORDER
                    if p.startswith('src/contracts/') or p.startswith('src/data/')]
    paths = ORDER[:3] + ['src/data/storage/schedules.splash', 'src/agent/context.splash', 'src/agent/history.splash', 'src/agent/results/validator.splash', 'src/agent/results/change.splash'] if args.agent_only else ['src/app/config.splash'] + data_modules + ['src/agent/context.splash', 'src/agent/history.splash', 'src/agent/results/validator.splash', 'src/agent/results/change.splash']
    source, _ = assemble(paths=paths)
    for name, file in [('fixture_rss', 'news-rss.xml'), ('fixture_atom', 'news-atom.xml'), ('fixture_hn', 'news-hn.json'),
                       ('fixture_weather', 'weather-daily.json'),
                       ('fixture_holiday_2026', 'holiday-cn-2026.json'),
                       ('fixture_holiday_empty', 'holiday-cn-unpublished.json'),
                       ('fixture_analysis_no_change', 'analysis-no-change.json'),
                       ('fixture_analysis_create', 'analysis-create.json'),
                       ('fixture_analysis_suggestion', 'analysis-suggestion.json'),
                       ('fixture_analysis_invalid_model_output', 'analysis-invalid-model-output.json')]:
        source += '\nlet ' + name + ' = ' + json.dumps((ROOT / 'tests/fixtures' / file).read_text(encoding='utf-8'), ensure_ascii=False) + '\n'
    source += (ROOT / 'tests/unit/agent_validation.splash').read_text(encoding='utf-8')
    if args.agent_only:
        source += '\nHostedView{full: View{Label{text: "Agent fixture tests"}}}\n'
        source += 'start_timeout(0.05, || { agent_test_validation() start_timeout(0.02, || { agent_test_confirmation() fs.write("runtime-report.json", {passed: agent_validation_passes failed: agent_validation_failures stage: "complete"}.to_json()) }) })\n'
    else:
        source += (ROOT / 'tests/unit/news_runtime.splash').read_text(encoding='utf-8')
        source += (ROOT / 'tests/unit/weather_runtime.splash').read_text(encoding='utf-8')
        source += (ROOT / 'tests/unit/holiday_runtime.splash').read_text(encoding='utf-8')
    (bundle / 'main.splash').write_text(source, encoding='utf-8')
    manifest = json.loads((ROOT / 'bundle/manifest.json').read_text())
    manifest['id'] = 'dev.cfaw.runtime-tests'
    manifest['integrity']['bundle_blake3'] = ''
    manifest['network']['hosts'] = []
    (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    startup = None
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    report_path = work / 'data' / manifest['id'] / 'runtime-report.json'
    weather_report_path = work / 'data' / manifest['id'] / 'weather-report.json'
    holiday_report_path = work / 'data' / manifest['id'] / 'holiday-report.json'
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(host), '--bundle', str(bundle), '--allow-unsigned', '--stamp', '--app-data', str(work / 'data'), '--remote', str(port)], cwd=host.parents[2], stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 20
            # The weather module reports separately; either report is enough to
            # read results, and the totals are merged when both arrive.
            while time.monotonic() < deadline and process.poll() is None:
                secondary = holiday_report_path if weather_report_path.exists() else weather_report_path
                if report_path.exists() and (args.agent_only or secondary.exists()):
                    break
                if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
                    break
                time.sleep(0.1)
            if not report_path.exists() and not weather_report_path.exists() and not holiday_report_path.exists():
                raise SystemExit(f'Runtime did not produce a report; inspect {work / "host.log"}')
            report = {'passed': 0, 'failed': 0, 'stages': {}}
            for label, path in (('news', report_path), ('weather', weather_report_path), ('holiday', holiday_report_path)):
                if path.exists():
                    part = json.loads(path.read_text(encoding='utf-8'))
                    report['passed'] += part.get('passed', 0)
                    report['failed'] += part.get('failed', 0)
                    report['stages'][label] = {k: part[k] for k in ('passed', 'failed') if k in part}
                    if part.get('failures'):
                        report['stages'][label]['failures'] = part['failures']
                    if part.get('failure_detail'):
                        report['stages'][label]['failure_detail'] = part['failure_detail']
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print(f'Report: {report_path if report_path.exists() else weather_report_path}')
            if report['failed']:
                raise SystemExit(1)
        finally:
            try:
                with urlopen(f'http://127.0.0.1:{port}/quit', timeout=2):
                    pass
            except OSError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=3)


if __name__ == '__main__':
    run()
