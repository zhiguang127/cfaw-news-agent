"""Verify bounded recall and terminal preparation states in isolated native Rinx."""
import json
import os
from pathlib import Path
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe
exe = ensure_native_probe()
work=ROOT/'.test-state/tracking-preparation'
(work/'bundle').mkdir(parents=True,exist_ok=True)
source,_=assemble(paths=ORDER[:-1])
source+=r"""
let prep_checks = [] let prep_failures = [] let prep_calls = 0 let prep_original_recall = bm25_recall
fn prep_assert(value, text){ if value { prep_checks.push(text) } else { prep_failures.push(text) } }
fn prep_report(){ fs.write("prep-report.json", {checks: prep_checks failures: prep_failures model_calls: prep_calls complete: true}.to_json()) }
fn prep_wait(condition, complete, deadline){
    if time_now() > deadline { prep_assert(false, "case timeout: " + tracking_status) prep_report() return }
    if condition() { start_timeout(0.01, complete) } else { start_timeout(0.02, || prep_wait(condition, complete, deadline)) }
}
fn prep_no_candidates(){
    bm25_recall = prep_original_recall
    app_feed_rows = []
    let calls = prep_calls
    tracking_start(nil)
    prep_wait(|| tracking_status == "no_candidates", || {
        prep_assert(prep_calls == calls && tracking_preparation_timer == nil && !tracking_in_progress(), "no candidates finishes without a model call")
        prep_report()
    }, time_now() + 3)
}
fn prep_cancel(){
    tracking_start(nil)
    analysis_cancel()
    prep_assert(tracking_status == "cancelled" && tracking_preparation_timer == nil && !tracking_in_progress(), "cancel clears preparation and permits retry")
    start_timeout(0.3, || {
        prep_assert(tracking_status == "cancelled", "cancelled preparation cannot later time out or publish")
        prep_no_candidates()
    })
}
fn prep_stale(){
    tracking_start(nil)
    let generation = tracking_recall_generation let key = tracking_context_key()
    topic_records.topics[0].version = topic_records.topics[0].version + 1
    prep_assert(!tracking_preparation_current(generation, key) && tracking_status == "stale" && tracking_preparation_timer == nil, "changed focus ends preparation instead of silently abandoning callbacks")
    prep_assert(!tracking_in_progress(), "stale preparation allows another check")
    prep_cancel()
}
fn prep_timeout(){
    bm25_recall = fn(rows, targets, current, complete){}
    tracking_config.preparation_timeout_seconds = 0.2
    tracking_start(nil)
    let generation = tracking_recall_generation
    prep_wait(|| tracking_status == "failed", || {
        prep_assert(regex("超时").test(tracking_message) && tracking_preparation_timer == nil && !tracking_in_progress(), "lost callback times out into an actionable failure")
        prep_assert(tracking_recall_generation > generation, "timed out callbacks cannot publish afterwards")
        let state = check_state_find("topic", topic_records.topics[0].topic_id, topic_records.topics[0].version)
        prep_assert(state != nil && state.status == "failed" && state.category == "timeout" && regex("超时").test(state.reason), "timeout is recorded without advancing a success watermark")
        prep_stale()
    }, time_now() + 3)
}
fn prep_full_feed(){
    app_feed_rows = fs.read("full-input.json").parse_json()
    tracking_start(nil)
    prep_wait(|| !tracking_in_progress(), || {
        fs.write("model-state.json", {status: tracking_status message: tracking_message error: analysis_error calls: prep_calls runs: tracking_cache.runs.len()}.to_json())
        prep_assert(tracking_status == "no_change" && tracking_cache.runs.len() == 1 && prep_calls == 1, "240 news complete recall and validated result publication")
        prep_assert(tracking_preparation_timer == nil, "model handoff clears the preparation watchdog")
        let diagnostic = fs.read("tracking_preparation_v1.json").parse_json()
        prep_assert(diagnostic.phase == "snapshot" && diagnostic.scanned == 240 && diagnostic.total == 240, "local preparation progress reaches the full feed and model handoff")
        prep_assert(diagnostic["topics"] == nil && diagnostic["schedules"] == nil && diagnostic["evidence"] == nil && diagnostic["prompt"] == nil, "local preparation diagnostics exclude private task and news content")
        prep_assert(agent_task.snapshot.evidence.len() > 0 && agent_task.snapshot.evidence.len() <= 8 && agent_task.snapshot.omitted_candidates + agent_task.snapshot.evidence.len() == 240, "candidate bounds and omission counts remain explicit after prompt shrinking")
        prep_assert(agent_task.snapshot.omitted_candidates > 232 && agent_task.prompt.to_bytes().len() <= tracking_config.max_prompt_bytes - 2048, "long summaries shrink whole candidates to the byte budget without cutting JSON")
        prep_timeout()
    }, time_now() + 40)
}
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    tracking_schedule_check = fn(){}
    user_schedules = [] user_interests = []
    let understanding = {title: "固定测试：会议记录与演示工具" purpose: "核对值得试的新功能，不承诺效率收益"
        preferences: ["不会编程" "每周两小时" "少看融资" "少看模型跑分" "证据不足先核实" "不承诺效率收益"]
        recall_rules: [{kind: "keyword" value: "AI 会议记录"} {kind: "keyword" value: "演示文稿"} {kind: "keyword" value: "meeting notes AI"} {kind: "keyword" value: "AI presentation"} {kind: "category" value: "ai"} {kind: "category" value: "tech"}]}
    let topic = understanding.to_json().parse_json()
    topic["scope"] = ["普通人可使用的会议记录整理与演示文稿制作新功能，关注可用性、使用条件和限制" "不会编程的用户每周只有两小时学习时间，优先低门槛功能，证据不足先核实" "presentation meeting notes productivity availability restrictions" "会议记录演示文稿使用条件限制功能新进展"]
    topic.topic_id = "fixture-preparation" topic.version = 1 topic.status = "active" topic.intent_kind = "goal"
    topic.original_input = "固定测试：整理会议记录和制作演示文稿" topic.supplement = "" topic.created_at = 1 topic.updated_at = 1
    topic_records.topics = [topic]
    let terms = bm25_terms({topics: [topic] schedules: [] legacy_interests: []})
    prep_assert(terms.len() == 24, "long practical goal respects the 24-term bound")
    let mixed = bm25_terms({topics: [] schedules: [] legacy_interests: [{kind: "keyword" value: "AI ai Ai 会议 会议"}]})
    prep_assert(mixed.len() == 2, "case insensitive duplicates and Han duplicates share one term")
    prep_assert(mixed[0].value == "ai" && mixed[1].value == "会议", "query terms retain canonical Latin keys and exact Han tokens")
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name != "octos.turn.start" { callback({is_ok: true data: {}}) return }
        prep_calls = prep_calls + 1
        let items = []
        for e in agent_task.snapshot.evidence { items.push({news_id: e.news_id relevance: "uncertain" topic_ids: [topic.topic_id] legacy_interest_ids: [] evidence_ids: [e.news_id] why_related: "固定测试：只有标题摘要，需要核实适用条件" uncertainties: ["固定替代模型回复"] schedule_impacts: []}) }
        let result = {schema_version: 2 outcome: "no_change" explanation: "固定测试：需核实使用条件，尚无充分依据改变计划" items: items insights: []}
        result.insights.push({target_type: "topic" target_id: topic.topic_id target_version: topic.version issue_key: "availability" summary: "固定测试：没有新的行动依据" change_kind: "new" decision_effect: "unknown" material_change: "" uncertainties: ["未验证效率收益"] evidence_ids: [items[0].news_id] evidence_refs: []})
        start_timeout(0.01, || callback({is_ok: true data: {text: result.to_json()}}))
    }
    let rows = fs.read("ranking-input.json").parse_json()
    rows.push(rows[239])
    bm25_recall(rows, {topics: [] schedules: [] legacy_interests: [{kind: "keyword" value: "rare common"}]}, || true, fn(recalled){
        prep_assert(recalled.rows.len() == 8 && recalled.matched == 240 && recalled.omitted_candidates == 232, "BM25 deduplicates and caps a full feed")
        prep_assert(recalled.rows[0].news_id == rows[239].news_id, "rare terms outrank repeated common words")
        prep_assert(recalled.rows[1].news_id == rows[0].news_id && recalled.rows[2].news_id == rows[1].news_id, "equal scores retain feed order")
        prep_assert(bm25_prefix("杭州abcdef", 3) == "杭州a", "prefix keeps Unicode boundaries")
        let text = rows[0].summary + "\n🙂abc"
        let bounded = bm25_prefix(text, 1800)
        prep_assert(bounded.to_chars().len() == 1800 && bounded.to_chars()[1799] == text.to_chars()[1799], "long Unicode prefix avoids counted wildcard regex and preserves the boundary")
        prep_assert(bm25_prefix("🙂杭州", 1) == "🙂" && bm25_prefix("🙂杭州", 0) == "", "prefix preserves supplementary codepoints and empty bounds")
        prep_full_feed()
    })
})
"""
(work/'bundle/main.splash').write_text(source,encoding='utf-8')
data=work/('data-'+str(time.time_ns()));(data/'host').mkdir(parents=True)
app=data/'dev.cfaw.runtime-tests';app.mkdir()
def sample(i, title, summary, group):
    url='https://example.invalid/'+group+'/'+str(i)
    return dict(news_id=url,evidence_id=url,content_version=title+'\n'+summary,title=title,summary=summary,source='固定测试来源',source_id='ithome',source_url=url,feed_url='https://www.ithome.com/rss',category='tech',language='zh',image_url=None,published_at=None,retrieved_at=time.time(),evidence_kind='rss_summary',timestamp_kind='published',references=[dict(source='固定测试来源',source_id='ithome',source_url=url,feed_url='https://www.ithome.com/rss')])
