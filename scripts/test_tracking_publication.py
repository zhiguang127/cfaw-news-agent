"""Native publication regression: bounded history, interruption and safe retry."""
import json
import os
import subprocess
import sys
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe

group = os.environ.get('CFAW_PUBLICATION_GROUP')
if group is None:
    # Each native process starts with twelve large historical runs. Separate
    # fault groups keep the fixture's own retained assertion closures bounded
    # on the production 32MiB heap; do not increase the host budget.
    reports = []
    for part in ('1', '2'):
        subprocess.run([sys.executable, __file__], env=dict(os.environ, CFAW_PUBLICATION_GROUP=part), check=True)
        reports.append(json.loads((ROOT / '.test-state/tracking-publication' / ('report-' + part + '.json')).read_text(encoding='utf-8')))
    combined = dict(complete=True, native_processes=2, checks=sum((r['checks'] for r in reports), []), failures=sum((r['failures'] for r in reports), []), model_calls=sum(r['model_calls'] for r in reports), host_interrupts=sum(r['host_interrupts'] for r in reports), native_errors=sum((r['native_errors'] for r in reports), []))
    (ROOT / '.test-state/tracking-publication/report.json').write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS:', len(combined['checks']), 'checks across twelve scenarios in two isolated native processes')
    sys.exit(0)

