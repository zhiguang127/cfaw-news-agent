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
    args = parser.parse_args()
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    checkout = ROOT / next(r['relative_checkout'] for r in lock['repositories'] if r['name'] == 'OctoSense-App-Hub')
    host = (args.host or checkout / 'target/release' / ('card-host.exe' if os.name == 'nt' else 'card-host')).resolve()
    if not host.is_file():
        raise SystemExit('Pinned card-host missing; supply --host. A graphical session is required.')
    work = ROOT / '.test-state' / ('runtime-' + uuid4().hex[:12])
    bundle = work / 'bundle'
    bundle.mkdir(parents=True)
    source, _ = assemble(paths=ORDER[:8])
    for name, file in [('fixture_rss', 'news-rss.xml'), ('fixture_atom', 'news-atom.xml'), ('fixture_hn', 'news-hn.json')]:
        source += '\nlet ' + name + ' = ' + json.dumps((ROOT / 'tests/fixtures' / file).read_text(encoding='utf-8'), ensure_ascii=False) + '\n'
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
        process = subprocess.Popen([str(host), '--bundle', str(bundle), '--allow-unsigned', '--stamp', '--app-data', str(work / 'data'), '--size', '430x860', '--remote', str(port)], cwd=host.parents[2], stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and process.poll() is None and not report_path.exists():
                if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
                    break
                time.sleep(0.1)
            if not report_path.exists():
                raise SystemExit(f'Runtime did not produce a report; inspect {work / "host.log"}')
            report = json.loads(report_path.read_text(encoding='utf-8'))
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
