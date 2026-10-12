"""Native topic queue checks with isolated storage and mock analysis only."""
import json
import os
import subprocess
import time

from assemble import ORDER, ROOT, assemble
from native_probe import ensure_native_probe


def fixture_topics():
    topics = []
    for index, name in enumerate(('甲', '乙', '丙', '暂停')):
        topics.append(dict(topic_id='queue-' + str(index), version=1,
                           title='合成测试话题' + name, purpose='检查逐话题排队',
                           scope=['合成测试'], preferences=[],
                           recall_rules=[dict(kind='keyword', value=name)],
                           original_input='合成测试，不是真实关注', supplement='',
                           created_at=1, updated_at=1,
                           status='paused' if index == 3 else 'active',
                           intent_kind='news', demo_preset=False))
    return topics


SOURCE = r'''
let queue_checks = [] let queue_failures = [] let queue_fixture = []
let queue_calls = [] let queue_auto_calls = 0 let queue_real_model_calls = 0 let queue_network_calls = 0
let queue_phase = "boot" let queue_mode = "all_checked" let queue_gap = "" let queue_gap_set = false
let queue_mock_seconds = 0.05 let queue_run_serial = 0
fn queue_assert(condition, label){ if condition { queue_checks.push(label) } else { queue_failures.push(label) } }
fn queue_progress(){ fs.write("progress.json", {phase: queue_phase calls: queue_calls completed: follow_check_completed failed: follow_check_failed running: follow_check_running}.to_json()) }
fn queue_report(){
    fs.write("report.json", {complete: true checks: queue_checks failures: queue_failures real_model_calls: queue_real_model_calls network_calls: queue_network_calls auto_calls: queue_auto_calls}.to_json())
}
fn queue_wait(condition, next, deadline){
    if time_now() > deadline { queue_assert(false, "phase timeout: " + queue_phase) queue_progress() queue_report() return }
    if condition() { start_timeout(0.01, next) }
    else { start_timeout(0.04, || queue_wait(condition, next, deadline)) }
}
fn queue_reset(phase){
    if follow_check_timer != nil { stop_timer(follow_check_timer) follow_check_timer = nil }
    if tracking_auto_timer != nil { stop_timer(tracking_auto_timer) tracking_auto_timer = nil }
    topic_records.topics = queue_fixture.to_json().parse_json()
    follow_check_running = false follow_check_queue = [] follow_check_waiting = nil
    follow_check_completed = 0 follow_check_failed = 0 follow_check_feedback = ""
    tracking_pending_run = nil tracking_status = "idle" tracking_save_active = false analysis_busy = false agent_task = nil
    busy = false intent_open = false intent_motion_active = false octos_testing = false reader_summary.state = "idle" analysis_needs_reopen = false
    tracking_check_pending = false agent_preferences.paused = false
    queue_calls = [] queue_phase = phase queue_mode = "all_checked" queue_gap = "" queue_gap_set = false queue_mock_seconds = 0.05
    queue_run_serial = queue_run_serial + 1
    queue_progress()
}
fn queue_set_gap(value){
    if queue_gap == "busy" { busy = value }
    if queue_gap == "intent" { intent_open = value }
    if queue_gap == "motion" { intent_motion_active = value }
    if queue_gap == "summary" { reader_summary.state = if value {"running"} else {"idle"} }
    if queue_gap == "probe" { octos_testing = value }
}
fn queue_finish_core(){
    queue_assert(queue_calls.len() == 3, "three active topics each get a turn after one failure")
    queue_assert(queue_calls[0].id == "queue-0" && queue_calls[1].id == "queue-1" && queue_calls[2].id == "queue-2", "active topic order retained and paused topic excluded")
    queue_assert(follow_check_completed == 3 && follow_check_failed == 1, "checked, failed and no-candidate results counted separately")
    queue_assert(check_state_find("topic", "queue-0", 1).status == "checked" && check_state_find("topic", "queue-1", 1).status == "failed" && check_state_find("topic", "queue-2", 1).status == "no_candidates", "real per-target check states reflect each mock outcome")
    queue_assert(queue_auto_calls == 0, "manual queue suppresses automatic tracking")
    queue_assert(regex("1 项未完成").test(follow_check_feedback), "completed queue reports failed topic count honestly")
    queue_gap_index = 0 queue_start_gap()
}
let queue_gap_cases = ["busy" "intent" "motion" "summary" "probe"] let queue_gap_index = 0
fn queue_start_gap(){
    if queue_gap_index >= queue_gap_cases.len() { queue_start_cancel() return }
    queue_reset("gap-" + queue_gap_cases[queue_gap_index])
    queue_gap = queue_gap_cases[queue_gap_index]
    follow_check_all()
    queue_wait(|| queue_gap_set, || {
        start_timeout(0.65, || {
            queue_assert(follow_check_running && queue_calls.len() == 1, queue_gap + " gap waits before starting another topic")
            queue_assert(follow_check_completed == 1 && follow_check_failed == 0, queue_gap + " gap does not falsely count unstarted topics as failures")
            tracking_schedule_check()
            queue_assert(tracking_auto_timer == nil, queue_gap + " queue gap suppresses automatic timer")
            queue_set_gap(false)
            queue_wait(|| !follow_check_running, || {
                queue_assert(queue_calls.len() == 3 && follow_check_completed == 3 && follow_check_failed == 0, queue_gap + " gap resumes all remaining topics")
                queue_gap_index = queue_gap_index + 1 queue_start_gap()
            }, time_now() + 4)
        })
    }, time_now() + 2)
}
fn queue_start_cancel(){
    queue_reset("cancel-late") queue_mock_seconds = 0.6
    follow_check_all()
    follow_stop_checks()
    queue_assert(!follow_check_running && follow_check_queue.len() == 0 && follow_check_timer == nil, "cancel clears queue and scheduled continuation")
    start_timeout(0.9, || {
        queue_assert(queue_calls.len() == 1 && !follow_check_running && follow_check_completed == 0, "late analysis callback after cancel cannot start another topic")
        queue_start_context()
    })
}
fn queue_start_context(){
    queue_reset("context-version")
    follow_check_all()
    topic_records.topics[1].version = 2
    queue_wait(|| !follow_check_running, || {
        queue_assert(queue_calls.len() == 1 && follow_check_queue.len() == 0, "topic version change stops remaining queue")
        queue_assert(regex("配置已变化").test(follow_check_feedback), "context change has a visible explanation")
        queue_start_unsaved()
    }, time_now() + 3)
}
fn queue_start_unsaved(){
    queue_reset("unsaved") queue_mode = "unsaved"
    follow_check_all()
    queue_wait(|| !follow_check_running, || {
        queue_assert(queue_calls.len() == 1 && follow_check_completed == 1, "unsaved result stops later topics")
        queue_assert(tracking_pending_run != nil && regex("尚未保存").test(follow_check_feedback), "unsaved result remains available with retry-save guidance")
        queue_start_single()
    }, time_now() + 3)
}
fn queue_start_single(){
    queue_reset("single")
    follow_check_topic("queue-1")
    queue_wait(|| !follow_check_running, || {
        queue_assert(queue_calls.len() == 1 && queue_calls[0].id == "queue-1" && follow_check_total == 1, "individual check targets only the selected active topic")
        queue_reset("entry-guards")
        busy = true follow_check_all()
        queue_assert(!follow_check_running && queue_calls.len() == 0, "busy feed rejects a new queue without analysis")
        busy = false follow_check_topic("queue-3")
        queue_assert(!follow_check_running && queue_calls.len() == 0, "paused topic cannot start an individual check")
        tracking_pending_run = {fixture: true} follow_check_all()
        queue_assert(!follow_check_running && queue_calls.len() == 0, "pending save rejects a new queue")
        queue_assert(queue_real_model_calls == 0 && queue_network_calls == 0 && queue_auto_calls == 0, "all queue checks use isolated mocks with no network or live model")
        queue_projection_retention()
        queue_report()
    }, time_now() + 3)
}
fn queue_projection_retention(){
    let previous_states = check_states.to_json().parse_json()
    let previous_runs = tracking_cache.runs
    let topic = topic_find("queue-0")
    tracking_cache.runs = [] check_states.items = []
    let card = follow_topic_projection(topic)
    queue_assert(card.status == "unseen" && card.checked_at == 0 && card.last_checked_at == 0,
        "first unchecked topic keeps the first-check state without analysis timestamps")
    // Reproduce the real bounded-history shape: the newest twelve runs all
    // belong to other topics, while this topic retains a success watermark.
    for index in tracking_config.max_runs {
        tracking_cache.runs.push({task_id: "retained-other-" + index checked_at: time_now() - index
            result: {insights: []} snapshot: {topics: [{topic_id: "other-" + index version: 1}]}})
    }
    let watermark = time_now() - 600
    let state = {target_type: "topic" target_id: topic.topic_id target_version: topic.version
        watermark: watermark attempt_at: watermark status: "checked" category: "" reason: ""}
    check_states.items = [state]
    card = follow_topic_projection(topic)
    queue_assert(tracking_cache.runs.len() == tracking_config.max_runs && card.status_label == "需重新检查" &&
        regex("保留范围").test(card.note), "evicted successful topic explains bounded history and requests a fresh check")
    queue_assert(card.checked_at == 0 && card.last_checked_at == watermark && !card.current && !card.basis_current &&
        card.values.len() == 0 && card.news_count == 0,
        "success watermark is separate from unavailable analysis, evidence and decisions")
    let time_label = follow_card_time(card)
    queue_assert(regex("上次完成检查").test(time_label) && regex("当前无分析详情").test(time_label) &&
        !regex("最近分析").test(time_label), "retained watermark is displayed as a check time rather than an analysis snapshot")
    state.status = "no_candidates" state.attempt_at = time_now()
    card = follow_topic_projection(topic)
    queue_assert(card.status_label == "未找到候选" && regex("来源覆盖有限").test(card.situations.to_json()) &&
        card.checked_at == 0 && card.last_checked_at == watermark,
        "no-candidate outcome overrides the retention warning without inventing an analysis snapshot")
    state.status = "failed" state.category = "timeout" state.reason = "合成测试：最近检查超时"
    card = follow_topic_projection(topic)
    queue_assert(card.status == "failed" && card.note == state.reason && card.checked_at == 0 &&
        card.last_checked_at == watermark && card.attempt_at == state.attempt_at,
        "failed attempt exposes its actual cause while keeping prior successful check time separate")
    state.target_version = topic.version + 1 state.status = "checked"
    card = follow_topic_projection(topic)
    queue_assert(card.status == "unseen" && card.last_checked_at == 0 && card.checked_at == 0,
        "a different topic-version watermark cannot imply that this version was checked")
    check_states = previous_states tracking_cache.runs = previous_runs
}
start_timeout(0.1, || {
    queue_fixture = fs.read("topics-fixture.json").parse_json()
    // No startup function is included. The real queue and check-state owners
    // execute; only the analysis boundary and rendering are replaced.
    page = "feed" follow_render = fn(){} tracking_ui_update = fn(){}
    analysis_host_has = fn(name){ false }
    analysis_host_request = fn(name, data, callback){ queue_real_model_calls = queue_real_model_calls + 1 start_timeout(0.01, || callback({is_ok: false error: "live host forbidden in fixture"})) }
    tracking_start = fn(row, verification = nil, target_override = nil){
        if target_override == nil { queue_auto_calls = queue_auto_calls + 1 return }
        queue_assert(row == nil && verification == nil, "queue dispatch uses no unrelated article or verification target")
        queue_assert(target_override.topics.len() == 1 && target_override.schedules.len() == 0 && target_override.legacy_interests.len() == 0, "each override contains exactly one topic without schedules or legacy rules")
        let topic = target_override.topics[0]
        queue_assert(topic.status == "active" && topic.version == topic_find(topic.topic_id).version, "dispatch uses current active topic version")
        queue_assert(!busy && !intent_open && !intent_motion_active && !octos_testing && reader_summary.state != "running", "queue waits for all unrelated work before dispatch")
        queue_calls.push({id: topic.topic_id version: topic.version})
        let serial = queue_run_serial let first = queue_calls.len() == 1 let mode = queue_mode
        tracking_recall_targets = target_override tracking_status = "recalling"
        check_states_record(target_override, "pending", "", false)
        start_timeout(queue_mock_seconds, || {
            if serial != queue_run_serial { return }
            let status = "checked"
            if mode == "mixed" && topic.topic_id == "queue-1" { status = "failed" }
            if mode == "mixed" && topic.topic_id == "queue-2" { status = "no_candidates" }
            check_states_record_reason(target_override, status, if status == "failed" {"timeout"} else {""}, status != "failed", if status == "failed" {"合成测试分析超时"} else {""})
            tracking_status = "idle"
            if mode == "unsaved" { tracking_pending_run = {fixture: true} }
            if first && queue_gap != "" { queue_gap_set = true queue_set_gap(true) }
            queue_progress()
        })
    }
    queue_reset("core") queue_mode = "mixed"
    // A queued automatic timer is cancelled by the explicit manual request.
    tracking_schedule_check()
    queue_assert(tracking_auto_timer != nil, "automatic timer is initially armed")
    follow_check_all()
    queue_assert(tracking_auto_timer == nil && !tracking_check_pending, "manual request cancels prior automatic timer")
    let first_count = queue_calls.len()
    follow_check_all() follow_check_topic("queue-2")
    queue_assert(queue_calls.len() == first_count && follow_check_total == 3, "repeated clicks cannot start or replace an active queue")
    tracking_schedule_check()
    queue_assert(tracking_auto_timer == nil, "automatic trigger cannot arm a timer while queue runs")
    queue_wait(|| !follow_check_running, queue_finish_core, time_now() + 5)
})
'''


