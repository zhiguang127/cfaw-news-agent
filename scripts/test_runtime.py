#!/usr/bin/env python3
"""Run OctoScript fixtures in isolated card-host or pinned Windows Rinx."""
import argparse
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import shutil
import struct
import time
import zlib
from urllib.request import urlopen
from urllib.parse import urlencode
from uuid import uuid4
from assemble import ROOT, ORDER, assemble


def collect_reports(report_paths):
    """Require every selected suite to complete, retaining failure details."""
    missing = [label for label, path in report_paths.items() if not path.is_file()]
    if missing:
        raise ValueError('Missing required reports: ' + ', '.join(missing))
    report = {'passed': 0, 'failed': 0, 'stage': 'complete', 'stages': {}}
    for label, path in report_paths.items():
        try:
            part = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise ValueError(f'{label}: unreadable report') from error
        if not isinstance(part, dict) or part.get('stage') != 'complete':
            raise ValueError(f'{label}: report did not complete')
        passed, failed = part.get('passed'), part.get('failed')
        if any(type(count) is not int or count < 0 for count in (passed, failed)):
            raise ValueError(f'{label}: invalid test counts')
        if passed + failed == 0:
            raise ValueError(f'{label}: no checks executed')
        report['passed'] += passed
        report['failed'] += failed
        report['stages'][label] = part
    return report


def region_has_ink(png, rect, logical_size):
    """Check actual PNG pixels: a surviving widget tree can still paint blank."""
    width, height, depth, color = struct.unpack('>IIBB', png[16:26])
    if depth != 8 or color != 6:
        raise ValueError('Expected native 8-bit RGBA PNG')
    compressed, offset = bytearray(), 8
    while offset < len(png):
        length = struct.unpack('>I', png[offset:offset + 4])[0]
        if png[offset + 4:offset + 8] == b'IDAT':
            compressed.extend(png[offset + 8:offset + 8 + length])
        offset += length + 12
    raw = zlib.decompress(compressed)
    x, y, w, h = rect
    left, right = max(0, int(x * width / logical_size[0])), min(width, int((x + w) * width / logical_size[0]))
    top, bottom = max(0, int(y * height / logical_size[1])), min(height, int((y + h) * height / logical_size[1]))
    stride, previous, colors = width * 4, bytearray(width * 4), set()
    for row in range(bottom):
        start = row * (stride + 1)
        kind, values = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            a, b, c = (values[i - 4] if i >= 4 else 0), previous[i], (previous[i - 4] if i >= 4 else 0)
            if kind == 1:
                predictor = a
            elif kind == 2:
                predictor = b
            elif kind == 3:
                predictor = (a + b) // 2
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
            elif kind == 0:
                predictor = 0
            else:
                raise ValueError('Unknown PNG row filter')
            values[i] = (values[i] + predictor) & 255
        if row >= top:
            colors.update(bytes(values[i:i + 3]) for i in range(left * 4, right * 4, 4))
            if len(colors) > 2:
                return True
        previous = values
    return False


