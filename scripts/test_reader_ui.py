"""Exercise the illustrated reader in the user's Rinx-main App, isolated from accounts."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
import zlib
from assemble import ROOT, ORDER, assemble
from test_runtime import region_has_ink
from PIL import Image as PillowImage


def paragraph_edges(png, rect, logical_size):
    """Measure actual text ink, not the label's full-width layout rectangle."""
    pixels = PillowImage.open(io.BytesIO(png)).convert('RGB')
    scale = pixels.width / logical_size[0]
    x, y, width, height = rect
    left, right = int(x*scale), int((x+width)*scale)
    bands, current = [], []
    for py in range(max(0,int(y*scale)), min(pixels.height,int((y+height)*scale))):
        ink = [px for px in range(left, right) if max(pixels.getpixel((px,py))) < 120]
        if ink:
            current.append(max(ink))
        elif current:
            bands.append(max(current)); current = []
    if current: bands.append(max(current))
    return [(right-edge)/scale for edge in bands]


def fixture_png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    pixels = b''.join(b'\0' + bytes([20 + y//3, 110, 220, 255])*480 for y in range(240))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 480, 240, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-root', type=Path, required=True)
    parser.add_argument('--window-size', default='430x860', choices=('430x860', '800x1050'))
    parser.add_argument('--article-url', help='Optional real HTTPS article; one explicitly granted hostname')
    parser.add_argument('--open-original', action='store_true', help='Actually click the real article link and verify Windows browser dispatch')
    parser.add_argument('--chinese', action='store_true', help='Use Chinese paragraph fixtures to check inter-character justification')
    args = parser.parse_args()
    release = args.host_root.resolve() / 'target/release'
    work = ROOT / ('.test-state/reader-' + args.window_size + ('-live' if args.article_url else '') + ('-zh' if args.chinese else ''))
    work.mkdir(parents=True, exist_ok=True)
    bundle = work / 'bundle'
    bundle.mkdir(exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    html = '<article><h2>Synthetic section</h2><p>First paragraph before the illustration. This text tests comfortable wrapping on a small screen.</p><img src="/reader-fixture.png" alt="Synthetic illustration for native reader testing"><figcaption>Synthetic image caption</figcaption><p>Second paragraph after the illustration.</p><ul><li>Synthetic list item</li></ul><blockquote>Synthetic quotation</blockquote><img src="https://unapproved.example/tracker.png"></article>'
    first_text = 'First paragraph before the illustration. This text tests comfortable wrapping on a small screen.'
    second_text = 'Second paragraph after the illustration.'
    if args.chinese:
        chinese_first = '这是一段用于验证新闻阅读排版的合成中文内容。两端对齐应使正文每一行的左右边缘整齐，段落最后一行保持自然宽度，同时保留清楚的段落间距，让读者更容易区分不同内容。'
        chinese_second = '这是配图之后的第二段合成文字。'
        html = html.replace(first_text, chinese_first).replace(second_text, chinese_second)
        first_text, second_text = chinese_first, chinese_second
    setup = ''
    if not args.article_url:
        setup = 'let extracted = article_extract(' + json.dumps(html) + ', "https://news.mit.edu/reader-fixture")\nfs.write("extract-check.json", {paragraphs: extracted.paragraphs.len() blocks: extracted.blocks.len() images: extracted.images.len()}.to_json())\n'
        setup += 'article_http_request = fn(url, redirects, callback){ callback({success: true body: ' + json.dumps(html) + '}) }\n'
        setup += 'let fixture_bytes = "".to_bytes()\nfor value in ' + json.dumps([float(b) for b in fixture_png()]) + ' { fixture_bytes.push(value) }\n'
        setup += 'fs.write("bytes-check.json", {length: fixture_bytes.len() a: fixture_bytes[0] b: fixture_bytes[1]}.to_json())\n'
        setup += 'article_image_request = fn(url, callback){ start_timeout(1.0, || callback({success: true bytes: fixture_bytes})) }\n'
    article_url = args.article_url or 'https://news.mit.edu/reader-fixture'
    source += '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    ''' + setup + '''
    let first = news_normalize({title: "Synthetic illustrated article" link: ''' + json.dumps(article_url) + '''}, news_source("mit"), time_now())
    let second = news_normalize({title: "Synthetic unsupported article" link: "https://unsupported.example/no-summary"}, news_source("mit"), time_now())
    app_feed_rows = [first second]
    render_main()
    start_timeout(0.1, || open_story(first))
    start_timeout(2.0, || { let states = [] for image in article_state.images { states.push(image.state) } fs.write("reader-state.json", {state: article_state.state error: article_state.error blocks: article_state.blocks.len() images: states}.to_json()) })
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    native = work / 'native'
    native.mkdir(exist_ok=True)
    executable = native / 'reader-probe.exe'
    libraries = list((release / 'deps').glob('librinx-*.rlib'))
    assert len(libraries) == 1, libraries
    command = ['rustc', '+1.98.0', '--edition=2024', '-C', 'opt-level=2', '--crate-name', 'cfaw_reader_probe', '--extern', 'rinx=' + str(libraries[0]), '-L', 'dependency=' + str(release / 'deps'), str(ROOT / 'tests/scenarios/rinx_render_probe.rs'), '-o', str(executable)]
    for output in (release / 'build').glob('*/output'):
        for line in output.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('cargo:rustc-link-search='):
                command += ['-L', line.split('=', 1)[1]]
    probe_source = ROOT / 'tests/scenarios/rinx_render_probe.rs'
    if not executable.exists() or executable.stat().st_mtime < max(probe_source.stat().st_mtime, libraries[0].stat().st_mtime):
        subprocess.run(command, check=True)
    for resource in ('makepad_widgets/resources', 'rinx/resources'):
        shutil.copytree(release / resource, native / resource, dirs_exist_ok=True)
    data = work / ('data-' + str(time.time_ns()))
    (data / 'host').mkdir(parents=True)
    env = os.environ.copy()
    env['RINX_DATA_DIR'] = str(data / 'host')
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    def get(route, **params):
        with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(params), timeout=8) as response:
            return response.read()
    def widgets():
        return json.loads(get('/snap'))['s']
    def find(text=None, ident=None):
        return next(w for w in widgets() if (text is None or w.get('t') == text) and (ident is None or w.get('i') == ident))
    def click(w):
        x, y, width, height = w['r']
        get('/click', x=x+width/2, y=y+height/2, wait=1)
        time.sleep(.2)
    command = [str(executable), '--bundle', str(bundle), '--app-data', str(data), '--remote='+str(port), '--size', args.window_size]
    if args.article_url:
        url = urlsplit(args.article_url)
        assert url.scheme == 'https' and not url.username and not url.port
        command += ['--network-host', url.hostname]
    checks = []
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=native, env=env, stdout=log, stderr=log)
        try:
            for _ in range(120):
                try:
                    initial = widgets()
                    metadata = next(w['r'] for w in initial if w.get('t') == 'MIT Research · 发布于 时间未知')
                    find(text='来源网页 · 图文阅读模式')
                    column = next(w['r'] for w in initial if w.get('ty') == 'View' and w['r'][:3] == metadata[:3])
                    find(ident='original_article')
                    break
                except (OSError, StopIteration):
                    time.sleep(.25)
            else:
                raise RuntimeError('Reader did not load the article')
            assert column[2] <= 720.1, column
            if args.window_size == '800x1050':
                shell = find(ident='app_shell')['r']
                assert shell[2] > 720 and column[0] > shell[0], (shell, column)
            if args.open_original:
                assert args.article_url, 'Only click a real public article in this test'
                click(find(ident='original_article'))
                assert 'open_url: dispatched HTTP(S) link to default browser' in (work / 'host.log').read_text(encoding='utf-8', errors='replace')
                checks.append('real original link clicked; Windows ShellExecute accepted default browser navigation')
            scroll_amount = 350
            if not args.article_url:
                initial_paragraph = next(w['r'] for w in initial if w.get('t') == first_text)
                scroll_amount = max(0, initial_paragraph[1] - find(ident='story_content')['r'][1] - 14)
            get('/m', k='scroll', x=column[0]+column[2]/2, y=580, dy=scroll_amount, wait=1)
            for _ in range(120):
                try:
                    image = next(w for w in widgets() if w.get('ty') == 'Image' and w['r'][2] > 100 and w['r'][3] > 100)
                    break
                except (OSError, StopIteration):
                    time.sleep(.25)
            else:
                (work / 'failure-snapshot.json').write_bytes(get('/snap'))
                (work / 'failure.png').write_bytes(get('/g', raw=1))
                raise RuntimeError('Reader never displayed a decoded image; inspect host.log')
            if not args.article_url:
                assert abs(image['r'][2]/image['r'][3] - 2) < .02, image
            if not args.article_url:
                first = find(text=first_text)
                second = find(text=second_text)
                assert first['r'][1] < image['r'][1] < second['r'][1]
                assert any(w.get('t') == 'Synthetic section' for w in initial)
                find(text='Synthetic image caption')
                assert len([w for w in widgets() if w.get('ty') == 'Image']) == 1
            time.sleep(.4)
            png = get('/g', raw=1)
            (work / 'reader.png').write_bytes(png)
            if not args.article_url:
                edges = paragraph_edges(png, first['r'], tuple(map(int, args.window_size.split('x'))))
                assert len(edges) >= 2, edges
                assert all(gap < (24 if args.chinese else 8) for gap in edges[:-1]), edges
                assert edges[-1] > 30, edges
                checks.append('actual paragraph ink reaches both edges on wrapped lines; final line remains left aligned')
            image = next(w for w in widgets() if w.get('ty') == 'Image' and w['r'][2] > 100)
            assert region_has_ink(png, image['r'], tuple(map(int, args.window_size.split('x')))), image
            checks.append('decoded source image visible, proportional sizing, bounded centered reader column, original link')
            if not args.article_url:
                get('/m', k='scroll', x=column[0]+column[2]/2, y=580, dy=350, wait=1)
                for label in ('Synthetic list item', 'Synthetic quotation'):
                    find(text=label)
                checks.append('article order, heading, paragraphs, caption, list and quote; unapproved image excluded')
                click(find(text='‹ 返回'))
                buttons = [w for w in widgets() if w.get('t') == '查看' and w.get('ty') != 'Label']
                click(buttons[0])
                click(find(text='‹ 返回'))
                buttons = [w for w in widgets() if w.get('t') == '查看' and w.get('ty') != 'Label']
                click(buttons[1])
                time.sleep(1.2)
                find(ident='original_article')
                find(text='此来源未提供摘要。点击上方“打开图文原文”查看文章和图片。')
                assert not any(w.get('ty') == 'Image' for w in widgets())
                (work / 'fallback.png').write_bytes(get('/g', raw=1))
                checks.append('unsupported empty-summary article has original entry; cancelled old image callback cannot leak into it')
        except Exception:
            (work / 'failure-snapshot.json').write_bytes(get('/snap'))
            (work / 'failure.png').write_bytes(get('/g', raw=1))
            raise
        finally:
            try:
                get('/quit')
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
                process.wait(timeout=5)
    assert '[E]' not in (work / 'host.log').read_text(encoding='utf-8', errors='replace')
    (work / 'report.json').write_text(json.dumps({'host': str(args.host_root), 'article_url': args.article_url, 'checks': checks}, indent=2), encoding='utf-8')
    print(work)


if __name__ == '__main__':
    main()
