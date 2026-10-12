"""Check title-only goal recovery without accepting unsupported model advice."""
import copy
import json
import os
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe
from test_tracking_quote_choices import evidence, insight, item, snapshot

SOURCE = r'''
let gap_fixture = nil let gap_checks = [] let gap_failures = [] let gap_index = 0 let gap_turns = 0
let gap_task_snapshot = nil let gap_decisions = ""
tracking_ui_update = fn(){}
notice = fn(text){}
fn gap_assert(value, label){ if value { gap_checks.push(label) } else { gap_failures.push(label) } }
fn gap_report(){ fs.write("report.json", {complete: true checks: gap_checks failures: gap_failures
    model_boundary_calls: gap_turns real_model_calls: 0 network_calls: 0 account_writes: 0}.to_json()) }
fn gap_wait(deadline){
    if tracking_in_progress() {
        if time_now() > deadline { gap_assert(false, "publication deadline") gap_report() return }
        start_timeout(0.02, || gap_wait(deadline)) return
    }
    gap_assert(tracking_cache.runs.len() == 1 && tracking_pending_run == nil, "neutral notice completes normal validated save")
    if tracking_cache.runs.len() == 1 {
        let run = tracking_cache.runs[0]
        gap_assert(run.result.judgment_origin == "evidence_gap", "durable result identifies system availability notice")
        gap_assert(run.result.insights[0].decision_effect == "unknown", "durable notice cannot change trial or learning decision")
        gap_assert(tracking_validate(run.result, run.snapshot).valid && tracking_judgment_validate(run.result, run.snapshot).valid, "saved result still passes strict historical validation")
        let card = follow_topic_projection(gap_fixture.topic)
        gap_assert(card.status_label == "正文待补" && regex("尚未完成内容判断").test(card.note), "topic card discloses the fallback and incomplete content assessment")
        gap_assert(card.next_steps.len() > 0 && regex("补充正文").test(card.next_steps[0]), "topic card presents a content verification route")
        gap_assert(card.news_count == gap_fixture.rows.len(), "evidence entry includes the entire bounded set of uncertain headlines")
    }
    gap_assert(gap_turns == 0 && agent_task.repair_count == 0, "title-only availability notice requires no model turn")
    gap_assert(topic_records.decisions.to_json() == gap_decisions, "existing user decisions remain unchanged")
    gap_assert(!analysis_busy && !tracking_save_active && agent_task.timer == nil, "success releases timers and queue")
    gap_report()
}
fn gap_owner(){
    topic_records.topics = [gap_fixture.topic] app_feed_rows = gap_fixture.rows
    for row in app_feed_rows { row.retrieved_at = time_now() }
    let targets = {topics: topic_records.topics schedules: [] legacy_interests: [] omitted_targets: 0}
    gap_task_snapshot = tracking_snapshot(app_feed_rows, targets)
    let payload = tracking_prompt_snapshot(gap_task_snapshot)
    gap_decisions = topic_records.decisions.to_json()
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name != "octos.turn.start" { start_timeout(0.01, || callback({is_ok: true data: {}})) return }
        gap_turns = gap_turns + 1
        start_timeout(0.01, || callback({is_ok: true data: {text: gap_fixture.model.to_json()}}))
    }
    tracking_started_at = time_now()
    tracking_dispatch_snapshot(gap_task_snapshot, payload, tracking_input_key(gap_task_snapshot), gap_decisions, tracking_prompt + payload.to_json())
    gap_wait(time_now() + 8)
}
fn gap_next(){
    if gap_index >= gap_fixture.cases.len() { start_timeout(0.01, gap_owner) return }
    let test = gap_fixture.cases[gap_index]
    let original = test.model.to_json()
    let checked = tracking_parse(original, "tracking_update", test.snapshot)
    gap_assert(checked.valid == test.valid, test.name + ": expected validation outcome")
    gap_assert(test.model.to_json() == original, test.name + ": original model fixture is untouched")
    if checked.valid {
        gap_assert((checked.result["judgment_origin"] == "evidence_gap") == test.fallback, test.name + ": availability origin is explicit")
        if test.fallback {
            let value = checked.result.insights[0]
            gap_assert(value.decision_effect == "unknown" && value.uncertainties.len() > 0 && value.next_step != nil, test.name + ": unknown with concrete verification and missing condition")
            gap_assert(checked.result.outcome == "insufficient_evidence" && value.material_change == "" && value.reschedule == nil && value.evidence_refs.len() == 0, test.name + ": no unsupported facts, quotes or actions")
            gap_assert(!regex("无需学习|不值得试用|取消学习|不需要投入").test(value.summary + value.next_step), test.name + ": rejected advice is not republished")
            gap_assert(checked.result.items[0].relevance == "uncertain", test.name + ": headline screening is not confirmed relevance")
            if test.name == "previous decision" { gap_assert(value.change_kind == "unchanged" && value.compared_run_id == "prior-goal", "gap notice does not reopen previous decision") }
        }
    } else {
        gap_assert(checked.error == test.error && checked.result == nil, test.name + ": invalid reference/content is not hidden by fallback")
    }
    gap_index = gap_index + 1 start_timeout(0.01, gap_next)
}
start_timeout(0.15, || { gap_fixture = fs.read("fixture.json").parse_json() start_timeout(0.01, gap_next) })
'''


