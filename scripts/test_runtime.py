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
    parser.add_argument('--inspect-ui', action='store_true', help='Capture and exercise the fixture results/detail UI (agent-only)')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    checkout = ROOT / next(r['relative_checkout'] for r in lock['repositories'] if r['name'] == 'OctoSense-App-Hub')
    host = (args.host or checkout / 'target/release' / ('card-host.exe' if os.name == 'nt' else 'card-host')).resolve()
    if not host.is_file():
        raise SystemExit('Pinned card-host missing; supply --host. A graphical session is required.')
    work = ROOT / '.test-state' / ('runtime-' + uuid4().hex[:12])
    bundle = work / 'bundle'
    bundle.mkdir(parents=True)
    paths = ORDER[:-1] if args.agent_only else ORDER[:ORDER.index('src/agent/runtime/connectivity.splash')]
    source, _ = assemble(paths=paths)
    for name, file in [('fixture_rss', 'news-rss.xml'), ('fixture_atom', 'news-atom.xml'), ('fixture_hn', 'news-hn.json'),
                       ('fixture_analysis_no_change', 'analysis-no-change.json'),
                       ('fixture_analysis_create', 'analysis-create.json'),
                       ('fixture_analysis_suggestion', 'analysis-suggestion.json'),
                       ('fixture_analysis_invalid_model_output', 'analysis-invalid-model-output.json')]:
        source += '\nlet ' + name + ' = ' + json.dumps((ROOT / 'tests/fixtures' / file).read_text(encoding='utf-8'), ensure_ascii=False) + '\n'
    source += (ROOT / 'tests/unit/agent_validation.splash').read_text(encoding='utf-8')
    if args.agent_only:
        source += (ROOT / 'tests/scenarios/analysis_runtime.splash').read_text(encoding='utf-8')
        source += '''
start_timeout(0.05, || agent_test_validation(|| {
    start_timeout(0.02, || agent_test_confirmation(|| {
        start_timeout(0.02, || agent_test_schedule_optimization(|| {
            start_timeout(0.02, || agent_test_history_optimization())
        }))
    }))
}))
'''


    else:
        source += (ROOT / 'tests/unit/news_runtime.splash').read_text(encoding='utf-8')
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
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(host), '--bundle', str(bundle), '--allow-unsigned', '--stamp', '--app-data', str(work / 'data'), '--remote', str(port)], cwd=host.parents[2], stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and process.poll() is None and not report_path.exists():
                if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
                    break
                time.sleep(0.1)
            if not report_path.exists():
                raise SystemExit(f'Runtime did not produce a report; inspect {work / "host.log"}')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            if args.inspect_ui and args.agent_only:
                time.sleep(1)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    snapshot = json.load(response)
                (work / 'results-ui.json').write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
                with urlopen(f'http://127.0.0.1:{port}/g?raw=1', timeout=3) as response:
                    (work / 'results-ui.png').write_bytes(response.read())
                buttons = [w for w in snapshot['s'] if w.get('t') == '查看证据与建议']
                if not buttons:
                    raise SystemExit('Results entry missing in native UI snapshot')
                x, y, width, height = buttons[0]['r']
                with urlopen(f'http://127.0.0.1:{port}/click?x={x + width / 2}&y={y + height / 2}&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/m?k=scroll&x=200&y=650&dy=460&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    detail = json.load(response)
                (work / 'detail-ui.json').write_text(json.dumps(detail, ensure_ascii=False), encoding='utf-8')
                if not any(w.get('t') == '接受' for w in detail['s']):
                    raise SystemExit('Persisted suggestion cannot be opened from results')
                with urlopen(f'http://127.0.0.1:{port}/g?raw=1', timeout=3) as response:
                    (work / 'detail-ui.png').write_bytes(response.read())
                accept = next(w for w in detail['s'] if w.get('t') == '接受')
                x, y, width, height = accept['r']
                with urlopen(f'http://127.0.0.1:{port}/click?x={x + width / 2}&y={y + height / 2}&wait=1', timeout=3):
                    pass
                with urlopen(f'http://127.0.0.1:{port}/m?k=scroll&x=200&y=650&dy=600&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    preview = json.load(response)
                confirm = next(w for w in preview['s'] if w.get('t') == '确认并保存')
                x, y, width, height = confirm['r']
                with urlopen(f'http://127.0.0.1:{port}/click?x={x + width / 2}&y={y + height / 2}&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    refused = json.load(response)
                if not any('重新分析' in w.get('t', '') and w.get('ty') == 'Label' for w in refused['s']):
                    raise SystemExit('Evidence rejection missing from confirmation UI')
                decisions = json.loads((report_path.parent / 'suggestions_v1.json').read_text(encoding='utf-8'))
                if decisions['items'][0]['state'] != 'pending':
                    raise SystemExit('Stale evidence confirmation changed the user decision')
                print(f'Native UI checked: {work}')
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print(f'Report: {report_path}')
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
