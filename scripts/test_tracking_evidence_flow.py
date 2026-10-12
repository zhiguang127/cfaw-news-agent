"""Native goal evidence flow, judgment guards and a real verification-button click."""
import json
import os
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe

exe = ensure_native_probe()
work = ROOT / '.test-state/tracking-evidence-flow'
(work / 'bundle').mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += r'''
let flow_checks = [] let flow_failures = [] let flow_calls = 0 let flow_requests = [] let flow_phase = 1
let flow_topic = nil let flow_id = "https://sspai.com/post/fixture-verification" let flow_show_results_seen = false
fn flow_assert(value, label){ if value { flow_checks.push(label) } else { flow_failures.push(label) } }
fn flow_wait(condition, complete, deadline){
    if time_now() > deadline { flow_assert(false, "phase deadline") flow_report() return }
    if condition() { start_timeout(0.1, complete) }
    else { start_timeout(0.03, || flow_wait(condition, complete, deadline)) }
}
fn flow_report(){ fs.write("flow-report.json", {complete: true checks: flow_checks failures: flow_failures
    model_calls: flow_calls requests: flow_requests}.to_json()) }
fn flow_result(){
    let items = [] let label = "" let e = nil
    for i evidence in agent_task.snapshot.evidence {
        let id = "E" + (i + 1)
        items.push({news_id: id relevance: "uncertain" topic_ids: [flow_topic.topic_id] legacy_interest_ids: []
            why_related: "固定测试：可能相关，需核实使用条件" evidence_ids: [id] uncertainties: [] schedule_impacts: []})
        if evidence.news_id == flow_id { label = id e = evidence }
    }
    let refs = []
    if e.paragraphs.len() > 0 { refs.push({news_id: label paragraph_id: e.paragraphs[0].paragraph_id quote: bm25_prefix(e.paragraphs[0].text, 80)}) }
    let insight = {target_type: "topic" target_id: flow_topic.topic_id target_version: 1 issue_key: "meeting-access"
        summary: "本期暂不新增试用建议，需先核实这篇会议工具报道的使用条件。" decision_effect: "unknown"
        next_step: "补充《固定测试：会议工具访问条件》的正文，并核实账号、费用与隐私要求。"
        uncertainties: ["账号与费用条件尚待核实"] evidence_ids: [label] evidence_refs: refs
        change_kind: "new" compared_run_id: nil material_change: "" reschedule: nil}
    if agent_task.snapshot.previous_by_target.len() > 0 {
        insight.compared_run_id = agent_task.snapshot.previous_by_target[0].run_id
        insight.change_kind = "updated" insight.material_change = "此次取得了此前未能读取的正文片段，使用条件仍待核实。"
        insight.summary = "来源正文披露了会议转写试用及注册要求，费用与隐私条件仍待核实，本期暂不新增试用建议。"
        insight.next_step = "核实该工具当前费用、开放范围与隐私条款，再决定是否试用。"
    }
    {schema_version: 2 outcome: if e.paragraphs.len() == 0 {"insufficient_evidence"} else {"update"}
        explanation: "本期检查仅覆盖选中的报道；待核实条件不会自动占用学习时间。" items: items insights: [insight]}
}
fn flow_first(){
    let run = tracking_cache.runs[0]
    flow_assert(flow_calls == 2 && run.result.outcome == "insufficient_evidence" && agent_task.repair_count == 1, "internal prose is repaired once and title-only goal ends as insufficient evidence")
    flow_assert(flow_requests.len() == 2 && flow_requests[0] == flow_id, "goal auto-enrichment prioritizes missing summaries and caps web requests")
    let local_count = 0
    for e in run.snapshot.evidence {
        if regex("/rss/").test(e.news_id) && e.paragraphs.len() > 0 { local_count = local_count + 1 }
    }
    flow_assert(local_count == 4, "four RSS bodies attach even after two web requests; cache does not evict them")
    let long = tracking_find(run.snapshot.evidence, "news_id", "https://www.ithome.com/rss/0")
    flow_assert(long.paragraphs.len() == 1 && long.body_truncated && long.paragraphs[0].text.to_bytes().len() <= 4000, "oversized first paragraph keeps a bounded real excerpt")
    flow_assert(regex("未引用原句").test(insight_basis_label(run.result.insights[0], long)), "available unquoted body is not mislabeled title-only or a quotation")
    let blocked = tracking_find(run.snapshot.evidence, "news_id", flow_id)
    flow_assert(blocked.paragraphs.len() == 0 && regex("验证").test(blocked.body_error), "verification response is not promoted to article evidence")
    flow_assert(evidence_summary_label(blocked) == "仅有标题", "title-only evidence is never labeled a summary")
    flow_assert(!evidence_retry_due(tracking_current_row(flow_id)), "failed web fetch has a cooldown")
    flow_assert(insight_basis_label(run.result.insights[0], blocked) == "判断依据 · 仅有标题", "no body quotation heading for title-only judgment")
    let candidate = run.result.to_json().parse_json()
    flow_assert(tracking_judgment_validate(candidate, run.snapshot).valid, "cautious goal with concrete verification passes")
    candidate.outcome = "no_change"
    flow_assert(!tracking_judgment_validate(candidate, run.snapshot).valid, "absence of title-only evidence is not confirmed no-change")
    candidate.outcome = "insufficient_evidence" candidate.insights[0].decision_effect = "none"
    flow_assert(!tracking_judgment_validate(candidate, run.snapshot).valid, "unsupported no-action judgment is rejected")
    candidate.insights[0].decision_effect = "unknown" candidate.insights[0].summary = "can_quote_body=false、paragraphs=[]"
    flow_assert(!tracking_judgment_validate(candidate, run.snapshot).valid, "internal diagnostics trigger bounded model repair")
    candidate.insights[0].summary = "固定测试：来源摘要披露了条件，判断仅限这些条件。" candidate.insights[0].decision_effect = "none" candidate.outcome = "no_change"
    let summary_snapshot = run.snapshot.to_json().parse_json()
    tracking_find(summary_snapshot.evidence, "news_id", flow_id).summary = "固定来源摘要：免费开放普通账号试用。"
    flow_assert(tracking_judgment_validate(candidate, summary_snapshot).valid, "a real supplied summary can support a scoped no-change claim without body quotes")
    let unrelated = run.result.to_json().parse_json()
    for item in unrelated.items { item.relevance = "unrelated" item.topic_ids = [] }
    flow_assert(!insights_validate(unrelated, run.snapshot).valid, "unrelated suicide-style candidate cannot support a product-tracking insight")
    let legacy_snapshot = run.snapshot.to_json().parse_json() legacy_snapshot.prompt_revision = "tracking-v2.4"
    flow_assert(insights_validate(unrelated, legacy_snapshot).valid, "historical records retain their original validation contract and are not discarded on upgrade")
    for item in unrelated.items { item.relevance = "uncertain" item.topic_ids = [] }
    flow_assert(!insights_validate(unrelated, run.snapshot).valid, "another target's uncertain story cannot support this goal")
    for item in unrelated.items { item.relevance = "unrelated" }
    unrelated.insights[0].evidence_ids = [] unrelated.insights[0].evidence_refs = []
    unrelated.insights[0].summary = "本期有限候选中没有找到此目标的相关新闻；不能确认产品是否有新进展。"
    flow_assert(insights_validate(unrelated, run.snapshot).valid && tracking_judgment_validate(unrelated, run.snapshot).valid, "no relevant stories permits an honest empty citation instead of forced unrelated evidence")
    unrelated.insights[0].decision_effect = "review"
    flow_assert(!insights_validate(unrelated, run.snapshot).valid, "empty evidence cannot reopen a decision")
    unrelated.insights[0].decision_effect = "unknown"
    let continued = run.snapshot.to_json().parse_json()
    continued.previous_by_target[0] = {target_type: "topic" target_id: flow_topic.topic_id run_id: "last-product-check" insights: [run.result.insights[0]]}
    unrelated.insights[0].compared_run_id = "last-product-check" unrelated.insights[0].change_kind = "unchanged"
    flow_assert(insights_validate(unrelated, continued).valid, "no new related news can retain the exact previous issue without inventing current evidence")
    let empty_view = {insight: unrelated.insights[0] state: "unchanged" run: {snapshot: continued result: unrelated}}
    flow_assert(results_news(empty_view).len() == 0 && results_cited_news(empty_view).len() == 0 && !insight_can_verify(empty_view), "empty relevant-news overview has no foreign sources or fetch button")
    flow_assert(results_heading(empty_view) == "本轮未确认实质变化", "unchanged judgment never announces new evidence")
    unrelated.insights[0].material_change = "凭空声称新依据"
    flow_assert(!insights_validate(unrelated, continued).valid, "unchanged cannot simultaneously claim material new facts")
    let human = insight_prose(run, "E2、E3等报道 can_quote_body=false，paragraphs=[]")
    flow_assert(!regex("E[23]|can_quote_body|paragraphs").test(human), "historical prose resolves labels and translates diagnostics")
    let old = {snapshot: {evidence: [{title: "上期会议工具"}]}}
    flow_assert(regex("上期会议工具").test(insight_prose(old, "E1的访问条件")), "old evidence label resolves against its own period")
    let schedule_rows = [{news_id: "a" title: "AI会议" summary: ""} {news_id: "b" title: "杭州 2026-10-11 交通调整" summary: ""}]
    flow_assert(evidence_select(schedule_rows, {topics: [flow_topic] schedules: [{location: "杭州"}]}, false)[0].news_id == "b", "dated schedule evidence retains priority")
    show_analysis_results()
    fs.write("phase-one.json", {ready: true checks: flow_checks failures: flow_failures}.to_json())
    flow_wait(|| flow_calls == 3 && !tracking_in_progress(), flow_second, time_now() + 35)
}
fn flow_second(){
    let run = tracking_cache.runs[tracking_cache.runs.len() - 1]
    let e = tracking_find(run.snapshot.evidence, "news_id", flow_id)
    flow_assert(tracking_cache.runs.len() == 2 && run.result.outcome == "update", "verification creates a new validated durable judgment")
    flow_assert(run.snapshot.check_scope == "targeted_verification", "verification discloses limited prior-candidate coverage")
    flow_assert(e.paragraphs.len() > 0 && run.result.insights[0].evidence_refs.len() == 1, "source-specific extraction supplies a validated exact quote")
    flow_assert(flow_requests[2] == flow_id && flow_requests.len() <= 4, "explicit retry bypasses failed-read cooldown with a bounded web budget")
    flow_assert(run.result.insights[0].compared_run_id == tracking_cache.runs[0].task_id, "verification compares the exact previous target judgment")
    flow_assert(insight_basis_label(run.result.insights[0], e) == "判断依据 · 正文引用", "body heading requires a real reference")
    let value = current_insights()[0]
    let writer = tracking_storage_write
    tracking_storage_write = fn(path, text){ false }
    flow_assert(!results_decide(value, "handled") && regex("未保存").test(results_feedback) && current_insights()[0].state == "pending", "failed storage cannot move the card or claim saved feedback")
    tracking_storage_write = writer
    results_feedback = ""
    notice("")
    flow_report()
}
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    user_schedules = [] user_interests = [] agent_preferences.paused = true
    flow_topic = fs.read("topic-input.json").parse_json() topic_records.topics = [flow_topic]
    app_feed_rows = fs.read("news-input.json").parse_json()
    bm25_recall = fn(rows, targets, current, complete, progress){
        start_timeout(0.01, || { if current() { complete({rows: rows matched: rows.len() omitted_candidates: 0 expired: 0}) } })
    }
    article_http_request = fn(url, redirects, callback){
        flow_requests.push(url)
        if url == flow_id && flow_calls == 0 { start_timeout(0.01, || callback({success: false category: "verification" error: "固定验证页"})) return }
        let body = "<div class=\"article__main__content\"><p>固定来源事实：会议工具提供转写试用，普通用户须注册账号，免费额度和隐私条件需核实。</p><div class=\"article__footer\">footer</div>"
        start_timeout(0.01, || callback({success: true body: body}))
    }
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name != "octos.turn.start" { callback({is_ok: true data: {}}) return }
        flow_calls = flow_calls + 1
        let result = flow_result()
        if flow_calls == 1 { result.insights[0].summary = "can_quote_body=false、paragraphs=[]，无需投入学习时间" }
        start_timeout(0.01, || callback({is_ok: true data: {text: result.to_json()}}))
    }
    start_interval(0.1, || {
        if !flow_show_results_seen && fs.exists("flow-show-results.signal") {
            flow_show_results_seen = true show_analysis_results()
        }
        fs.write("flow-navigation.json", {page: page section: tracking_section detail: detail_kind}.to_json())
    })
    tracking_start(nil)
    flow_wait(|| !tracking_in_progress(), flow_first, time_now() + 20)
})
'''
(work / 'bundle/main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
(data / 'host').mkdir(parents=True)
app = data / 'dev.cfaw.runtime-tests'
app.mkdir()
topic = dict(title='固定测试：两小时学习会议工具', purpose='不会编程，先核实再试用', scope=['会议工具'], preferences=['每周两小时', '不承诺效率收益'], recall_rules=[dict(kind='keyword', value='会议')], topic_id='evidence-flow', version=1, status='active', intent_kind='goal', original_input='固定测试', supplement='', created_at=1, updated_at=1)
rows = []
for i in range(8):
    url = ('https://www.ithome.com/rss/' + str(i)) if i < 4 else ('https://sspai.com/post/fixture-verification' if i == 4 else 'https://sspai.com/post/fixture-' + str(i))
    summary = '固定来源摘要：工具使用条件需核实。' if i < 4 or i == 7 else ''
    row = dict(news_id=url, evidence_id=url, content_version='fixture', title='固定测试：会议工具访问条件' if i == 4 else '固定测试：会议工具 ' + str(i), summary=summary, source='固定来源', source_id='ithome' if i < 4 else 'sspai', source_url=url, feed_url='https://www.ithome.com/rss', category='tech', language='zh', image_url=None, published_at=None, retrieved_at=time.time(), evidence_kind='rss_summary', timestamp_kind='unknown', references=[dict(source='固定来源', source_id='ithome', source_url=url, feed_url='https://www.ithome.com/rss')])
    if i < 4:
        row.update(body_html='<p>' + ('固定来源正文会议工具的真实使用条件。' * (300 if i == 0 else 2)) + '</p>', body_origin='publisher_rss', body_truncated=False)
    rows.append(row)
for name, value in [('topic', topic), ('news', rows)]:
    (app / (name + '-input.json')).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
def get(route, **params):
    with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as r: return r.read()
def wait_file(path, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.is_file(): return json.loads(path.read_text(encoding='utf-8'))
        time.sleep(.1)
    raise RuntimeError('Native flow deadline: ' + path.name)
def widgets(): return json.loads(get('/snap'))['s']
def labels(): return [w.get('t','') for w in widgets() if w.get('ty') != 'Splash']
def find(label=None, ident=None):
    items=widgets(); nav_ids=('feed_tab','tracking_tab','schedule_tab','account_tab')
    limit=860 if ident in nav_ids else min((w['r'][1] for w in items if w.get('i') in nav_ids),default=840)
    return next(w for w in items if w.get('ty') != 'Splash'
                and (label is None or w.get('t') == label) and (ident is None or w.get('i') == ident)
                and w['r'][3] > 0 and 0 <= w['r'][1] and w['r'][1] + w['r'][3] <= limit)
def click(label=None, ident=None):
    x,y,w,h=find(label,ident)['r']; get('/click',x=x+w/2,y=y+h/2,wait=1); time.sleep(.25)
def top(): get('/m',k='scroll',x=200,y=650,dy=-10000,wait=1)
def seek(label):
    for _ in range(50):
        try: return find(label)
        except StopIteration: get('/m',k='scroll',x=200,y=650,dy=100,wait=1)
    raise AssertionError('Missing visible result: ' + label)
def nav_state(): return json.loads((app / 'flow-navigation.json').read_text(encoding='utf-8'))
def no_orb():
    assert 'AI' not in labels(), 'floating orb covers the suggestions or source detail'
def bottom_navigation():
    tabs=[find(ident=ident) for ident in ('feed_tab','tracking_tab','schedule_tab','account_tab')]
    assert [w.get('t','').split(' ·')[0] for w in tabs] == ['首页','关注','日程','我的'],tabs
    assert len({round(w['r'][1]) for w in tabs}) == 1,tabs
    return tabs
startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(exe), '--bundle', str(work / 'bundle'), '--app-data', str(data), '--remote=' + str(port), '--size', '430x860'], cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
    try:
        first = wait_file(app / 'phase-one.json', 25)
        assert not first['failures'], first
        time.sleep(.3)
        bottom_navigation(); no_orb()
        assert nav_state()=={'page':'tracking','section':'suggestions','detail':''},nav_state()
        click(ident='feed_tab'); tabs=bottom_navigation(); orb=find('AI')
        assert orb['r'][1]+orb['r'][3] <= min(w['r'][1] for w in tabs), (orb,tabs)
        click(ident='tracking_tab')
        assert nav_state()['page']=='tracking' and nav_state()['section']=='topics',nav_state()
        assert not any(t in ('动态', '建议', '今日精选', '最新文章') for t in labels()), labels()
        # The retained schedule/results board still exercises evidence repair
        # and decisions; the follow landing now has its own native UI check.
        (app / 'flow-show-results.signal').write_text('open retained results board', encoding='utf-8')
        deadline = time.monotonic() + 5
        while nav_state()['section'] != 'suggestions' and time.monotonic() < deadline:
            time.sleep(.1)
        no_orb(); bottom_navigation(); top()
        assert nav_state()=={'page':'tracking','section':'suggestions','detail':''},nav_state()
        seek('相关新闻'); seek('当前情况')
        seek('本期暂不新增试用建议，需先核实这篇会议工具报道的使用条件。')
        seek('建议下一步')
        button=seek('补充正文并重新判断')
        visible = labels()
        assert not any('can_quote_body' in t or 'paragraphs=[]' in t for t in visible), visible
        (work / 'before-verify.png').write_bytes(get('/g', raw=1))
        x,y,w,h = button['r']; get('/click', x=x+w/2, y=y+h/2, wait=1)
        report = wait_file(app / 'flow-report.json', 25)
        assert not report['failures'], report
        time.sleep(.5)  # Let publication-triggered UI updates finish before clicks.
        report['checks'].append('430x860 native verification button rendered and accepted a real click')
        report['checks'] += ['four bottom tabs remain visible; follow landing uses topics and the retained results route remains available',
                             'related news and current situation are traversed before the next-step verification action',
                             'suggestions hide the floating orb and home restores it above bottom navigation']
        (work / 'after-verify.png').write_bytes(get('/g', raw=1))
        get('/m', k='scroll', x=200, y=650, dy=-10000, wait=1)
        def click_result(label):
            seek(label); click(label)
        click_result('查看判断依据')
        for _ in range(10):
            snap = json.loads(get('/snap'))['s']
            if any(w.get('ty') != 'Splash' and w.get('t') == '判断依据 · 正文引用' for w in snap): break
            get('/m', k='scroll', x=200, y=650, dy=300, wait=1)
        else: raise AssertionError('Verified body reference not displayed')
        report['checks'].append('verified result visibly distinguishes exact body quotation')
        (work / 'evidence-quote.png').write_bytes(get('/g', raw=1))
        click_result('查看来源与引用段落')
        find('新闻详情'); find('固定测试：会议工具访问条件'); no_orb()
        assert nav_state()=={'page':'tracking','section':'suggestions','detail':'story'},nav_state()
        (work / 'quoted-news-detail.png').write_bytes(get('/g',raw=1))
        click('‹ 返回'); no_orb(); bottom_navigation()
        assert nav_state()=={'page':'tracking','section':'suggestions','detail':''},nav_state()
        report['checks'].append('opening cited news and returning retains the suggestions section and its hidden orb')
        get('/m', k='scroll', x=200, y=650, dy=-10000, wait=1)
        click_result('收起判断依据')
        get('/m', k='scroll', x=200, y=650, dy=-10000, wait=1)
        click_result('继续观察')
        labels = [w.get('t','') for w in json.loads(get('/snap'))['s'] if w.get('ty') != 'Splash']
        assert '观察 1' in labels and '你选择继续观察' in '\n'.join(labels), labels
        assert '已移到观察；有实质新证据时重新提示。' in labels, labels
        (work / 'watch.png').write_bytes(get('/g', raw=1))
        click_result('已处理')
        labels = [w.get('t','') for w in json.loads(get('/snap'))['s'] if w.get('ty') != 'Splash']
        assert '记录 1' in labels and '你已标记处理' in '\n'.join(labels), labels
        saved = json.loads((app / 'topics_v2.json').read_text(encoding='utf-8'))
        assert saved['decisions'][-1]['state'] == 'handled' and saved['decisions'][-2]['state'] == 'watch', saved
        assert len(saved['topics']) == 1, saved
        (work / 'record.png').write_bytes(get('/g', raw=1))
        click_result('待办 0')
        labels = [w.get('t','') for w in json.loads(get('/snap'))['s'] if w.get('ty') != 'Splash']
        assert '暂时没有需要处理的建议' in labels and not any('建议下一步' == t for t in labels), labels
        report['checks'] += ['native detail expands and collapses on demand', 'observe decision moves card with visible saved feedback', 'handled decision moves to records and both decisions exist on disk without deleting goal', 'handled evidence does not remain an active to-do']
    except Exception:
        try: (work / 'failure.png').write_bytes(get('/g', raw=1))
        except Exception: pass
        raise
    finally:
        process.terminate(); process.wait(timeout=5)
errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
report['native_errors'] = errors
(work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
assert not errors, errors
print('PASS:', len(report['checks']), 'native evidence/judgment/UI checks; three mock model calls including one repair; no real model/network/account writes')
