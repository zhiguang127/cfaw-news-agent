"""No-association outcomes, per-topic aggregation and safe neutral publication."""
import copy
import json
import os
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe
from test_tracking_quote_choices import evidence, insight, item, snapshot

SOURCE = r'''
let nr_fixture = nil let nr_checks = [] let nr_failures = [] let nr_index = 0 let nr_turns = 0 let nr_decisions = ""
tracking_ui_update = fn(){}
notice = fn(text){}
fn nr_assert(value, label){ if value { nr_checks.push(label) } else { nr_failures.push(label) } }
fn nr_report(){ fs.write("report.json", {complete: true checks: nr_checks failures: nr_failures
    model_boundary_calls: nr_turns real_model_calls: 0 network_calls: 0 account_writes: 0}.to_json()) }
fn nr_wait(deadline){
    if tracking_in_progress() {
        if time_now() > deadline { nr_assert(false, "publication deadline") nr_report() return }
        start_timeout(0.02, || nr_wait(deadline)) return
    }
    nr_assert(nr_turns == 1 && agent_task.repair_count == 0, "no-associated-news feedback needs no corrective model turn")
    nr_assert(tracking_cache.runs.len() == 1 && tracking_pending_run == nil, "neutral feedback completes normal async verified storage")
    if tracking_cache.runs.len() == 1 {
        let run = tracking_cache.runs[0]
        nr_assert(tracking_validate(run.result, run.snapshot).valid && tracking_judgment_validate(run.result, run.snapshot).valid, "neutral run passes strict historical validation")
        nr_assert(run.result.judgment_origin == "no_related_evidence" && run.result.insights[0].evidence_ids.len() == 0, "saved result identifies absence of new associated basis")
        let card = follow_topic_projection(nr_fixture.topic)
        nr_assert(card.status_label == "暂未确认新进展" && card.status != "failed", "topic card shows completed limited check instead of format failure")
        nr_assert(card.news_count == 0 && card.next_steps.len() > 0, "no unrelated source appears as decision basis; next step remains available")
        nr_assert(insight_attention_count() == 0 && results_group(card.values[0]) == "watch", "neutral check does not create a new action alert")
    }
    nr_assert(topic_records.decisions.to_json() == nr_decisions, "user decisions are unchanged")
    nr_assert(!analysis_busy && !tracking_save_active && agent_task.timer == nil, "completed notice releases queue and timers")
    nr_report()
}
fn nr_owner(){
    topic_records.topics = [nr_fixture.topic] app_feed_rows = nr_fixture.rows
    topic_records.decisions = [{kind: "insight" target_type: "topic" target_id: nr_fixture.topic.topic_id target_version: 1
        issue_key: "existing-user-choice" state: "handled" decided_at: 10 evidence_facts: ["隔离测试：用户此前已经核实并作出决定。"]}]
    for row in app_feed_rows { row.retrieved_at = time_now() }
    let targets = {topics: topic_records.topics schedules: [] legacy_interests: [] omitted_targets: 0}
    let snapshot = tracking_snapshot(app_feed_rows, targets)
    let payload = tracking_prompt_snapshot(snapshot)
    nr_decisions = topic_records.decisions.to_json()
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name != "octos.turn.start" { start_timeout(0.01, || callback({is_ok: true data: {}})) return }
        nr_turns = nr_turns + 1
        start_timeout(0.01, || callback({is_ok: true data: {text: nr_fixture.model.to_json()}}))
    }
    tracking_started_at = time_now()
    tracking_dispatch_snapshot(snapshot, payload, tracking_input_key(snapshot), nr_decisions, tracking_prompt + payload.to_json())
    nr_wait(time_now() + 8)
}
fn nr_next(){
    if nr_index >= nr_fixture.cases.len() { start_timeout(0.01, nr_owner) return }
    let test = nr_fixture.cases[nr_index]
    let original = test.model.to_json() let context = test.snapshot.to_json()
    let checked = tracking_parse(original, "tracking_update", test.snapshot)
    nr_assert(checked.valid == test.valid, test.name + ": expected validation outcome")
    nr_assert(test.model.to_json() == original && test.snapshot.to_json() == context, test.name + ": original input and evidence remain unchanged")
    if checked.valid {
        nr_assert((checked.result["judgment_origin"] == "no_related_evidence") == test.neutral, test.name + ": system feedback origin is explicit")
        if test.neutral {
            nr_assert(checked.result.outcome == "insufficient_evidence", test.name + ": empty association cannot become no-change certainty")
            for value in checked.result.insights {
                nr_assert(value.decision_effect == "unknown" && value.evidence_ids.len() == 0 && value.evidence_refs.len() == 0 && value.material_change == "" && value.reschedule == nil,
                    test.name + ": no current facts, quotes or action change")
                nr_assert(value.next_step != nil && !regex("无需学习|不值得试用|取消学习").test(value.summary), test.name + ": unsupported verdict is discarded; next step supplied")
                if test.name == "previous neutral check" { nr_assert(value.change_kind == "unchanged" && value.compared_run_id == "prior-topic", "same neutral issue does not reopen a prior check") }
            }
        }
        if test.name == "one topic empty another supported" { nr_assert(checked.result.outcome == "update" && checked.result.insights[1].evidence_ids.len() == 1, "per-topic lack of evidence does not block another supported topic") }
    } else { nr_assert(checked.error == test.error && checked.result == nil, test.name + ": reference/version/structure failure is not hidden") }
    nr_index = nr_index + 1 start_timeout(0.01, nr_next)
}
start_timeout(0.15, || { nr_fixture = fs.read("fixture.json").parse_json() start_timeout(0.01, nr_next) })
'''


