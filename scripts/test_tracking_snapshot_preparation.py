"""Run owner restore, 128-row recall, snapshot, prompt, publication and reuse.

The supplied account profile is read once and copied into fresh isolated
storage. Its private text is never included in reports or screenshots. HTTP,
thumbnails and Octos are mocked at their external boundaries; BM25, snapshot
construction, prompt projection, validation, persistence and cache reuse run
unchanged. Existing RSS body extraction and cached snapshots remain real.
The unrelated full startup UI is covered by test_startup_topics.py; this test
restores the relevant owners separately to isolate the preparation defect.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from assemble import ORDER, ROOT, assemble
from native_probe import ensure_native_probe


WORK = ROOT / '.test-state/tracking-snapshot-preparation'
SCRIPT = r'''
let boot_finished = false let boot_phase = "restore" let snap_restoring = false
let snap_phase = "startup" let snap_complete = false let snap_checks = [] let snap_failures = []
let snap_models = 0 let snap_http = 0 let snap_starts = 0 let snap_progress = [] let snap_topic = nil
let snap_targets = nil let snap_rows = [] let snap_seed_index = 0 let snap_mode = "core"
let snap_boot_counts = nil let snap_started = 0 let snap_first_seconds = 0 let snap_first_snapshot = nil
let snap_seen_phases = {} let snap_cancelled = false let snap_first_run = "" let snap_faults = 0
let snap_prompt_bytes = 0 let snap_final_evidence_count = 0 let snap_trimmed = 0 let snap_source_keys = []
let snap_original_preferences_load = agent_preferences_load
agent_preferences_load = fn(){ snap_original_preferences_load() agent_preferences.paused = true }
news_http_request = fn(url, redirects, callback){
    snap_http = snap_http + 1
    start_timeout(0.01, || callback({success: false category: "network" error: "隔离回归不访问远端"}))
}
article_http_request = fn(url, redirects, callback){
    snap_http = snap_http + 1
    start_timeout(0.01, || callback({success: false category: "network" error: "隔离回归不访问正文远端"}))
}
news_thumbnail_allowed = fn(row){ false }
analysis_host_has = fn(name){ true }
analysis_host_request = fn(name, data, callback){
    if name != "octos.turn.start" { start_timeout(0.01, || callback({is_ok: true data: {}})) return }
    snap_models = snap_models + 1
    let snapshot = agent_task.snapshot
    snap_first_snapshot = snapshot
    snap_prompt_bytes = data.text.to_bytes().len() snap_final_evidence_count = snapshot.evidence.len()
    snap_trimmed = snap_rows.len() - snapshot.evidence.len()
    let body_count = 0
    for e in snapshot.evidence { if e.paragraphs.len() > 0 { body_count = body_count + 1 } }
    snap_assert(snapshot.evidence.len() > 0 && snapshot.evidence.len() <= 8, "real snapshot contains bounded recall candidates")
    snap_assert(body_count > 0, "real RSS body extraction supplies cached body evidence")
    snap_assert(snapshot.previous_by_target.len() > 0, "current target version retains matching historical judgment")
    snap_assert(data.text.to_bytes().len() <= tracking_config.max_prompt_bytes, "real projected prompt fits host byte limit")
    snap_assert(tracking_snapshot_valid(snapshot), "real immutable snapshot retains the production validation contract")
    snap_assert(snapshot.topics[0].topic_id == snap_topic.topic_id && snapshot.topics[0].version == snap_topic.version,
        "snapshot belongs to the selected current topic version")
    if snap_mode == "once" {
        snap_assert(snap_trimmed > 0 && snapshot.omitted_candidates == tracking_recall_candidates.omitted_candidates + snap_trimmed,
            "real oversized body context trims whole trailing records and reports the exact omitted count")
        let projected = (data.text.replace(tracking_prompt, "")).parse_json()
        let quote_valid = true
        for i e in snapshot.evidence {
            if projected.evidence[i].news_id != "E" + (i + 1) || projected.evidence[i].title != e.title { quote_valid = false }
            for p in projected.evidence[i].paragraphs {
                let original = tracking_find(e.paragraphs, "paragraph_id", p.paragraph_id)
                if original == nil || p.quote_choices.to_json() != tracking_quote_choices(original).to_json() { quote_valid = false }
            }
        }
        snap_assert(quote_valid, "trimmed E labels and paragraph quote choices still map to immutable original evidence")
        let source_valid = true
        for i row in snap_rows { if tracking_evidence_key(row) != snap_source_keys[i] { source_valid = false } }
        snap_assert(source_valid && analysis_articles.len() == snap_rows.len(),
            "prompt trimming leaves feed facts and real cached body entries intact")
    }
    let result = snap_result(snapshot)
    start_timeout(0.01, || callback({is_ok: true data: {text: result.to_json()}}))
}
fn snap_assert(value, label){ if value { snap_checks.push(label) } else { snap_failures.push(label) } }
fn snap_result(snapshot){
    let items = [] let ids = [] let refs = []
    for i e in snapshot.evidence {
        let id = "E" + (i + 1) ids.push(id)
        items.push({news_id: id relevance: "uncertain" topic_ids: [snap_topic.topic_id] legacy_interest_ids: []
            why_related: "隔离固定回归：候选召回与正文准备路径已执行，不能代替真实新闻判断。"
            evidence_ids: [id] uncertainties: ["这是模拟模型边界结果"] schedule_impacts: []})
        if i == 0 && e.paragraphs.len() > 0 {
            refs.push({news_id: id paragraph_id: e.paragraphs[0].paragraph_id quote: bm25_prefix(e.paragraphs[0].text, 80)})
        }
    }
    let previous = nil if snapshot.previous_by_target.len() > 0 { previous = snapshot.previous_by_target[0] }
    let issue = "isolated-preparation" if previous != nil && previous.insights.len() > 0 { issue = previous.insights[0].issue_key }
    let insight = {target_type: "topic" target_id: snap_topic.topic_id target_version: snap_topic.version issue_key: issue
        summary: "隔离固定回归：准备链路已取得候选与正文片段，模拟结果不代表真实新闻判断。"
        decision_effect: "unknown" next_step: "请在实际应用中根据原文核实真实报道。"
        uncertainties: ["这是隔离测试，不能用于真实决定"] evidence_ids: ids evidence_refs: refs
        change_kind: if previous == nil {"new"} else {"unchanged"}
        compared_run_id: if previous == nil {nil} else {previous.run_id} material_change: "" reschedule: nil}
    {schema_version: 2 outcome: "insufficient_evidence" explanation: "隔离回归模型边界固定输出，仅验证准备、校验和保存流程。"
        items: items insights: [insight]}
}
let snap_original_progress = tracking_preparation_progress
tracking_preparation_progress = fn(generation, progress){
    if snap_phase != "startup" && snap_phase != "prewarm" {
        if snap_seen_phases[progress.phase] != true {
            snap_seen_phases[progress.phase] = true
            snap_progress.push({phase: progress.phase scanned: progress.scanned total: progress.total elapsed: time_now() - snap_started})
        }
    }
    snap_original_progress(generation, progress)
    if snap_phase == "check" && !snap_cancelled && (snap_mode == "cancel" || snap_mode == "stale") && regex("^snapshot").test(progress.phase) {
        snap_cancelled = true
        start_timeout(0.01, || {
            if snap_mode == "cancel" { analysis_cancel() }
            else { snap_topic.version = snap_topic.version + 1 }
        })
    }
}
fn snap_state(){
    fs.write("snapshot-state.json", {phase: snap_phase complete: snap_complete boot_finished: boot_finished
        boot_phase: boot_phase news_count: app_feed_rows.len() run_count: tracking_cache.runs.len() models: snap_models http_boundary_calls: snap_http
        status: tracking_status preparation: tracking_preparation_info started: snap_started elapsed: if snap_started > 0 {time_now() - snap_started} else {0}
        fault_count: snap_faults checks: snap_checks failures: snap_failures}.to_json())
}
fn snap_report(){
    snap_complete = true
    fs.write("snapshot-report.json", {complete: true mode: snap_mode checks: snap_checks failures: snap_failures
        before_check: snap_boot_counts news_count: app_feed_rows.len() run_count: tracking_cache.runs.len()
        model_boundary_calls: snap_models http_boundary_calls: snap_http start_count: snap_starts fault_count: snap_faults
        preparation: tracking_preparation_info phases: snap_progress status: tracking_status first_check_seconds: snap_first_seconds
        original_candidates: snap_rows.len() final_evidence_count: snap_final_evidence_count trimmed_candidates: snap_trimmed
        prompt_bytes: snap_prompt_bytes preparation_timeout_seconds: tracking_config.preparation_timeout_seconds
        synthetic_bodies: false real_model_calls: 0 real_network_calls: 0 account_writes: 0}.to_json())
    snap_state()
}
fn snap_wait(condition, complete, deadline){
    if snap_complete { return }
    if time_now() > deadline { snap_assert(false, "native phase deadline: " + snap_phase) snap_report() return }
    if condition() { start_timeout(0.04, complete) }
    else { start_timeout(0.05, || snap_wait(condition, complete, deadline)) }
}
fn snap_after_first(){
    snap_first_seconds = time_now() - snap_started
    if snap_mode != "core" && snap_mode != "once" { snap_edge_finish() return }
    if snap_mode == "once" { snap_assert(snap_faults == 1, "one injected helper budget interruption resumes exactly once") }
    snap_assert(snap_models == 1 && tracking_status == "insufficient_evidence", "first real preparation reaches one mock model and saves its validated result")
    snap_assert(tracking_pending_run == nil && !tracking_save_active, "validated result publication completes before reuse")
    snap_assert(tracking_cache.runs.len() == 12 && tracking_cache.revision > snap_boot_counts.cache_revision,
        "publication appends through the owner and retains bounded twelve-run history")
    if tracking_cache.runs.len() > 0 { snap_first_run = tracking_cache.runs[tracking_cache.runs.len() - 1].task_id }
    snap_phase = "reuse" snap_starts = snap_starts + 1 tracking_start(nil, nil, snap_targets)
    snap_wait(|| !tracking_in_progress(), || {
        snap_assert(snap_models == 1 && regex("未再次调用助手").test(tracking_message), "unchanged actual snapshot reuses saved result without another model")
        snap_assert(tracking_cache.runs[tracking_cache.runs.len() - 1].task_id == snap_first_run,
            "cache reuse does not append or overwrite another analysis")
        snap_assert(check_state_find("topic", snap_topic.topic_id, snap_topic.version).status == "checked",
            "reuse records the real current target as checked")
        snap_report()
    }, time_now() + 55)
}
fn snap_edge_finish(){
    snap_assert(snap_models == 0, "interrupted preparation never reaches the model boundary")
    snap_assert(tracking_cache.revision == snap_boot_counts.cache_revision && tracking_cache.runs.len() == snap_boot_counts.runs,
        "interrupted preparation preserves all existing history")
    if snap_mode == "cancel" {
        snap_assert(tracking_status == "cancelled", "explicit cancellation ends preparation")
    } else if snap_mode == "stale" {
        snap_assert(tracking_status == "stale", "changed topic version stops stale preparation")
    } else {
        snap_assert(tracking_status == "failed", "permanent callback failure ends at bounded preparation deadline")
        snap_assert(check_state_find("topic", snap_topic.topic_id, snap_topic.version).category == "timeout",
            "failed preparation records actual timeout rather than successful refresh")
    }
    snap_report()
}
fn snap_start(){
    if snap_mode == "permanent" { tracking_config.preparation_timeout_seconds = 10 }
    snap_phase = "check" snap_started = time_now() snap_starts = snap_starts + 1
    tracking_start(nil, nil, snap_targets)
    snap_wait(|| !tracking_in_progress(), snap_after_first, time_now() + 56)
}
fn snap_boot_ready(){
    if tracking_auto_timer != nil { stop_timer(tracking_auto_timer) tracking_auto_timer = nil }
    tracking_check_pending = false
    let selected = fs.read("selected-topic-index.json").parse_json()
    snap_topic = topic_records.topics[selected.index]
    snap_targets = {topics: [snap_topic] schedules: [] legacy_interests: [] omitted_targets: 0}
    snap_boot_counts = {topics: topic_records.topics.len() decisions: topic_records.decisions.len() runs: tracking_cache.runs.len()
        news: app_feed_rows.len() topic_revision: topic_records.revision cache_revision: tracking_cache.revision}
    snap_assert(snap_boot_counts.news == 128, "production feed owner restores all 128 actual cached news rows")
    snap_assert(snap_boot_counts.runs == 12, "production history owner restores all twelve actual historical snapshots")
    snap_assert(snap_topic.status == "active", "selected source topic remains the actual active record")
    // Only disposable retrieval clocks in isolated memory are made current.
    // The account source bytes, authored topics and decisions remain untouched.
    for row in app_feed_rows { row.retrieved_at = time_now() }
    snap_phase = "prewarm"
    bm25_recall(app_feed_rows, snap_targets, || true, fn(candidates){
        snap_rows = candidates.rows
        for row in snap_rows { snap_source_keys.push(tracking_evidence_key(row)) }
        snap_assert(snap_rows.len() > 0 && snap_rows.len() <= 8, "production BM25 selects bounded candidates for real body-cache prewarming")
        evidence_enrich(evidence_select(snap_rows, snap_targets, false), || true, || start_timeout(0.01, snap_start))
    }, fn(progress){})
}
fn snap_restore_step(index){
    if index == 0 {
        let document = fs.read("interests_v1.json").parse_json()
        records_apply_interests(document)
        start_timeout(0.01, || snap_restore_step(1))
    } else if index == 1 {
        schedules_load() start_timeout(0.01, || snap_restore_step(2))
    } else if index == 2 {
        topics_load_async(|| start_timeout(0.01, || snap_restore_step(3)))
    } else if index == 3 {
        agent_preferences_load() check_states_load()
        start_timeout(0.01, || snap_restore_step(4))
    } else {
        feed_initialize()
        start_timeout(0.01, || feed_restore_cache(enabled_source_ids, 0, feed_generation, || {
            rebuild_feed(|| {boot_finished = true snap_boot_ready()})
        }))
    }
}
start_interval(0.2, snap_state)
start_timeout(0.1, || {
    let mode = fs.read("test-mode.json").parse_json() snap_mode = mode.mode
    snap_restore_step(0)
})
'''


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def run_case(source, profile, mode, baseline=False):
    name = ('baseline-' if baseline else '') + mode
    work = WORK / name
    work.mkdir(parents=True, exist_ok=True)
    bundle = work / 'bundle'; bundle.mkdir(exist_ok=True)
    data = work / ('data-' + str(time.time_ns()))
    app = data / 'dev.cfaw.runtime-tests'; app.mkdir(parents=True)
    (data / 'host').mkdir()
    original = {p.name: p.read_bytes() for p in profile.glob('*.json*') if p.is_file()}
    for name, content in original.items():
        (app / name).write_bytes(content)
    topics = json.loads(original['topics_v2.json'])
    history = json.loads(original['tracking_results_v1.json'])['runs']
    def prior_count(topic):
        return sum(any(old['topic_id'] == topic['topic_id'] and old['version'] == topic['version']
                       for old in run['snapshot']['topics']) for run in history)
    selected = max((i for i, topic in enumerate(topics['topics']) if topic['status'] == 'active'),
                   key=lambda i: prior_count(topics['topics'][i]))
    write(app / 'selected-topic-index.json', {'index': selected})
    write(app / 'test-mode.json', {'mode': mode})
    script = SCRIPT
    if baseline:
        # The old-source comparison observes one attempt only. Never wait for
        # a second 45-second retry or classify an unrelated restore failure as
        # the reported preparation defect.
        script = script.replace('snap_first_seconds = time_now() - snap_started',
                    'snap_first_seconds = time_now() - snap_started\n    snap_report() return')
    if mode in ('once', 'permanent'):
        script += r'''
let snap_original_prompt_evidence = tracking_prompt_evidence
tracking_prompt_evidence = fn(e, index, revision){
    if snap_phase == "check" && (snap_mode == "permanent" || snap_faults == 0) {
        snap_faults = snap_faults + 1
        let spins = 0 while spins < 30000 { spins = spins + 1 }
    }
    snap_original_prompt_evidence(e, index, revision)
}
'''
    (bundle / 'main.splash').write_text(source + '\n' + script, encoding='utf-8')
    exe = ensure_native_probe()
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
    state = None; report = None
    begin = time.monotonic()
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data),
                  '--remote=' + str(port), '--size', '430x860'], cwd=exe.parent,
                  env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + (60 if baseline else 140)
            while time.monotonic() < deadline:
                try:
                    state = json.loads((app / 'snapshot-state.json').read_text(encoding='utf-8'))
                    if (app / 'snapshot-report.json').is_file():
                        report = json.loads((app / 'snapshot-report.json').read_text(encoding='utf-8'))
                        break
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                if process.poll() is not None: break
                time.sleep(.15)
        finally:
            process.terminate(); process.wait(timeout=5)
    elapsed = time.monotonic() - begin
    errors = [line.split('Source:')[0] for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    profile_unchanged = all((profile / name).read_bytes() == content for name, content in original.items())
    if report is None:
        report = dict(complete=False, checks=[], failures=['native report deadline'], state=state)
    checks = report['checks']; failures = report['failures']
    def check(value, label): (checks if value else failures).append(label)
    expected_errors = []
    if mode in ('once', 'permanent'):
        expected_errors = [line for line in errors if 'script instruction limit exceeded' in line or 'script time budget exceeded' in line]
    unexpected_errors = [line for line in errors if line not in expected_errors]
    if not baseline:
        check(not unexpected_errors, 'production native callbacks have no unexpected VM errors')
        if mode in ('once', 'permanent'):
            check(bool(expected_errors), 'injected callback budget interruption is observed by the native host')
        check(profile_unchanged, 'every source account file retains identical bytes')
        protected = ('topics_v2.json', 'topics_v2.json.backup', 'schedules_v1.json', 'schedules_v1.json.backup')
        check(all((app / name).read_bytes() == original[name] for name in protected if name in original),
              'isolated check preserves original topic, decision and schedule documents')
    report.update(case=mode, baseline=baseline, passed=not failures if not baseline else None,
                  native_errors=errors, expected_budget_errors=expected_errors, unexpected_native_errors=unexpected_errors,
                  elapsed_seconds=round(elapsed, 3), profile_unchanged=profile_unchanged,
                  original_sha256={n: hashlib.sha256(b).hexdigest() for n,b in original.items()},
                  production_order=ORDER[:-1], source_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest(),
                  fixture_app_data=str(data), real_model_calls=0, real_network_calls=0, account_writes=0)
    write(work / 'report.json', report)
    print(json.dumps(dict(case=mode, baseline=baseline, passed=report['passed'], checks=len(checks), failures=failures,
              expected_budget_error_count=len(expected_errors), unexpected_native_error_count=len(unexpected_errors),
              preparation=report.get('preparation'), model_boundary_calls=report.get('model_boundary_calls'),
              elapsed_seconds=round(elapsed,3)), ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True,
                        help='Read-only source profile copied into fresh isolated storage; no private text output')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--case', choices=('core', 'once', 'permanent', 'cancel', 'stale'), default='core')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.baseline:
        source = (WORK / 'baseline-main.splash').read_text(encoding='utf-8').split('// BEGIN src/app/startup.splash')[0]
    else:
        source, _ = assemble(paths=ORDER[:-1])
    report = run_case(source, args.profile, args.case, args.baseline)
    if args.baseline:
        write(WORK / 'baseline-report.json', report)
    else:
        cases = []
        for name in ('core', 'once', 'cancel', 'stale', 'permanent'):
            path = WORK / name / 'report.json'
            if path.is_file():
                saved = json.loads(path.read_text(encoding='utf-8'))
                if saved['source_sha256'] == report['source_sha256']:
                    cases.append(saved)
        write(WORK / 'report.json', dict(passed=all(r['passed'] for r in cases),
              checks=sum((r['checks'] for r in cases), []), failures=sum((r['failures'] for r in cases), []),
              cases=cases, expected_budget_errors=sum((r.get('expected_budget_errors', []) for r in cases), []),
              unexpected_native_errors=sum((r.get('unexpected_native_errors', []) for r in cases), []),
              real_model_calls=0, real_network_calls=0, account_writes=0))
    if not args.baseline:
        assert report['passed'], report['failures'] + report['native_errors']
        print('PASS:', len(report['checks']), 'real preparation checks; no real model/network/account writes')


if __name__ == '__main__':
    main()
