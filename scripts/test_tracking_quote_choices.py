"""Native quote-choice integrity and bounded repair; isolated fixtures only."""
import copy
import json
import os
import subprocess
import time

from assemble import ORDER, ROOT, assemble
from native_probe import ensure_native_probe


def evidence(url, title, paragraphs):
    return dict(news_id=url, title=title, summary='固定来源摘要：使用条件须核实。',
                source_url=url, published_at=None, retrieved_at=1,
                timestamp_kind='unknown', evidence_kind='body_excerpt',
                content_key='fixture', references=[], summary_truncated=False,
                paragraphs=[dict(paragraph_id=key, text=text) for key, text in paragraphs],
                body_truncated=False, body_error='')


def snapshot(topics, schedules, articles):
    return dict(schema_version=1, topics=topics, schedules=schedules,
                legacy_interests=[], evidence=articles, previous_result=None,
                previous_by_target=[], decisions=[], omitted_targets=0,
                omitted_candidates=0, omitted_decisions=0, context_key='fixture',
                prompt_revision='tracking-v2.7')


def item(label, topic_ids):
    return dict(news_id=label, relevance='related' if topic_ids else 'uncertain',
                topic_ids=topic_ids, legacy_interest_ids=[],
                why_related='固定测试：该报道直接涉及被关注对象。',
                evidence_ids=[label], uncertainties=[], schedule_impacts=[])


def insight(kind, target, ids, refs):
    return dict(target_type=kind, target_id=target, target_version=1,
                issue_key='fixture-update', change_kind='new',
                summary='固定测试：报道披露了访问条件，限制仍须核实。',
                decision_effect='unknown', next_step='核实目前的费用与限制。',
                material_change='', uncertainties=['使用限制尚待核实'],
                evidence_ids=ids, evidence_refs=refs, compared_run_id=None,
                reschedule=None)


def fixtures():
    topic = dict(title='固定测试关注', purpose='了解真实使用条件',
                 scope=['普通账号使用条件'], preferences=['不承诺效率收益'],
                 recall_rules=[dict(kind='keyword', value='账号')],
                 topic_id='quote-topic', version=1, status='active', intent_kind='news',
                 original_input='固定测试', supplement='', created_at=1, updated_at=1)
    long = '固定来源中文：支持普通账号。🙂 中文原句。 ' + '界' * 390 + ' 中文第二片段：不承诺效率收益。'
    english = 'Published source: "Free" signup requires an account; no productivity guarantee. Emoji 🙂 and punctuation (a+b)? [test] $5.'
    articles = [evidence('https://example.com/chinese', '固定测试中文报道', [('p1', long)]),
                evidence('https://example.com/english', 'Fixed English report', [('p1', english)])]
    refs = [dict(news_id='E1', paragraph_id='p1', quote_id='q2', quote='中文改写而非原句'),
            dict(news_id='E2', paragraph_id='p1', quote_id='q1', quote='被翻译的模型引文')]
    model = dict(schema_version=2, outcome='update', explanation='固定测试：有限报道的来源事实。',
                 items=[item('E1', ['quote-topic']), item('E2', ['quote-topic'])],
                 insights=[insight('topic', 'quote-topic', ['E1', 'E2'], refs)])
    schedule = dict(schedule_id='quote-schedule', version=1, title='固定杭州活动',
                    content='', location='杭州', timezone='Asia/Shanghai', status='active',
                    time_precision='exact', allow_reschedule=True,
                    start='2026-10-15T09:00:00+08:00', end='2026-10-15T11:00:00+08:00')
    paragraph = '固定测试：杭州 2026-10-15 活动调整。原活动时段 2026-10-15T09:30 至 2026-10-15T10:30。替代时段 2026-10-15T13:00 至 2026-10-15T14:00。'
    schedule_articles = [evidence('https://example.com/schedule', '固定测试活动调整', [
        ('p1', paragraph),
        ('p2', '固定测试：2026-10-15 原活动时段 2026-10-15T09:30 至 2026-10-15T10:30；地点待核实。'),
        ('p3', '固定测试：杭州活动调整，具体日期尚未公开。'),
        ('p4', '固定测试：杭州 2026-10-15 替代时段从 2026-10-15T13:00 开始，结束时间未知。'),
        ('p5', '固定测试：杭州 2026-10-15 替代时段到 2026-10-15T14:00 结束，开始时间未知。')])]
    ref = dict(news_id='E1', paragraph_id='p1', quote_id='q1')
    impact = dict(schedule_id='quote-schedule', schedule_version=1, goal_key='event-time',
                  impact_summary='固定测试：原时段受影响。', event_start='2026-10-15T09:30:00+08:00',
                  event_end='2026-10-15T10:30:00+08:00', event_location='杭州',
                  overlap_reason='事件与既有安排重合。', evidence_ids=['E1'],
                  evidence_refs=[copy.deepcopy(ref)], uncertainties=[], material_change='')
    schedule_item = item('E1', [])
    schedule_item['schedule_impacts'] = [impact]
    schedule_insight = insight('schedule', 'quote-schedule', ['E1'], [copy.deepcopy(ref)])
    schedule_insight['reschedule'] = dict(start='2026-10-15T13:00:00+08:00',
                                          end='2026-10-15T14:00:00+08:00', timezone='Asia/Shanghai',
                                          reason='固定测试：来源给出替代时段。', evidence_refs=[copy.deepcopy(ref)])
    schedule_model = dict(schema_version=2, outcome='update', explanation='固定测试：来源给出调整依据。',
                          items=[schedule_item], insights=[schedule_insight])
    return dict(snapshot=snapshot([topic], [], articles), model=model,
                schedule_snapshot=snapshot([], [schedule], schedule_articles), schedule_model=schedule_model,
                expected_second=long[400:], expected_english=english,
                expected_cross_boundary=long[395:415], expected_schedule=paragraph)


