#!/usr/bin/env python3
"""Configure the real Rinx import form and probe its host-owned MiniMax Agent.

No fixture replies, login bypass or credential arguments. Secrets enter through
MINIMAX_API_KEY, a private key file, the existing Rinx profile, or getpass.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'MiniMax-M3'
BASE_URL = 'https://api.minimax.cn/v1'
FAMILY = 'minimax'
TEST_INTENT = '测试意图：关注开源 Agent 框架的离线部署能力，少看融资新闻。仅用于联调。'
TEST_SCHEDULE = '测试日程：2026年11月3日，美国东部时间下午2点到3点，线上讨论新闻应用。仅用于联调，请整理预览，不要实际保存。'


def read_key(key_file, data_dir):
    key = os.environ.get('MINIMAX_API_KEY', '').strip()
    if not key and key_file:
        key = key_file.read_text(encoding='utf-8').strip()
    if not key:
        profile = data_dir / 'octos/.octos/profiles/_main.json'
        if profile.is_file():
            value = json.loads(profile.read_text(encoding='utf-8'))
            primary = value.get('config', {}).get('llm', {}).get('primary', {})
            if primary.get('family_id') in ('minimax', 'minimax-cn'):
                env_name = primary.get('route', {}).get('api_key_env', 'MINIMAX_API_KEY')
                key = value.get('config', {}).get('env_vars', {}).get(env_name, '')
    if not key:
        key = getpass.getpass('MiniMax API key (hidden, saved only by Rinx): ').strip()
    if not key or key.startswith('keychain:'):
        raise ValueError('Supply MINIMAX_API_KEY or --minimax-key-file containing the actual key')
    return key


def redact(text, key):
    return re.sub(r'sk-(?:api|cp)-[A-Za-z0-9_-]+', '[REDACTED]', text.replace(key, '[REDACTED]'))


def probe_api(key, model=MODEL):
    payload = {'model': model, 'max_completion_tokens': 8192,
               'messages': [{'role': 'user', 'content': 'Connectivity test. Reply with only OCTOS_OK.'}]}
    if model == 'MiniMax-M3.1-Flash-Preview':
        payload['reasoning_effort'] = 'max'
    request = Request(BASE_URL + '/chat/completions', json.dumps(payload).encode(),
                      {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as error:
        # Never write the request, headers or full response body into a report.
        try:
            body = json.loads(error.read(4096))
            detail = body.get('error', {}).get('message', '')
        except (ValueError, AttributeError):
            detail = ''
        raise RuntimeError(redact('MiniMax API HTTP ' + str(error.code) + ': ' + detail, key)) from None
    except URLError:
        raise RuntimeError('MiniMax API connection failed') from None
    choices = result.get('choices') or []
    content = choices[0].get('message', {}).get('content', '') if choices else ''
    if isinstance(content, str):
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
    if content != 'OCTOS_OK':
        code = result.get('base_resp', {}).get('status_code')
        raise RuntimeError('MiniMax returned no expected final text; status=' + str(code))
    return {'model': result.get('model', model), 'reasoning_effort': payload.get('reasoning_effort', 'provider_default'),
            'connected': True, 'usage': result.get('usage', {})}


class RinxUI:
    def __init__(self, port):
        self.endpoint = 'http://127.0.0.1:' + str(port)

    def call(self, route, **params):
        # POST keeps secrets out of URLs and HTTP access logs.
        request = Request(self.endpoint + route, json.dumps(params).encode(),
                          {'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            return response.read()

    def widgets(self):
        return json.loads(self.call('/snap'))['s']

    def wait(self, predicate, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                widgets = self.widgets()
                value = next((w for w in widgets if predicate(w)), None)
                if value:
                    return value
            except (OSError, ValueError):
                pass
            time.sleep(.15)
        raise RuntimeError('Expected Rinx control did not appear within ' + str(seconds) + ' seconds')

    def click(self, widget):
        x, y, width, height = widget['r']
        self.call('/click', x=x + width / 2, y=y + height / 2, wait=True)

    def button(self, text, scroll=False):
        for _ in range(9 if scroll else 1):
            widgets = self.widgets()
            available = next((w for w in widgets if w.get('t') == text and w.get('ty') == 'Button'), None)
            if available:
                self.click(available)
                return
            if scroll:
                window = next(w for w in widgets if w.get('ty') == 'Window')
                x, y, width, height = window['r']
                self.call('/m', k='scroll', x=x + width / 2, y=y + height * .7, dy=300, wait=True)
                time.sleep(.15)
        raise RuntimeError('Rinx button not visible: ' + text)

    def control(self, widget_id):
        self.click(self.wait(lambda w: w.get('i') == widget_id))

    def fill(self, widget_id, value):
        self.click(self.wait(lambda w: w.get('i') == widget_id and w.get('ty') == 'TextInput'))
        self.call('/key', c='KeyA', ctrl=True, wait=True)
        self.call('/text', text=value, wait=True)


def configure_effort(data_dir, model):
    # The pinned Octos does not yet detect M3.1's effort dialect. Its existing
    # supported model_hints override sends max verbatim (Effort would clamp to
    # high). This config belongs to the host, never octos.turn.start payloads.
    path = data_dir / 'octos/.octos/profiles/_main.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    primary = value['config']['llm']['primary']
    if primary['family_id'] != FAMILY or primary['model_id'] != model:
        raise RuntimeError('Rinx did not save the requested MiniMax provider')
    primary['model_hints'] = {'uses_completion_tokens': True}
    if model == 'MiniMax-M3.1-Flash-Preview':
        primary['reasoning_effort'] = 'max'
        primary['model_hints']['reasoning_style'] = 'effort_max_only'
    else:
        primary.pop('reasoning_effort', None)
    tmp = path.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as stream:
        os.chmod(tmp, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
    tmp.replace(path)


def run_live(args):
    data_dir = (args.rinx_data_dir or ROOT / '.local-state/rinx').resolve()
    key = read_key(args.minimax_key_file, data_dir)
    work = ROOT / '.test-state' / ('live-minimax-' + uuid4().hex[:12])
    work.mkdir(parents=True)
    model = args.minimax_model
    test_kind = args.minimax_intent
    test_input = TEST_SCHEDULE if test_kind == 'schedule' else TEST_INTENT
    report = {'model': model, 'base_url': BASE_URL, 'provider': FAMILY,
              'intent_kind': test_kind,
              'api': 'not_run', 'host': 'not_run', 'business': 'not_run'}
    process = None
    try:
        print('Checking MiniMax API: ' + model, flush=True)
        report['api'] = probe_api(key, model)
        print('MiniMax API replied OCTOS_OK.', flush=True)
        if args.minimax_api_only:
            return
        subprocess.run([os.sys.executable, ROOT / 'scripts/package.py'], cwd=ROOT, check=True)
        port = args.rinx_remote_port
        if not port:
            lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
            checkout = ROOT / next(r['relative_checkout'] for r in lock['repositories'] if r['name'] == 'Rinx')
            host = checkout / 'target/release' / ('rinx.exe' if os.name == 'nt' else 'rinx')
            if not host.is_file():
                raise RuntimeError('Build the pinned Rinx first; or supply --rinx-remote-port')
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            env = os.environ.copy()
            env['RINX_DATA_DIR'] = str(data_dir)
            env['ROBRIX_DATA_DIR'] = str(data_dir)
            process = subprocess.Popen([str(host), '--remote', str(port)], cwd=checkout, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def drain_log():
                with (work / 'host.log').open('w', encoding='utf-8') as log:
                    for line in process.stdout:
                        log.write(redact(line, key))
                        log.flush()
            threading.Thread(target=drain_log, daemon=True).start()
        ui = RinxUI(port)
        ui.wait(lambda w: w.get('ty') == 'Window', seconds=45)
        widgets = ui.widgets()
        if any(w.get('t') == 'cfaw-news' for w in widgets if w.get('ty') == 'Label'):
            ui.click(ui.wait(lambda w: w.get('i') == 'close' and w.get('ty') == 'Button'))
            widgets = ui.widgets()
        if not any(w.get('i') == 'local_family' and w.get('ty') == 'TextInput' for w in widgets):
            if not any(w.get('i') == 'import_app' for w in widgets):
                entry = ui.wait(lambda w: w.get('i') in ('octoscript_apps_button', 'discover_mini_apps', 'discover_tab'), seconds=45)
                ui.click(entry)
                if entry.get('i') == 'discover_tab':
                    ui.control('discover_mini_apps')
            ui.control('import_app')
        ui.fill('path', str(ROOT / 'bundle'))
        ui.fill('local_family', FAMILY)
        ui.fill('local_model', model)
        ui.fill('local_base_url', BASE_URL)
        ui.fill('local_key', key)
        ui.control('use_local')
        # The key field is cleared by Rinx before any captures are written.
        configure_effort(data_dir, model)
        ui.control('review')
        ui.control('run')
        ui.wait(lambda w: w.get('t') == 'cfaw-news' and w.get('ty') == 'Label', seconds=30)
        time.sleep(.5)
        report['host'] = 'bundle reviewed and launched through Rinx import UI'
        try:
            (work / 'home.png').write_bytes(ui.call('/g', raw=1))
        except (OSError, HTTPError):
            report['capture'] = 'native screenshot unavailable; UI controls verified'
        print('Rinx filled bundle/provider/model/base URL/key and launched the app.', flush=True)
        # Do not overwrite an existing user draft during a live service test.
        owner = data_dir / 'miniapps'
        drafts = list(owner.glob('*/dev.cfaw.news/topics_v2.json'))
        if any((json.loads(path.read_text(encoding='utf-8')).get('draft') or {}).get('original_input', '').strip() not in ('', TEST_INTENT, TEST_SCHEDULE) or (json.loads(path.read_text(encoding='utf-8')).get('draft') or {}).get('supplement', '').strip() for path in drafts):
            report['business'] = 'skipped: existing user draft preserved'
            print('Existing user draft preserved; intent test skipped.', flush=True)
            return
        # Exercise the real intent adapter and deterministic result validator.
        widgets = ui.widgets()
        entry = next((w for w in widgets if w.get('ty') == 'Button' and (w.get('i') == 'ai_orb' or w.get('t') in ('表达我的意图  ↗', '继续我的意图  ↗'))), None)
        if entry:
            ui.click(entry)
        else:
            ui.control('menu_button')
            ui.button('表达关注 / 继续草稿')
        ui.wait(lambda w: w.get('i') == 'intent_input' and w.get('ty') == 'TextInput')
        ui.button('安排日程' if test_kind == 'schedule' else '关注新闻')
        ui.fill('intent_input', test_input)
        report['stage'] = 'submit_test_intent'
        ui.button('整理我的想法 ↗', scroll=True)
        report['stage'] = 'await_understanding'
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            widgets = ui.widgets()
            if any(w.get('t') == '待确认的理解' for w in widgets if w.get('ty') == 'Label'):
                break
            failure = next((w.get('t') for w in widgets if w.get('ty') == 'Label' and w.get('t', '').startswith(('Octos 请求失败', 'Octos 上下文失败', '意图结果', '理解结果', '模型回复', '请求超时'))), None)
            if failure:
                raise RuntimeError('App rejected the live model reply: ' + failure)
            time.sleep(.25)
        else:
            raise RuntimeError('App intent understanding did not complete within 180 seconds')
        try:
            (work / 'intent-understanding.png').write_bytes(ui.call('/g', raw=1))
        except (OSError, HTTPError):
            report['capture'] = 'native screenshot unavailable; UI controls verified'
        report['business'] = 'real MiniMax ' + test_kind + ' reply accepted by app validator; user confirmation pending'
        report['stage'] = 'discard_test_draft'
        ui.button('丢弃草稿', scroll=True)
        ui.wait(lambda w: w.get('i') == 'search' and w.get('ty') == 'TextInput')
        report['stage'] = 'complete'
        print('Real MiniMax intent understanding passed app validation. Test draft discarded.', flush=True)
    except Exception as error:
        report['error'] = redact(str(error), key)
        raise RuntimeError(report['error']) from None
    finally:
        (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Live test report: ' + str(work / 'report.json'), flush=True)
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def add_arguments(parser):
    parser.add_argument('--live-minimax', action='store_true', help='Real API + Rinx form autofill + intent validation; no fixed model replies')
    parser.add_argument('--minimax-model', choices=('MiniMax-M3', 'MiniMax-M3.1-Flash-Preview'), default=MODEL, help='Default M3; Flash Preview requires account availability')
    parser.add_argument('--minimax-intent', choices=('news', 'schedule'), default='news', help='Validate a real news or schedule understanding, without confirming it')
    parser.add_argument('--minimax-key-file', type=Path, help='Private key file; alternatively MINIMAX_API_KEY or saved Rinx MiniMax profile')
    parser.add_argument('--minimax-api-only', action='store_true', help='Check the real endpoint without opening Rinx')
    parser.add_argument('--rinx-data-dir', type=Path, help='Rinx data directory with an existing Matrix login; default .local-state/rinx')
    parser.add_argument('--rinx-remote-port', type=int, help='Autofill a running Rinx remote endpoint on 127.0.0.1 instead of launching it')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    try:
        run_live(parser.parse_args())
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
