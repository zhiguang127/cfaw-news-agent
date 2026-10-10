"""One real public feed in isolated Rinx; no account, model or fixture replies."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import time
from assemble import ROOT, ORDER, assemble, source_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='hn')
    parser.add_argument('--startup', action='store_true')
    parser.add_argument('--copy-data', type=Path)
    parser.add_argument('--diagnose', action='store_true')
    args = parser.parse_args()
    entries = source_catalog()['sources']
    entry = next(s for s in entries if s['id'] == args.source)
    from urllib.parse import urlsplit
    host = urlsplit(entry['url']).hostname
    work = ROOT / '.test-state' / ('live-news-' + args.source + '-' + str(time.time_ns()))
    bundle = work / 'bundle'
    bundle.mkdir(parents=True)
    source, _ = assemble(paths=ORDER if args.startup else ORDER[:-1])
    if args.diagnose:
        for label, needle in [('interests-returned', '    if interests != nil {'), ('interests-items', '        user_interests = interests.items'), ('interests-ids', '            enabled_source_ids = []'), ('interests-loop', '                for id in interests.enabled_source_ids {'), ('interests-check-id', '                    if news_source(id) != nil'), ('records-enter', '    tracking_revision = tracking_revision + 1'), ('records-bookmarks', '    let bookmarks = records_read(bookmark_file, "bookmarks")'), ('records-interests', '    let interests = records_read(interest_file, "interests")'), ('records-tracking', '    let tracking = records_read(tracking_file, "tracking")'), ('records-index', '    records_index_unread()'), ('records-clean-main', '    records_clean_demo_bookmarks(bookmark_file.path)'), ('records-clean-backup', '    records_clean_demo_bookmarks(bookmark_file.path + ".backup")'), ('clean-exists', '        if !fs.exists(path) { return }'), ('clean-read', '        let value = fs.read(path).parse_json()'), ('clean-valid', '        if !records_document_valid(value, "bookmarks") { return }'), ('clean-count', '        let count = value.items.len()'), ('clean-write', '        if count != value.items.len() { fs.write(path, value.to_json()) }')]:
            source = source.replace(needle, '    fs.write("startup-stage.txt", "' + label + '")\n' + needle)
    source += ('''\nstart_interval(1.0, || fs.write("live-news.json", {busy: busy task: feed_task statuses: feed_status_by_source rows: app_feed_rows.len()}.to_json()))\n''' if args.startup else '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    enabled_source_ids = [''' + json.dumps(args.source) + ''']
    tracking_schedule_check = fn(){}
    render_main()
    start_interval(1.0, || fs.write("live-news.json", {busy: busy task: feed_task statuses: feed_status_by_source rows: app_feed_rows.len()}.to_json()))
    start_timeout(0.1, || refresh_sources(enabled_source_ids))
})
''')
    if args.startup:
        source = source.replace('busy: busy task: feed_task', 'phase: boot_phase finished: boot_finished busy: busy task: feed_task')
    # Omit callbacks from the report; callable values are not JSON domain data.
    source = source.replace('task: feed_task', 'completed: if feed_task == nil {0} else {feed_task.completed} active: if feed_task == nil {0} else {feed_task.active}')
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = ROOT / '.test-state/intent-context/native/intent-probe.exe'
    if not executable.is_file():
        raise SystemExit('Build the isolated native probe with test_intent_context.py first')
    data = work / 'data'
    (data / 'host').mkdir(parents=True)
    if args.copy_data:
        shutil.copytree(args.copy_data, data / 'dev.cfaw.runtime-tests', dirs_exist_ok=True)
    network_args = []
    domains = set(json.loads((ROOT / 'bundle/manifest.json').read_text(encoding='utf-8'))['network']['hosts']) if args.startup else {host}
    for domain in sorted(domains):
        network_args += ['--network-host', domain]
    env = dict(os.environ, RINX_DATA_DIR=str(data / 'host'))
    report_path = data / 'dev.cfaw.runtime-tests/live-news.json'
    # A copied prior probe report is evidence from another run, never readiness.
    if report_path.exists():
        report_path.unlink()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data),
                                    *network_args, '--size', '430x860'],
                                   cwd=executable.parent, env=env, stdout=log, stderr=log, startupinfo=startup)
        report = None
        try:
            deadline = time.monotonic() + 110
            while time.monotonic() < deadline and process.poll() is None:
                if report_path.is_file():
                    try:
                        report = json.loads(report_path.read_text(encoding='utf-8'))
                    except (OSError, ValueError):
                        pass
                    if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
                        break
                    if report and not report['busy'] and (report['completed'] >= 1 or (args.startup and report['finished'] and report['rows'] > 0)):
                        break
                time.sleep(.2)
        finally:
            process.terminate()
            process.wait(timeout=5)
    print(str(work), flush=True)
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    if not report or report['busy'] or (report['completed'] < 1 and not (args.startup and report['finished'] and report['rows'] > 0)):
        raise SystemExit('Live news refresh did not finish; inspect host.log')
    if report['rows'] == 0:
        raise SystemExit('Feed completed with no news; inspect source status')
    if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
        raise SystemExit('Host reported a script error; inspect host.log')


if __name__ == '__main__':
    main()
