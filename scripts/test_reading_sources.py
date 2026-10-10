"""Verify real publisher samples and labelled synthetic Agent replies in Rinx."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble

work = ROOT / '.test-state/reading-sources'
bundle = work / 'bundle'
bundle.mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += (ROOT / 'tests/scenarios/reading_sources.splash').read_text(encoding='utf-8')
(bundle / 'main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
app_data = data / 'dev.cfaw.runtime-tests'
app_data.mkdir(parents=True)
(data / 'host').mkdir()
for path in (work / 'samples').glob('*'):
    shutil.copy2(path, app_data / path.name)
(app_data / 'summary-long-fixture.txt').write_text('合成长文段落：我们验证摘要分段提取时不会丢失新闻正文末尾。' * 450, encoding='utf-8')
executable = ROOT / '.test-state/reader-430x860-live/native/reader-probe.exe'
if not executable.is_file():
    raise SystemExit('Build the isolated reader probe with test_reader_ui.py first')
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
def get(route, **params):
    with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as response:
        return response.read()
report_path = app_data / 'reading-report.json'
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data), '--remote=' + str(port), '--size', '430x860'],
                               cwd=executable.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')),
                               stdout=log, stderr=log, startupinfo=startup)
    clicked = False
    summary_checked = False
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and process.poll() is None:
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding='utf-8'))
                if report['stage'] == 'ui_ready' and not clicked:
                    widgets = json.loads(get('/snap'))['s']
                    button = next(w for w in widgets if w.get('i') == 'agent_summary_button' and w.get('ty') == 'Button')
                    (work / 'summary-before.json').write_text(json.dumps(widgets, ensure_ascii=False), encoding='utf-8')
                    (work / 'summary-before.png').write_bytes(get('/g', raw=1))
                    x, y, width, height = button['r']
                    get('/click', x=x + width / 2, y=y + height / 2, wait=1)
                    clicked = True
                if report['stage'] == 'summary_ready' and not summary_checked:
                    widgets = json.loads(get('/snap'))['s']
                    (work / 'summary-after.json').write_text(json.dumps(widgets, ensure_ascii=False), encoding='utf-8')
                    (work / 'summary-after.png').write_bytes(get('/g', raw=1))
                    expected = '这是合成模型回复，用于验证手动摘要流程。'
                    summary = next((w for w in widgets if w.get('i') == 'reader_agent_summary_text' and w.get('t') == expected and w.get('ty') == 'Label'), None)
                    if summary is None or summary['r'][2] <= 0 or summary['r'][3] <= 0:
                        raise RuntimeError('Generated summary text missing or collapsed in actual UI; inspect summary-after.json/png')
                    summary_checked = True
                    (app_data / 'summary-ui-checked.txt').write_text('checked', encoding='utf-8')
                if report['stage'] == 'complete':
                    break
            time.sleep(.1)
        else:
            raise RuntimeError('Reading checks did not finish; inspect ' + str(work / 'host.log'))
    finally:
        process.terminate()
        process.wait(timeout=5)
report = json.loads(report_path.read_text(encoding='utf-8'))
(work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: report[key] for key in ('passed', 'failed', 'stage', 'sources', 'model_calls', 'tail_seen')}, ensure_ascii=False, indent=2))
errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
if report['failed'] or errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print('Native UI button clicked and generated summary text visible; publisher samples and synthetic Agent checks passed: ' + str(work))
