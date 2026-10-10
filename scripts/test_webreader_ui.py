"""Exercise verification routing and a real public page in isolated Windows WebView2."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-root', type=Path, required=True)
    parser.add_argument('--url', default='https://arstechnica.com/security/2026/10/hackers-obtain-counterfeit-tls-certificates-for-google-and-other-large-services/')
    args = parser.parse_args()
    release = args.host_root.resolve() / 'target/release'
    work = ROOT / '.test-state' / ('webreader-' + str(time.time_ns()))
    bundle, native, data, captures = (work / p for p in ('bundle', 'native', 'data', 'captures'))
    for path in (bundle, native, data / 'host', captures): path.mkdir(parents=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    article_http_request = fn(url, redirects, callback){ callback({success: false error: "Synthetic verification fixture" category: "verification"}) }
    let row = news_normalize({title: "Synthetic verification routing — real source page" link: ''' + json.dumps(args.url) + '''}, news_source("ars"), time_now())
    app_feed_rows = [row]
    render_main()
    let verified_headers = news_http_verification({"x-amzn-waf-action": ["captcha"]}) && news_http_verification({"X-Amzn-Waf-Action": ["challenge"]}) && news_http_verification({"cf-mitigated": ["challenge"]}) && !news_http_verification({"cf-mitigated": ["other"]}) && !news_http_verification(nil)
    start_interval(0.2, || fs.write("webreader-state.json", {headers: verified_headers open: original_article_open native_open: ui.original_reader.is_open() detail: detail_kind verification: article_state.requires_verification paragraphs: article_state.paragraphs.len() reading: if reading == nil {""} else {reading.news_id}}.to_json()))
    start_timeout(0.1, || open_story(row))
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = native / 'webreader-probe.exe'
    libs = sorted((release / 'deps').glob('librinx-*.rlib'), key=lambda p: p.stat().st_mtime, reverse=True)
    assert libs, 'Build the host first'
    command = ['rustc', '+1.98.0', '--edition=2024', '-C', 'opt-level=2', '--crate-name', 'cfaw_webreader_probe', '--extern', 'rinx='+str(libs[0]), '-L', 'dependency='+str(release / 'deps'), str(ROOT / 'tests/scenarios/rinx_render_probe.rs'), '-o', str(executable)]
    for output in (release / 'build').glob('*/output'):
        for line in output.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('cargo:rustc-link-search='): command += ['-L', line.split('=', 1)[1]]
    subprocess.run(command, check=True)
    for resource in ('makepad_widgets/resources', 'rinx/resources'): shutil.copytree(release / resource, native / resource)
    env = dict(os.environ, RINX_DATA_DIR=str(data / 'host'), CFAW_WEBREADER_PROBE_DIR=str(captures))
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    def get(route, **params):
        with urlopen(f'http://127.0.0.1:{port}{route}?'+urlencode(params), timeout=8) as response: return response.read()
    def widgets(): return json.loads(get('/snap'))['s']
    def find(text=None, ident=None):
        return next(w for w in widgets() if w.get('ty') != 'Splash' and (text is None or w.get('t') == text) and (ident is None or w.get('i') == ident))
    def click(text=None, ident=None):
        x,y,w,h=find(text, ident)['r']; get('/click', x=x+w/2, y=y+h/2, wait=1); time.sleep(.4)
    def state(): return json.loads((data / 'dev.cfaw.runtime-tests/webreader-state.json').read_text(encoding='utf-8'))
    log_path = work / 'host.log'
    checks = []
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(bundle), '--app-data', str(data), '--remote='+str(port), '--size', '430x860', '--web-reader-test'], cwd=native, env=env, stdout=log, stderr=log)
        try:
            for _ in range(150):
                try:
                    find('如页面提示验证，请完成后继续阅读原文。')
                    initial = state()
                    assert initial['headers'] and initial['open'] and initial['native_open'] and initial['verification'] and initial['paragraphs'] == 0
                    break
                except (OSError, ValueError, StopIteration, AssertionError): time.sleep(.2)
            else: raise RuntimeError('Verification did not route to WebReader')
            checks.append('AWS/Cloudflare challenge headers recognized; ordinary responses rejected; synthetic verification automatically opens original in-app with no fabricated body')
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if list(captures.glob('*.png')) and 'loading=false' in log_path.read_text(errors='replace'): break
                time.sleep(.2)
            else: raise RuntimeError('Real page never rendered; inspect host.log')
            from PIL import Image
            picture = next(captures.glob('*.png'))
            image = Image.open(picture).convert('RGB')
            assert image.width > 250 and image.height > 300, image.size
            assert len(image.resize((100,100)).getcolors(10001)) > 10, 'WebView capture is blank'
            checks.append('real public page completes navigation; native WebView PNG contains rendered content')
            (work / 'app-shell.png').write_bytes(get('/g', raw=1))
            click('‹ 返回')
            closed = state()
            assert not closed['open'] and not closed['native_open'] and closed['reading'] == initial['reading'], closed
            find(ident='original_article')
            checks.append('return closes native page and preserves article')
            click(ident='original_article')
            time.sleep(1)
            assert state()['native_open']
            click('‹ 返回'); click('‹ 返回')
            assert state()['reading'] == '' and not state()['native_open']
            checks.append('reopening works; second return restores feed')
            text = log_path.read_text(encoding='utf-8', errors='replace')
            assert 'Not implemented on this platform: CxOsOp::' not in text
            assert 'open_url: dispatched HTTP(S)' not in text
            assert '[E]' not in text, text[-2000:]
        except Exception:
            try: (work / 'failure-snapshot.json').write_bytes(get('/snap'))
            except OSError: pass
            raise
        finally:
            try: get('/quit'); process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired): process.terminate(); process.wait(timeout=5)
    (work / 'report.json').write_text(json.dumps({'url': args.url, 'checks': checks, 'capture': str(picture), 'captcha_solution': 'not automated or verified'}, indent=2), encoding='utf-8')
    print(work)


if __name__ == '__main__': main()
