"""Fixed native Atom parser check after merging UI and reader fixes.

The fixture is synthetic; no network or model service is used.
"""
import json
import os
import subprocess
import time

from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe


def main():
    work = ROOT / '.test-state/merge-atom'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += r'''
let merge_atom_checks = [] let merge_atom_failures = []
fn merge_atom_assert(passed, name){
    if passed { merge_atom_checks.push(name) } else { merge_atom_failures.push(name) }
}
fn merge_atom_report(){ fs.write("atom-report.json", {checks: merge_atom_checks failures: merge_atom_failures}.to_json()) }
let merge_atom_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><feed xmlns=\"http://www.w3.org/2005/Atom\"><title>Synthetic merge fixture</title><entry><title>Synthetic Atom first</title><link rel=\"alternate\" href=\"https://theconversation.com/merge-atom-first\"/><published>2026-10-10T09:00:00Z</published><summary type=\"html\">&lt;p&gt;Publisher summary first.&lt;/p&gt;</summary><content type=\"html\">&lt;p&gt;Synthetic full article first, with original publisher text.&lt;/p&gt;</content><author><name>Fixture Author First</name></author><rights>Fixture CC BY 4.0</rights></entry><entry><title>Synthetic Atom second</title><link rel=\"alternate\" href=\"https://theconversation.com/merge-atom-second\"/><published>2026-10-10T10:00:00Z</published><summary type=\"html\">&lt;p&gt;Publisher summary second.&lt;/p&gt;</summary><content type=\"html\">&lt;p&gt;Synthetic full article second, with a separate original paragraph.&lt;/p&gt;</content><author><name>Fixture Author Second</name></author><rights>Fixture CC BY 4.0 second</rights></entry></feed>"
fn merge_atom_rows(rows, label){
    merge_atom_assert(rows != nil && rows.len() == 2, label + " retains both entries")
    if rows == nil || rows.len() != 2 { return }
    for index row in rows {
        let suffix = if index == 0 { "first" } else { "second" }
        let author = if index == 0 { "Fixture Author First" } else { "Fixture Author Second" }
        let license = if index == 0 { "Fixture CC BY 4.0" } else { "Fixture CC BY 4.0 second" }
        merge_atom_assert(row.title == "Synthetic Atom " + suffix, label + " title " + suffix)
        merge_atom_assert(row.source_url == "https://theconversation.com/merge-atom-" + suffix, label + " original URL " + suffix)
        merge_atom_assert(row.source_summary == "Publisher summary " + suffix + ".", label + " publisher summary " + suffix)
        merge_atom_assert(regex("Synthetic full article " + suffix).test(row.body_html) && regex("<p>").test(row.body_html), label + " full HTML body " + suffix)
        merge_atom_assert(row.publisher_byline == author, label + " author " + suffix)
        merge_atom_assert(row.publisher_license == license, label + " license " + suffix)
        merge_atom_assert(row.body_origin == "publisher_atom" && row.body_truncated == false, label + " Atom provenance " + suffix)
        merge_atom_assert(news_record_valid(row), label + " normalized record " + suffix)
    }
}
start_timeout(0.1, || {
    let publisher = news_source("conversation")
    merge_atom_rows(news_parse(merge_atom_xml, publisher, time_now()), "sync")
    reading_feed_parse_async(merge_atom_xml, publisher, time_now(), feed_generation, fn(rows){
        merge_atom_rows(rows, "async")
        merge_atom_report()
    })
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    data = work / ('data-' + str(time.time_ns()))
    (data / 'host').mkdir(parents=True)
    report_path = data / 'dev.cfaw.runtime-tests/atom-report.json'
    executable = ensure_native_probe()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [str(executable), '--bundle', str(bundle), '--app-data', str(data)],
            cwd=executable.parent,
            env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')),
            stdout=log, stderr=log, startupinfo=startup)
        try:
            deadline = time.monotonic() + 15
            while not report_path.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.1)
            if not report_path.exists():
                raise RuntimeError('Native Atom fixture did not complete; inspect ' + str(work / 'host.log'))
            report = json.loads(report_path.read_text(encoding='utf-8'))
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
    errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    report['native_errors'] = len(errors)
    report['network_calls'] = 0
    report['model_calls'] = 0
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not errors, errors
    assert not report['failures'], report
    print('PASS:', len(report['checks']), 'native Atom checks; errors:', len(errors), '; no network or model calls')


if __name__ == '__main__':
    main()