def inspect_rinx_navigation(work, port, rounds):
    def get(route, **params):
        query = '?' + urlencode(params) if params else ''
        with urlopen(f'http://127.0.0.1:{port}{route}{query}', timeout=10) as response:
            return response.read()

    def snapshot(label, expected=None):
        data = get('/snap')
        widgets = json.loads(data)['s']
        png = get('/g', raw=1)
        (work / (label + '.json')).write_bytes(data)
        (work / (label + '.png')).write_bytes(png)
        brand = next(w for w in widgets if w.get('ty') == 'Label' and w.get('t') == 'cfaw-news')
        size = json.loads(get('/s'))['w'][0]['sz']
        if not region_has_ink(png, brand['r'], size):
            raise SystemExit(f'Blank painted app header despite live widget tree; inspect {work}')
        if expected:
            heading = next((w for w in widgets if w.get('ty') == 'Label' and expected in w.get('t', '')), None)
            if heading is None or not region_has_ink(png, heading['r'], size):
                raise SystemExit(f'Missing or blank painted page heading {expected}; inspect {work}')
        return widgets

    widgets = snapshot('rinx-before-navigation')
    nav = {name: next(w for w in widgets if w.get('ty') == 'Button' and w.get('t') == name)
           for name in ('首页', '日程')}

    def click(name, wait=0):
        x, y, w, h = nav[name]['r']
        get('/click', x=x + w / 2, y=y + h / 2, wait=wait)

    for index in range(rounds):
        for name in ('日程', '首页', '日程', '首页'):
            click(name)
        if index % 100 == 0:
            print(f'Rinx navigation round {index}/{rounds}', flush=True)
            snapshot('rinx-round-' + str(index))
    for name, expected in [('日程', '我的日程'), ('首页', '240 条新闻')]:
        click(name, 1)
        time.sleep(.15)
        snapshot('rinx-navigation-' + name, expected)
    for label, expected in [('关注动态', '我的关注'), ('我的收藏', '条收藏')]:
        widgets = json.loads(get('/snap'))['s']
        menu = next(w for w in widgets if w.get('i') == 'menu_button')
        x, y, w, h = menu['r']
        get('/click', x=x + w / 2, y=y + h / 2, wait=1)
        widgets = json.loads(get('/snap'))['s']
        action = next(w for w in widgets if w.get('ty') == 'Button' and w.get('t') == label)
        x, y, w, h = action['r']
        get('/click', x=x + w / 2, y=y + h / 2, wait=1)
        snapshot('rinx-navigation-' + label, expected)
        click('首页', 1)
    time.sleep(1)
    snapshot('rinx-navigation-settled')
    text = (work / 'host.log').read_text(encoding='utf-8', errors='replace')
    counters = re.findall(r'\[upload-probe\].*?bytes=(\d+) limit=(\d+) refusals=(\d+)', text)
    if not counters:
        raise SystemExit('Rinx upload diagnostics missing')
    measurements = [tuple(map(int, row)) for row in counters]
    metrics = {'queued_clicks': rounds * 4, 'peak_accounted_bytes': max(row[0] for row in measurements),
               'final_accounted_bytes': measurements[-1][0], 'test_upload_limit_bytes': measurements[-1][1],
               'allocation_refusals': max(row[2] for row in measurements)}
    serials = re.findall(r'\[serial-probe\].*?submitted=(\d+) completed=(\d+)', text)
    if serials:
        metrics['final_submitted_serial'], metrics['final_completed_serial'] = map(int, serials[-1])
    (work / 'render-report.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    if ('[E]' in text or metrics['allocation_refusals']
            or metrics['peak_accounted_bytes'] > metrics['test_upload_limit_bytes']):
        raise SystemExit(f'Native rendering failure; inspect {work / "host.log"}')
    print(f'Rinx App/Modal fixture navigation checked: {rounds * 4} queued clicks; 64 MiB test upload limit; {work}')