SOURCE = r'''
let quote_fixture = nil let quote_checks = [] let quote_failures = []
let quote_step = 0 let quote_model_calls = 0 let quote_repair_prompts = []
let quote_case_calls = 0 let quote_repeat_bad = false let quote_last_error = ""
fn quote_assert(value, label){
    if value { quote_checks.push(label) }
    else { quote_failures.push({label: label error: quote_last_error}) }
    fs.write("progress.json", {checks: quote_checks failures: quote_failures step: quote_step}.to_json())
}
fn quote_clone(value){ value.to_json().parse_json() }
fn quote_parse(value, snapshot){
    let checked = tracking_parse(value.to_json(), "tracking_update", snapshot)
    quote_last_error = checked.message
    checked
}
fn quote_static_step(){
    if quote_step >= 23 { quote_save_case() return }
    // Each independent case runs in its own native callback and heap slice.
    start_timeout(0.03, quote_static_step)
    let step = quote_step quote_step = quote_step + 1
    let value = quote_clone(quote_fixture.model)
    let snapshot = quote_clone(quote_fixture.snapshot)
    if step == 0 {
        let checked = quote_parse(value, snapshot)
        quote_assert(checked.valid, "v2.7 insight choices pass with copied model quote replaced")
        if checked.valid {
            quote_assert(checked.result.insights[0].evidence_refs[0].quote == quote_fixture.expected_second, "Chinese second chunk is restored from the source")
            quote_assert(checked.result.insights[0].evidence_refs[1].quote == quote_fixture.expected_english, "English emoji and regex punctuation remain source-verbatim")
            quote_assert(checked.result.insights[0].evidence_refs[0].news_id == snapshot.evidence[0].news_id, "E labels expand before quote resolution")
        }
    } else if step == 1 {
        let before = snapshot.to_json()
        let payload = tracking_prompt_snapshot(snapshot)
        quote_assert(snapshot.to_json() == before, "quote projection leaves the immutable local snapshot unchanged")
        quote_assert(payload.evidence[0].paragraphs[0]["text"] == nil && payload.quote_format == "paragraph-choices-v1", "model projection sends choices instead of duplicate paragraph text")
        let reconstructed = ""
        for choice in payload.evidence[0].paragraphs[0].quote_choices {
            reconstructed = reconstructed + choice.text
            quote_assert(choice.text.to_chars().len() <= 400, "Unicode chunk respects 400-character quote limit")
        }
        quote_assert(reconstructed == snapshot.evidence[0].paragraphs[0].text, "choice projection preserves the entire supplied paragraph once")
        let prompt = tracking_prompt + payload.to_json()
        quote_assert(prompt.to_bytes().len() < tracking_config.max_prompt_bytes - 2048, "representative choice prompt keeps repair headroom")
    } else if step == 2 {
        value.insights[0].evidence_refs[0].news_id = "E99"
        quote_assert(!quote_parse(value, snapshot).valid, "unknown news label is rejected despite a plausible copied quote")
    } else if step == 3 {
        value.insights[0].evidence_refs[0].paragraph_id = "p99"
        quote_assert(!quote_parse(value, snapshot).valid, "unknown paragraph is rejected")
    } else if step == 4 {
        value.insights[0].evidence_refs[0].quote_id = "q99"
        value.insights[0].evidence_refs[0].quote = quote_fixture.expected_second
        quote_assert(!quote_parse(value, snapshot).valid, "unknown quote ID never falls back to even an accurate model quote")
    } else if step == 5 {
        value.insights[0].evidence_refs[0].quote_id = 1
        quote_assert(!quote_parse(value, snapshot).valid, "non-string quote ID is rejected")
    } else if step == 6 {
        value.insights[0].evidence_refs[0].quote_id = nil
        value.insights[0].evidence_refs[0].quote = quote_fixture.expected_cross_boundary
        let checked = quote_parse(value, snapshot)
        quote_assert(checked.valid && checked.result.insights[0].evidence_refs[0].quote == quote_fixture.expected_cross_boundary, "accurate legacy quote spanning a choice boundary remains supported")
    } else if step == 7 {
        value.insights[0].evidence_refs[1].quote_id = nil
        value.insights[0].evidence_refs[1].quote = "免费注册需要账号"
        quote_assert(!quote_parse(value, snapshot).valid, "translated quote without a source choice is rejected")
    } else if step == 8 {
        value.insights[0].evidence_refs[1].quote_id = nil
        value.insights[0].evidence_refs[1].quote = "Published source: Emoji 🙂"
        quote_assert(!quote_parse(value, snapshot).valid, "stitched non-contiguous quote without a source choice is rejected")
    } else if step == 9 {
        snapshot.prompt_revision = "tracking-v2.6"
        value.insights[0].evidence_refs[0].quote = quote_fixture.expected_cross_boundary
        value.insights[0].evidence_refs[1].quote = quote_fixture.expected_english
        let checked = quote_parse(value, snapshot)
        quote_assert(checked.valid && checked.result.insights[0].evidence_refs[0].quote == quote_fixture.expected_cross_boundary, "v2.6 history retains exact quote contract and ignores choice hydration")
        value.insights[0].evidence_refs[1].quote = "免费注册需要账号"
        quote_assert(!quote_parse(value, snapshot).valid, "legacy translated quote remains invalid")
    } else if step == 10 {
        value.schema_version = 1
        quote_assert(!quote_parse(value, snapshot).valid, "v2.7 still requires schema 2")
    } else if step == 11 {
        for item in value.items { item.relevance = "unrelated" item.topic_ids = [] }
        quote_assert(!quote_parse(value, snapshot).valid, "authentic quote cannot make unrelated evidence support a topic")
    } else if step == 12 {
        value.insights[0].summary = "can_quote_body=true，paragraphs=[]"
        quote_assert(!quote_parse(value, snapshot).valid, "v2.7 user-prose judgment guard still rejects internal fields")
        value.insights[0].summary = "quote_choices 尚待核实"
        quote_assert(!quote_parse(value, snapshot).valid, "new quote_choices field never leaks into user summary")
        value.insights[0].summary = "固定测试：来源条件仍须核实。"
        value.insights[0].next_step = "核实 quote_id 的结果"
        quote_assert(!quote_parse(value, snapshot).valid, "new quote_id field never leaks into user next-step advice")
    } else if step == 13 {
        snapshot.topics[0].intent_kind = "goal"
        for article in snapshot.evidence { article.summary = "" article.paragraphs = [] }
        value.insights[0].evidence_refs = [] value.insights[0].decision_effect = "none"
        value.outcome = "no_change"
        quote_assert(!quote_parse(value, snapshot).valid, "title-only goal cannot claim evidence-backed no-action")
    } else if step == 14 {
        snapshot.topics[0].intent_kind = "goal"
        for article in snapshot.evidence { article.summary = "" article.paragraphs = [] }
        value.insights[0].evidence_refs = [] value.outcome = "insufficient_evidence"
        quote_assert(quote_parse(value, snapshot).valid, "honest title-only goal remains valid with uncertainty and verification")
    } else {
        value = quote_clone(quote_fixture.schedule_model)
        snapshot = quote_clone(quote_fixture.schedule_snapshot)
        if step == 15 {
            let checked = quote_parse(value, snapshot)
            quote_assert(checked.valid, "schedule impact and reschedule accept authentic source choice")
            if checked.valid {
                quote_assert(checked.result.items[0].schedule_impacts[0].evidence_refs[0].quote == quote_fixture.expected_schedule, "schedule impact hydrates the exact source quote")
                quote_assert(checked.result.insights[0].reschedule.evidence_refs[0].quote == quote_fixture.expected_schedule, "reschedule hydrates the exact source quote")
                quote_assert(checked.result.insights[0].evidence_refs[0].quote == quote_fixture.expected_schedule, "schedule insight also hydrates source quote")
            }
        } else if step == 16 {
            value.items[0].schedule_impacts[0].evidence_refs[0].paragraph_id = "p2"
            quote_assert(!quote_parse(value, snapshot).valid, "schedule impact cannot use a source choice lacking its location")
        } else if step == 17 {
            value.items[0].schedule_impacts[0].evidence_refs[0].paragraph_id = "p3"
            quote_assert(!quote_parse(value, snapshot).valid, "schedule impact cannot use a source choice lacking its event date")
        } else if step == 18 {
            value.insights[0].reschedule.evidence_refs[0].paragraph_id = "p4"
            quote_assert(!quote_parse(value, snapshot).valid, "reschedule rejects source quote lacking the alternative end time")
        } else if step == 19 {
            value.insights[0].reschedule.evidence_refs[0].paragraph_id = "p5"
            quote_assert(!quote_parse(value, snapshot).valid, "reschedule rejects source quote lacking the alternative start time")
        } else if step == 20 {
            value.insights[0].reschedule.evidence_refs[0].quote_id = "q99"
            value.insights[0].reschedule.evidence_refs[0].quote = quote_fixture.expected_schedule
            quote_assert(!quote_parse(value, snapshot).valid, "reschedule unknown ID cannot fall back to model quote")
        } else if step == 21 {
            value.items[0].schedule_impacts[0].evidence_refs[0].quote_id = "q99"
            quote_assert(!quote_parse(value, snapshot).valid, "schedule impact unknown choice ID is rejected")
        } else {
            snapshot.schedules[0].allow_reschedule = false
            quote_assert(!quote_parse(value, snapshot).valid, "source quote never grants reschedule permission")
        }
    }
    mod.gc.run()
}
fn quote_save_case(){
    let snapshot = quote_clone(quote_fixture.snapshot)
    let checked = quote_parse(quote_clone(quote_fixture.model), snapshot)
    if !checked.valid { quote_assert(false, "canonical result available for persistent history") quote_finish() return }
    let run = {task_id: "quote-fixture-run" checked_at: 1 input_key: "fixture" snapshot: snapshot result: checked.result}
    let document = {schema_version: 1 revision: 1 runs: [run]}
    tracking_cache_save(document, || true, fn(error){
        quote_last_error = error
        quote_assert(error == "", "canonical quotes pass real asynchronous history save and readback")
        let saved = fs.read(tracking_cache_file.path).parse_json()
        quote_assert(tracking_cache_run_valid(saved.runs[0]), "saved canonical quote is verified by historical validation without hydration")
        quote_assert(saved.runs[0].result.insights[0].evidence_refs[0].quote == quote_fixture.expected_second, "stored history contains true original text instead of the model paraphrase")
        saved.runs[0].result.insights[0].evidence_refs[0].quote = "伪造的保存引文"
        quote_assert(!tracking_cache_run_valid(saved.runs[0]), "tampered stored quotation fails instead of being silently rehydrated")
        start_timeout(0.03, quote_repair_case)
    })
}
fn quote_repair_case(){
    quote_case_calls = 0
    let snapshot = quote_clone(quote_fixture.snapshot)
    let prompt = tracking_prompt + tracking_prompt_snapshot(snapshot).to_json()
    let error = agent_task_start("tracking_update", snapshot, prompt, || true, fn(reply){
        quote_last_error = reply.error
        if !quote_repeat_bad {
            quote_assert(reply.success && quote_case_calls == 2 && agent_task.repair_count == 1, "unknown choice triggers one bounded repair and publishes corrected true quote")
            if reply.success { quote_assert(reply.result.insights[0].evidence_refs[0].quote == quote_fixture.expected_second, "repair publishes authentic source text") }
            quote_repeat_bad = true
            start_timeout(0.05, quote_repair_case)
        } else {
            quote_assert(!reply.success && quote_case_calls == 2 && agent_task.repair_count == 1, "a second invalid choice ends the task with no extra repair")
            start_timeout(0.2, || {
                quote_assert(quote_model_calls == 4, "two repair scenarios make exactly four mock model calls")
                quote_assert(quote_repair_prompts.len() == 2, "exactly one correction prompt per failed initial response")
                quote_finish()
            })
        }
    })
    quote_last_error = error quote_assert(error == "", "isolated tracking task starts")
}
fn quote_finish(){
    fs.write("report.json", {complete: true checks: quote_checks failures: quote_failures
        model_calls: quote_model_calls real_model_calls: 0 network_calls: 0 account_writes: 0}.to_json())
}
start_timeout(0.1, || {
    quote_fixture = fs.read("fixture.json").parse_json()
    tracking_check_pending = false intent_parse_pending = false
    agent_progress_handler = |stage| {}
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        if name != "octos.turn.start" { start_timeout(0.01, || callback({is_ok: true data: {}})) return }
        quote_case_calls = quote_case_calls + 1 quote_model_calls = quote_model_calls + 1
        if quote_case_calls == 2 { quote_repair_prompts.push(data.text) }
        let value = quote_clone(quote_fixture.model)
        if quote_repeat_bad || quote_case_calls == 1 { value.insights[0].evidence_refs[0].quote_id = "q99" }
        start_timeout(0.01, || callback({is_ok: true data: {text: value.to_json()}}))
    }
    quote_static_step()
})
'''


