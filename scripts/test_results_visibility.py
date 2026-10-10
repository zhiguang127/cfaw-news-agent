"""Native Rinx presentation checks with synthetic records, no accounts or model calls."""
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
    work = ROOT / '.test-state/results-visibility'
    bundle, native = work / 'bundle', work / 'native'
    bundle.mkdir(parents=True, exist_ok=True)
    native.mkdir(exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    let row = news_normalize({title: "Synthetic retained Chinese news" link: "https://example.org/retained"},
        {id: "fixture" label: "Synthetic source" kind: "rss" category: "china" language: "zh" url: "https://example.org/feed"}, time_now())
    app_feed_rows = [row]
    records_toggle_bookmark(row)
    enabled_source_ids = ["bbc"]
    news_http_request = fn(url, redirects, callback){ callback({success: false error: "Synthetic source unavailable" category: "network"}) }
    analysis_history = [{analysis_id: "fixture-analysis" news_id: row.news_id outcome: "no_change"
        explanation: "Synthetic archived analysis" created_at: time_now() news_snapshot: row prompt_revision: "obsolete"}]
    suggestion_history = [
        {suggestion_id: "fixture-accepted" analysis_id: "fixture-analysis" news_id: row.news_id state: "accepted" change_summary: "Synthetic archived accepted suggestion"}
        {suggestion_id: "fixture-pending" analysis_id: "fixture-analysis" news_id: row.news_id state: "pending" change_summary: "Synthetic pending suggestion" rationale: "Synthetic pending rationale" uncertainties: [] proposed_action: nil}
    ]
    tracking_cache.runs = [{checked_at: time_now() snapshot: {prompt_revision: "obsolete" topics: [] legacy_interests: [] schedules: []}
        result: {explanation: "Synthetic archived target check" items: [] insights: []}}]
    schedule_actions.items = [{action_id: "fixture-applied" state: "applied" original: {title: "Synthetic archived reschedule"
        start: "2030-10-06T12:00:00+08:00" end: "2030-10-06T13:00:00+08:00" timezone: "Asia/Shanghai"}
        start: "2030-10-06T14:00:00+08:00" end: "2030-10-06T15:00:00+08:00"}]
    let previous = {target_type: "topic" target_id: "fixture-goal" target_version: 1 issue_key: "fixture-terms"
        summary: "Synthetic previous interpretation" next_step: "Synthetic previous check"}
    tracking_cache.runs.push({task_id: "fixture-comparison" checked_at: time_now() - 60
        snapshot: {prompt_revision: "obsolete" topics: [] schedules: [] legacy_interests: [] evidence: []}
        result: {insights: [previous] items: [] explanation: "Synthetic previous check"}})
    let current = {title: "Synthetic current target" state: "pending" run: {snapshot: {evidence: [] topics: [{topic_id: "fixture-goal" version: 1 purpose: "Synthetic family photo goal" preferences: ["Synthetic no repeated headlines"]}]}}
        insight: {target_type: "topic" target_id: "fixture-goal" target_version: 1 issue_key: "fixture-terms" compared_run_id: "fixture-comparison"
            change_kind: "updated" summary: "Synthetic current change" material_change: "Synthetic clarified applicability"
            uncertainties: [] evidence_ids: [] next_step: "Synthetic check terms" decision_effect: "review"}}
    current.run.ui_fixture_current = true
    // Synthetic presentation fixture; real stale/version guards have separate tests.
    tracking_run_current = fn(run){ run["ui_fixture_current"] == true }
    let handled = current.to_json().parse_json()
    handled.title = "Synthetic handled target" handled.state = "handled" handled.insight.summary = "Synthetic archived handled change"
    let withdrawn = current.to_json().parse_json()
    withdrawn.title = "Synthetic withdrawn target" withdrawn.state = "withdrawn"
    withdrawn.insight.change_kind = "withdrawn" withdrawn.insight.summary = "Synthetic withdrawn interpretation"
    current_insights = fn(){ [current handled withdrawn] }
    render_main()
    start_timeout(0.1, || refresh())
    start_interval(0.2, || fs.write("record-counts.json", {analyses: analysis_history.len() suggestions: suggestion_history.len()
        runs: tracking_cache.runs.len() actions: schedule_actions.items.len() bookmarks: user_bookmarks.len()}.to_json()))
    start_interval(0.2, || fs.write("plan-state.json", {draft: intent_draft schedules: user_schedules.len() error: intent_error}.to_json()))
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = native / 'presentation-probe.exe'
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
    def seek(label):
        for _ in range(10):
            try: return find(label)
            except StopIteration: get('/m',k='scroll',x=200,y=650,dy=400,wait=1)
        raise AssertionError('Missing visible result: '+label)
    def top(): get('/m',k='scroll',x=200,y=650,dy=-10000,wait=1)
    def no_archives():
        labels=texts()
        assert not any('历史' in text or 'Synthetic archived' in text or text in ('最近分析','旧版建议记录') for text in labels),labels
    checks=[]
    with (work/'host.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(executable),'--bundle',str(bundle),'--app-data',str(data),'--remote='+str(port),'--size','430x860'],cwd=native,env=env,stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    if find(ident='status').get('t')=='1 条新闻': break
                except (OSError,StopIteration): pass
                time.sleep(.1)
            else: raise RuntimeError('Fixture feed did not finish refresh')
            assert '中文' not in texts()
            assert not any('部分来源暂时不可用' in text for text in texts())
            find('Synthetic retained Chinese news')
            (work/'feed.png').write_bytes(get('/g',raw=1))
            checks.append('failed-source refresh completes without partial-source banner; Chinese category absent, article retained')
            menu('我的收藏')
            assert '中文' not in texts()
            find('Synthetic retained Chinese news')
            (work/'bookmarks.png').write_bytes(get('/g',raw=1))
            checks.append('bookmark category removed; original Chinese bookmark remains under all')
            menu('关注动态'); click('查看分析与建议')
            find('Synthetic family photo goal'); no_archives()
            seek('Synthetic previous interpretation')
            seek('Synthetic current change')
            seek('改变判断的新事实：Synthetic clarified applicability')
            (work/'tracking-results.png').write_bytes(get('/g',raw=1))
            seek('Synthetic withdrawn interpretation')
            (work/'withdrawn.png').write_bytes(get('/g',raw=1))
            seek('Synthetic pending suggestion'); no_archives(); top()
            checks.append('current goal and exact previous interpretation are visible; withdrawn changes stay visible; handled records hidden by default')
            click('查看本轮全部判断与决定')
            seek('Synthetic archived handled change')
            top(); click('只看需要关注的判断'); no_archives()
            checks.append('all-current-results toggle exposes recorded decisions without erasing or reopening them')
            seek('把核实安排到日程'); click('把核实安排到日程'); time.sleep(.8)
            plan=json.loads((data/'dev.cfaw.runtime-tests/plan-state.json').read_text(encoding='utf-8'))
            assert plan['draft']['intent_kind']=='schedule' and 'Synthetic check terms' in plan['draft']['original_input'],plan
            assert plan['schedules']==0,plan
            (work/'plan-check.png').write_bytes(get('/g',raw=1))
            seek('取消并保留草稿'); click('取消并保留草稿'); time.sleep(.6)
            top(); seek('把核实安排到日程'); click('把核实安排到日程'); time.sleep(.8)
            blocked=json.loads((data/'dev.cfaw.runtime-tests/plan-state.json').read_text(encoding='utf-8'))
            assert blocked['draft']['draft_id']==plan['draft']['draft_id'] and '已有草稿已保留' in blocked['error'],blocked
            assert blocked['schedules']==0,blocked
            seek('取消并保留草稿'); click('取消并保留草稿'); time.sleep(.6)
            checks.append('next check becomes an unsaved schedule draft; existing draft is preserved on repeat entry')
            click('‹ 返回'); click(ident='menu_button'); click(ident='suggestions_button')
            seek('Synthetic current change'); no_archives()
            get('/m',k='scroll',x=200,y=650,dy=550,wait=1); no_archives()
            (work/'menu-results.png').write_bytes(get('/g',raw=1))
            counts=json.loads((data/'dev.cfaw.runtime-tests/record-counts.json').read_text())
            assert counts=={'analyses':1,'suggestions':2,'runs':2,'actions':1,'bookmarks':1},counts
            checks.append('menu entry also excludes archives through page bottom; backing record counts unchanged')
        except Exception:
            (work/'failure-snapshot.json').write_bytes(get('/snap')); (work/'failure.png').write_bytes(get('/g',raw=1)); raise
        finally:
            try: get('/quit'); process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired): process.terminate();process.wait(timeout=5)
    assert '[E]' not in (work/'host.log').read_text(encoding='utf-8',errors='replace')
    (work/'report.json').write_text(json.dumps({'checks':checks,'records':counts},indent=2),encoding='utf-8')
    print(work)


if __name__=='__main__': main()
