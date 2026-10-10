"""Click article follow in the native UI; labelled synthetic model output only."""
import json
import os
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble

work = ROOT / '.test-state/follow-topic'
bundle = work / 'bundle'
bundle.mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += r'''
let follow_test_calls = 0
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    tracking_schedule_check = fn(){}
    analysis_host_has = |name| true
    analysis_host_request = fn(name, data, callback){
        if name == "octos.turn.start" {
            follow_test_calls = follow_test_calls + 1
            start_timeout(0.1, || callback({is_ok: true data: {text: "{\"schema_version\":1,\"status\":\"ready\",\"question\":\"\",\"understanding\":{\"title\":\"笔记本续航（合成测试）\",\"purpose\":\"了解办公笔记本续航变化\",\"scope\":[\"笔记本续航\"],\"preferences\":[],\"recall_rules\":[{\"kind\":\"keyword\",\"value\":\"续航\"}]}}"}}))
        } else { callback({is_ok: true data: {}}) }
    }
    let row = news_normalize({title: "合成测试：办公笔记本续航升级" link: "https://www.ithome.com/follow-fixture" summary: "明确标注的交互测试新闻"}, news_source("ithome"), time_now())
    app_feed_rows = [row] feed_rows_by_source["ithome"] = [row]
    render_main()
    start_interval(0.1, || fs.write("follow-state.json", {draft: intent_draft topics: topic_records.topics interests: user_interests calls: follow_test_calls}.to_json()))
})
'''
(bundle / 'main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
(data / 'host').mkdir(parents=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
exe = ROOT / '.test-state/intent-context/native/intent-probe.exe'
state_path = data / 'dev.cfaw.runtime-tests/follow-state.json'

def get(route, **params):
    with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as response:
        return response.read()

def widgets():
    return json.loads(get('/snap'))['s']

def click(label):
    for _ in range(30):
        button = next((w for w in widgets() if w.get('t') == label and w.get('ty') == 'Button' and 0 < w['r'][1] < 830), None)
        if button:
            x, y, width, height = button['r']
            get('/click', x=x + width / 2, y=y + height / 2, wait=1)
            time.sleep(.65)
            return
        get('/m', k='scroll', x=200, y=700, dy=300, wait=1)
    raise RuntimeError('Button unavailable: ' + label)

def state():
    return json.loads(state_path.read_text(encoding='utf-8'))

startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
checks = []
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data), '--remote=' + str(port), '--size', '430x860'],
        cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
    try:
        for _ in range(100):
            if state_path.exists():
                break
            time.sleep(.1)
        click('关注话题')
        first = state()
        assert first['calls'] == 0 and not first['topics'] and not first['interests']
        assert '办公笔记本续航升级' in first['draft']['original_input']
        assert 'https://www.ithome.com/follow-fixture' in first['draft']['supplement']
        assert any('办公笔记本续航升级' in w.get('t', '') for w in widgets() if w.get('ty') == 'TextInput')
        (work / 'article-draft.png').write_bytes(get('/g', raw=1))
        checks.append('Actual article button opens editable article context without model calls or source subscriptions')
        click('取消并保留草稿')
        click('关注话题')
        assert state()['draft']['draft_id'] == first['draft']['draft_id']
        assert state()['draft']['original_input'] == first['draft']['original_input']
        checks.append('Existing draft survives another article-follow click')
        click('整理我的想法 ↗')
        time.sleep(.6)
        assert not state()['topics'] and state()['calls'] == 1
        click('确认关注并保存')
        final = state()
        assert len(final['topics']) == 1 and not final['interests']
        assert final['topics'][0]['recall_rules'] == [{'kind': 'keyword', 'value': '续航'}]
        checks.append('Only explicit confirmation creates a scoped topic; no publisher-wide rule')
    except Exception:
        (work / 'failure.json').write_bytes(get('/snap'))
        (work / 'failure.png').write_bytes(get('/g', raw=1))
        raise
    finally:
        process.terminate()
        process.wait(timeout=5)
assert '[E]' not in (work / 'host.log').read_text(encoding='utf-8', errors='replace')
(work / 'report.json').write_text(json.dumps({'checks': checks}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(checks, ensure_ascii=False))
