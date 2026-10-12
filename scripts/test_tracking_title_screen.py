"""Native title screening and subsequent body enrichment, with isolated data."""
import json
import os
from pathlib import Path
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe

SOURCE = r'''
let title_checks = [] let title_failures = [] let title_requests = [] let title_case = 0
let title_cases = nil let title_rows = [] let title_targets = nil
tracking_ui_update = fn(){}
fn title_assert(value, label){ if value { title_checks.push(label) } else { title_failures.push(label) } }
fn title_finish(){
    fs.write("report.json", {complete: true checks: title_checks failures: title_failures
        real_model_calls: 0 network_calls: 0 account_writes: 0}.to_json())
}
fn title_enrich(candidates){
    let selected = evidence_select(candidates.rows, title_targets, false)
    title_assert(selected.len() == 2, "news-awareness topics select content, not only goal topics")
    title_assert(selected[0].summary == "", "missing-summary candidate receives first body request")
    article_http_request = fn(url, redirects, callback){
        title_requests.push(url)
        start_timeout(0.01, || callback({success: true body: "<article><p>隔离来源正文：漫步者新品已披露使用条件，具体价格仍需核实。</p></article>"}))
    }
    evidence_enrich(selected, || true, || {
        title_assert(title_requests.len() == 2, "bounded requests read only title-screened candidates")
        for url in title_requests { title_assert(regex("title-pass").test(url), "unrelated headline never triggers a body request") }
        let snapshot = tracking_snapshot(candidates.rows, title_targets)
        evidence_attach(snapshot, candidates.rows)
        for e in snapshot.evidence {
            title_assert(e.paragraphs.len() > 0, "real extraction attaches body before subsequent model input")
            title_assert(e.summary == tracking_find(candidates.rows, "news_id", e.news_id).summary, "source summary remains intact after body enrichment")
        }
        let payload = tracking_prompt_snapshot(snapshot)
        title_assert(payload.evidence.len() == 2 && payload.evidence[0].paragraphs.len() > 0, "subsequent analysis receives screened news and extracted body")
        title_assert(regex("Title-first workflow").test(tracking_prompt), "analysis prompt verifies relevance before situation and next steps")
        title_finish()
    })
}
fn title_next(){
    if title_case >= title_cases.len() { return }
    let input = title_cases[title_case]
    title_rows = [] title_targets = {topics: input.topics schedules: [] legacy_interests: [] omitted_targets: 0}
    for i value in input.rows {
        let row = news_normalize({title: value.title link: "https://www.ithome.com/title-" + value.id}, news_source("ithome"), time_now())
        row.summary = value.summary row.news_id = value.id title_rows.push(row)
    }
    bm25_recall(title_rows, title_targets, || true, fn(candidates){
        let ids = [] for row in candidates.rows { ids.push(row.news_id) }
        title_assert(ids.len() == input.expected.len(), input.name + ": only expected headline candidates remain")
        for id in input.expected { title_assert(record_contains(ids, id), input.name + ": expected " + id + " is retained") }
        for row in title_rows {
            if !record_contains(input.expected, row.news_id) { title_assert(!record_contains(ids, row.news_id), input.name + ": rejected " + row.news_id + " is excluded") }
        }
        title_assert(candidates.title_rejected == input.rows.len() - input.expected.len(), input.name + ": title rejection count is explicit")
        title_case = title_case + 1
        if title_case < title_cases.len() { start_timeout(0.01, title_next) }
        else {
            // Actual content path on the final brand case, with real extraction.
            for row in candidates.rows { row.source_url = "https://www.ithome.com/title-pass-" + row.news_id }
            title_enrich(candidates)
        }
    })
}
start_timeout(0.1, || { title_cases = fs.read("cases.json").parse_json() start_timeout(0.01, title_next) })
'''


def topic(title, *keywords, scope=None):
    return dict(title=title, purpose='', scope=scope or ['新品及公司动态'],
                preferences=[], intent_kind='news', recall_rules=[
                    *[dict(kind='keyword', value=k) for k in keywords],
                    dict(kind='category', value='tech'), dict(kind='source', value='IT之家')],
                topic_id='title-fixture', version=1, status='active',
                original_input=title, supplement='', created_at=1, updated_at=1)


