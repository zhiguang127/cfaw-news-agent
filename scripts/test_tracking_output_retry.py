"""Output truncation recovery through the real adapter, validator and store.

All news, model replies and storage are isolated fixtures; no account profile,
credentials, public endpoints or real model service is used.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe

CASES = ('recover', 'repeat', 'bad-quote', 'format-then-truncate', 'cancel',
         'stale', 'total-timeout', 'preparation-timeout', 'network', 'parameter',
         'host-recover', 'host-repeat', 'host-bad-quote', 'host-then-truncate',
         'format-then-timeout', 'host-cancel', 'host-stale', 'host-total-timeout',
         'host-preparation-timeout', 'host-late-reply')
SOURCE = r'''
let out_checks = [] let out_failures = [] let out_case = "" let out_turns = 0 let out_sessions = 0 let out_interrupts = 0
let out_initial = nil let out_initial_text = "" let out_task_id = "" let out_stages = [] let out_final = false
let out_fixture = nil let out_second_count = 0 let out_second_prompt = "" let out_original_key = ""
let out_first_prompt_bytes = 0
fn out_assert(value, label){ if value { out_checks.push(label) } else { out_failures.push(label) } }
tracking_ui_update = fn(){}
notice = fn(text){}
fn out_result(snapshot){
    let items = [] let ids = []
    for index e in snapshot.evidence {
        let id = "E" + (index + 1) ids.push(id)
        items.push({news_id: id relevance: "uncertain" topic_ids: [snapshot.topics[0].topic_id] legacy_interest_ids: []
            why_related: "隔离测试：条件需要核实" evidence_ids: [id] uncertainties: ["仅验证程序流程"] schedule_impacts: []})
    }
    let ref = {news_id: "E1" paragraph_id: "p1" quote_id: "q1"}
    if out_case == "bad-quote" || out_case == "host-bad-quote" { ref.quote_id = "q999" }
    let value = {schema_version: 2 outcome: "insufficient_evidence" explanation: "隔离测试：仅验证重试与保存流程"
        items: items insights: [{target_type: "topic" target_id: snapshot.topics[0].topic_id target_version: 1
            issue_key: "fixture-conditions" change_kind: "new" summary: "隔离测试来源披露了条件，实际适用性仍需核实。"
            decision_effect: "unknown" next_step: "核实条件" material_change: "" uncertainties: ["隔离模拟回复"]
            evidence_ids: ids evidence_refs: [ref] compared_run_id: nil reschedule: nil}]}
    value.to_json()
}
analysis_host_has = fn(name){ true }
analysis_host_request = fn(name, data, callback){
    if name == "octos.session.open" { out_sessions = out_sessions + 1 start_timeout(0.01, || callback({is_ok: true data: {}})) return }
    if name == "octos.turn.interrupt" { out_interrupts = out_interrupts + 1 start_timeout(0.01, || callback({is_ok: true data: {}})) return }
    out_turns = out_turns + 1
    if out_turns == 1 { out_task_id = agent_task.id out_first_prompt_bytes = data.text.to_bytes().len() }
    else {
        out_second_count = agent_task.snapshot.evidence.len() out_second_prompt = data.text
        out_assert(agent_task.id == out_task_id, "retry keeps the original task ID")
        if out_case != "format-then-truncate" && out_case != "format-then-timeout" {
            let host_timeout = regex("^host-").test(out_case)
            out_assert(out_second_count == if host_timeout {2} else {3}, "retry retains the bounded candidate count")
            out_assert(agent_task.snapshot.omitted_candidates == if host_timeout {6} else {5}, "retry declares all removed candidates")
            out_assert(agent_task.snapshot.check_scope == if host_timeout {"reduced_timeout_retry"} else {"reduced_output_retry"}, "limited retry has its own coverage scope")
            out_assert(data.text.to_bytes().len() <= tracking_config.max_prompt_bytes, "retry input fits the existing byte limit")
            if host_timeout { out_assert(data.text.to_bytes().len() < out_first_prompt_bytes, "timeout retry sends less input than the original turn") }
            out_assert(regex(if host_timeout {"reduced retry after a host turn timeout"} else {"OUTPUT-LENGTH RETRY"}).test(data.text), "retry explicitly requests a complete compact result")
        }
    }
    if out_case == "network" { start_timeout(0.01, || callback({is_ok: false error: "Service timed out"})) return }
    if out_case == "parameter" { start_timeout(0.01, || callback({is_ok: false error: "Invalid max_tokens value"})) return }
    if (out_case == "format-then-truncate" || out_case == "format-then-timeout") && out_turns == 1 {
        start_timeout(0.01, || callback({is_ok: true data: {text: "{"}})) return
    }
    if (regex("^host-").test(out_case) && out_turns == 1) || out_case == "host-repeat" || out_case == "format-then-timeout" {
        if out_case == "host-late-reply" && out_turns == 1 {
            let old_answer = out_result(out_initial)
            start_timeout(0.08, || callback({is_ok: true data: {text: old_answer}}))
        }
        start_timeout(0.01, || callback({is_ok: false error: "The assistant's turn timed out"})) return
    }
    if out_turns == 1 || out_case == "repeat" || out_case == "format-then-truncate" || out_case == "host-then-truncate" {
        // The partial data is deliberately supplied: it must never be parsed,
        // combined with the second reply, or saved as a successful judgment.
        start_timeout(0.01, || callback({is_ok: false error: "Model output was truncated (max_tokens); the response is incomplete" data: {text: "{partial"}}))
        return
    }
    let result = out_result(agent_task.snapshot)
    let delay = if out_case == "total-timeout" || out_case == "host-total-timeout" {1.0} else {0.01}
    start_timeout(delay, || callback({is_ok: true data: {text: result}}))
}
agent_progress_handler = fn(stage){
    out_stages.push(stage)
    if stage == "retry_preparation" && (out_case == "cancel" || out_case == "host-cancel") { start_timeout(0.001, analysis_cancel) }
    if stage == "retry_preparation" && (out_case == "stale" || out_case == "host-stale") {
        start_timeout(0.001, || {
            let next = topic_records.to_json().parse_json()
            next.topics[0].version = 2 topic_records = next
        })
    }
}
fn out_finish(){
    out_final = true
    out_assert(out_sessions == 1, "retry does not reopen a separate session")
    out_assert(out_turns <= 2, "format repair and truncation share one corrective turn")
    out_assert(out_initial.to_json() == out_initial_text, "original full snapshot remains unchanged")
    out_assert(!analysis_busy && !tracking_save_active && agent_task.terminal, "terminal releases the task and storage queue")
    out_assert(agent_task.timer == nil && agent_task.phase_timer == nil && agent_task.progress_timer == nil, "terminal clears all task deadlines")
    if out_case == "recover" || out_case == "host-recover" || out_case == "host-late-reply" {
        let kept = if regex("^host-").test(out_case) {2} else {3}
        out_assert(out_turns == 2 && tracking_status == "insufficient_evidence", "compact reply validates and publishes after truncation")
        out_assert(tracking_cache.runs.len() == 1 && tracking_cache.runs[0].snapshot.evidence.len() == kept, "saved result uses the actual reduced snapshot")
        let run = tracking_cache.runs[0]
        out_assert(run.input_key == tracking_input_key(run.snapshot) && run.input_key != out_original_key, "saved input key belongs to reduced coverage")
        out_assert(run.result.items.len() == kept && tracking_cache_run_valid(run), "saved references and candidate cardinality pass real historical validation")
        out_assert(run.result.insights[0].evidence_refs[0].quote == out_fixture.body, "v2.8 quote choice restores the exact source text")
        out_assert(check_state_find("topic", "out-topic", 1).watermark > 10, "success watermark advances only after verified save")
        out_assert(fs.exists(tracking_cache_file.path), "successful retry persists to isolated storage")
    } else {
        out_assert(tracking_cache.runs.len() == 0 && tracking_pending_run == nil, "failure never publishes or saves a partial model reply")
        let state = check_state_find("topic", "out-topic", 1)
        out_assert(state.watermark == 10, "failure keeps the previous successful watermark")
        if out_case == "repeat" || out_case == "host-then-truncate" { out_assert(out_turns == 2 && analysis_error_category == "output_truncated", "second truncation ends with a readable specific error") }
        if out_case == "bad-quote" || out_case == "host-bad-quote" { out_assert(out_turns == 2 && analysis_error_category == "invalid_reference", "compact retry cannot bypass exact source quote validation or get a third turn") }
        if out_case == "format-then-truncate" { out_assert(out_turns == 2 && agent_task.output_retry_count == 0, "prior format repair consumes the retry budget") }
        if out_case == "cancel" || out_case == "host-cancel" { out_assert(out_turns == 1 && analysis_error_category == "cancelled", "cancelled preparation cannot send the second model turn") }
        if out_case == "stale" || out_case == "host-stale" { out_assert(out_turns == 1 && analysis_error_category == "stale_context", "changed target stops compact retry before send") }
        if out_case == "total-timeout" || out_case == "host-total-timeout" { out_assert(agent_task.timeout_phase == "total" && out_interrupts == 1, "same original total deadline still limits the second turn") }
        if out_case == "preparation-timeout" || out_case == "host-preparation-timeout" { out_assert(out_turns == 1 && agent_task.timeout_phase == "retry_preparation", "retry material preparation has a bounded phase") }
        if out_case == "host-repeat" || out_case == "format-then-timeout" { out_assert(out_turns == 2 && analysis_error_category == "timeout", "host timeout cannot get a third model turn") }
        if out_case == "network" { out_assert(out_turns == 1 && analysis_error_category == "timeout", "network timeout is not treated as output truncation") }
        if out_case == "parameter" { out_assert(out_turns == 1 && analysis_error_category == "request_failed", "invalid max_tokens parameter is not mistaken for truncated output") }
    }
    fs.write("report.json", {complete: true checks: out_checks failures: out_failures case: out_case turns: out_turns
        sessions: out_sessions interrupts: out_interrupts status: tracking_status category: analysis_error_category
        stages: out_stages repair_count: agent_task.repair_count output_retry_count: agent_task.output_retry_count timeout_retry_count: agent_task.timeout_retry_count
        real_model_calls: 0 network_calls: 0 account_writes: 0}.to_json())
}
fn out_wait(deadline){
    if !tracking_in_progress() { start_timeout(0.1, out_finish) return }
    if time_now() > deadline { out_assert(false, "fixture deadline exceeded") out_finish() return }
    start_timeout(0.02, || out_wait(deadline))
}
start_timeout(0.15, || {
    out_fixture = fs.read("fixture.json").parse_json() out_case = out_fixture.case
    if out_case == "total-timeout" || out_case == "host-total-timeout" { tracking_config.total_timeout_seconds = 0.8 }
    if out_case == "preparation-timeout" || out_case == "host-preparation-timeout" { tracking_config.preparation_timeout_seconds = 0.025 }
    topic_records.topics = [out_fixture.topic]
    check_states.items = [{target_type: "topic" target_id: "out-topic" target_version: 1 watermark: 10 attempt_at: 10 status: "checked" category: ""}]
    app_feed_rows = out_fixture.rows
    for row in app_feed_rows {
        row.retrieved_at = time_now()
        analysis_article_store(row, {paragraphs: [out_fixture.body] truncated: false}, "")
    }
    let targets = {topics: topic_records.topics schedules: [] legacy_interests: [] omitted_targets: 0}
    out_initial = tracking_snapshot(app_feed_rows, targets)
    out_initial_text = out_initial.to_json() out_original_key = tracking_input_key(out_initial)
    let payload = tracking_prompt_snapshot(out_initial)
    tracking_dispatch_snapshot(out_initial, payload, out_original_key, topic_records.decisions.to_json(), tracking_prompt + payload.to_json())
    out_wait(time_now() + 5)
})
'''


def fixture(case):
    topic = dict(topic_id='out-topic', version=1, title='隔离测试关注', purpose='核实普通账号使用条件',
                 scope=['普通账号条件'], preferences=['不承诺效率收益'],
                 recall_rules=[dict(kind='keyword', value='账号')], intent_kind='news', status='active',
                 original_input='隔离测试', supplement='', created_at=1, updated_at=1)
    rows = []
    for i in range(8):
        url = 'https://www.ithome.com/output-fixture-' + str(i)
        rows.append(dict(news_id=url, evidence_id=url, content_version='fixture', title='隔离测试报道' + str(i),
                         summary='固定来源摘要：普通账号条件还需核实。', source='隔离测试来源', source_id='ithome',
                         source_url=url, feed_url='https://www.ithome.com/rss', category='tech', language='zh',
                         image_url=None, published_at=None, retrieved_at=1, evidence_kind='rss_summary',
                         timestamp_kind='published', references=[]))
    return dict(case=case, topic=topic, rows=rows, body='固定来源原句：普通账号的使用条件仍需核实。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args()
    exe = ensure_native_probe()
    work = ROOT / '.test-state/tracking-output-retry'
    source, _ = assemble(paths=ORDER[:-1])
    reports = []
    for case in ([args.case] if args.case else CASES):
        directory = work / case
        bundle = directory / 'bundle'
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / 'main.splash').write_text(source + SOURCE, encoding='utf-8')
        data = directory / ('data-' + str(time.time_ns()))
        app = data / 'dev.cfaw.runtime-tests'
        app.mkdir(parents=True)
        (data / 'host').mkdir()
        (app / 'fixture.json').write_text(json.dumps(fixture(case), ensure_ascii=False), encoding='utf-8')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        report = None
        with (directory / 'host.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data), '--size', '430x860'],
                                       cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')),
                                       stdout=log, stderr=log, startupinfo=startup)
            try:
                until = time.monotonic() + 12
                while time.monotonic() < until:
                    path = app / 'report.json'
                    if path.exists():
                        report = json.loads(path.read_text(encoding='utf-8'))
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(.1)
            finally:
                process.terminate()
                process.wait(timeout=5)
        errors = [s for s in (directory / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in s]
        if report is None:
            raise RuntimeError('No output retry report for ' + case + ': ' + '\n'.join(errors))
        report['native_errors'] = errors
        (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(case, len(report['checks']), 'checks;', report['failures'], 'native errors:', len(errors), flush=True)
        reports.append(report)
        if report['failures'] or errors:
            raise AssertionError(report['failures'] + errors)
    combined = dict(complete=True, checks=sum((r['checks'] for r in reports), []),
                    failures=sum((r['failures'] for r in reports), []),
                    native_errors=sum((r['native_errors'] for r in reports), []), cases=reports,
                    real_model_calls=0, network_calls=0, account_writes=0)
    (work / 'report.json').write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS:', len(combined['checks']), 'native output retry checks; zero real model/network/account writes')


if __name__ == '__main__':
    main()
