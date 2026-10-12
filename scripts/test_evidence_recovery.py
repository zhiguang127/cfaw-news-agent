"""Inject a VM instruction bail in isolated body extraction; check fallback."""
import json
import os
from pathlib import Path
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe
exe = ensure_native_probe()

work = ROOT / '.test-state/evidence-recovery'
(work / 'bundle').mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += r'''
start_timeout(0.1, || {
    news_config.request_timeout_seconds = 0.15
    article_url_allowed = fn(url){ true }
    article_http_request = fn(url, redirects, callback){
        start_timeout(0.01, || callback({success: true body: "injected native budget failure"}))
    }
    article_extract = fn(body, url = nil){
        // Deliberately exhaust the native callback, which script try cannot catch.
        let spins = 0 while spins < 30000 { spins = spins + 1 }
        nil
    }
    let row = {news_id: "fixture-evidence-bail" title: "固定测试：正文提取中断"
        summary: "固定来源摘要仍可用" source_url: "https://example.invalid/evidence"
        published_at: nil timestamp_kind: "unknown" evidence_kind: "rss_summary"}
    evidence_enrich([row], || true, || {
        let article = analysis_article_find(row)
        fs.write("recovery.json", {complete: true recovered: article != nil && article.paragraphs.len() == 0 && regex("超时").test(article.error)}.to_json())
    })
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
        report_path = data / 'dev.cfaw.runtime-tests/recovery.json'
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding='utf-8'))
                if report.get('complete'): break
            time.sleep(.1)
        else: raise RuntimeError('Body extraction did not recover')
    finally:
        process.terminate()
        process.wait(timeout=5)
errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
assert len(errors) == 1 and 'script instruction limit exceeded' in errors[0], errors
assert report['recovered'], report
(work / 'report.json').write_text(json.dumps(dict(report, expected_native_bails=len(errors)), indent=2), encoding='utf-8')
print('PASS: injected native extraction bail fell back to the source summary and completed; one expected budget diagnostic, no model or network calls')
