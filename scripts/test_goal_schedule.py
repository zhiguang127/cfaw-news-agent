"""Native trial plan and explicit calendar approval regression; synthetic news and model plans."""
import json
import os
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe


def main():
    work = ROOT / '.test-state/goal-schedule'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    (bundle / 'main.splash').write_text(source + (ROOT / 'tests/scenarios/goal_schedule.splash').read_text(encoding='utf-8'), encoding='utf-8')
    data = work / ('data-' + str(time.time_ns()))
    app = data / 'dev.cfaw.runtime-tests'
    app.mkdir(parents=True)
    (data / 'host').mkdir()
    host = ensure_native_probe()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(host), '--bundle', str(bundle), '--app-data', str(data), '--size', '430x860'],
                                   cwd=host.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if (app / 'goal-schedule.json').exists():
                    report = json.loads((app / 'goal-schedule.json').read_text(encoding='utf-8'))
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('Native goal schedule checks did not complete')
        finally:
            process.terminate()
            process.wait(timeout=5)
    errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    report['native_errors'] = errors
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not report['failures'] and not errors, report
    print('PASS:', len(report['checks']), 'trial plan, approval, conflicts, stale evidence and idempotent import checks')


if __name__ == '__main__':
    main()