def fixture():
    topic = dict(title='会议记录与演示文稿', purpose='每周两小时，先核实再试用', scope=['会议记录'],
                 preferences=['不承诺效率收益'], recall_rules=[dict(kind='keyword', value='会议记录')],
                 topic_id='nr-topic', version=1, status='active', intent_kind='goal',
                 original_input='隔离目标', supplement='', created_at=1, updated_at=1)
    articles = [evidence('https://www.ithome.com/no-related-'+str(i), '其他公司融资新闻 '+str(i), []) for i in range(2)]
    snap = snapshot([topic], [], articles); snap['prompt_revision']='tracking-v2.11'
    items=[item('E1', []), item('E2', [])]
    for x in items: x.update(relevance='unrelated', why_related='不涉及当前目标')
    iv=insight('topic','nr-topic',[],[])
    iv.update(summary='没有相关新闻，所以无需学习、不值得试用', decision_effect='none', material_change='', next_step=None, uncertainties=[])
    model=dict(schema_version=2,outcome='no_change',explanation='没有报道关联本目标',items=items,insights=[iv])
    cases=[]
    def case(name, valid=True, neutral=True, error='invalid_schema'):
        x=dict(name=name,snapshot=copy.deepcopy(snap),model=copy.deepcopy(model),valid=valid,neutral=neutral,error=error)
        cases.append(x); return x
    case('empty topic wrong decision')
    x=case('empty topic wrong round outcome'); x['model']['insights'][0]['decision_effect']='unknown'
    x=case('empty topic update claim'); x['model']['outcome']='update'
    x=case('valid empty association'); x['model']['outcome']='insufficient_evidence'; x['model']['insights'][0]['decision_effect']='unknown'
    x=case('news-awareness empty association'); x['snapshot']['topics'][0]['intent_kind']='news'
    x=case('one topic empty another supported',neutral=False)
    other=copy.deepcopy(topic); other.update(topic_id='other-topic',title='其他公司业务',intent_kind='news',purpose='')
    x['snapshot']['topics'].append(other); x['model']['outcome']='update'
    x['model']['insights'][0].update(decision_effect='unknown',summary='本目标暂无关联依据')
    x['model']['items'][0].update(relevance='related',topic_ids=['other-topic'])
    other_insight=insight('topic','other-topic',['E1'],[]); other_insight.update(decision_effect='none',summary='来源摘要提供公司业务事实')
    x['model']['insights'].append(other_insight)
    x=case('two topics both empty'); x['snapshot']['topics'].append(copy.deepcopy(other))
    oi=copy.deepcopy(iv); oi['target_id']='other-topic'; x['model']['insights'].append(oi)
    x=case('unrelated source forced into evidence',valid=False,error='invalid_reference'); x['model']['insights'][0]['evidence_ids']=['E1']
    x=case('related candidate omitted',valid=False,error='invalid_reference'); x['model']['items'][0].update(relevance='uncertain',topic_ids=['nr-topic'])
    x=case('bad quote',valid=False,error='invalid_reference'); x['model']['insights'][0]['evidence_refs']=[dict(news_id='E1',paragraph_id='p1',quote_id='q999')]
    x=case('wrong version',valid=False,error='invalid_reference'); x['model']['insights'][0]['target_version']=2
    x=case('wrong target',valid=False,error='invalid_reference'); x['model']['insights'][0]['target_id']='unknown'
    x=case('wrong history',valid=False,error='invalid_reference'); x['model']['insights'][0]['compared_run_id']='foreign-run'
    x=case('invalid next step',valid=False); x['model']['insights'][0]['next_step']=12
    x=case('unsupported reschedule',valid=False,error='invalid_reference'); x['model']['insights'][0]['reschedule']={'start':'2026-10-15T13:00:00+08:00'}
    x=case('old contract',valid=False); x['snapshot']['prompt_revision']='tracking-v2.10'
    x=case('previous neutral check'); prior=copy.deepcopy(iv); prior.update(issue_key='no-related-news',decision_effect='unknown',next_step='保持已有决定')
    x['snapshot']['previous_by_target']=[dict(target_type='topic',target_id='nr-topic',target_version=1,run_id='prior-topic',checked_at=1,insights=[prior])]
    x['model']['insights'][0]['compared_run_id']='prior-topic'
    rows=[]
    for e in articles:
        rows.append(dict(news_id=e['news_id'],evidence_id=e['news_id'],content_version='fixture',title=e['title'],summary=e['summary'],source='隔离来源',source_id='ithome',
                         source_url=e['source_url'],feed_url='https://www.ithome.com/rss',category='tech',language='zh',image_url=None,published_at=None,retrieved_at=1,
                         evidence_kind='rss_summary',timestamp_kind='unknown',references=[]))
    return dict(topic=topic,rows=rows,model=model,cases=cases)


