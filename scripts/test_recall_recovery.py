"""Verify exact token counts and recall continuation after a native VM bail."""
import json
import os
from pathlib import Path
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe
exe = ensure_native_probe()

work = ROOT / '.test-state/recall-recovery'
(work / 'bundle').mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += r'''
let recall_bail_once = true let recall_current_bail_once = true let recall_observed = nil let recall_progress_seen = false
fn recall_current(){
    if recall_current_bail_once {
        recall_current_bail_once = false
        let spins = 0 while spins < 30000 { spins = spins + 1 }
    }
    true
}
let recall_prefix = bm25_prefix
bm25_prefix = fn(value, limit){
    if recall_bail_once {
        recall_bail_once = false
        let spins = 0 while spins < 30000 { spins = spins + 1 }
    }
    recall_prefix(value, limit)
}
let recall_rank = bm25_rank_step
bm25_rank_step = fn(work){
    if recall_observed == nil {
        let terms = [] for term in work.terms { terms.push({value: bm25_word_key(term.value) df: term.df}) }
        let docs = [] for doc in work.docs { docs.push({id: doc.row.news_id counts: doc.counts}) }
        recall_observed = {terms: terms docs: docs}
    }
    recall_rank(work)
}
start_timeout(0.1, || {
    let rows = []
    for input in [{id: "first" title: "固定测试 AI AI AI paid" summary: "人人人 a1AI"}
        {id: "second" title: "固定测试 Ai paid AI" summary: "人 a1"}] {
        let row = news_normalize({title: input.title link: "https://www.ithome.com/recall-fixture-" + input.id}, news_source("ithome"), time_now())
        row.news_id = input.id row.summary = input.summary rows.push(row)
    }
    bm25_recall(rows, {topics: [] schedules: [] legacy_interests: [{kind: "keyword" value: "AI 人人 人 a1"}]}, recall_current, fn(result){
        let report = {complete: false matched: result.matched count: result.rows.len()
            progress_seen: recall_progress_seen observed: recall_observed}
        let products = []
        for i in 24 {
            let row = news_normalize({title: "新品产品音频功能耳机发布兼容设备性能测试 " + i link: "https://www.ithome.com/generic-" + i}, news_source("ithome"), time_now())
            products.push(row)
        }
        products.push(news_normalize({title: "漫步者 Lolli Spark 通过 OpenHarmony 认证" link: "https://www.ithome.com/brand-fixture"}, news_source("ithome"), time_now()))
        bm25_recall(products, {topics: [{recall_rules: [{kind: "keyword" value: "漫步者"} {kind: "category" value: "tech"}]
            scope: ["新品产品音频功能耳机发布兼容设备性能测试"]}] schedules: [] legacy_interests: []}, || true, fn(ranked){
            report.complete = true report.product_first = ranked.rows[0].title report.product_count = ranked.rows.len()
            fs.write("recovery.json", report.to_json())
        })
    }, fn(progress){ if progress.scanned == 2 { recall_progress_seen = true } })
})
'''
(work / 'bundle/main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
(data / 'host').mkdir(parents=True)
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(exe), '--bundle', str(work / 'bundle'), '--app-data', str(data), '--size', '430x860'], cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
    try:
        path = data / 'dev.cfaw.runtime-tests/recovery.json'
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if path.is_file():
                report = json.loads(path.read_text(encoding='utf-8'))
                if report.get('complete'): break
            time.sleep(.1)
        else: raise RuntimeError('Interrupted recall did not resume')
    finally:
        process.terminate()
        process.wait(timeout=5)
errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
assert len(errors) == 2 and all('script instruction limit exceeded' in line for line in errors), errors
assert report['matched'] == report['count'] == 2 and report['progress_seen'], report
terms = report['observed']['terms']
docs = {d['id']: dict(zip([t['value'] for t in terms], d['counts'])) for d in report['observed']['docs']}
assert docs['first'] == {'ai': 3, '人人': 2, '人': 3, 'a1': 0}, docs
assert docs['second'] == {'ai': 2, '人人': 0, '人': 1, 'a1': 1}, docs
assert {t['value']: t['df'] for t in terms} == {'ai': 2, '人人': 1, '人': 2, 'a1': 1}, terms
assert report['product_first'] == '漫步者 Lolli Spark 通过 OpenHarmony 认证', report
assert report['product_count'] <= 8, report
report['expected_native_bails'] = len(errors)
(work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS: native recall interruption resumes; exact Latin word boundaries, case folding, overlapping Han bigrams, singleton counts and DF verified')