def row(id, title, summary=''):
    return dict(id=id, title=title, summary=summary)


def main():
    brand = topic('漫步者新品与产品动向跟踪', '漫步者', '新品', '耳机',
                  scope=['新品产品音频功能耳机发布兼容设备性能测试'])
    goal = topic('整理会议记录与演示文稿', 'AI', '会议纪要', '演示文稿', 'PPT')
    goal['intent_kind'] = 'goal'
    cases = [
        dict(name='named brand', topics=[brand], rows=[
            row('brand', '漫步者 Lolli Spark 通过认证'),
            row('motor', '张雪机车宣布拿下国内品牌销量第一', '摘要偶然提及漫步者新品'),
            row('generic', '新品产品音频功能耳机发布兼容设备性能测试'),
            row('other', '其他公司推出新耳机'),
            row('summary', '个人数字生活一周回顾', '本周漫步者耳机发布')], expected=['brand']),
        dict(name='company', topics=[topic('小米公司动向关注', '小米', '产品', '手机')], rows=[
            row('xiaomi', '小米公布公司季度业务情况'),
            row('apple', '苹果发布新手机', '与小米手机对比'),
            row('finance', '国内公司新品发布及融资消息')], expected=['xiaomi']),
        dict(name='practical tasks', topics=[topic('AI会议记录与演示文稿', 'AI', '会议记录', '演示文稿')], rows=[
            row('meeting', 'AI会议记录工具开放转写功能'),
            row('slides', '演示文稿生成功能上线'),
            row('funding', 'AI公司获得融资', '用于会议记录和演示文稿'),
            row('benchmark', 'AI模型刷新跑分')], expected=['meeting', 'slides']),
        dict(name='broad AI intentionally selected', topics=[topic('AI动态', 'AI')], rows=[
            row('ai', 'AI助手开放功能'), row('daily', 'Daily 新闻'), row('airpods', 'AirPods 新品')], expected=['ai']),
        dict(name='goal task aliases', topics=[goal], rows=[
            row('notes', '会议纪要工具开放转写'), row('ppt', 'PPT 生成功能上线'),
            row('slides2', '演示文稿生成新功能'), row('funding2', 'AI融资新消息')], expected=['notes', 'ppt', 'slides2']),
        dict(name='multiple topics', topics=[brand, topic('小米公司动态', '小米', '产品')], rows=[
            row('edifier', '漫步者公布新品'), row('xiaomi2', '小米季度报告'),
            row('motor2', '张雪机车销量上涨')], expected=['edifier', 'xiaomi2']),
        dict(name='category alone', topics=[topic('科技资讯', scope=['科技'])], rows=[
            row('motor3', '张雪机车销量上涨'), row('generic2', '新品发布')], expected=[]),
        dict(name='body after screening', topics=[brand], rows=[
            row('good-a', '漫步者新品公布访问条件', '来源摘要：新品条件需要核实'),
            row('good-b', '漫步者发布新耳机'),
            row('motor4', '张雪机车销量第一', '漫步者也有新品')], expected=['good-a', 'good-b']),
    ]
    work = ROOT / '.test-state/tracking-title-screen'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    (bundle / 'main.splash').write_text(source + SOURCE, encoding='utf-8')
    data = work / ('data-' + str(time.time_ns()))
    app = data / 'dev.cfaw.runtime-tests'
    app.mkdir(parents=True)
    (data / 'host').mkdir()
    (app / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
    exe = ensure_native_probe()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    report = None
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data), '--size', '430x860'],
            cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')),
            stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if (app / 'report.json').is_file():
                    report = json.loads((app / 'report.json').read_text(encoding='utf-8'))
                    break
                time.sleep(.1)
        finally:
            process.terminate()
            process.wait(timeout=5)
    errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    if report is None:
        raise RuntimeError('No title screen report: ' + '\n'.join(errors))
    report['native_errors'] = errors
    report['cases'] = len(cases)
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not report['failures'] and not errors, report
    print('PASS:', len(report['checks']), 'native title/content checks; no real model/network/account writes')


if __name__ == '__main__':
    main()
