"""Native adapter deadlines with fixed replies; no model, network or user data."""
import json
import os
import socket
import subprocess
import time

from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe


def main():
    executable = ensure_native_probe()
    work = ROOT / '.test-state/tracking-deadlines'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += r'''
let deadline_checks = [] let deadline_failures = [] let deadline_results = []
let deadline_cases = [
    {name: "delayed-model" delays: [0.25] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0 duplicate_delay: 0.10}
    {name: "repair-new-window" delays: [0.40 0.40] responses: ["invalid" "valid"] expected_success: true expected_turns: 2 expected_interrupts: 0}
    {name: "model-timeout" delays: [0.90] responses: ["valid"] expected_success: false expected_turns: 1 expected_interrupts: 1 expected_phase: "model" duplicate_delay: 0.15}
    {name: "after-model-timeout" delays: [0.40] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0}
    {name: "session-timeout" session_delay: 0.55 delays: [] responses: [] expected_success: false expected_turns: 0 expected_interrupts: 1 expected_phase: "session"}
    {name: "after-session-timeout" delays: [0.40] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0}
    {name: "total-timeout" total_seconds: 0.70 delays: [0.40 0.40] responses: ["invalid" "valid"] expected_success: false expected_turns: 2 expected_interrupts: 1 expected_phase: "total"}
    {name: "cancel" cancel_after: 0.12 delays: [0.45] responses: ["valid"] expected_success: false expected_turns: 1 expected_interrupts: 1 duplicate_delay: 0.20}
    {name: "after-cancel" delays: [0.40] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0}
    {name: "duplicate-reply" delays: [0.15] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0 duplicate_delay: 0.10}
    {name: "host-timeout-reply" host_timeout: true delays: [0.15] responses: ["valid"] expected_success: false expected_turns: 1 expected_interrupts: 0 expected_phase: "model"}
    {name: "duplicate-session-open" session_duplicate_delay: 0.05 delays: [0.20] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0}
    {name: "ordinary-request-bound" kind: "article_summary" delays: [0.25] responses: ["valid"] expected_success: false expected_turns: 1 expected_interrupts: 1 expected_phase: "total"}
    {name: "waiting-progress" model_seconds: 5.80 total_seconds: 6.60 delays: [5.20] responses: ["valid"] expected_success: true expected_turns: 1 expected_interrupts: 0}
]
let deadline_index = 0 let deadline_active = nil
fn deadline_assert(value, label){
    if value { deadline_checks.push(label) } else { deadline_failures.push(label) }
}
fn deadline_final(){
    for item in deadline_cases {
        let prefix = item.name + ": "
        deadline_assert(item.completions == 1, prefix + "late and duplicate callbacks cannot complete twice")
        deadline_assert(item.turns == item.expected_turns, prefix + "expected number of model turns")
        deadline_assert(item.interrupts == item.expected_interrupts, prefix + "interrupt is sent once when required")
        deadline_assert(item.task.terminal && item.task.timer == nil && item.task.phase_timer == nil && item.task.progress_timer == nil && item.task.interrupt_timer == nil,
            prefix + "terminal clears total, phase, progress and interrupt timers")
        deadline_assert(item.reply.success == item.expected_success, prefix + "expected result")
        if item["expected_phase"] != nil {
            deadline_assert(item.reply.category == "timeout" && item.task.timeout_phase == item.expected_phase,
                prefix + "timeout identifies the actual waiting phase")
            deadline_assert(item.reply.result == nil, prefix + "late timed-out result is not published")
        }
        if item.name == "cancel" {
            deadline_assert(item.reply.category == "cancelled" && item.reply.result == nil, prefix + "cancelled reply cannot publish")
        }
        if item.name == "delayed-model" {
            deadline_assert(item.elapsed > tracking_config.request_timeout_seconds,
                prefix + "tracking succeeds beyond the ordinary request limit")
        }
        if item.name == "repair-new-window" {
            deadline_assert(item.elapsed > 0.60 && item.task.repair_count == 1,
                prefix + "each correction receives a fresh model wait window")
            deadline_assert(record_contains(item.stages, "repairing"), prefix + "correction stage is observable")
        }
        if item.name == "total-timeout" {
            deadline_assert(item.task.repair_count == 1, prefix + "total bound wins during individually valid correction windows")
        }
        if item.name == "waiting-progress" {
            let ticks = 0 for stage in item.stages { if stage == "model" { ticks = ticks + 1 } }
            deadline_assert(ticks >= 2, prefix + "progress notification continues while model is waiting")
        }
        deadline_results.push({name: item.name elapsed_seconds: item.elapsed success: item.reply.success
            category: item.reply.category phase: item.task["timeout_phase"] turns: item.turns interrupts: item.interrupts
            completions: item.completions stages: item.stages})
    }
    deadline_assert(!analysis_busy && !analysis_needs_reopen, "queue is unlocked after every completed or acknowledged interrupted case")
    fs.write("deadline-report.json", {complete: true checks: deadline_checks failures: deadline_failures cases: deadline_results}.to_json())
}
fn deadline_start_next(){
    if deadline_index >= deadline_cases.len() { start_timeout(0.40, deadline_final) return }
    let item = deadline_cases[deadline_index] deadline_index = deadline_index + 1 deadline_active = item
    item.turns = 0 item.interrupts = 0 item.completions = 0 item.stages = [] item.started = time_now()
    tracking_started_at = time_now() tracking_recall_seconds = 0 tracking_enrichment_seconds = 0
    tracking_config.model_timeout_seconds = if item["model_seconds"] != nil {item.model_seconds} else {0.60}
    tracking_config.total_timeout_seconds = if item["total_seconds"] != nil {item.total_seconds} else {1.80}
    let kind = if item["kind"] != nil {item.kind} else {"tracking_update"}
    let error = agent_task_start(kind, {prompt_revision: "fixed-deadline-test"}, "fixed adapter input", || true,
        fn(reply){
            item.completions = item.completions + 1 item.reply = reply item.elapsed = time_now() - item.started
            deadline_assert(!analysis_busy, item.name + ": completion releases queue lock")
            if item.completions == 1 { start_timeout(0.08, deadline_start_next) }
        })
    item.task = agent_task
    deadline_assert(error == "", item.name + ": task starts without an old lock")
    if item["cancel_after"] != nil {
        start_timeout(item.cancel_after, || {
            if agent_task != nil && agent_task.id == item.task.id { agent_task_stop("cancelled", "固定测试取消", "cancelled") }
        })
    }
}
start_timeout(0.10, || {
    tracking_config.request_timeout_seconds = 0.12 tracking_config.session_timeout_seconds = 0.30
    tracking_config.interrupt_timeout_seconds = 0.30
    tracking_check_pending = false tracking_status = "idle" analysis_needs_reopen = false
    tracking_ui_update = fn(){} intent_after_interrupt = fn(){} tracking_schedule_check = fn(){}
    agent_task_record_metrics = fn(task, published, result, state, category){}
    agent_progress_handler = fn(stage){ if deadline_active != nil { deadline_active.stages.push(stage) } }
    tracking_parse = fn(text, kind, snapshot){
        if text == "invalid" { return {valid: false error: "invalid_schema" message: "固定格式修正"} }
        {valid: true result: {schema_version: 1 outcome: "no_change" explanation: "固定测试结果" items: []}}
    }
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        let item = deadline_active
        if name == "octos.session.open" {
            let delay = if item["session_delay"] != nil {item.session_delay} else {0.01}
            start_timeout(delay, || callback({is_ok: true data: {}}))
            if item["session_duplicate_delay"] != nil {
                start_timeout(delay + item.session_duplicate_delay, || callback({is_ok: true data: {}}))
            }
            return
        }
        if name == "octos.turn.interrupt" {
            item.interrupts = item.interrupts + 1
            start_timeout(0.01, || callback({is_ok: true data: {}})) return
        }
        if name == "octos.turn.start" {
            let call = item.turns item.turns = item.turns + 1
            if call >= item.delays.len() { deadline_assert(false, item.name + ": unexpected turn") return }
            let text = item.responses[call] let delay = item.delays[call]
            if item["host_timeout"] == true {
                start_timeout(delay, || callback({is_ok: false error: "Service timed out"}))
            } else { start_timeout(delay, || callback({is_ok: true data: {text: text}})) }
            if item["duplicate_delay"] != nil {
                start_timeout(delay + item.duplicate_delay, || callback({is_ok: true data: {text: text}}))
            }
            return
        }
        deadline_assert(false, "unexpected host service: " + name)
    }
    deadline_start_next()
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8')
    data = work / ('data-' + str(time.time_ns()))
    (data / 'host').mkdir(parents=True)
    app = data / 'dev.cfaw.runtime-tests'
    app.mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    report_file = app / 'deadline-report.json'
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [str(executable), '--bundle', str(bundle), '--app-data', str(data),
             '--remote=' + str(port), '--size', '430x860'],
            cwd=executable.parent,
            env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')),
            stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if report_file.is_file():
                    report = json.loads(report_file.read_text(encoding='utf-8'))
                    break
                if process.poll() is not None:
                    raise RuntimeError('Native deadline fixture exited before reporting')
                time.sleep(0.10)
            else:
                raise RuntimeError('Native deadline fixture did not report within 35 seconds')
        finally:
            process.terminate()
            process.wait(timeout=5)
    errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    report['native_errors'] = errors
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not report['failures'], report['failures']
    assert not errors, errors
    print('PASS:', len(report['checks']), 'native deadline/correction/cancellation/progress checks;',
          len(report['cases']), 'fixed cases; no real model, network or user data')


if __name__ == '__main__':
    main()
