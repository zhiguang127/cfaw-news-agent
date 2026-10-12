"""Native refresh deadlines, retry and rejection of old parser completions."""
import json
import os
from pathlib import Path
import subprocess
import time
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe


def main():
    work = ROOT / '.test-state/news-refresh-recovery'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += r'''
let recovery_checks = [] let recovery_failures = [] let recovery_done = 0
let recovery_updates = 0 let recovery_late = nil let recovery_rows = nil let recovery_status = nil
let recovery_parser = reading_feed_parse_async
fn recovery_assert(value, name){
    if value { recovery_checks.push(name) } else { recovery_failures.push(name) }
}
fn recovery_report(){ fs.write("recovery-report.json", {checks: recovery_checks failures: recovery_failures timeout_status: recovery_status}.to_json()) }
let recovery_xml = "<rss><channel><item><title>Synthetic recovery fixture</title><link>https://www.ithome.com/recovery-fixture</link><description>Fixture body</description></item></channel></rss>"
fn recovery_request(url, redirects, complete){ complete({success: true body: recovery_xml}) }
fn recovery_retry(){
    recovery_status = feed_status_by_source["sspai"].to_json().parse_json()
    recovery_assert(recovery_done == 1 && feed_task.done && feed_task.completed == 2, "lost parser continuation ends the refresh")
    recovery_assert(recovery_updates == 2 && feed_task.successes == 1, "healthy and timed-out sources each announce exactly once")
    recovery_assert(feed_status_by_source["sspai"].state == "error" && regex("超时").test(feed_status_by_source["sspai"].error), "parser timeout keeps an actionable source error")
    recovery_assert(feed_rows_by_source["sspai"] == recovery_rows && feed_rows_by_source["sspai"].len() == 1, "timeout preserves existing source rows")
    reading_feed_parse_async = recovery_parser
    news_config.source_timeout_seconds = 3
    feed_refresh(["ithome"], || { recovery_updates = recovery_updates + 1 }, fn(successes){
        recovery_done = recovery_done + 1
        recovery_assert(successes == 1 && feed_task.completed == 1, "retry completes with new public-format fixture data")
        recovery_assert(recovery_updates == 3 && recovery_done == 2, "late old completion never re-announces or finishes the newer generation")
        recovery_report()
    }, recovery_request)
    recovery_late([])
}
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    news_config.source_timeout_seconds = 0.3
    recovery_rows = news_parse(recovery_xml, news_source("sspai"), time_now())
    feed_rows_by_source["sspai"] = recovery_rows
    feed_status_by_source["sspai"] = {state: "cached" retrieved_at: time_now() error: "" count: 1}
    reading_feed_parse_async = fn(body, source, retrieved_at, generation, complete){
        if source.id == "sspai" { recovery_late = complete return }
        recovery_parser(body, source, retrieved_at, generation, complete)
    }
    feed_refresh(["ithome" "sspai"], || { recovery_updates = recovery_updates + 1 }, fn(successes){
        recovery_done = recovery_done + 1
        start_timeout(0.1, || recovery_retry())
    }, recovery_request)
    start_timeout(6, || { if recovery_done < 2 { recovery_assert(false, "fixture deadline") recovery_report() } })
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    data = work / ('data-' + str(time.time_ns()))
    (data / 'host').mkdir(parents=True)
    executable = ensure_native_probe()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    report_path = data / 'dev.cfaw.runtime-tests/recovery-report.json'
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data)],
            cwd=executable.parent, env=dict(os.environ, RINX_DATA_DIR=str(data/'host')),
            stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 15
            while not report_path.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.1)
            report = json.loads(report_path.read_text(encoding='utf-8'))
        finally:
            process.terminate()
            process.wait(timeout=5)
    errors = [line for line in (work/'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    (work/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not errors, errors
    assert not report['failures'], report
    print('PASS:', len(report['checks']), 'native recovery checks; synthetic RSS, no model or network calls')


if __name__ == '__main__':
    main()
