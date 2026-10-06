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
    work = ROOT / '.test-state/intent-context'
    bundle, native = work / 'bundle', work / 'native'
    bundle.mkdir(parents=True, exist_ok=True)
    native.mkdir(exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += r"""
let intent_probe_reply = "{\"schema_version\": 1, \"status\": \"ready\", \"question\": \"\", \"understanding\": {\"title\": \"AI 日常应用（固定测试）\", \"purpose\": \"了解工作与学习中的 AI 新进展\", \"scope\": [\"AI 新功能\", \"工作、学习与日常应用\"], \"preferences\": [], \"recall_rules\": [{\"kind\": \"keyword\", \"value\": \"AI\"}]}}"
let intent_probe_calls = 0
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name == "octos.session.open" { callback({is_ok: true data: {}}) }
        else if name == "octos.turn.start" {
            intent_probe_calls = intent_probe_calls + 1
            let call = intent_probe_calls
            start_timeout(0.5, || {
                if call == 1 { intent_changed(intent_draft.original_input, false) }
                else { intent_changed(intent_draft.original_input + "（固定测试修改）", false) }
            })
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
    executable = native / 'intent-probe.exe'
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
            click('我想做…')
            click(ident='intent_input')
            get('/t',t='我想了解最新 AI 进展如何帮助我的工作、学习和日常生活',wait=1)
            click('整理我的想法 ↗')
            time.sleep(1.8)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            (work/'intent.png').write_bytes(get('/g',raw=1))
            assert counts['state']=='succeeded',counts
            find('确认目标关注并保存')
            click('确认目标关注并保存')
            time.sleep(.7)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            assert len(counts['topics'])==1 and counts['draft'] is None,counts
            checks.append('same-value input notification preserves delayed reply; preview and explicit confirm persist one goal')
            click(ident='menu_button');click('管理关注')
            find('AI 日常应用（固定测试）')
            (work/'manage-tracking.png').write_bytes(get('/g',raw=1))
            click('‹ 返回');click(ident='menu_button');click('关注动态')
            find('我的关注 · 1 项 · 0 条未读更新')
            find('已保存关注，当前没有匹配的相关新闻；可刷新新闻或调整关注范围。')
            (work/'tracking.png').write_bytes(get('/g',raw=1))
            checks.append('management shows saved goal; tracking counts it and distinguishes no matching news from no focus')
            click(ident='manage_tracking_button');click('修改');time.sleep(.8)
            click('整理我的想法 ↗');time.sleep(1.8)
            counts=json.loads((data/'dev.cfaw.runtime-tests/state.json').read_text(encoding='utf-8'))
            assert counts['state']=='failed' and '输入文字已修改' in counts['error'],counts
            assert '未新增或修改关注' in counts['error'],counts
            assert len(counts['topics'])==1 and counts['topics'][0]['version']==1,counts
            assert counts['draft']['state']=='editing',counts
            find(counts['error'])
            (work/'real-edit-rejected.png').write_bytes(get('/g',raw=1))
            checks.append('real edit rejects old reply with concrete reason and leaves saved topic unchanged')
        except Exception:
            (work/'failure-snapshot.json').write_bytes(get('/snap')); (work/'failure.png').write_bytes(get('/g',raw=1)); raise
        finally:
            try: get('/quit'); process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired): process.terminate();process.wait(timeout=5)
    assert '[E]' not in (work/'host.log').read_text(encoding='utf-8',errors='replace')
    (work/'report.json').write_text(json.dumps({'checks':checks,'records':counts},indent=2),encoding='utf-8')
    print(work)


if __name__=='__main__': main()