def main():
    exe = ensure_native_probe()
    work = ROOT / '.test-state/tracking-quote-choices'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    (bundle / 'main.splash').write_text(source + SOURCE, encoding='utf-8')
    data = work / ('data-' + str(time.time_ns()))
    app = data / 'dev.cfaw.runtime-tests'
    app.mkdir(parents=True)
    (data / 'host').mkdir()
    (app / 'fixture.json').write_text(json.dumps(fixtures(), ensure_ascii=False), encoding='utf-8')
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
                    raise RuntimeError('Native probe exited before completing quote checks')
                time.sleep(.1)
            if report is None:
                progress = app / 'progress.json'
                raise RuntimeError('Native quote test timed out; last progress: ' +
                                   (progress.read_text(encoding='utf-8') if progress.is_file() else 'none'))
        finally:
            process.terminate()
            process.wait(timeout=5)
    native_errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    report['native_errors'] = native_errors
    report['fixture_data'] = str(data)
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not report['failures'], report
    assert not native_errors, native_errors
    saved = json.loads((app / 'tracking_results_v1.json').read_text(encoding='utf-8'))
    reference = saved['runs'][0]['result']['insights'][0]['evidence_refs'][0]
    assert reference['quote'] == fixtures()['expected_second'], reference
    assert report['model_calls'] == 4 and report['real_model_calls'] == report['network_calls'] == report['account_writes'] == 0, report
    print('PASS:', len(report['checks']), 'native quote/projection/history/repair checks; four mock model calls; no real model/network/account writes')


if __name__ == '__main__':
    main()
