"""Exercise bounded correction in isolated native Rinx with synthetic model replies."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble


def main():
    work = ROOT / '.test-state/tracking-repair'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += (ROOT / 'tests/scenarios/tracking_repair.splash').read_text(encoding='utf-8')
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = ROOT / '.test-state/intent-context/native/intent-probe.exe'
    if not executable.exists():
        raise SystemExit('Run scripts/test_intent_context.py first to build the native probe')
    data = work / ('data-' + str(time.time_ns()))
    (data / 'host').mkdir(parents=True)
    env = os.environ.copy()
    env['RINX_DATA_DIR'] = str(data / 'host')
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    report_path = data / 'dev.cfaw.runtime-tests/repair-report.json'
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data), '--remote=' + str(port), '--size', '800x1050'], cwd=executable.parent, env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and process.poll() is None and not report_path.exists():
                time.sleep(.2)
            report = json.loads(report_path.read_text(encoding='utf-8'))
            (work / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
            assert report['failed'] == 0, report
        finally:
            try:
                with urlopen(f'http://127.0.0.1:{port}/quit', timeout=2):
                    pass
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
                process.wait(timeout=5)
    assert '[E]' not in (work / 'host.log').read_text(encoding='utf-8', errors='replace')


if __name__ == '__main__':
    main()
