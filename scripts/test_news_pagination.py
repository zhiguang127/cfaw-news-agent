"""Exercise page boundaries in the native UI with labelled synthetic news."""
import json
import os
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe

work = ROOT / '.test-state/news-pagination'
bundle = work / 'bundle'
bundle.mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    tracking_schedule_check = fn(){}
    let rows = []
    for i in 81 {
        rows.push(news_normalize({title: "合成分页测试 #" + i link: "https://www.ithome.com/pagination-fixture-" + i}, news_source("ithome"), time_now()))
    }
    app_feed_rows = rows feed_rows_by_source["ithome"] = rows
    render_main()
    start_interval(0.1, || fs.write("pagination-state.json", {offset: feed_page_offset total: app_feed_rows.len()}.to_json()))
})
'''
(bundle / 'main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
(data / 'host').mkdir(parents=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
exe = ensure_native_probe()
state_path = data / 'dev.cfaw.runtime-tests/pagination-state.json'

def get(route, **params):
    with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as response:
        return response.read()

def titles():
    return [w['t'] for w in json.loads(get('/snap'))['s'] if w.get('ty') == 'Label' and w.get('t', '').startswith('合成分页测试 #')]

def check_page(offset, count):
    for _ in range(40):
        state = json.loads(state_path.read_text(encoding='utf-8'))
        shown = titles()
        if state['offset'] == offset and shown:
            assert state['total'] == 81
            assert set(shown).issubset({'合成分页测试 #' + str(i) for i in range(offset, offset + count)})
            return
        time.sleep(.1)
    raise RuntimeError('Unexpected page: ' + str(state) + ' ' + str(shown))

def click(identifier):
    for _ in range(40):
        widgets = json.loads(get('/snap'))['s']
        button = next((w for w in widgets if w.get('i') == identifier and 0 < w['r'][1] < 810), None)
        if button:
            x, y, width, height = button['r']
            get('/click', x=x + width / 2, y=y + height / 2, wait=1)
            time.sleep(.3)
            return
        get('/m', k='scroll', x=200, y=700, dy=800, wait=1)
    raise RuntimeError('Pagination button unavailable: ' + identifier)

startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data), '--remote=' + str(port), '--size', '430x860'],
        cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
    try:
        for _ in range(100):
            if state_path.exists():
                break
            time.sleep(.1)
        check_page(0, 40)
        click('next_news_page')
        check_page(40, 40)
        (work / 'second-page.png').write_bytes(get('/g', raw=1))
        click('next_news_page')
        check_page(80, 1)
        click('previous_news_page')
        check_page(40, 40)
        click('previous_news_page')
        check_page(0, 40)
    finally:
        process.terminate()
        process.wait(timeout=5)
assert '[E]' not in (work / 'host.log').read_text(encoding='utf-8', errors='replace')
report = {'pages': [40, 40, 1], 'back_navigation': True, 'retained_news': 81, 'synthetic': True}
(work / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
