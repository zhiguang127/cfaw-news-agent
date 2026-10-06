"""Regress intent validity, confirmation and visible tracking with delayed synthetic replies."""
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


def main():
    release = Path('D:/Hackathon_agenticapp/Rinx-main/target/release')
    work = ROOT / '.test-state/intent-recovery'
    bundle, native = work / 'bundle', work / 'native'
    bundle.mkdir(parents=True, exist_ok=True)
    native.mkdir(exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += r"""
let intent_probe_reply = "{\"schema_version\": 1, \"status\": \"ready\", \"question\": \"\", \"understanding\": {\"title\": \"具身智能（固定测试）\", \"purpose\": \"持续了解具身智能领域发展\", \"scope\": [\"具身智能\", \"机器人与人工智能\"], \"preferences\": [], \"recall_rules\": [{\"kind\": \"keyword\", \"value\": \"具身智能\"}, {\"kind\": \"keyword\", \"value\": \"robotics\"}]}}"
let intent_probe_calls = 0
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    let initial = topic_new_draft(nil)
    initial.original_input = "旧关注（固定测试）"
    initial.state = "ready" initial.understanding = intent_probe_reply.parse_json().understanding
    topic_confirm(initial)
    let next = topic_records.to_json().parse_json()
    next.topics[0].version = 3 topics_commit(next)
    let old_id = topic_records.topics[0].topic_id
    let editing = topic_new_draft(old_id)
    editing.original_input = "关注具身智能领域"
    topic_save_draft(editing)
    topic_set_status(old_id, 3, "cancelled")
    topics_load()
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name == "octos.session.open" { callback({is_ok: true data: {}}) }
        else if name == "octos.turn.start" {
            intent_probe_calls = intent_probe_calls + 1
            let call = intent_probe_calls
            if call == 2 {
                start_timeout(0.4, || topic_set_status(intent_draft.target_topic_id, intent_draft.target_version, "paused"))
            }
            start_timeout(1.2, || {
                fs.write("before-reply.json", {open: intent_open draft: intent_draft busy: analysis_busy}.to_json())
                callback({is_ok: true data: {text: intent_probe_reply}})
            })
        } else { callback({is_ok: true data: {}}) }
    }
    intent_begin(nil)
    start_interval(0.2, || fs.write("state.json", {open: intent_open state: analysis_state error: intent_error draft: intent_draft topics: topic_records.topics}.to_json()))
})
"""
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = ROOT / '.test-state/intent-context/native/intent-probe.exe'
    if not executable.exists(): executable = native / 'intent-recovery-probe.exe'
    libraries = list((release / 'deps').glob('librinx-*.rlib'))
    assert len(libraries) == 1
    probe = ROOT / 'tests/scenarios/rinx_render_probe.rs'
    command = ['rustc', '+1.98.0', '--edition=2024', '-C', 'opt-level=2', '--crate-name', 'cfaw_presentation_probe', '--extern', 'rinx='+str(libraries[0]), '-L', 'dependency='+str(release/'deps'), str(probe), '-o', str(executable)]
    for output in (release/'build').glob('*/output'):
        for line in output.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('cargo:rustc-link-search='): command += ['-L',line.split('=',1)[1]]
    if not executable.exists() or executable.stat().st_mtime < max(probe.stat().st_mtime,libraries[0].stat().st_mtime):
        subprocess.run(command, check=True)
    for resources in ('makepad_widgets/resources', 'rinx/resources'):
        shutil.copytree(release/resources, native/resources, dirs_exist_ok=True)
    data = work / ('data-'+str(time.time_ns()))
    (data/'host').mkdir(parents=True)
    env = os.environ.copy(); env['RINX_DATA_DIR'] = str(data/'host')
    sock = socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
    def get(route, **params):
        with urlopen(f'http://127.0.0.1:{port}{route}?'+urlencode(params), timeout=8) as response: return response.read()
    def widgets(): return json.loads(get('/snap'))['s']
    def texts(): return [w.get('t','') for w in widgets() if w.get('ty')!='Splash']
    def find(label=None, ident=None):
        return next(w for w in widgets() if w.get('ty')!='Splash' and (label is None or w.get('t')==label) and (ident is None or w.get('i')==ident))
    def click(label=None, ident=None):
        x,y,w,h=find(label,ident)['r']; get('/click',x=x+w/2,y=y+h/2,wait=1); time.sleep(.25)
    def menu(label): click(ident='menu_button'); click(label)
    checks=[]
    with (work/'host.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(executable),'--bundle',str(bundle),'--app-data',str(data),'--remote='+str(port),'--size','800x1050'],cwd=native,env=env,stdout=log,stderr=log)
        try:
            time.sleep(2.0)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            assert counts['draft']['target_topic_id'] is None and counts['draft']['original_input']=='关注具身智能领域',counts
            assert counts['topics'][0]['status']=='cancelled' and counts['topics'][0]['version']==4,counts
            find('新建关注 · 确认后新增一条关注')
            find('原关注已取消或不存在，已保留输入并转为新建关注。')
            (work/'recovered.png').write_bytes(get('/g',raw=1))
            click('重试整理');time.sleep(1.8)
            find('确认关注并保存');click('确认关注并保存');time.sleep(.7)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            assert len(counts['topics'])==2 and counts['draft'] is None,counts
            assert counts['topics'][0]['status']=='cancelled' and counts['topics'][0]['version']==4,counts
            assert counts['topics'][1]['status']=='active' and counts['topics'][1]['original_input']=='关注具身智能领域',counts
            checks.append('restored draft bound to cancelled v3/v4 target becomes a new topic, keeps input, and never resurrects old target')
            click(ident='menu_button');click('管理关注');find('具身智能（固定测试）')
            (work/'new-topic.png').write_bytes(get('/g',raw=1))
            click('修改');time.sleep(.8);click('整理我的想法 ↗');time.sleep(1.8)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            assert '原关注版本已更新' in counts['error'],counts
            find('加载原关注最新版本')
            (work/'version-conflict.png').write_bytes(get('/g',raw=1))
            click('加载原关注最新版本');click('重试整理');time.sleep(1.8)
            find('确认关注并保存');click('确认关注并保存');time.sleep(.7)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            assert len(counts['topics'])==2 and counts['topics'][1]['version']==3,counts
            assert counts['topics'][0]['status']=='cancelled',counts
            checks.append('actual active-target version change rejects stale reply, explicit reload allows new preview and confirmation')
        except Exception:
            (work/'failure-snapshot.json').write_bytes(get('/snap')); (work/'failure.png').write_bytes(get('/g',raw=1)); raise
        finally:
            try: get('/quit'); process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired): process.terminate();process.wait(timeout=5)
    assert '[E]' not in (work/'host.log').read_text(encoding='utf-8',errors='replace')
    (work/'report.json').write_text(json.dumps({'checks':checks,'records':counts},indent=2),encoding='utf-8')
    print(work)


if __name__=='__main__': main()
