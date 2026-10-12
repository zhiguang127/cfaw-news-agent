"""Verify reading facets and actual filter clicks using labelled synthetic news."""
import json
import argparse
import os
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ui-size', choices=['430x860', '360x860'], default='430x860')
args = parser.parse_args()
viewport_width = int(args.ui_size.split('x')[0])
work = ROOT / '.test-state' / ('browse-categories-' + args.ui_size)
bundle = work / 'bundle'
bundle.mkdir(parents=True, exist_ok=True)
source, _ = assemble(paths=ORDER[:-1])
source += r'''
let browse_test = {passed: 0 failed: [] category: "all" shown: [] offset: 0 total: 0}
fn browse_assert(passed, label){ if passed { browse_test.passed = browse_test.passed + 1 } else { browse_test.failed.push(label) } }
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    tracking_schedule_check = fn(){}
    let samples = [{title: "合成分类：Claude 大模型支持智能体工作流" source: "36kr" expected: "browse_tech"}
        {title: "合成分类：AI 笔记本显卡评测" source: "36kr" expected: "browse_tech"}
        {title: "合成分类：浏览器笔记工具与效率" source: "sspai" expected: "browse_tech"}
        {title: "合成分类：NASA 月球研究" source: "nasa" expected: "browse_tech"}
        {title: "合成分类：创业企业融资与财报" source: "36kr" expected: "browse_industry"}
        {title: "合成分类：云相册订阅与隐私变化" source: "sspai" expected: "browse_life"}
        {title: "合成分类：hurricane home protection" source: "popsci" expected: "browse_life"}
        {title: "合成分类：AirPods 耳机评测" source: "expreview" expected: "browse_tech"}]
    let rows = []
    for i sample in samples {
        let row = news_normalize({title: sample.title link: "https://www.ithome.com/category-fixture-" + i}, news_source(sample.source), time_now())
        rows.push(row)
        browse_assert(news_browse_matches(row, sample.expected), sample.expected + " recognized")
    }
    browse_assert(news_browse_matches(rows[1], "browse_tech") && news_browse_topics(rows[1]).len() == 1, "AI notebook has one merged technology facet")
    browse_assert(news_browse_matches(rows[7], "browse_tech") && !news_browse_matches(rows[7], "browse_industry"), "AirPods stays in technology")
    browse_assert(news_filter(rows, [], "finance", false, "").len() == 3, "legacy category retains source-based semantics")
    browse_assert(news_filter(rows, [], "browse_tech", false, "notebook").len() == 0, "query combines with category")
    let saved = news_browse_topics(rows[0])
    rows[0].title = "合成分类：家庭隐私设置"
    browse_assert(news_browse_matches(rows[0], "browse_life") && !news_browse_matches(rows[0], "browse_tech"), "changed content invalidates derived category")
    rows[0].title = samples[0].title
    let unknown = news_normalize({title: "合成分类：无明显关键词" link: "https://www.ithome.com/unknown-category"}, news_source("nasa"), time_now())
    browse_assert(news_browse_matches(unknown, "browse_tech"), "source fallback only when no signal")
    app_feed_rows = rows feed_rows_by_source["ithome"] = rows
    render_main()
    start_interval(0.1, || {
        if fs.exists("capacity-input.json") && app_feed_rows.len() == 8 {
            app_feed_rows = fs.read("capacity-input.json").parse_json()
            pick_category("all")
        }
        let titles = [] for row in display_rows { titles.push(row.title) }
        browse_test.category = category browse_test.shown = titles browse_test.offset = feed_page_offset browse_test.total = app_feed_rows.len()
        fs.write("categories-state.json", browse_test.to_json())
    })
})
'''
(bundle / 'main.splash').write_text(source, encoding='utf-8')
data = work / ('data-' + str(time.time_ns()))
(data / 'host').mkdir(parents=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
exe = ensure_native_probe()
state_path = data / 'dev.cfaw.runtime-tests/categories-state.json'

def state_read():
    for _ in range(30):
        try:
            return json.loads(state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            time.sleep(.02)
    raise RuntimeError('Native state report unavailable')

def category_click(label):
    for _ in range(30):
        widgets = json.loads(get('/snap'))['s']
        button = next((w for w in widgets if w.get('ty') == 'Button' and w.get('t') == label and 10 < w['r'][0] + w['r'][2] / 2 < viewport_width - 8), None)
        if button:
            x, y, width, height = button['r']
            get('/click', x=x + width / 2, y=y + height / 2, wait=1)
            return
        get('/m', k='scroll', x=300, y=259, dx=180, dy=0, wait=1)
    raise RuntimeError('Category tab unavailable: ' + label)

def get(route, **params):
    with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as response:
        return response.read()

startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
with (work / 'host.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([str(exe), '--bundle', str(bundle), '--app-data', str(data), '--remote=' + str(port), '--size', args.ui_size],
        cwd=exe.parent, env=dict(os.environ, RINX_DATA_DIR=str(data / 'host')), stdout=log, stderr=log, startupinfo=startup)
    try:
        for _ in range(100):
            if state_path.exists():
                break
            time.sleep(.1)
        initial = state_read()
        assert not initial['failed'], initial
        assert initial['passed'] == 14, initial
        expected = {'科技': ['Claude', 'AI 笔记本', '浏览器', 'NASA', 'AirPods'], '商业': ['融资'], '生活': ['云相册', 'hurricane']}
        for label, markers in expected.items():
            category_click(label)
            for _ in range(30):
                state = state_read()
                if len(state['shown']) == len(markers) and all(any(marker in title for title in state['shown']) for marker in markers):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Incorrect category result: ' + str(state))
            assert state['offset'] == 0 and state['total'] == 8
            (work / ('category-' + state['category'] + '.png')).write_bytes(get('/g', raw=1))
        capacity = []
        headlines = ['Claude 大模型', '笔记本显卡', '浏览器笔记工具', 'NASA 月球研究', '创业企业融资', '家庭隐私订阅']
        for i in range(240):
            url = f'https://www.ithome.com/synthetic-category-capacity-{i}'
            title = '合成容量测试：' + headlines[i % 6] + ' #' + str(i)
            summary = '明确标注的固定输入容量测试。' * 90
            capacity.append(dict(news_id=url, evidence_id=url, content_version=title + '\n' + summary, title=title,
                source='合成容量来源', source_id='ithome', source_url=url, feed_url='https://www.ithome.com/rss',
                category='tech', language='zh', summary=summary, image_url=None, published_at=None, retrieved_at=time.time(),
                evidence_kind='rss_summary', timestamp_kind='published', references=[dict(source_id='ithome', source='合成容量来源', source_url=url, feed_url='https://www.ithome.com/rss')]))
        (state_path.parent / 'capacity-input.json').write_text(json.dumps(capacity, ensure_ascii=False), encoding='utf-8')
        for _ in range(40):
            state = state_read()
            if state['total'] == 240 and state['category'] == 'all' and len(state['shown']) == 240:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Capacity initialization failed: ' + str(state))
        category_click('科技')
        category_click('生活')
        for _ in range(40):
            state = state_read()
            if state['category'] == 'browse_life' and len(state['shown']) == 40 and all(headlines[5] in title for title in state['shown']):
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Rapid switching published stale categories: ' + str(state))
        capacity_expected = {'科技': (160, headlines[:4]), '商业': (40, [headlines[4]]), '生活': (40, [headlines[5]])}
        for label, (count, keywords) in capacity_expected.items():
            category_click(label)
            for _ in range(30):
                state = state_read()
                if len(state['shown']) == count and all(any(word in title for word in keywords) for title in state['shown']):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Capacity category failed: ' + str(state))
        (work / 'report.json').write_text(json.dumps({'checks': initial['passed'], 'tabs_clicked': list(expected), 'synthetic': True, 'capacity_rows': 240, 'capacity_per_category': [160, 40, 40], 'rapid_switch': True, 'viewport': args.ui_size}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        process.terminate()
        process.wait(timeout=5)
assert '[E]' not in (work / 'host.log').read_text(encoding='utf-8', errors='replace')
print((work / 'report.json').read_text(encoding='utf-8'))