def main():
    work=ROOT/'.test-state/tracking-no-related'; bundle=work/'bundle'; bundle.mkdir(parents=True,exist_ok=True)
    source,_=assemble(paths=ORDER[:-1]); (bundle/'main.splash').write_text(source+SOURCE,encoding='utf-8')
    data=work/('data-'+str(time.time_ns())); app=data/'dev.cfaw.runtime-tests'; app.mkdir(parents=True); (data/'host').mkdir()
    (app/'fixture.json').write_text(json.dumps(fixture(),ensure_ascii=False),encoding='utf-8')
    exe=ensure_native_probe(); startup=subprocess.STARTUPINFO(); startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow=0
    report=None
    with (work/'host.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(exe),'--bundle',str(bundle),'--app-data',str(data),'--size','430x860'],cwd=exe.parent,env=dict(os.environ,RINX_DATA_DIR=str(data/'host')),stdout=log,stderr=log,startupinfo=startup)
        try:
            until=time.monotonic()+15
            while time.monotonic()<until:
                if (app/'report.json').exists(): report=json.loads((app/'report.json').read_text(encoding='utf-8')); break
                time.sleep(.1)
        finally: process.terminate(); process.wait(timeout=5)
    errors=[s for s in (work/'host.log').read_text(encoding='utf-8',errors='replace').splitlines() if '[E]' in s]
    if report is None: raise RuntimeError('No report: '+'\n'.join(errors))
    report['native_errors']=errors; (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not report['failures'] and not errors,report
    print('PASS:',len(report['checks']),'native no-association/topic/save/card checks; no real model/network/account writes')


if __name__=='__main__': main()
