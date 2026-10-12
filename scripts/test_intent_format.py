"""Exercise intent schema diagnostics, bounded repair and confirmation in isolated native Rinx."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from assemble import ROOT, ORDER, assemble

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--live-replies',type=Path,help='Directory containing authorized baseline/updated final replies')
args=parser.parse_args()
work=ROOT/'.test-state/intent-format'
bundle=work/'bundle'
bundle.mkdir(parents=True,exist_ok=True)
source,_=assemble(paths=ORDER[:-1])
user_input='我想用 AI 减少整理会议记录和制作演示文稿的时间。我不会编程，每周只有两小时学习。关注普通人已经能使用的新功能、使用条件和限制，少看融资与模型跑分。帮我判断什么值得试，证据不足时先核实，不要承诺效率收益'
good=dict(schema_version=1,status='ready',question='',understanding=dict(title='AI会议记录与演示工具（固定测试）',purpose='判断值得尝试的会议记录和演示文稿功能',scope=['会议记录','演示文稿','已可使用的新功能及条件限制'],preferences=['不会编程，每周只有两小时学习','优先普通人可直接使用的功能','少看融资与模型跑分','证据不足先核实，不承诺效率收益'],recall_rules=[dict(kind='keyword',value='AI'),dict(kind='keyword',value='会议记录'),dict(kind='keyword',value='演示文稿')]))
source+='\nlet format_input = '+json.dumps(user_input,ensure_ascii=False)+'\nlet format_good = '+json.dumps(json.dumps(good,ensure_ascii=False),ensure_ascii=False)+'.parse_json()\n'
live={}
if args.live_replies:
    live={name:(args.live_replies/(name+'-reply.txt')).read_text(encoding='utf-8') for name in ('baseline','updated')}
source+='let format_live = '+json.dumps(live,ensure_ascii=False)+'\n'
source+=r"""
let format_checks = [] let format_failures = [] let format_calls = 0 let format_reply = nil let format_prompt = "" let format_live_results = {}
fn format_assert(value, label){ if value { format_checks.push(label) } else { format_failures.push(label) } fs.write("format-progress.json", {checks: format_checks failures: format_failures calls: format_calls}.to_json()) }
fn format_begin(){ intent_begin(nil) intent_pick_mode("goal") intent_changed(format_input, false) intent_submit() }
fn format_done(){
    for name in ["baseline" "updated"] {
        if format_live[name] == nil { continue }
        let checked = tracking_parse(format_live[name], "parse_intent", {previous_question: ""})
        format_live_results[name] = {valid: checked.valid message: checked.message}
        format_assert(checked.valid, "real model " + name + " final reply passes native validator")
    }
    fs.write("format-report.json", {checks: format_checks failures: format_failures live: format_live_results calls: format_calls complete: true}.to_json())
}
fn format_cancel_case(){
    format_begin() let calls = format_calls
    format_reply({is_ok: true data: {text: "bad JSON"}})
    analysis_cancel()
    start_timeout(0.2, || {
        format_assert(analysis_state == "cancelled" && format_calls == calls, "cancel stops queued correction")
        format_assert(intent_draft.original_input == format_input && topic_records.topics.len() == 1, "cancel preserves input and confirmed records")
        format_done()
    })
}
fn format_stale_case(){
    format_begin() let calls = format_calls
    format_reply({is_ok: true data: {text: "bad JSON"}})
    intent_changed(format_input + "；我修改了输入", false)
    start_timeout(0.2, || {
        format_assert(analysis_state == "failed" && analysis_error_category == "stale_context" && format_calls == calls, "edited draft prevents queued correction from running")
        format_assert(intent_draft.state == "editing" && intent_draft.understanding == nil, "edited draft never adopts stale understanding")
        format_cancel_case()
    })
}
fn format_limit_case(){
    format_begin() let calls = format_calls
    format_reply({is_ok: true data: {text: "bad JSON"}})
    start_timeout(0.15, || {
        format_assert(format_calls == calls + 1, "invalid JSON triggers one correction")
        let malformed_scope = format_good.to_json().parse_json() malformed_scope.understanding["scope"] = "AI"
        format_reply({is_ok: true data: {text: malformed_scope.to_json()}})
        start_timeout(0.15, || {
            format_assert(analysis_state == "failed" && format_calls == calls + 1 && regex("scope").test(intent_error), "second failure stops with specific field error")
            format_assert(intent_draft.original_input == format_input && intent_draft.state == "editing" && topic_records.topics.len() == 1, "failed correction preserves original draft without saving")
            format_stale_case()
        })
    })
}
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    tracking_schedule_check = fn(){}
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name == "octos.turn.start" { format_calls = format_calls + 1 format_reply = callback format_prompt = data.text }
        else { callback({is_ok: true data: {}}) }
    }
    agent_progress_handler = agent_progress
    format_assert(intent_validate(format_good).valid, "complete constrained intent is accepted")
    let bad = format_good.to_json().parse_json()
    bad.understanding.preferences = ["不会编程" "每周两小时" "新功能" "使用条件" "限制" "少融资跑分" "先核实不承诺收益"]
    format_assert(!intent_validate(bad).valid && regex("preferences").test(intent_validate(bad).message), "seven preferences reproduce the former generic failure with a precise diagnostic")
    let wrong = format_good.to_json().parse_json() wrong.understanding.recall_rules = ["AI"]
    format_assert(!intent_validate(wrong).valid && regex("recall_rules").test(intent_validate(wrong).message), "plain string rules are rejected with their field")
    let empty_scope = format_good.to_json().parse_json() empty_scope.understanding["scope"] = []
    format_assert(!intent_validate(empty_scope).valid, "missing scope cannot be accepted")
    wrong = format_good.to_json().parse_json() wrong.understanding.purpose = nil
    format_assert(!intent_validate(wrong).valid && regex("purpose").test(intent_validate(wrong).message), "missing purpose requires a corrected string")
    wrong = format_good.to_json().parse_json() wrong.question = "你想怎么用？"
    format_assert(!intent_validate(wrong).valid && regex("question").test(intent_validate(wrong).message), "ready cannot carry an unresolved question")
    wrong = format_good.to_json().parse_json() wrong.understanding.recall_rules = [{kind: "category" value: "exclude:financing"}]
    format_assert(!intent_validate(wrong).valid, "invented negative category remains rejected")
    format_begin()
    format_assert(agent_task.snapshot.prompt_revision == "intent-v1.1", "intent uses independent prompt revision")
    let first_reply = format_reply let deadline_timer = agent_task.timer
    first_reply({is_ok: true data: {text: bad.to_json()}})
    format_assert(analysis_busy && agent_task.repair_count == 1 && agent_task.timer == deadline_timer, "repair retains the original deadline and task")
    first_reply({is_ok: true data: {text: format_good.to_json()}})
    format_assert(analysis_busy && intent_draft.state == "editing", "duplicate first reply cannot publish while correction is queued")
    start_timeout(0.15, || {
        format_assert(format_calls == 2 && regex("preferences").test(format_prompt) && regex(literal_pattern(format_input)).test(format_prompt), "correction carries validator detail and the same user input")
        format_reply({is_ok: true data: {text: format_good.to_json()}})
        format_assert(analysis_state == "succeeded" && intent_draft.state == "ready" && topic_records.topics.len() == 0, "corrected reply becomes a preview without saving")
        format_assert(intent_draft.original_input == format_input && intent_draft.understanding.preferences.to_json() == format_good.understanding.preferences.to_json(), "all explicit skill time priorities and uncertainty constraints survive")
        intent_confirm()
        format_assert(topic_records.topics.len() == 1 && intent_draft == nil, "only explicit confirmation persists one topic")
        topics_load()
        format_assert(topic_records.topics[0].original_input == format_input && topic_records.topics[0].preferences.to_json() == format_good.understanding.preferences.to_json(), "confirmed intent and constraints survive filesystem reload")
        format_limit_case()
    })
})
"""
(bundle/'main.splash').write_text(source,encoding='utf-8')
data=work/('data-'+str(time.time_ns()))
(data/'host').mkdir(parents=True)
exe=ROOT/'.test-state/intent-context/native/intent-probe.exe'
startup=subprocess.STARTUPINFO()
startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow=0
with (work/'host.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen([str(exe),'--bundle',str(bundle),'--app-data',str(data),'--size','430x860'],cwd=exe.parent,env=dict(os.environ,RINX_DATA_DIR=str(data/'host')),stdout=log,stderr=log,startupinfo=startup)
    try:
        report_path=data/'dev.cfaw.runtime-tests/format-report.json'
        for _ in range(200):
            if report_path.is_file():
                try:
                    report=json.loads(report_path.read_text(encoding='utf-8'))
                    if report.get('complete'): break
                except (OSError,ValueError): pass
            if process.poll() is not None: raise RuntimeError('Native process exited before report')
            time.sleep(.1)
        else: raise RuntimeError('Native report timed out; see '+str(work/'host.log'))
    finally:
        process.terminate()
        process.wait(timeout=5)
assert not report['failures'], report
assert '[E]' not in (work/'host.log').read_text(encoding='utf-8',errors='replace')
(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