long_summary='普通人可使用的新功能、条件与限制；不会编程，每周学习两小时。'+('研究新闻分析科学技术人工智能应用工作学习生活🙂'*120)
full=[sample(i,'固定测试：AI会议记录与演示文稿 '+str(i),long_summary,'preparation') for i in range(240)]
ranking=[sample(i,'rare' if i==239 else 'common common common',('rare' if i==239 else 'common filler filler filler filler')+' '+('研究新闻分析科学技术应用工作学习生活🙂'*120),'bm25') for i in range(240)]
for name,rows in [('full',full),('ranking',ranking)]: (app/(name+'-input.json')).write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
with (work/'host.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen([str(exe),'--bundle',str(work/'bundle'),'--app-data',str(data),'--size','430x860'],cwd=exe.parent,env=dict(os.environ,RINX_DATA_DIR=str(data/'host')),stdout=log,stderr=log,startupinfo=startup)
    try:
        p=data/'dev.cfaw.runtime-tests/prep-report.json'
        for _ in range(900):
            if p.is_file():
                try:
                    report=json.loads(p.read_text(encoding='utf-8'))
                    if report.get('complete'): break
                except (OSError,ValueError): pass
            if process.poll() is not None: raise RuntimeError('Native process exited')
            time.sleep(.1)
        else: raise RuntimeError('Native preparation checks timed out')
    finally: process.terminate();process.wait(timeout=5)
(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
assert not report['failures'], report
assert '[E]' not in (work/'host.log').read_text(encoding='utf-8',errors='replace')
