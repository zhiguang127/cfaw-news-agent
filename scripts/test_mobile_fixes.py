"""Native UI regression on isolated synthetic news; no accounts or model calls."""
import json
import struct
import zlib
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.request import urlopen
from urllib.parse import urlencode, urlsplit
from assemble import ROOT, ORDER, assemble


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-size', default='430x860', choices=('430x860', '360x860', '800x1050'))
    parser.add_argument('--host', type=Path, help='Existing isolated Rinx render probe (uses resources beside it)')
    parser.add_argument('--image-cards', action='store_true', help='Exercise merged thumbnail and featured-card layout')
    parser.add_argument('--article-url', help='Optional real HTTPS article smoke test, one explicitly granted host')
    args = parser.parse_args()
    network_args = []
    if args.article_url:
        url = urlsplit(args.article_url)
        if url.scheme != 'https' or not url.hostname or url.username or url.port:
            parser.error('Article test requires a plain HTTPS source URL')
        network_args = ['--network-host', url.hostname]
    work = ROOT / ('.test-state/mobile-fixes-' + args.window_size)
    work.mkdir(parents=True, exist_ok=True)
    (work / 'report.json').unlink(missing_ok=True)
    bundle = work / 'bundle'
    bundle.mkdir(exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    start_timeout(0.05, || {
        let one = news_normalize({title: "Synthetic tech bookmark" link: "https://example.org/tech"}, news_source("hn"), time_now())
        let two = news_normalize({title: "Synthetic world bookmark" link: "https://example.org/world"}, news_source("bbc"), time_now())
        app_feed_rows = [one two]
        if user_schedules.len() == 0 {
            let result = schedule_create("项目讨论", "2030-10-06T12:00:00+08:00", "2030-10-06T13:00:00+08:00", "Asia/Shanghai", nil)
            if result.success { schedule_set_status(result.item.schedule_id, result.item.version, "completed") }
        }
        records_toggle_bookmark(one) records_toggle_bookmark(two)
        if topic_records.topics.len() == 0 {
            let draft = topic_new_draft(nil)
            draft.original_input = "Synthetic follow"
            draft.state = "ready"
            draft.understanding = {title: "Synthetic follow" purpose: "Fixture cancellation"
                preferences: [] recall_rules: [{kind: "keyword" value: "Synthetic"}]}
            draft.understanding["scope"] = ["Synthetic"]
            let error = topic_confirm(draft)
            if error != "" { fs.write("fixture-error.txt", error) }
        }
        news_http_request = fn(url, redirects, callback){}
        enabled_source_ids = ["bbc"]
        render_main()
        start_timeout(0.05, || orb_load())
    })
})
'''
    if args.article_url:
        source += '\nlet public_article_request = news_http_request\narticle_http_request = fn(url, redirects, callback){ public_article_request(url, redirects, callback) }\nstart_timeout(0.3, || { let row = news_normalize({title: "Public article smoke" link: ' + json.dumps(args.article_url) + '}, news_source("mit"), time_now()); article_load(row, || fs.write("article-smoke.json", {state: article_state.state error: article_state.error paragraph_count: article_state.paragraphs.len()}.to_json())) })\n'
    if args.image_cards:
        # A local fixed image exercises decoding/layout without network access.
        def png_chunk(kind, payload):
            return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
        rows = b''.join(b'\x00' + bytes([70, 120, 210, 255] if y < 8 else [180, 100, 210, 255]) * 16 for y in range(16))
        png = b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 6, 0, 0, 0)) + png_chunk(b'IDAT', zlib.compress(rows)) + png_chunk(b'IEND', b'')
        source += '\nlet fixed_thumbnail_bytes = "".to_bytes()\nfor value in ' + json.dumps(list(png)) + ' { fixed_thumbnail_bytes.push(value) }\nlet fixed_thumbnail = binary_resource(fixed_thumbnail_bytes)\nnews_thumbnail_resource = fn(url){ fixed_thumbnail }\nstart_timeout(0.5, || { app_feed_rows[0].image_url = "https://ichef.bbci.co.uk/fixed-image.png" if user_bookmarks.len() > 0 { user_bookmarks[0].image_url = "https://ichef.bbci.co.uk/fixed-image.png" } app_feed_rows[1].image_url = "https://unadmitted.example/fixed.png" render_main() })\n'
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    from build_windows_sdf_host import link_rinx_entry
    native = work / 'native'
    native.mkdir(exist_ok=True)
    host = native / 'mobile-probe.exe'
    dev = ROOT / '.dev/vendor'
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    if args.host:
        host = args.host.resolve()
        if not host.is_file(): parser.error('Render probe not found')
        native = host.parent
    else:
        link_rinx_entry(dev, ROOT / 'tests/scenarios/rinx_render_probe.rs', host,
                        lock['toolchain']['rinx_rust_channel'], 'cfaw_mobile_probe')
        for res in ('makepad_widgets/resources', 'rinx/resources'):
            shutil.copytree(dev / 'Rinx/target/release' / res, native / res, dirs_exist_ok=True)
    data = work / ('data-' + str(time.time_ns()))
    (data / 'host').mkdir(parents=True)
    env = os.environ.copy()
    env['RINX_DATA_DIR'] = str(data / 'host')
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    def get(route, **kw):
        with urlopen(f'http://127.0.0.1:{port}{route}?' + urlencode(kw), timeout=8) as r:
            return r.read()
    def widgets():
        return json.loads(get('/snap'))['s']
    def find(ident=None, text=None):
        for attempt in range(10):
            found = next((w for w in widgets() if (ident is None or w.get('i') == ident)
                          and (text is None or w.get('t') == text)), None)
            if found is not None: return found
            if text not in ('恢复', '取消关注'): break
            shell = next(w for w in widgets() if w.get('i') == 'app_shell')['r']
            get('/m', k='scroll', x=shell[0]+shell[2]/2, y=shell[1]+shell[3]-150, dy=180, wait=1)
            time.sleep(.15)
        raise StopIteration(text or ident)
    def click(w):
        # Controls in the editor may need scrolling in a narrow viewport.
        for _ in range(12):
            if w.get('i') in ('menu_button', 'feed_tab', 'schedule_tab', 'intent_close', 'ai_orb') or w.get('t') == '‹ 返回':
                break
            shell = find(ident='app_shell')['r']
            x, y, width, height = w['r']
            if shell[1] + 140 <= y and y + height <= shell[1] + shell[3] - 58:
                break
            direction = 180 if y + height > shell[1] + shell[3] - 58 else -180
            get('/m', k='scroll', x=shell[0]+shell[2]/2, y=shell[1]+shell[3]-120, dy=direction, wait=1)
            time.sleep(.15)
            w = find(text=w.get('t')) if w.get('t') else find(ident=w.get('i'))
        x, y, width, height = w['r']
        get('/click', x=x+width/2, y=y+height/2, wait=1)
        time.sleep(.25)
    checks = []
    with (work / 'host.log').open('w', encoding='utf-8') as log:
        p = subprocess.Popen([str(host), '--bundle', str(bundle), '--app-data', str(data),
                              '--remote=' + str(port), '--size', args.window_size] + network_args, cwd=native, env=env, stdout=log, stderr=log)
        try:
            for _ in range(80):
                try:
                    find(text='Synthetic tech bookmark')
                    break
                except (OSError, StopIteration):
                    time.sleep(.25)
            else:
                raise RuntimeError('Synthetic app did not become ready')
            frame = find(ident='app_shell')['r']
            if args.window_size == '800x1050':
                assert frame[2] > 430, frame
            checks.append({'restored_host_filling_layout': frame})
            if args.image_cards:
                for _ in range(40):
                    try: find(text='今日热点'); break
                    except StopIteration: time.sleep(.25)
                else: raise RuntimeError('Featured image card did not render')
                search = find(ident='search')['r']
                navigation = find(ident='navigation')['r']
                assert search[1] < find(ident='feed_list')['r'][1] < navigation[1]
                assert not any(w.get('t') == '中文' for w in widgets())
                checks.append('merged image-card branch renders; search above feed, navigation below; no Chinese category tab')
                time.sleep(1)
                (work / 'merged-feed.png').write_bytes(get('/g', raw=1))
                click(find(ident='menu_button'))
                click(find(text='我的收藏'))
                assert not any(w.get('t') == '今日热点' for w in widgets())
                assert len([w for w in widgets() if w.get('t') == '查看']) == 2
                (work / 'saved-list.png').write_bytes(get('/g', raw=1))
                checks.append('bookmarks render every article as a regular row without featured section')
                click(find(ident='feed_tab'))
            click(find(ident='schedule_tab'))
            assert not any(w.get('i') == 'refresh_news' or w.get('t') == '主动获取最新新闻' for w in widgets())
            find(text='项目讨论')
            find(text='已完成')
            click(find(text='取消日程'))
            assert not any(w.get('t') in ('项目讨论', '已取消') for w in widgets())
            find(text='暂无日程。添加安排后，Agent 可结合内容与地点分析影响。')
            schedules = json.loads((data / 'dev.cfaw.runtime-tests/schedules_v1.json').read_text(encoding='utf-8'))
            assert schedules['items'][0]['status'] == 'cancelled' and schedules['items'][0]['version'] == 3
            checks.append('schedule page hides news refresh; completed project discussion can be cancelled and versioned')
            click(find(ident='feed_tab'))
            click(find(ident='menu_button'))
            click(find(text='管理关注'))
            find(text='Synthetic follow')
            (work / 'before-pause.json').write_bytes(get('/snap'))
            click(find(text='暂停'))
            (work / 'after-pause.png').write_bytes(get('/g', raw=1))
            find(text='恢复')
            click(find(text='取消关注'))
            assert not any(w.get('t') == 'Synthetic follow' for w in widgets())
            find(text='尚未添加关注。可从新闻条目创建话题草稿，确认范围后保存。')
            topics = json.loads((data / 'dev.cfaw.runtime-tests/topics_v2.json').read_text(encoding='utf-8'))
            assert topics['topics'][0]['status'] == 'cancelled' and topics['topics'][0]['version'] == 3
            checks.append('paused topic can be cancelled; hidden immediately and versioned on disk')
            click(find(text='‹ 返回'))
            top = find(ident='back_to_top')['r']
            assert top[0] > frame[0] + frame[2]/2
            checks.append('return-to-top button is at the bottom right')
            orb = find(ident='ai_orb')['r']
            x, y = orb[0]+36, orb[1]+36
            get('/m', k='down', x=x, y=y, wait=1)
            time.sleep(.1)
            # Real mouse users can drift beyond the native pan threshold while
            # holding. Regression: native hold used to be suppressed forever.
            get('/m', k='move', x=x-12, y=y-2, wait=1)
            time.sleep(.5)
            drag_x = frame[0] + 40
            get('/m', k='move', x=drag_x+10, y=y-130, wait=1)
            time.sleep(.2)
            get('/m', k='move', x=drag_x, y=y-160, wait=1)
            time.sleep(.2)
            get('/m', k='up', x=drag_x, y=y-160, wait=1)
            time.sleep(.4)
            moved = find(ident='ai_orb')['r']
            assert moved[0] < orb[0] and moved[1] < orb[1], (orb, moved)
            assert not any(w.get('i') == 'intent_input' for w in widgets())
            pref = json.loads((data / 'dev.cfaw.runtime-tests/agent_preferences_v1.json').read_text())
            assert pref['orb_x'] == 0 and 0 <= pref['orb_y'] <= 1, pref
            checks.append('mouse jitter before long press, continuous drag, edge snap, no accidental open, persisted position')
            click(find(ident='ai_orb'))
            time.sleep(.6)
            find(ident='intent_close')
            click(find(ident='intent_close'))
            time.sleep(.6)
            assert find(ident='ai_orb')['r'] == moved
            checks.append('short click opens and close returns to moved position')
            click(find(ident='menu_button'))
            click(find(text='我的收藏'))
            click(find(text='科技'))
            time.sleep(.3)
            assert any(w.get('t') == 'Synthetic tech bookmark' for w in widgets())
            assert not any(w.get('t') == 'Synthetic world bookmark' for w in widgets())
            click(find(text='国际'))
            time.sleep(.3)
            assert any(w.get('t') == 'Synthetic world bookmark' for w in widgets())
            assert not any(w.get('t') == 'Synthetic tech bookmark' for w in widgets())
            checks.append('bookmark categories filter independently')
            click(find(ident='feed_tab'))
            click(find(ident='refresh_news'))
            find(text='停止更新')
            click(find(ident='refresh_news'))
            find(text='刷新新闻')
            checks.append('visible refresh starts requests, second click cancels')
            if args.article_url:
                report_path = data / 'dev.cfaw.runtime-tests/article-smoke.json'
                for _ in range(80):
                    if report_path.exists():
                        break
                    time.sleep(.25)
                result = json.loads(report_path.read_text(encoding='utf-8'))
                (work / 'article-smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                checks.append({'live_article_result': result})
            (work / 'screen.png').write_bytes(get('/g', raw=1))
        finally:
            try:
                get('/quit')
            except OSError:
                pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.terminate()
                p.wait(timeout=5)
    with (work / 'restart.log').open('w', encoding='utf-8') as log:
        p = subprocess.Popen([str(host), '--bundle', str(bundle), '--app-data', str(data),
                              '--remote=' + str(port), '--size', args.window_size] + network_args,
                             cwd=native, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    restored = find(ident='ai_orb')['r']
                    if all(abs(a-b) < 1 for a, b in zip(restored, moved)):
                        break
                except (OSError, StopIteration):
                    pass
                time.sleep(.2)
            else:
                raise RuntimeError('Fresh host process did not restore the moved orb')
            checks.append('fresh native process restores saved orb position')
            click(find(ident='schedule_tab'))
            assert not any(w.get('t') in ('项目讨论', '已取消') for w in widgets())
            click(find(ident='feed_tab'))
            click(find(ident='menu_button'))
            click(find(text='管理关注'))
            assert not any(w.get('t') == 'Synthetic follow' for w in widgets())
            checks.append('cancelled schedules and topics stay hidden after native restart')
        finally:
            try:
                get('/quit')
            except OSError:
                pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.terminate()
                p.wait(timeout=5)
    for name in ('host.log', 'restart.log'):
        assert '[E]' not in (work / name).read_text(encoding='utf-8', errors='replace'), name
    (work / 'report.json').write_text(json.dumps({'passed': checks}, ensure_ascii=False, indent=2))
    print(json.dumps(checks, ensure_ascii=False), flush=True)
    print(work)


if __name__ == '__main__':
    run()