def fixture():
    topic = dict(title='会议记录与演示文稿', purpose='每周两小时，不会编程，先核实再尝试',
                 scope=['会议记录', '演示文稿'], preferences=['不承诺效率收益'],
                 recall_rules=[dict(kind='keyword', value='会议记录')],
                 topic_id='gap-topic', version=1, status='active', intent_kind='goal',
                 original_input='隔离目标', supplement='', created_at=1, updated_at=1)
    articles = [evidence('https://www.ithome.com/gap-fixture-'+str(i), '会议记录工具公开新功能 '+str(i), []) for i in range(2)]
    for e in articles:
        e['summary'] = ''
        e['body_error'] = '隔离模拟：网站验证，正文未读取'
    snap = snapshot([topic], [], articles)
    snap['prompt_revision'] = 'tracking-v2.9'
    model = dict(schema_version=2, outcome='no_change', explanation='无需学习，无需投入时间',
                 items=[item('E1', ['gap-topic']), item('E2', ['gap-topic'])],
                 insights=[insight('topic', 'gap-topic', ['E1', 'E2'], [])])
    model['insights'][0].update(summary='不值得试用，取消学习安排', decision_effect='none',
                                next_step=None, uncertainties=[])
    cases = []
    def case(name, s=None, m=None, valid=True, fallback=True, error='invalid_schema'):
        value = dict(name=name, snapshot=copy.deepcopy(s or snap), model=copy.deepcopy(m or model),
                     valid=valid, fallback=fallback, error=error)
        cases.append(value)
        return value
    case('unsupported title decision')
    value = case('missing verification'); value['model']['insights'][0]['decision_effect'] = 'unknown'
    value = case('wrong outcome'); value['model']['insights'][0].update(decision_effect='unknown', uncertainties=['条件未核实'], next_step='补充正文')
    value = case('valid title notice', fallback=False); value['model']['outcome']='insufficient_evidence'
    value['model']['insights'][0].update(summary='只有标题，须核实', decision_effect='unknown', uncertainties=['条件未核实'], next_step='补充正文')
    value = case('supplied summary', fallback=False); value['snapshot']['evidence'][0]['summary']='来源明确披露了普通账号条件'
    value = case('model cannot forge availability origin', fallback=False)
    value['snapshot']['evidence'][0]['summary']='来源披露了有限使用条件'
    value['model']['judgment_origin']='evidence_gap'
    value = case('supplied body', fallback=False); value['snapshot']['evidence'][0]['paragraphs']=[dict(paragraph_id='p1', text='来源正文：普通账号需注册。')]
    value = case('other selected content', valid=False); value['model']['insights'][0]['evidence_ids']=['E1']
    value['snapshot']['evidence'][1]['summary']='这个已关联候选有正文摘要，不能假装不存在'
    value = case('bad quote', valid=False, error='invalid_reference'); value['model']['insights'][0]['evidence_refs']=[dict(news_id='E1', paragraph_id='p1', quote_id='q999')]
    value = case('wrong version', valid=False, error='invalid_reference'); value['model']['insights'][0]['target_version']=2
    value = case('wrong target', valid=False, error='invalid_reference'); value['model']['items'][0]['topic_ids']=['other-topic']
    value = case('old contract', valid=False); value['snapshot']['prompt_revision']='tracking-v2.8'
    value = case('news awareness', fallback=False); value['snapshot']['topics'][0]['intent_kind']='news'
    value = case('previous decision'); prior=copy.deepcopy(value['model']['insights'])
    value['model']['outcome']='update'
    value['snapshot']['previous_by_target']=[dict(target_type='topic', target_id='gap-topic', target_version=1, run_id='prior-goal', checked_at=1, insights=prior)]
    value['model']['insights'][0].update(change_kind='updated', compared_run_id='prior-goal', material_change='标题被误当成实质新依据')
    rows=[]
    for i in range(8):
        url='https://www.ithome.com/gap-fixture-'+str(i)
        rows.append(dict(news_id=url, evidence_id=url, content_version='fixture', title='会议记录工具公开新功能 '+str(i), summary='',
                         source='隔离来源', source_id='ithome', source_url=url, feed_url='https://www.ithome.com/rss',
                         category='tech', language='zh', image_url=None, published_at=None, retrieved_at=1,
                         evidence_kind='rss_summary', timestamp_kind='unknown', references=[]))
    return dict(topic=topic, rows=rows, model=model, cases=cases)


def main():
    work=ROOT/'.test-state/tracking-title-gap'
    bundle=work/'bundle'; bundle.mkdir(parents=True, exist_ok=True)
    source,_=assemble(paths=ORDER[:-1])
    (bundle/'main.splash').write_text(source+SOURCE, encoding='utf-8')
    data=work/('data-'+str(time.time_ns())); app=data/'dev.cfaw.runtime-tests'
    app.mkdir(parents=True); (data/'host').mkdir()
    (app/'fixture.json').write_text(json.dumps(fixture(),ensure_ascii=False),encoding='utf-8')
    exe=ensure_native_probe(); startup=subprocess.STARTUPINFO()
    startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow=0
    report=None
    with (work/'host.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(exe),'--bundle',str(bundle),'--app-data',str(data),'--size','430x860'],cwd=exe.parent,
            env=dict(os.environ,RINX_DATA_DIR=str(data/'host')),stdout=log,stderr=log,startupinfo=startup)
        try:
            until=time.monotonic()+15
            while time.monotonic()<until:
                if (app/'report.json').exists():
                    report=json.loads((app/'report.json').read_text(encoding='utf-8')); break
                time.sleep(.1)
        finally:
            process.terminate(); process.wait(timeout=5)
    errors=[s for s in (work/'host.log').read_text(encoding='utf-8',errors='replace').splitlines() if '[E]' in s]
    if report is None: raise RuntimeError('No title gap report: '+'\n'.join(errors))
    report['native_errors']=errors
    (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not report['failures'] and not errors,report
    print('PASS:',len(report['checks']),'native title-gap/validation/persistence/card checks; no real model/network/account writes')


if __name__=='__main__': main()
