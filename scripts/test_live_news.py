"""One real public feed in isolated Rinx; no account, model or fixture replies."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import time
import socket
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble, source_catalog
from native_probe import ensure_native_probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='hn')
    parser.add_argument('--startup', action='store_true')
    parser.add_argument('--copy-data', type=Path)
    parser.add_argument('--refresh-rounds', type=int, choices=range(1, 4), default=1)
    args = parser.parse_args()
    entries = source_catalog()['sources']
    entry = next(s for s in entries if s['id'] == args.source)
    work = ROOT / '.test-state' / ('live-news-' + args.source + '-' + str(time.time_ns()))
    bundle = work / 'bundle'
    bundle.mkdir(parents=True)
    source, _ = assemble(paths=ORDER if args.startup else ORDER[:-1])
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
    # Public-feed diagnostics must never start a model task using copied goals.
    source += '\nforeground_tracking_arm = fn(){}\ntracking_schedule_check = fn(){}\n'
    if args.startup:
        source = source.replace('busy: busy task: feed_task', 'phase: boot_phase finished: boot_finished busy: busy task: feed_task')
    # Omit callbacks from the report; callable values are not JSON domain data.
    source = source.replace('task: feed_task', 'generation: feed_generation completed: if feed_task == nil {0} else {feed_task.completed} active: if feed_task == nil {0} else {feed_task.active}')
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = ensure_native_probe()
    data = work / 'data'
    (data / 'host').mkdir(parents=True)
    if args.copy_data:
        shutil.copytree(args.copy_data, data / 'dev.cfaw.runtime-tests', dirs_exist_ok=True)
    network_args = []
    # Publisher images and optional homepage services use the same reviewed
    # allowlist as the shipped bundle, even when testing only one RSS source.
    domains = set(json.loads((ROOT / 'bundle/manifest.json').read_text(encoding='utf-8'))['network']['hosts'])
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
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    def get(route, **params):
        with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as r:
            return r.read()
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data),
                                    *network_args, '--remote=' + str(port), '--size', '430x860'],
                                   cwd=executable.parent, env=env, stdout=log, stderr=log, startupinfo=startup)
        report = None
        clicked_generation = -1
        completed_rounds = 0
        completed_generation = -1
        try:
            deadline = time.monotonic() + 110
            while time.monotonic() < deadline and process.poll() is None:
                if report_path.is_file():
                    try:
                        report = json.loads(report_path.read_text(encoding='utf-8'))
                    except (OSError, ValueError):
                        pass
                    if any('[E] splash:' in line or 'mini-app isolate panic' in line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines()):
                        time.sleep(1.2)
                        report = json.loads(report_path.read_text(encoding='utf-8'))
                        report['rounds'] = completed_rounds
                        break
                    if report and not report['busy'] and report['rows'] > 0 and report['completed'] > 0 and report['generation'] != completed_generation:
                        completed_rounds += 1
                        completed_generation = report['generation']
                    if report:
                        report['rounds'] = completed_rounds
                    if report and not report['busy'] and report['rows'] > 0 and report['rounds'] < args.refresh_rounds and report['generation'] != clicked_generation:
                        buttons = json.loads(get('/snap'))['s']
                        button = next((w for w in buttons if w.get('i') == 'refresh_news' and w.get('t') == '刷新新闻'), None)
                        if button is not None:
                            (work/'before-refresh.json').write_text(json.dumps(button, ensure_ascii=False), encoding='utf-8')
                            x,y,w,h = button['r']
                            get('/click', x=x+w/2, y=y+h/2, wait=1)
                            clicked_generation = report['generation']
                    if report and report['rounds'] >= args.refresh_rounds and not report['busy'] and (report['completed'] >= 1 or (args.startup and report['finished'] and report['rows'] > 0)):
                        time.sleep(.6)
                        snapshot = json.loads(get('/snap'))
                        labels = [w.get('t','') for w in snapshot['s'] if w.get('ty') != 'Splash']
                        assert any(w.get('i') == 'status' and w.get('t','').startswith(str(report['rows']) + ' 条新闻') for w in snapshot['s']), 'Native homepage did not display fetched news count'
                        assert any(w.get('i') == 'refresh_news' and w.get('t') == '刷新新闻' for w in snapshot['s']), 'Native refresh control remained busy'
                        (work/'visible-news.json').write_text(json.dumps(labels, ensure_ascii=False), encoding='utf-8')
                        (work/'feed.png').write_bytes(get('/g', raw=1))
                        break
                time.sleep(.2)
        finally:
            if not report or report.get('rounds', 0) < args.refresh_rounds:
                try:
                    (work/'failure.png').write_bytes(get('/g', raw=1))
                    (work/'failure-snapshot.json').write_bytes(get('/snap'))
                except OSError:
                    pass
            process.terminate()
            process.wait(timeout=5)
    native_errors = [line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
    print('Native host diagnostics:', len(native_errors), flush=True)
    print(str(work), flush=True)
    summary = None if report is None else dict(rows=report['rows'], rounds=completed_rounds, busy=report['busy'], completed=report['completed'], sources={id: {'state': s['state'], 'count': s['count'], 'error': s['error']} for id,s in report['statuses'].items() if s['state'] != 'not_loaded'}, native_errors=len(native_errors))
    (work/'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    if not report or report['rounds'] < args.refresh_rounds or report['busy'] or (report['completed'] < 1 and not (args.startup and report['finished'] and report['rows'] > 0)):
        raise SystemExit('Live news refresh did not finish; inspect host.log')
    if report['rows'] == 0:
        raise SystemExit('Feed completed with no news; inspect source status')
    if any('[E] splash:' in line or 'mini-app isolate panic' in line for line in (work / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines()):
        raise SystemExit('Host reported a script error; inspect host.log')


if __name__ == '__main__':
    main()