def inspect_feed_ui(work, port, logical_size='430x860'):
    """Exercise the full-capacity fixture feed through native widget events."""
    def get(route, **params):
        query = '?' + urlencode(params) if params else ''
        with urlopen(f'http://127.0.0.1:{port}{route}{query}', timeout=5) as response:
            return response.read()

    def snapshot(label, expected=None):
        deadline = time.monotonic() + 3
        data = get('/snap')
        while expected and not expected(json.loads(data)['s']) and time.monotonic() < deadline:
            time.sleep(.05)
            data = get('/snap')
        (work / (label + '.json')).write_bytes(data)
        png = get('/g', raw=1)
        (work / (label + '.png')).write_bytes(png)
        widgets = json.loads(data)['s']
        brand = next(w for w in widgets if w.get('ty') == 'Label' and w.get('t') == 'cfaw-news')
        if not region_has_ink(png, brand['r'], tuple(map(int, logical_size.split('x')))):
            raise SystemExit(f'Painted header missing during {label}; inspect {work}')
        return widgets

    def click(widget):
        x, y, width, height = widget['r']
        get('/click', x=x + width / 2, y=y + height / 2, wait=1)
        time.sleep(.15)

    def menu_action(label):
        widgets = json.loads(get('/snap'))['s']
        click(next(w for w in widgets if w.get('i') == 'menu_button'))
        widgets = json.loads(get('/snap'))['s']
        click(next(w for w in widgets if w.get('t') == label and w.get('ty') == 'Button'))

    time.sleep(.3)
    widgets = snapshot('feed-after-refresh')
    if any(w.get('i') in ('home_attention', 'feed_keyword_input', 'home_input') for w in widgets):
        raise SystemExit('The removed attention section or duplicate input is still visible')
    if sum(w.get('i') == 'search' and w.get('ty') == 'TextInput' for w in widgets) != 1:
        raise SystemExit('Home must have exactly one news search input')
    weather = next((w for w in widgets if w.get('i') == 'weather_header_hit'), None)
    if weather is None or weather['r'][2] <= 0:
        raise SystemExit('Weather header entry disappeared from the new home layout')
    click(weather)
    forecast = snapshot('feed-weather')
    if not any(w.get('t') == '逐日预报' for w in forecast):
        raise SystemExit('Weather header cannot open the forecast')
    click(next(w for w in forecast if w.get('t') == '选择城市' and w.get('ty') == 'Button'))
    picker = snapshot('feed-weather-picker')
    click(next(w for w in picker if w.get('t') == '杭州' and w.get('ty') == 'Button'))
    selected = snapshot('feed-weather-selected')
    if not any(w.get('t') == '杭州' and w.get('ty') == 'Label' for w in selected):
        raise SystemExit('Weather city selection stopped working')
    click(next(w for w in selected if w.get('t') == '‹ 返回' and w.get('ty') == 'Button'))
    widgets = snapshot('feed-weather-returned')
    if not any(w.get('t', '').startswith('杭州 ·') for w in widgets):
        raise SystemExit('Selected weather city missing after returning to the home feed')
    titles = [w for w in widgets if w.get('ty') == 'Label' and w.get('t', '').startswith('Synthetic capacity news')]
    # /snap reports painted widgets in the viewport, not every off-screen row.
    if len(titles) < 3 or not any(w.get('t') == '240 条新闻' for w in widgets):
        raise SystemExit('Full-capacity native list is not visible')
    first = min(titles, key=lambda w: w['r'][1])
    inline = next((w for w in widgets if w.get('ty') == 'Label' and w.get('t', '').startswith('Agent · 日程「Synthetic evaluation」')), None)
    if inline is None:
        raise SystemExit('Validated schedule impact is missing from its prioritized news row')
    click(inline)
    impact_detail = snapshot('feed-impact-detail')
    if not any(w.get('t') == 'Synthetic impact explanation' for w in impact_detail):
        raise SystemExit('Inline Agent hint cannot open its evidence and explanation')
    click(next(w for w in impact_detail if w.get('t') == '‹ 返回' and w.get('ty') == 'Button'))
    widgets = json.loads(get('/snap'))['s']
    click(min((w for w in widgets if w.get('t') == '查看' and w.get('ty') == 'Button'), key=lambda w: w['r'][1]))
    detail = snapshot('feed-story')
    back = next((w for w in detail if w.get('t') == '‹ 返回' and w.get('ty') != 'Label'), None)
    if back is None:
        raise SystemExit('News detail did not open after full-capacity refresh')
    click(back)
    get('/m', k='scroll', x=170, y=500, dy=8500, wait=1)
    time.sleep(.3)
    scrolled = snapshot('feed-scrolled')
    if not any(w.get('ty') == 'Label' and w.get('t', '').startswith('Synthetic capacity news') and 180 < w['r'][1] < 750 for w in scrolled):
        raise SystemExit('Feed cannot be scrolled after repeated refreshes')
    click(next(w for w in scrolled if w.get('t') == '↑' and w.get('ty') != 'Label'))
    time.sleep(.3)
    top = snapshot('feed-returned-top')
    if not any(w.get('t') == first['t'] and abs(w['r'][1] - first['r'][1]) < 1 for w in top):
        raise SystemExit('Return-to-top stopped working after repeated refreshes')
    click(next(w for w in top if w.get('t') == '收藏' and w.get('ty') != 'Label' and 180 < w['r'][1] < 650))
    saved = snapshot('feed-bookmarked', lambda ws: any(w.get('t') == '已收藏' for w in ws))
    if not any(w.get('t') == '已收藏' for w in saved):
        raise SystemExit('Bookmark callback failed after repeated refreshes')
    menu_action('我的收藏')
    bookmarks = snapshot('feed-bookmarks-page')
    if not any(w.get('t') == '1 条收藏' for w in bookmarks) or not any(w.get('t') == first['t'] for w in bookmarks):
        raise SystemExit('Deferred rendering lost the saved news row')
    click(next(w for w in bookmarks if w.get('t') == '首页' and w.get('ty') == 'Button'))
    menu_action('管理关注')
    widgets = json.loads(get('/snap'))['s']
    click(next(w for w in widgets if w.get('i') == 'keyword_input' and w.get('ty') == 'TextInput'))
    get('/t', t='/1')
    widgets = json.loads(get('/snap'))['s']
    click(next(w for w in widgets if w.get('t') == '添加关注' and w.get('ty') == 'Button'))
    widgets = json.loads(get('/snap'))['s']
    click(next(w for w in widgets if w.get('t') == '‹ 返回' and w.get('ty') == 'Button'))
    priority = snapshot('feed-priority', lambda ws: any(w.get('t') == '匹配关键词：/1' for w in ws))
    ranked = sorted((w for w in priority if w.get('ty') == 'Label' and w.get('t', '').startswith('Synthetic capacity news')), key=lambda w: w['r'][1])
    if not ranked or '/1' not in ranked[0]['t'] or ranked[0]['t'] == first['t']:
        raise SystemExit('Followed news did not move to the top of the same feed')
    if not any(w.get('t') == '匹配关键词：/1' for w in priority):
        raise SystemExit('Prioritized rule match has no honest relevance explanation')
    if any(w.get('ty') == 'Label' and w.get('t', '').startswith('Agent · 日程') for w in priority):
        raise SystemExit('Context change left an old Agent impact in the feed')
    stored = json.loads((work / 'data/dev.cfaw.runtime-tests/interests_v1.json').read_text(encoding='utf-8'))
    if not any(i.get('kind') == 'keyword' and i.get('value') == '/1' for i in stored['items']):
        raise SystemExit('Interest management did not persist its rule')
    menu_action('关注动态')
    followed = snapshot('feed-followed')
    if not any('我的关注' in w.get('t', '') for w in followed):
        raise SystemExit('The menu cannot open the followed news')
    click(next(w for w in followed if w.get('t') == '首页' and w.get('ty') == 'Button'))
    widgets = snapshot('feed-home-returned', lambda ws: any(w.get('t') == '240 条新闻' for w in ws) and any(w.get('ty') == 'Label' and w.get('t', '').startswith('Synthetic capacity news') for w in ws))
    click(next(w for w in widgets if w.get('t') == '科技' and w.get('ty') != 'Label'))
    filtered = snapshot('feed-category', lambda ws: any(w.get('t') == '全部' and w.get('ty') == 'Button' for w in ws) and any(w.get('ty') == 'Label' and w.get('t', '').startswith('Synthetic capacity news') for w in ws))
    if not any(w.get('t', '').startswith('Synthetic capacity news') for w in filtered):
        raise SystemExit('Category callback lost the feed')
    click(next(w for w in filtered if w.get('t') == '全部' and w.get('ty') != 'Label'))
    widgets = json.loads(get('/snap'))['s']
    click(next(w for w in widgets if w.get('i') == 'search' and w.get('ty') == 'TextInput'))
    get('/t', t='capacity')
    time.sleep(.3)
    searched = snapshot('feed-search')
    if not any(w.get('t', '').startswith('Synthetic capacity news') for w in searched):
        raise SystemExit('Search callback lost the feed')
    # The two root tabs keep their top rectangles while secondary lists live
    # in the menu. Exercise overlapping redraws without a frame barrier.
    navigation = {
        name: max((w for w in searched if w.get('t') == name and w.get('ty') == 'Button'), key=lambda w: w['r'][1])
        for name in ('首页', '日程')
    }
    for _ in range(20):
        for name in ('日程', '首页', '日程', '首页'):
            x, y, width, height = navigation[name]['r']
            get('/click', x=x + width / 2, y=y + height / 2)
    time.sleep(.3)
    for name, expected in [('日程', '我的日程'), ('首页', '240 条新闻')]:
        click(navigation[name])
        widgets = snapshot('navigation-' + name)
        if not any(w.get('ty') == 'Label' and expected in w.get('t', '') for w in widgets):
            raise SystemExit('Page missing after rapid navigation: ' + name)
    menu_action('我的收藏')
    if not any(w.get('t') == '1 条收藏' for w in snapshot('navigation-bookmarks')):
        raise SystemExit('Bookmarks missing from the menu after rapid navigation')
    click(navigation['首页'])
    errors = (work / 'host.log').read_text(encoding='utf-8', errors='replace')
    if '[E]' in errors:
        raise SystemExit(f'Runtime error during feed interaction; inspect {work / "host.log"}')
    print(f'Native feed UI checked at {logical_size} (single search, priority, inline Agent impact, weather, city selection, detail, scroll, menu interests/bookmarks, filters, 80 rapid page switches): {work}')


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, help='Pinned card-host executable')
    parser.add_argument('--agent-only', action='store_true', help='Run isolated agent validation tests')
    parser.add_argument('--inspect-ui', action='store_true', help='Capture and exercise the fixture UI (agent-only or --suites feed)')
    parser.add_argument('--ui-size', choices=('360x860', '430x860'), default='430x860', help='Feed UI inspection viewport')
    parser.add_argument('--rinx-render-probe', action='store_true', help='Use pinned Windows Rinx App/Modal with isolated fixtures; no login or admission')
    parser.add_argument('--navigation-rounds', type=int, default=1000, help='Rinx render-probe rounds, four queued page clicks each (1..2000)')
    parser.add_argument('--suites', nargs='+', choices=('news', 'weather', 'holiday', 'fx', 'feed'), help='Run selected suites; feed exercises application refresh (default: data suites)')
    args = parser.parse_args()
    if args.agent_only and args.suites:
        parser.error('--suites cannot be combined with --agent-only')
    suites = args.suites or ['news', 'weather', 'holiday', 'fx']
    if 'feed' in suites and len(suites) != 1:
        parser.error('feed uses the application UI; run it separately from data suites')
    if args.rinx_render_probe and (os.name != 'nt' or args.host or args.agent_only or suites != ['feed']):
        parser.error('--rinx-render-probe requires Windows and --suites feed, without --host/--agent-only')
    if args.rinx_render_probe and args.ui_size != '430x860':
        parser.error('The pinned Rinx render probe has a fixed 430x860 window')
    if not 1 <= args.navigation_rounds <= 2000:
        parser.error('--navigation-rounds must be 1..2000')
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    checkout = ROOT / next(r['relative_checkout'] for r in lock['repositories'] if r['name'] == 'OctoSense-App-Hub')
    host = (args.host or checkout / 'target/release' / ('card-host.exe' if os.name == 'nt' else 'card-host')).resolve()
    if not args.rinx_render_probe and not host.is_file():
        raise SystemExit('Pinned card-host missing; supply --host. A graphical session is required.')
    work = ROOT / '.test-state' / ('runtime-' + uuid4().hex[:12])
    bundle = work / 'bundle'
    bundle.mkdir(parents=True)
    host_environment = os.environ.copy()
    if args.rinx_render_probe:
        from build_windows_sdf_host import link_rinx_entry
        from patch_windows_render_host import artifacts_match
        dev_root = ROOT / '.dev/vendor'
        if not artifacts_match(dev_root):
            raise SystemExit('Build the recorded D3D11 fix first: scripts/build_windows_tools.ps1 -Mode Rinx')
        native = work / 'native'
        native.mkdir()
        host = native / 'rinx-render-probe.exe'
        link_rinx_entry(dev_root, ROOT / 'tests/scenarios/rinx_render_probe.rs', host,
                        lock['toolchain']['rinx_rust_channel'], 'cfaw_rinx_render_probe')
        for resource in ('makepad_widgets/resources', 'rinx/resources'):
            shutil.copytree(dev_root / 'Rinx/target/release' / resource, native / resource)
        host_data = work / 'host-data'
        host_data.mkdir()
        host_environment['RINX_DATA_DIR'] = str(host_data)
        print(f'Rinx render probe artifacts: {work}', flush=True)
    paths = ORDER[:-1] if args.agent_only or 'feed' in suites else ORDER[:ORDER.index('src/agent/runtime/connectivity.splash')]
    source, _ = assemble(paths=paths)
    if 'feed' in suites:
        summary = 'Synthetic retained summary for bounded-memory refresh regression. ' * 24
        items, hits = [], []
        for index in range(20):
            link = f'https://example.org/capacity/__SOURCE__/{index}'
            title = f'Synthetic capacity news __SOURCE__/{index}'
            items.append(f'<item><title>{title}</title><link>{link}</link><description>{summary}</description></item>')
            hits.append({'objectID': str(index), 'title': title, 'url': link, 'created_at_i': None})
        catalog = json.loads((ROOT / 'src/data/ingestion/sources.json').read_text(encoding='utf-8'))['sources']
        for name, value in [('fixture_capacity_rss', '<rss><channel>' + ''.join(items) + '</channel></rss>'),
                            ('fixture_capacity_hn', json.dumps({'hits': hits}))]:
            bodies = {item['id']: value.replace('__SOURCE__', item['id']) for item in catalog}
            source += '\nlet ' + name + ' = ' + json.dumps(bodies) + '\n'
    for name, file in [('fixture_rss', 'news-rss.xml'), ('fixture_atom', 'news-atom.xml'), ('fixture_hn', 'news-hn.json'),
                       ('fixture_weather', 'weather-daily.json'),
                       ('fixture_holiday_2026', 'holiday-cn-2026.json'),
                       ('fixture_holiday_empty', 'holiday-cn-unpublished.json'),
                       ('fixture_fx_new', 'fx-cny-2026-10-01.json'),
                       ('fixture_fx_old', 'fx-cny-2026-09-30.json'),
                       ('fixture_analysis_no_change', 'analysis-no-change.json'),
                       ('fixture_analysis_create', 'analysis-create.json'),
                       ('fixture_analysis_suggestion', 'analysis-suggestion.json'),
                       ('fixture_analysis_invalid_model_output', 'analysis-invalid-model-output.json')]:
        source += '\nlet ' + name + ' = ' + json.dumps((ROOT / 'tests/fixtures' / file).read_text(encoding='utf-8'), ensure_ascii=False) + '\n'
    source += (ROOT / 'tests/unit/agent_validation.splash').read_text(encoding='utf-8')
    if args.agent_only:
        source += (ROOT / 'tests/scenarios/analysis_runtime.splash').read_text(encoding='utf-8')
        source += '''
start_timeout(0.05, || agent_test_validation(|| {
    start_timeout(0.02, || agent_test_confirmation(|| {
        start_timeout(0.02, || agent_test_schedule_optimization(|| {
            start_timeout(0.02, || agent_test_history_optimization())
        }))
    }))
}))
'''


    else:
        for name in suites:
            directory = 'scenarios' if name == 'feed' else 'unit'
            source += (ROOT / f'tests/{directory}/{name}_runtime.splash').read_text(encoding='utf-8')
    (bundle / 'main.splash').write_text(source, encoding='utf-8')
    manifest = json.loads((ROOT / 'bundle/manifest.json').read_text())
    manifest['id'] = 'dev.cfaw.runtime-tests'
    manifest['integrity']['bundle_blake3'] = ''
    manifest['network']['hosts'] = []
    (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    startup = None
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    report_path = work / 'data' / manifest['id'] / 'runtime-report.json'
    report_paths = {'agent': report_path} if args.agent_only else {
        label: report_path if label == 'news' else report_path.with_name(label + '-report.json')
        for label in suites
    }
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        command = [str(host), '--bundle', str(bundle), '--allow-unsigned', '--stamp', '--app-data', str(work / 'data'), '--remote', str(port)]
        if args.inspect_ui and 'feed' in suites:
            command += ['--size', args.ui_size]
        if args.rinx_render_probe:
            command += ['--upload-limit-test']
        process = subprocess.Popen(command, cwd=host.parent if args.rinx_render_probe else host.parents[2], stdout=log, stderr=log, startupinfo=startup, env=host_environment)
        try:
            deadline = time.monotonic() + (45 if 'feed' in suites else 20)
            while time.monotonic() < deadline and process.poll() is None:
                if all(path.exists() for path in report_paths.values()):
                    break
                if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
                    break
                time.sleep(0.1)
            if process.poll() is not None:
                raise SystemExit(f'Runtime exited early ({process.returncode}); inspect {work / "host.log"}')
            if '[E]' in (work / 'host.log').read_text(encoding='utf-8', errors='replace'):
                raise SystemExit(f'Runtime script error; inspect {work / "host.log"}')
            try:
                report = collect_reports(report_paths)
            except ValueError as error:
                raise SystemExit(f'{error}; inspect {work / "host.log"}') from error
            (work / 'combined-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            if args.rinx_render_probe:
                inspect_rinx_navigation(work, port, args.navigation_rounds)
                if args.inspect_ui:
                    inspect_feed_ui(work, port, args.ui_size)
            elif args.inspect_ui and 'feed' in suites:
                inspect_feed_ui(work, port, args.ui_size)
            if args.inspect_ui and args.agent_only:
                time.sleep(1)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    snapshot = json.load(response)
                (work / 'results-ui.json').write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
                with urlopen(f'http://127.0.0.1:{port}/g?raw=1', timeout=3) as response:
                    (work / 'results-ui.png').write_bytes(response.read())
                buttons = [w for w in snapshot['s'] if w.get('t') == '查看证据与建议']
                if not buttons:
                    raise SystemExit('Results entry missing in native UI snapshot')
                x, y, width, height = buttons[0]['r']
                with urlopen(f'http://127.0.0.1:{port}/click?x={x + width / 2}&y={y + height / 2}&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/m?k=scroll&x=200&y=650&dy=460&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    detail = json.load(response)
                (work / 'detail-ui.json').write_text(json.dumps(detail, ensure_ascii=False), encoding='utf-8')
                if not any(w.get('t') == '接受' for w in detail['s']):
                    raise SystemExit('Persisted suggestion cannot be opened from results')
                with urlopen(f'http://127.0.0.1:{port}/g?raw=1', timeout=3) as response:
                    (work / 'detail-ui.png').write_bytes(response.read())
                accept = next(w for w in detail['s'] if w.get('t') == '接受')
                x, y, width, height = accept['r']
                with urlopen(f'http://127.0.0.1:{port}/click?x={x + width / 2}&y={y + height / 2}&wait=1', timeout=3):
                    pass
                with urlopen(f'http://127.0.0.1:{port}/m?k=scroll&x=200&y=650&dy=600&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    preview = json.load(response)
                confirm = next(w for w in preview['s'] if w.get('t') == '确认并保存')
                x, y, width, height = confirm['r']
                with urlopen(f'http://127.0.0.1:{port}/click?x={x + width / 2}&y={y + height / 2}&wait=1', timeout=3):
                    pass
                time.sleep(0.3)
                with urlopen(f'http://127.0.0.1:{port}/snap', timeout=3) as response:
                    refused = json.load(response)
                if not any('重新分析' in w.get('t', '') and w.get('ty') == 'Label' for w in refused['s']):
                    raise SystemExit('Evidence rejection missing from confirmation UI')
                decisions = json.loads((report_path.parent / 'suggestions_v1.json').read_text(encoding='utf-8'))
                if decisions['items'][0]['state'] != 'pending':
                    raise SystemExit('Stale evidence confirmation changed the user decision')
                print(f'Native UI checked: {work}')
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print(f'Report: {work / "combined-report.json"}')
            if report['failed']:
                raise SystemExit(1)
        finally:
            try:
                with urlopen(f'http://127.0.0.1:{port}/quit', timeout=2):
                    pass
            except OSError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=3)


if __name__ == '__main__':
    run()