def main():
    previous_probe = ROOT.parent / 'cfaw-news-agent-10.9/.test-state/intent-context/native/intent-probe.exe'
    if not os.environ.get('CFAW_NATIVE_PROBE') and previous_probe.is_file():
        os.environ['CFAW_NATIVE_PROBE'] = str(previous_probe)
    exe = ensure_native_probe()
    work = ROOT / '.test-state/follow-topic-queue'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    (bundle / 'main.splash').write_text(source + SOURCE, encoding='utf-8')
    data = work / ('data-' + str(time.time_ns()))
    app = data / 'dev.cfaw.runtime-tests'
    app.mkdir(parents=True)
    (data / 'host').mkdir()
    (app / 'topics-fixture.json').write_text(json.dumps(fixture_topics(), ensure_ascii=False), encoding='utf-8')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    report = None
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data), '--size', '430x860'],
                                   cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')),
                                   stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                path = app / 'report.json'
                if path.is_file():
                    report = json.loads(path.read_text(encoding='utf-8'))
                    break
                if process.poll() is not None:
                    raise RuntimeError('Native probe exited before queue checks completed')
                time.sleep(.1)
            if report is None:
                progress = app / 'progress.json'
                raise RuntimeError('Native queue checks timed out; last progress: ' +
                                   (progress.read_text(encoding='utf-8') if progress.is_file() else 'none'))
        finally:
            process.terminate()
            process.wait(timeout=5)
    errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    report['native_errors'] = errors
    report['fixture_data'] = str(data)
    report['network_capability'] = False
    report['real_model_service_available'] = False
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not report['failures'], report
    assert not errors, errors
    stored = json.loads((app / 'target_checks_v1.json').read_text(encoding='utf-8'))
    assert stored['revision'] > 0 and stored['items'], stored
    print('PASS:', len(report['checks']), 'native topic queue/check-state checks; mock analysis only; no live model/network/account data')


if __name__ == '__main__':
    main()
