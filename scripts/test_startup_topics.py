"""Production startup regression with large persisted tracking history.

The entire production ORDER (including startup.splash) runs unchanged. Only
public HTTP and model service boundaries are mocked, in fresh isolated storage.
Optional --profile reads existing files once into an isolated copy and omits
private text from reports. The original profile is never written; no real
model or remote news endpoint is used.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from assemble import ORDER, ROOT, assemble
from native_probe import ensure_native_probe


WORK = ROOT / '.test-state/newstartup'
CASES = ('valid', 'cache-backup', 'cache-rejected', 'topics-backup', 'topics-rejected', 'empty', 'budget-once', 'budget-permanent')
TITLE = '隔离启动回归：小米产品发布'
SCRIPT = r'''
let startup_fixture_requests = [] let startup_fixture_models = 0
let startup_fixture_boot_status = boot_status
let startup_fixture_run_valid = tracking_cache_run_valid
let startup_fixture_validated = 0
let startup_fixture_validation_failures = 0
let startup_fixture_validation_passes = 0
let startup_fixture_readonly_probe = ""
boot_status = fn(phase){
    fs.write("startup-phase.json", {phase: phase time: time_now()}.to_json())
    startup_fixture_boot_status(phase)
}
tracking_cache_run_valid = fn(run){
    startup_fixture_validated = startup_fixture_validated + 1
    let valid = startup_fixture_run_valid(run)
    if !valid { startup_fixture_validation_failures = startup_fixture_validation_failures + 1 }
    else { startup_fixture_validation_passes = startup_fixture_validation_passes + 1 }
    valid
}
news_http_request = fn(url, redirects, callback){
    startup_fixture_requests.push(url)
    if regex("ithome[.]com/rss").test(url) {
        let rss = "<rss><channel><title>隔离启动回归来源</title><item><title>隔离启动回归：小米产品发布</title><link>https://www.ithome.com/startup-fixture-news</link><description>隔离固定来源摘要：新产品的价格仍需核实。</description></item></channel></rss>"
        start_timeout(0.01, || callback({success: true body: rss}))
    } else {
        start_timeout(0.01, || callback({success: false error: "隔离启动回归：不访问远端" category: "network"}))
    }
}
article_http_request = fn(url, redirects, callback){
    startup_fixture_requests.push(url)
    start_timeout(0.01, || callback({success: false error: "隔离启动回归禁止正文联网" category: "network"}))
}
analysis_host_has = fn(name){ false }
analysis_host_request = fn(name, input, callback){
    startup_fixture_models = startup_fixture_models + 1
    start_timeout(0.01, || callback({is_ok: false error: "隔离启动回归没有模型服务"}))
}
// Images are a second outbound boundary. Do not let cache thumbnails issue
// requests outside the news HTTP adapter in this deliberately offline test.
news_thumbnail_allowed = fn(row){ false }
start_interval(0.2, || {
    fs.write("startup-state.json", {boot_finished: boot_finished boot_phase: boot_phase
        page: page news_count: app_feed_rows.len() first_news: if app_feed_rows.len() > 0 {app_feed_rows[0].title} else {""}
        topics: topic_records.topics.len() draft: topic_records.draft
        decisions: topic_records.decisions.len() runs: tracking_cache.runs.len()
        topic_warning: topic_warning topic_writable: topic_file.writable topic_recovered: topic_file.recovered
        cache_writable: tracking_cache_file.writable cache_recovered: tracking_cache_file.recovered
        cache_revision: tracking_cache.revision topic_revision: topic_records.revision
        validated_runs: startup_fixture_validated rejected_runs: startup_fixture_validation_failures
        validation_passes: startup_fixture_validation_passes
        readonly_probe: startup_fixture_readonly_probe
        mock_requests: startup_fixture_requests model_calls: startup_fixture_models}.to_json())
})
'''


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def topic(ident='startup-fixture', status='active'):
    return dict(topic_id=ident, version=1, title='隔离启动回归：产品动态',
                purpose='了解发布事实和使用条件', scope=['小米产品动态'],
                preferences=['先核实再决定'], recall_rules=[dict(kind='keyword', value='小米')],
                original_input='隔离启动回归：关注小米动态', supplement='',
                created_at=1, updated_at=1, status=status, intent_kind='news')


def documents():
    now = time.time()
    target = topic()
    preset = topic('preset-agent-development-v1', 'paused')
    preset['demo_preset'] = True
    draft = dict(draft_id='preserved-startup-draft', version=1, target_topic_id=target['topic_id'],
                 target_version=1, original_input='尚未保存的修改', supplement='',
                 understanding=copy.deepcopy(target), understanding_edit=None,
                 state='ready', question='', origin_reminder_id=None, intent_kind='news',
                 schedule_understanding=None, schedule_timezone='Asia/Shanghai')
    decisions = [dict(kind='insight', target_type='topic', target_id=target['topic_id'],
                      target_version=1, issue_key='fixture-update', state='watch',
                      evidence_facts=[], decided_at=1)]
    topics = dict(schema_version=2, revision=9, topics=[target, preset], draft=draft, decisions=decisions)
    rows, evidence, items = [], [], []
    long_summary = ('隔离来源摘要：小米新品发布，账号和设备使用条件需核实。' * 45)[:1200]
    paragraph = '隔离来源原文：小米产品已发布，售价和上市日期需核实。' + '固定来源正文中的产品使用条件仍待确认。' * 100
    refs = []
    for i in range(8):
        url = 'https://www.ithome.com/startup-fixture-' + str(i)
        source_ref = dict(source='隔离固定来源', source_id='ithome', source_url=url, feed_url='https://www.ithome.com/rss')
        rows.append(dict(news_id=url, evidence_id=url, content_version='isolated-startup-fixture', title=TITLE if i == 0 else '隔离启动回归：小米动态 ' + str(i),
                         summary=long_summary, source='隔离固定来源', source_id='ithome',
                         source_url=url, feed_url=source_ref['feed_url'], category='tech', language='zh',
                         image_url=None, published_at=None, retrieved_at=now, evidence_kind='rss_summary',
                         timestamp_kind='published', references=[source_ref],
                         body_html='<p>隔离来源正文：小米产品发布，条件需核实。</p>',
                         source_summary=long_summary, body_origin='publisher_rss', body_truncated=False))
        evidence.append(dict(news_id=url, title=rows[-1]['title'], summary=long_summary,
                             source_url=url, published_at=None, retrieved_at=now,
                             timestamp_kind='published', evidence_kind='body_excerpt',
                             content_key='isolated-fixture-'+str(i), references=[source_ref], summary_truncated=False,
                             paragraphs=[dict(paragraph_id='p1', text=paragraph)],
                             body_truncated=False, body_error=''))
        items.append(dict(news_id=url, relevance='related', topic_ids=[target['topic_id']],
                          legacy_interest_ids=[], why_related='隔离固定来源涉及小米产品。',
                          evidence_ids=[url], uncertainties=[], schedule_impacts=[]))
        refs.append(dict(news_id=url, paragraph_id='p1', quote='隔离来源原文：小米产品已发布，售价和上市日期需核实。'))
    snapshot = dict(schema_version=1, topics=[target], schedules=[], legacy_interests=[],
                    evidence=evidence, previous_result=None, previous_by_target=[], decisions=decisions,
                    omitted_targets=0, omitted_candidates=0, omitted_decisions=0,
                    context_key='isolated-startup-fixture', prompt_revision='tracking-v2.7')
    insight = dict(target_type='topic', target_id=target['topic_id'], target_version=1,
                   issue_key='fixture-update', change_kind='new',
                   summary='隔离固定判断：报道披露了产品发布，上市日期与售价仍待核实。',
                   decision_effect='unknown', next_step='核实正式上市日期和售价。',
                   material_change='', uncertainties=['正式上市日期与售价待核实'],
                   evidence_ids=[r['news_id'] for r in rows], evidence_refs=refs,
                   compared_run_id=None, reschedule=None)
    result = dict(schema_version=2, outcome='update', explanation='隔离固定判断只采用提供的证据。',
                  items=items, insights=[insight])
    runs = [dict(task_id='startup-old-' + str(i), checked_at=now-i, input_key='startup-key-'+str(i),
                 snapshot=copy.deepcopy(snapshot), result=copy.deepcopy(result)) for i in range(12)]
    cache = dict(schema_version=1, revision=12, runs=runs)
    schedule = dict(schedule_id='preset-shanghai-trip-v1', version=1, demo_preset=True,
                    title='隔离行程记录', content='原有记录保留', location='上海', news_keywords=['上海'],
                    time_precision='day', start='2026-10-25T00:00:00+08:00', end='2026-10-26T00:00:00+08:00',
                    timezone='Asia/Shanghai', status='cancelled', allow_reschedule=False)
    return topics, cache, rows, schedule


def prepare(app, case):
    topics, cache, rows, schedule = documents()
    write(app / 'agent_preferences_v1.json', dict(schema_version=1, revision=0, paused=True,
          important_only=False, interval_seconds=900, orb_x=1, orb_y=.86))
    write(app / 'interests_v1.json', dict(schema_version=1, reading_sources_revision=3, items=[], enabled_source_ids=['ithome']))
    if case != 'empty':
        write(app / 'topics_v2.json', topics)
        write(app / 'tracking_results_v1.json', cache)
        write(app / 'schedules_v1.json', dict(schema_version=1, items=[schedule]))
        write(app / 'news_cache_v1_ithome.json', dict(schema_version=1, source_id='ithome', retrieved_at=time.time(), items=rows))
    if case.startswith('cache-'):
        tampered = copy.deepcopy(cache)
        tampered['runs'][7]['result']['insights'][0]['evidence_refs'][0]['quote'] = '伪造的引用'
        write(app / 'tracking_results_v1.json', tampered)
        backup = cache if case == 'cache-backup' else tampered
        write(app / 'tracking_results_v1.json.backup', backup)
    if case.startswith('topics-'):
        (app / 'topics_v2.json').write_text('{broken JSON', encoding='utf-8')
        if case == 'topics-backup':
            write(app / 'topics_v2.json.backup', topics)
    return {p.name: p.read_bytes() for p in app.iterdir() if p.is_file()}


def probe_get(port, route, **params):
    with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as response:
        return response.read()


def run_case(source, case, baseline=False, profile=None):
    work = WORK / (('baseline-' if baseline else '') + case)
    bundle = work / 'bundle'
    data = work / ('data-' + str(time.time_ns()))
    app = data / 'dev.cfaw.runtime-tests'
    bundle.mkdir(parents=True, exist_ok=True)
    app.mkdir(parents=True)
    (data / 'host').mkdir()
    fixture_script = SCRIPT
    if case in ('budget-once', 'budget-permanent'):
        fault = 'startup_fixture_faulted' if case == 'budget-once' else 'false'
        fixture_script = fixture_script.replace('let startup_fixture_readonly_probe = ""', 'let startup_fixture_readonly_probe = ""\nlet startup_fixture_faulted = false')
        fixture_script = fixture_script.replace('let valid = startup_fixture_run_valid(run)', f'''if !{fault} {{
        startup_fixture_faulted = true
        let spins = 0 while spins < 30000 {{ spins = spins + 1 }}
    }}
    let valid = startup_fixture_run_valid(run)''')
    if case in ('cache-rejected', 'topics-rejected', 'budget-permanent'):
        file = 'topic_file' if case == 'topics-rejected' else 'tracking_cache_file'
        document = '{schema_version: 2 revision: 0 topics: [] draft: nil decisions: []}' if case == 'topics-rejected' else '{schema_version: 1 revision: 0 runs: []}'
        validator = 'topic_document_valid' if case == 'topics-rejected' else 'tracking_cache_valid'
        fixture_script += f'''
start_interval(0.2, || {{
    if boot_finished && startup_fixture_readonly_probe == "" {{
        startup_fixture_readonly_probe = tracking_store_write({file}, {document}, {validator})
    }}
}})
'''
    if profile:
        # Copy bytes into a new test app. The source account is never opened for
        # writing; private text is omitted from monitor output and reports.
        for path in profile.glob('*.json*'):
            (app / path.name).write_bytes(path.read_bytes())
        original = {p.name: p.read_bytes() for p in app.iterdir() if p.is_file()}
        fixture_script = fixture_script.replace('if regex("ithome[.]com/rss").test(url) {', 'if false {')
        fixture_script = fixture_script.replace('draft: topic_records.draft', 'draft: nil has_draft: topic_records.draft != nil')
        fixture_script = fixture_script.replace('first_news: if app_feed_rows.len() > 0 {app_feed_rows[0].title} else {""}', 'first_news: "redacted"')
        fixture_script += r'''
let startup_fixture_preferences_load = agent_preferences_load
agent_preferences_load = fn(){ startup_fixture_preferences_load() agent_preferences.paused = true }
'''
    else:
        original = prepare(app, case)
    (bundle / 'main.splash').write_text(source + '\n' + fixture_script, encoding='utf-8')
    executable = ensure_native_probe()
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
    state, labels, elapsed = None, [], 0
    before = time.monotonic()
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data),
                  '--remote=' + str(port), '--size', '430x860'], cwd=executable.parent,
                  env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + (19 if baseline else 35)
            ready_at = None
            while time.monotonic() < deadline:
                try:
                    state = json.loads((app / 'startup-state.json').read_text(encoding='utf-8'))
                    if state['boot_finished'] and state['news_count'] > 0:
                        if ready_at is None: ready_at = time.monotonic()
                        if time.monotonic() - ready_at > .7: break
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                if process.poll() is not None: break
                time.sleep(.12)
            elapsed = time.monotonic() - before
            try:
                widgets = json.loads(probe_get(port, '/snap'))['s']
                labels = [w.get('t', '') for w in widgets]
                if not profile:
                    (work / 'widgets.json').write_text(json.dumps(widgets, ensure_ascii=False, indent=2), encoding='utf-8')
                    (work / 'screenshot.png').write_bytes(probe_get(port, '/g'))
            except (OSError, ValueError):
                pass
        finally:
            process.terminate(); process.wait(timeout=5)
    errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    preserved = [name for name, content in original.items() if (app / name).read_bytes() == content]
    changed = [name for name in original if name not in preserved]
    checks = []
    failures = []
    def check(value, label):
        (checks if value else failures).append(label)
    if not baseline:
        check(state is not None and state['boot_finished'], 'production boot completes: ' + case)
        check(state is not None and state['news_count'] > 0, 'production cache or refresh supplies news: ' + case)
        check(any(TITLE in text for text in labels) if not profile else any('条新闻' in text for text in labels), 'actual home widgets display news: ' + case)
        if case in ('budget-once', 'budget-permanent'):
            check(len(errors) > 0 and all('script instruction limit exceeded' in line for line in errors), 'injected budget interruption is the only native error: ' + case)
        else:
            check(not errors, 'native callback budgets and script execution succeed: ' + case)
        protected_changed = [name for name in changed if name not in ('tracking_state_v1.json', 'tracking_state_v1.json.backup')]
        check(not protected_changed, 'existing user documents and source caches retain identical bytes: ' + case)
        check(state is not None and state['model_calls'] == 0, 'startup uses no model service: ' + case)
        if state and profile:
            original_topics = json.loads(original['topics_v2.json'])
            original_cache = json.loads(original['tracking_results_v1.json'])
            check(state['topics'] == len(original_topics['topics']) and state['decisions'] == len(original_topics['decisions']), 'original topic and decision counts restore: ' + case)
            check(state['runs'] == len(original_cache['runs']), 'all original stored runs are validated and restored: ' + case)
            check(state['validation_passes'] >= len(original_cache['runs']), 'production per-run evidence validator completes for every original run: ' + case)
            check(state['cache_revision'] == original_cache['revision'] and state['topic_revision'] == original_topics['revision'], 'original revisions restore unchanged: ' + case)
            check(state['has_draft'] == (original_topics['draft'] is not None), 'original pending draft presence restores: ' + case)
        elif state and case != 'empty':
            check(state['runs'] == (0 if case in ('cache-rejected', 'budget-permanent') else 12), 'cache adopts all valid runs or rejects unverifiable cache: ' + case)
            if case != 'topics-rejected':
                check(state['topics'] == 2 and state['decisions'] == 1 and state['draft']['draft_id'] == 'preserved-startup-draft', 'topics, draft and user decision restore: ' + case)
            if case.startswith('cache-'):
                check(state['cache_writable'] is False and state['cache_recovered'] == (case == 'cache-backup'), 'tampered primary is read-only and backup recovery is explicit: ' + case)
                check('tracking_results_v1.json' in state['topic_warning'] and ('校验' in state['topic_warning'] or '格式' in state['topic_warning']) and '保留' in state['topic_warning'], 'cache rejection is diagnosed: ' + case)
            if case.startswith('topics-'):
                check(state['topic_writable'] is False and state['topic_recovered'] == (case == 'topics-backup'), 'corrupt topic primary is retained and recovery is explicit: ' + case)
            if case in ('cache-rejected', 'topics-rejected', 'budget-permanent'):
                check('只读' in state['readonly_probe'], 'storage write rejects original readonly document: ' + case)
            if case == 'budget-permanent':
                check(state['cache_writable'] is False and not state['cache_recovered'] and '恢复超时' in state['topic_warning'], 'bounded recovery timeout retains cache readonly and continues home boot: ' + case)
    unexpected_errors = [] if case in ('budget-once', 'budget-permanent') and all('script instruction limit exceeded' in line for line in errors) else errors
    report = dict(case=case, baseline=baseline, passed=not failures if not baseline else None,
                  checks=checks, failures=failures, state=state, native_errors=errors, elapsed_seconds=round(elapsed, 3),
                  unexpected_native_errors=unexpected_errors,
                  preserved=preserved, changed=changed, original_sha256={n:hashlib.sha256(b).hexdigest() for n,b in original.items()},
                  fixture_app_data=str(data), real_model_calls=0, real_network_calls=0, account_writes=0,
                  production_order=ORDER, source_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest())
    write(work / 'report.json', report)
    print(json.dumps(dict(case=case, baseline=baseline, passed=report['passed'], checks=len(checks), failures=failures,
          phase=state['boot_phase'] if state else None, news=state['news_count'] if state else None,
          elapsed_seconds=report['elapsed_seconds'], native_error_count=len(errors), unexpected_native_error_count=len(unexpected_errors)), ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--profile', type=Path, help='Read-only source profile copied into isolated storage; omit private text from reports')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    source = (WORK / 'baseline-main.splash').read_text(encoding='utf-8') if args.baseline else assemble(paths=ORDER)[0]
    reports = [run_case(source, case, args.baseline, args.profile) for case in (['actual-copy'] if args.profile else ([args.case] if args.case else (['valid'] if args.baseline else CASES)))]
    combined = dict(passed=all(r['passed'] for r in reports) if not args.baseline else None,
                    checks=sum((r['checks'] for r in reports), []), failures=sum((r['failures'] for r in reports), []),
                    native_errors=sum((r['native_errors'] for r in reports), []), cases=reports,
                    real_model_calls=0, real_network_calls=0, account_writes=0)
    target = 'baseline-report.json' if args.baseline else ('actual-copy-report.json' if args.profile else 'report.json')
    write(WORK / target, combined)
    if args.profile and not args.baseline and (WORK / 'report.json').is_file():
        matrix = json.loads((WORK / 'report.json').read_text(encoding='utf-8'))
        previous = [r for r in matrix['cases'] if r['case'] != 'actual-copy']
        # Append the private-copy checks only to a matrix of the identical
        # production source. Never silently mix checks from different builds.
        if previous and all(r['source_sha256'] == reports[0]['source_sha256'] for r in previous):
            all_reports = previous + reports
            write(WORK / 'report.json', dict(passed=all(r['passed'] for r in all_reports),
                  checks=sum((r['checks'] for r in all_reports), []), failures=sum((r['failures'] for r in all_reports), []),
                  native_errors=sum((r['native_errors'] for r in all_reports), []), cases=all_reports,
                  real_model_calls=0, real_network_calls=0, account_writes=0))
    if not args.baseline:
        assert combined['passed'], combined['failures'] + combined['native_errors']
        print('PASS:', len(combined['checks']), 'production startup checks; no real model/network/account writes')


if __name__ == '__main__':
    main()