exe = ensure_native_probe()
work = ROOT / '.test-state/tracking-publication'
(work / 'bundle').mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += r'''
let pub_checks = [] let pub_failures = [] let pub_calls = 0 let pub_interrupts = 0
let pub_case = "initial" let pub_once = false let pub_before = nil let pub_pending = nil let pub_watermark = 0
let pub_cases = ["normal" "stage_bail" "write_bail" "write_error" "ack_lost" "callback_lost" "stale" "concurrent" "cancel" "readonly" "corrupt" "recovered"]
let pub_case_index = 0 let pub_call_count = 0 let pub_topic = nil
fn pub_assert(value, text){ if value { pub_checks.push(text) } else { pub_failures.push(text) } }
fn pub_report(){ fs.write("publication-report.json", {complete: true checks: pub_checks failures: pub_failures
    model_calls: pub_calls host_interrupts: pub_interrupts case: pub_case}.to_json()) }
fn pub_wait(condition, complete, deadline){
    if time_now() > deadline { pub_assert(false, "case deadline: " + pub_case + " / " + tracking_status) pub_report() return }
    if condition() { start_timeout(0.05, complete) }
    else { start_timeout(0.02, || pub_wait(condition, complete, deadline)) }
}
fn pub_spin(){ let spins = 0 while spins < 30000 { spins = spins + 1 } }
fn pub_result(snapshot, labels){
    let items = []
    for i e in snapshot.evidence {
        let id = e.news_id if labels { id = "E" + (i + 1) }
        items.push({news_id: id relevance: "uncertain" topic_ids: [pub_topic.topic_id] legacy_interest_ids: []
            evidence_ids: [id] why_related: "固定测试：需要核实适用条件" uncertainties: ["固定替代模型回复"] schedule_impacts: []})
    }
    let result = {schema_version: 2 outcome: "no_change" explanation: "固定测试：已核验保存，没有新的行动依据" items: items insights: []}
    result.insights.push({target_type: "topic" target_id: pub_topic.topic_id target_version: pub_topic.version issue_key: "availability"
        summary: "固定测试：没有新的行动依据" change_kind: "new" decision_effect: "unknown" material_change: ""
        uncertainties: ["未验证效率收益"] evidence_ids: [items[0].news_id] evidence_refs: []})
    if snapshot.previous_by_target.len() > 0 {
        result.insights[0].compared_run_id = snapshot.previous_by_target[0].run_id
        result.insights[0].change_kind = "unchanged"
    }
    result
}
let pub_original_progress = agent_progress
agent_progress_handler = fn(stage){
    pub_original_progress(stage)
    if stage == "publishing" && pub_case == "stage_bail" && !pub_once { pub_once = true pub_spin() }
    if stage == "publishing" { pub_assert(analysis_busy && analysis_state == "publishing", "queue remains locked until saved: " + pub_case) }
    if stage == "publishing" {
        let id = agent_task.id
        let error = agent_task_start("parse_intent", {}, "fixture", || true, fn(reply){})
        pub_assert(error != "" && agent_task.id == id, "new task cannot replace a publication in progress: " + pub_case)
    }
}
let pub_original_writer = tracking_storage_write
tracking_storage_write = fn(path, text){
    if pub_case == "write_error" && path == tracking_cache_file.path { fs.write(".", text) return }
    pub_original_writer(path, text)
    if pub_case == "write_bail" && path == tracking_cache_file.path && !pub_once { pub_once = true pub_spin() }
}
let pub_original_step = tracking_cache_save_step
tracking_cache_save_step = fn(save){
    if save.phase == "write" && !pub_once {
        if pub_case == "stale" { pub_once = true pub_topic.version = pub_topic.version + 1 }
        if pub_case == "cancel" { pub_once = true analysis_cancel() }
    }
    if save.phase == "backup" && pub_case == "concurrent" && !pub_once {
        pub_once = true
        let text = fs.read(save.path).replace("\"revision\":" + tracking_cache.revision + ",", "\"revision\":" + (tracking_cache.revision + 10) + ",")
        fs.write(save.path, text)
        text = nil
    }
    pub_original_step(save)
}
let pub_original_finish = tracking_publish_finish
tracking_publish_finish = fn(save, error, next){
    if pub_case == "ack_lost" && error == "" { return }
    pub_original_finish(save, error, next)
}
let pub_original_publish = tracking_publish_async
tracking_publish_async = fn(run, current, complete){
    if pub_case == "callback_lost" { pub_spin() return }
    pub_original_publish(run, current, complete)
}
fn pub_retry_check(){
    mod.gc.run()
    pub_assert(pub_calls == pub_call_count, "retry does not call model: " + pub_case)
    pub_assert(tracking_status == "no_change" && tracking_pending_run == nil && !analysis_busy, "retry finishes and releases queue: " + pub_case)
    let text = fs.read(tracking_cache_file.path)
    let count = text.match_all(regex("\"task_id\":\"" + literal_pattern(pub_pending.task_id) + "\"", "g")).len()
    pub_assert(count == 1 && text == tracking_cache.to_json() && tracking_cache_file.revision == tracking_cache.revision, "retry verifies one durable task and matching revisions: " + pub_case)
    start_timeout(0.1, pub_next)
}
fn pub_finished(){
    mod.gc.run()
    fs.write("publication-progress.json", {case: pub_case status: tracking_status message: tracking_message
        analysis_state: analysis_state error: analysis_error checks: pub_checks failures: pub_failures}.to_json())
    pub_call_count = pub_calls
    pub_assert(!analysis_busy && !tracking_save_active && agent_task.publication_timer == nil && !agent_task.publication_pending, "completion clears both locks and task deadline: " + pub_case)
    pub_assert(pub_calls == pub_case_index + 1, "one model call per check despite duplicate reply: " + pub_case)
    if pub_case == "normal" || pub_case == "stage_bail" || pub_case == "write_bail" || pub_case == "recovered" {
        pub_assert(tracking_status == "no_change" && tracking_message == agent_task.publication_result.explanation && analysis_state == "succeeded", "saved outcome replaces publishing state: " + pub_case)
        pub_assert(tracking_pending_run == nil && tracking_cache.runs.len() == 12, "verified result retains twelve-run cap: " + pub_case)
        let path = tracking_cache_file.path if pub_case == "recovered" { path = path + ".backup" }
        let disk = fs.read(path)
        pub_assert(disk == tracking_cache.to_json() && tracking_cache_file.revision == tracking_cache.revision && tracking_cache.runs[11].task_id == agent_task.id, "success means verified on-disk task: " + pub_case)
        if pub_case == "recovered" {
            pub_assert(fs.read(tracking_cache_file.path) == "broken publication fixture", "recovered save updates backup and preserves corrupt primary")
            fs.write(tracking_cache_file.path, fs.read(path)) tracking_cache_file.writable = true tracking_cache_file.recovered = false
        } else {
            pub_assert(fs.exists(tracking_cache_file.path + ".backup") && fs.read(tracking_cache_file.path + ".backup") == pub_before, "validated prior primary remains in backup: " + pub_case)
        }
        pub_assert(check_state_find("topic", pub_topic.topic_id, pub_topic.version).watermark > 0, "verified success advances watermark: " + pub_case)
        if pub_case == "normal" {
            pub_pending = tracking_cache.runs[11] tracking_pending_run = pub_pending tracking_status = "failed"
            tracking_retry_save()
            pub_wait(|| !tracking_in_progress(), pub_retry_check, time_now() + 6) return
        }
        start_timeout(0.1, pub_next) return
    }
    pub_assert(tracking_status == "failed" || tracking_status == "cancelled", "failed publication ends visibly: " + pub_case)
    pub_assert(tracking_pending_run != nil, "model result retained for retry: " + pub_case)
    let check = check_state_find("topic", pub_topic.topic_id, 1)
    pub_assert(check == nil || check.watermark == pub_watermark, "failure does not advance success watermark: " + pub_case)
    if pub_case == "write_error" || pub_case == "stale" || pub_case == "callback_lost" || pub_case == "cancel" || pub_case == "readonly" {
        pub_assert(fs.read(tracking_cache_file.path) == pub_before, "failed check preserves prior primary: " + pub_case)
    }
    if pub_case == "corrupt" {
        pub_assert(fs.read(tracking_cache_file.path) == "broken publication fixture", "corrupt primary is preserved on failure")
        fs.write(tracking_cache_file.path, pub_before)
    }
    if pub_case == "corrupt" || pub_case == "readonly" { tracking_cache_file.writable = true tracking_cache_file.recovered = false }
    if pub_case == "concurrent" {
        let expected = pub_before.replace("\"revision\":" + tracking_cache.revision + ",", "\"revision\":" + (tracking_cache.revision + 10) + ",")
        pub_assert(fs.read(tracking_cache_file.path) == expected && expected != pub_before, "concurrent revision is never overwritten")
        expected = nil
        fs.write(tracking_cache_file.path, pub_before)
    }
    if pub_case == "cancel" { pub_assert(pub_interrupts == 0, "local save cancellation does not interrupt a finished host turn") }
    if pub_case == "stale" { pub_topic.version = 1 }
    pub_pending = tracking_pending_run
    let saved_case = pub_case pub_case = "retry"
    tracking_retry_save()
    pub_wait(|| !tracking_in_progress(), || { pub_case = saved_case pub_retry_check() }, time_now() + 6)
}
fn pub_launch(){
    mod.gc.run()
    tracking_started_at = time_now()
    tracking_start_candidates({rows: app_feed_rows matched: 8 omitted_candidates: 0}, tracking_targets())
    pub_wait(|| !tracking_in_progress(), pub_finished, time_now() + 7)
}
fn pub_next(){
    if pub_case != "initial" { pub_case_index = pub_case_index + 1 }
    if pub_case_index >= pub_cases.len() { pub_report() return }
    pub_case = pub_cases[pub_case_index] pub_once = false
    for i row in app_feed_rows { row.title = "固定测试 AI 会议记录 " + pub_case_index + " / " + i }
    pub_before = fs.read(tracking_cache_file.path)
    if pub_case == "readonly" { tracking_cache_file.writable = false }
    if pub_case == "corrupt" || pub_case == "recovered" { fs.write(tracking_cache_file.path, "broken publication fixture") }
    if pub_case == "recovered" { fs.write(tracking_cache_file.path + ".backup", pub_before) tracking_cache_file.writable = false tracking_cache_file.recovered = true }
    let check = check_state_find("topic", pub_topic.topic_id, 1)
    pub_watermark = if check == nil {0} else {check.watermark}
    tracking_pending_run = nil
    tracking_config.publication_timeout_seconds = if pub_case == "ack_lost" || pub_case == "callback_lost" {2} else {15}
    start_timeout(0.05, pub_launch)
}
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    user_schedules = [] user_interests = [] agent_preferences.paused = true
    // This stress test isolates publication from the separately known cost
    // of rendering every historical result. Real status controls stay active.
    render_feed = fn(){ start_timeout(0.01, || mod.gc.run()) }
    pub_topic = fs.read("topic-input.json").parse_json() topic_records.topics = [pub_topic]
    app_feed_rows = fs.read("news-input.json").parse_json()
    page = "tracking"
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name == "octos.turn.interrupt" { pub_interrupts = pub_interrupts + 1 callback({is_ok: true data: {}}) return }
        if name != "octos.turn.start" { callback({is_ok: true data: {}}) return }
        pub_calls = pub_calls + 1
        let result = pub_result(agent_task.snapshot, true)
        start_timeout(0.01, || { callback({is_ok: true data: {text: result.to_json()}}) callback({is_ok: true data: {text: result.to_json()}}) })
    }
    let snapshot = tracking_snapshot(app_feed_rows, tracking_targets())
    let result = pub_result(snapshot, false)
    for i in 12 { tracking_cache.runs.push({task_id: "old-fixture-" + i checked_at: 1 input_key: "old-" + i snapshot: snapshot result: result}) }
    tracking_cache.revision = 12 tracking_cache_file.revision = 12
    start_timeout(0.01, || { fs.write(tracking_cache_file.path, tracking_cache.to_json()) start_timeout(0.05, pub_next) })
})
'''
all_cases = ['normal', 'stage_bail', 'write_bail', 'write_error', 'ack_lost', 'callback_lost', 'stale', 'concurrent', 'cancel', 'readonly', 'corrupt', 'recovered']
cases = all_cases[:6] if group == '1' else all_cases[6:]
source = source.replace('let pub_cases = [' + ' '.join(json.dumps(c) for c in all_cases) + ']', 'let pub_cases = [' + ' '.join(json.dumps(c) for c in cases) + ']')
(work / 'bundle/main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
(data / 'host').mkdir(parents=True)
app = data / 'dev.cfaw.runtime-tests'
app.mkdir()
topic = dict(title='固定测试：会议记录工具', purpose='核实功能条件', scope=['AI会议记录'], preferences=['不承诺效率收益'], recall_rules=[dict(kind='keyword', value='AI')], topic_id='publication-fixture', version=1, status='active', intent_kind='goal', original_input='固定测试', supplement='', created_at=1, updated_at=1)
rows = []
for i in range(8):
    url = 'https://example.invalid/publication/' + str(i)
    summary = '普通人使用条件与限制。' * 90
    rows.append(dict(news_id=url, evidence_id=url, content_version='fixture', title='固定测试 AI '+str(i), summary=summary, source='固定测试来源', source_id='ithome', source_url=url, feed_url='https://www.ithome.com/rss', category='tech', language='zh', image_url=None, published_at=None, retrieved_at=time.time(), evidence_kind='rss_summary', timestamp_kind='published', references=[dict(source='固定测试来源', source_id='ithome', source_url=url, feed_url='https://www.ithome.com/rss')]))
for name, value in [('topic', topic), ('news', rows)]:
    (app / (name + '-input.json')).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(exe), '--bundle', str(work / 'bundle'), '--app-data', str(data), '--size', '430x860'], cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
    try:
        report_path = app / 'publication-report.json'
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding='utf-8'))
                if report.get('complete'): break
            time.sleep(.1)
        else: raise RuntimeError('Publication regression timed out; see host.log')
    finally:
        process.terminate()
        process.wait(timeout=5)
errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
report['native_errors'] = errors
(work / ('report-' + group + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'native_errors'}, ensure_ascii=True, indent=2))
assert not report['failures'], report
assert len(errors) == (3 if group == '1' else 0) and all('script instruction limit exceeded' in line for line in errors), errors
assert report['model_calls'] == 6 and report['host_interrupts'] == 0, report
print('PASS: six publication scenarios; no real model, network or account writes')
