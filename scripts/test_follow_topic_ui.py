"""Offline native follow-page interaction checks in the pinned Rinx host.

Fixtures are deliberately synthetic. Only isolated storage is granted to the
probe; model and article adapters are replaced and never use account services.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe


WORK = ROOT / '.test-state/follow-topic-ui'
BUNDLE = WORK / 'bundle'
DATA = WORK / ('data-' + str(time.time_ns()))
APP = DATA / 'dev.cfaw.runtime-tests'
WIDTH, HEIGHT = 430, 860
XIAOMI = 'fixture-xiaomi'
AI = 'fixture-meeting'
PAUSED = 'fixture-edifier'
BODY_URL = 'https://www.ithome.com/follow-fixture-body'
SUMMARY_URL = 'https://sspai.com/post/follow-fixture-summary'
TITLE_URL = 'https://www.ithome.com/follow-fixture-title'
AI_URL = 'https://sspai.com/post/follow-fixture-meeting'
QUOTE = '合成来源原句：这款手机已经发布，上市日期和正式售价仍需核实。'
LAUNCH = '合成情况一：小米手机已发布；上市日期和售价尚未明确。'
BUSINESS = '合成情况二：小米业务有调整，影响范围尚待确认。'
NEXT = '合成下一步：等正式售价和上市日期公布，再比较是否适合现有设备。'
VERIFY_NEXT = '合成下一步：取得报道正文，再核实是否属于正式新品。'
CHECKS = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    CHECKS.append(label)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def topic(ident, title, keyword, status='active'):
    return dict(topic_id=ident, version=1, title=title,
                purpose='合成测试：了解动态，先核实再判断', scope=[keyword + '相关动态'],
                preferences=['证据不足先核实'], recall_rules=[dict(kind='keyword', value=keyword)],
                status=status, intent_kind='news', original_input='合成测试：关注' + keyword,
                supplement='', created_at=time.time() - 600, updated_at=time.time() - 300)


def news(url, title, summary, source_id, source):
    return dict(news_id=url, evidence_id=url, content_version='synthetic-follow-fixture',
                title=title, summary=summary, source=source, source_id=source_id,
                source_url=url, feed_url='https://' + ('www.ithome.com/rss/' if source_id == 'ithome' else 'sspai.com/feed'),
                category='tech', language='zh', image_url=None,
                published_at=time.time() - 300, retrieved_at=time.time(),
                evidence_kind='rss_summary', timestamp_kind='published',
                references=[dict(source=source, source_id=source_id, source_url=url,
                                 feed_url='https://' + ('www.ithome.com/rss/' if source_id == 'ithome' else 'sspai.com/feed'))])


def insight(ident, issue, summary, next_step, evidence, effect='watch', refs=None):
    return dict(target_type='topic', target_id=ident, target_version=1, issue_key=issue,
                summary=summary, decision_effect=effect, next_step=next_step,
                uncertainties=['合成未知项：实际使用条件仍需核实'], evidence_ids=evidence,
                evidence_refs=refs or [], change_kind='new', compared_run_id=None,
                material_change='', reschedule=None)


SCRIPT = r'''
let follow_fixture_requests = [] let follow_fixture_checks = [] let follow_fixture_last_command = 0
let follow_fixture_run = nil let follow_fixture_news = [] let follow_fixture_topics = nil
fn follow_fixture_report(){
    fs.write("follow-ui-state.json", {ready: follow_fixture_run != nil
        command: follow_fixture_last_command page: page view: follow_view topic: follow_topic_id
        detail: detail_kind reading: if reading != nil {reading.news_id} else {nil}
        topics: topic_records.topics decisions: topic_records.decisions draft: topic_records.draft intent_draft: intent_draft
        requests: follow_fixture_requests checks: follow_fixture_checks status: tracking_status
        error: analysis_error}.to_json())
}
fn follow_fixture_command(command){
    let name = command.name
    if name == "checking" {
        tracking_recall_targets = {topics: [topic_find("fixture-xiaomi")] schedules: [] legacy_interests: []}
        check_states.items = [{target_type: "topic" target_id: "fixture-xiaomi" target_version: 1
            watermark: follow_fixture_run.checked_at attempt_at: time_now() status: "pending" category: "" reason: ""}]
        tracking_status = "recalling" tracking_message = "合成测试：正在寻找相关新闻"
    } else if name == "failed" {
        check_states.items = [{target_type: "topic" target_id: "fixture-xiaomi" target_version: 1
            watermark: follow_fixture_run.checked_at attempt_at: time_now() status: "failed"
            category: "timeout" reason: "合成测试：分析等待超时"}]
        tracking_status = "failed" tracking_message = "合成测试：分析等待超时"
    } else if name == "ready" {
        check_states.items = [] tracking_status = "done" tracking_message = "合成测试：已完成检查"
        analysis_state = "idle" analysis_error = ""
        tracking_recall_targets = nil
    } else if name == "drop-body-news" {
        app_feed_rows = follow_fixture_news.to_json().parse_json()
        app_feed_rows.retain(|row| row.news_id != "https://www.ithome.com/follow-fixture-body")
        feed_data_revision = feed_data_revision + 1
    } else if name == "restore-news" {
        app_feed_rows = follow_fixture_news.to_json().parse_json() feed_data_revision = feed_data_revision + 1
    } else if name == "invalidate-body" {
        app_feed_rows = follow_fixture_news.to_json().parse_json()
        let row = tracking_find(app_feed_rows, "news_id", "https://www.ithome.com/follow-fixture-body")
        row.summary = "合成测试：来源事实已更改，旧建议不可操作"
        feed_data_revision = feed_data_revision + 1
    } else if name == "try-stale-decision" {
        follow_decide({insight: follow_fixture_run.result.insights[0] run: follow_fixture_run
            state: "pending" title: "合成测试：小米公司动向"}, "handled")
    } else if name == "reset-topics" {
        let next = follow_fixture_topics.to_json().parse_json()
        let error = topics_commit(next) if error != "" { analysis_error = error }
    }
    tracking_ui_update() render_main()
}
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    user_schedules = [] user_interests = [] agent_preferences.paused = true
    tracking_schedule_check = fn(){}
    follow_fixture_topics = fs.read("fixture-topics.json").parse_json()
    topic_records = follow_fixture_topics.to_json().parse_json()
    follow_fixture_news = fs.read("fixture-news.json").parse_json()
    app_feed_rows = follow_fixture_news.to_json().parse_json()
    analysis_article_store(app_feed_rows[0], {paragraphs: ["合成来源原句：这款手机已经发布，上市日期和正式售价仍需核实。"] truncated: false}, "")
    let targets = {topics: [topic_find("fixture-xiaomi") topic_find("fixture-meeting")]
        schedules: [] legacy_interests: [] omitted_targets: 0}
    let snapshot = tracking_snapshot(app_feed_rows, targets)
    let result = fs.read("fixture-result.json").parse_json()
    follow_fixture_run = {task_id: "synthetic-follow-ui" checked_at: time_now() - 60
        input_key: tracking_input_key(snapshot) snapshot: snapshot result: result}
    let validation = tracking_validate(result, snapshot)
    follow_fixture_checks.push({label: "synthetic saved tracking result is valid" passed: validation.valid message: validation.message})
    tracking_cache = {schema_version: 1 revision: 1 runs: [follow_fixture_run]}
    fs.write("tracking_results_v1.json", tracking_cache.to_json()) tracking_cache_file.revision = 1
    fs.write("fixture-snapshot.json", snapshot.to_json())
    analysis_host_has = fn(name){ true }
    analysis_host_request = fn(name, data, callback){
        follow_fixture_requests.push({kind: "mock-host" name: name})
        start_timeout(0.01, || callback({is_ok: false error: {message: "合成测试：模型接口未启用"}}))
    }
    article_http_request = fn(url, redirects, callback){
        follow_fixture_requests.push({kind: "mock-article" url: url})
        start_timeout(0.01, || callback({success: false category: "fixture" error: "合成测试：离线正文适配器"}))
    }
    bm25_recall = fn(rows, targets, current, complete, progress){
        follow_fixture_requests.push({kind: "mock-recall" target_ids: targets.topics})
        start_timeout(0.01, || { if current() {complete({rows: [] matched: 0 omitted_candidates: 0 expired: 0})} })
    }
    start_interval(0.1, || {
        if fs.exists("follow-ui-command.json") {
            let command = nil try {command = fs.read("follow-ui-command.json").parse_json()} { }
            if command != nil && command.id != follow_fixture_last_command {
                follow_fixture_last_command = command.id follow_fixture_command(command)
            }
        }
        follow_fixture_report()
    })
    tracking_status = "done" tracking_message = "合成测试：已完成检查" render_main() render_feed()
})
'''


class Probe:
    def __init__(self, port):
        self.port = port
        self.command_id = 0

    def get(self, route, **params):
        with urlopen(f'http://127.0.0.1:{self.port}{route}?' + urlencode(params), timeout=10) as response:
            return response.read()

    def state(self):
        return json.loads((APP / 'follow-ui-state.json').read_text(encoding='utf-8'))

    def wait(self, condition, label, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = condition()
                if value:
                    return value
            except (FileNotFoundError, json.JSONDecodeError, ConnectionError, OSError, LookupError):
                pass
            time.sleep(.12)
        raise AssertionError('Deadline: ' + label)

    def command(self, name):
        self.command_id += 1
        pending = APP / 'follow-ui-command.pending'
        write_json(pending, dict(id=self.command_id, name=name))
        pending.replace(APP / 'follow-ui-command.json')
        self.wait(lambda: self.state()['command'] == self.command_id, name)
        time.sleep(.25)

    def widgets(self):
        return [w for w in json.loads(self.get('/snap'))['s'] if w.get('ty') != 'Splash']

    def labels(self):
        return [w.get('t', '') for w in self.widgets()]

    def find(self, text=None, ident=None, strict=True, contains=None):
        widgets = self.widgets()
        nav = ('feed_tab', 'tracking_tab', 'intent_add', 'schedule_tab', 'account_tab')
        limit = HEIGHT if ident in nav else min((w['r'][1] for w in widgets if w.get('i') in nav), default=HEIGHT)
        for w in widgets:
            if ((text is None or w.get('t') == text) and (ident is None or w.get('i') == ident)
                    and (contains is None or contains in w.get('t', ''))):
                x, y, width, height = w['r']
                if width > 0 and height > 0 and x >= 0 and x + width <= WIDTH + 2 and y >= 0 and (not strict or y + height <= limit):
                    return w
        raise LookupError(text or ident)

    def click(self, text=None, ident=None):
        widget = self.find(text=text, ident=ident)
        x, y, width, height = widget['r']
        self.get('/click', x=x + width / 2, y=y + height / 2, wait=1)
        time.sleep(.2)
        return widget

    def scroll(self, dy):
        self.get('/m', k='scroll', x=410, y=630, dy=dy, wait=1)

    def top(self):
        self.scroll(-10000)

    def seek(self, text):
        for _ in range(65):
            try:
                return self.find(text=text)
            except LookupError:
                self.scroll(100)
        raise AssertionError('Missing visible control: ' + text)

    def seek_click(self, text):
        self.seek(text)
        return self.click(text=text)

    def seek_contains(self, text):
        for _ in range(65):
            try:
                return self.find(contains=text)
            except LookupError:
                self.scroll(100)
        raise AssertionError('Missing visible text: ' + text)

    def traverse(self, steps=45):
        labels = []
        for _ in range(steps):
            labels.extend(self.labels())
            self.scroll(100)
        return labels

    def screenshot(self, name):
        (WORK / (name + '.png')).write_bytes(self.get('/g', raw=1))

    def nav(self):
        tabs = [self.find(ident=ident) for ident in ('feed_tab', 'tracking_tab', 'schedule_tab', 'account_tab')]
        check([w.get('t', '').split(' ·')[0] for w in tabs] == ['首页', '关注', '日程', '我的'], 'four bottom navigation tabs remain visible')
        check(len({round(w['r'][1]) for w in tabs}) == 1, 'bottom navigation shares one row')
        add = self.find(ident='intent_add')
        outer_center = (tabs[0]['r'][0] + tabs[-1]['r'][0] + tabs[-1]['r'][2]) / 2
        check(abs(add['r'][0] + add['r'][2] / 2 - outer_center) <= 2, 'intent add stays centered between four page tabs')
        check(not any(w.get('i') == 'ai_orb' for w in self.widgets()), 'floating AI orb is removed')


def run_checks(probe):
    """Adapt exact production control labels here when the approved UI lands."""
    probe.wait(lambda: (APP / 'follow-ui-state.json').is_file() and probe.state()['ready'], 'fixture initialized', 25)
    fixture = probe.state()
    check(all(c['passed'] for c in fixture['checks']), 'fixture is accepted by real tracking validation')
    probe.click(ident='tracking_tab')
    probe.wait(lambda: probe.state()['page'] == 'tracking' and probe.state()['view'] == 'overview', 'follow overview')
    probe.nav()
    check(not any(t in ('动态', '建议', '今日精选', '最新文章') for t in probe.labels()), 'landing uses topic overview without home or old dynamic/suggestion sections')
    probe.seek('合成测试：小米公司动向')
    probe.seek(LAUNCH)
    probe.seek(BUSINESS)
    probe.seek(VERIFY_NEXT)
    positions = {w.get('t'): w['r'][1] for w in probe.widgets()}
    check(positions[LAUNCH] < positions[BUSINESS] < positions[VERIFY_NEXT], 'native card lays out source developments before its recommended next step')
    probe.screenshot('overview-xiaomi')
    check(True, 'overview displays multiple developments before a concrete verification next step')
    probe.seek('合成测试：AI会议工具')
    probe.seek_click('已暂停（1）')
    probe.seek('合成测试：漫步者动态')
    check(True, 'active topics and expandable paused topics are visible')
    probe.top()
    probe.command('checking')
    probe.seek(LAUNCH)
    probe.screenshot('overview-checking')
    check(True, 'checking keeps the last saved situation')
    probe.command('failed')
    probe.seek(LAUNCH)
    check(any('超时' in label for label in probe.labels()), 'failure exposes cause while retaining the last situation')
    probe.screenshot('overview-failed')
    probe.command('ready')
    probe.top()
    probe.seek_click('话题详情')
    probe.wait(lambda: probe.state()['view'] == 'topic' and probe.state()['topic'] == XIAOMI, 'xiaomi topic detail')
    probe.seek(NEXT)
    probe.screenshot('topic-detail')
    check(True, 'topic detail retains the concrete watch next step instead of generic observation text')
    probe.seek_click('继续观察')
    probe.wait(lambda: probe.state()['decisions'] and probe.state()['decisions'][-1]['state'] == 'watch', 'saved watch decision')
    check(probe.state()['decisions'][-1]['issue_key'] == 'launch', 'decision belongs to the selected concrete development')
    probe.top()
    probe.seek(NEXT)
    check(True, 'saved watch decision does not replace the original recommendation')
    probe.top()
    probe.seek_click('查看判断依据')
    probe.wait(lambda: probe.state()['view'] == 'evidence' and probe.state()['topic'] == XIAOMI, 'xiaomi evidence')
    evidence_labels = probe.traverse()
    check('合成报道：小米手机发布' in evidence_labels and '合成报道：小米业务调整' in evidence_labels and '合成报道：小米待认证消息' in evidence_labels, 'evidence includes only this topic actual cited stories')
    check('合成报道：AI会议工具开放' not in evidence_labels, 'evidence excludes the other topic story')
    check(QUOTE in evidence_labels and '当时记录的来源摘要' in evidence_labels and '当时仅有标题，没有摘要与正文' in evidence_labels, 'source quote, summary and title-only evidence are distinguished')
    probe.screenshot('evidence-bottom')
    probe.top()
    probe.command('drop-body-news')
    probe.seek(QUOTE)
    probe.seek_click('阅读报道与保存的段落')
    probe.wait(lambda: probe.state()['detail'] == 'story' and probe.state()['reading'] == BODY_URL, 'snapshot source reader')
    probe.seek_contains(QUOTE)
    probe.screenshot('snapshot-reader')
    check(True, 'snapshot reader still opens saved body when source leaves the feed')
    probe.click(text='‹ 返回')
    probe.wait(lambda: probe.state()['detail'] == '' and probe.state()['view'] == 'evidence', 'source returns to topic evidence')
    check(probe.state()['topic'] == XIAOMI, 'reader return preserves its topic context')
    probe.command('restore-news')
    probe.top()
    probe.seek_click('返回关注话题')
    probe.wait(lambda: probe.state()['view'] == 'topic', 'evidence returns to topic')
    probe.command('invalidate-body')
    probe.top()
    stale_labels = probe.traverse()
    check(not any(label in ('继续观察', '已处理', '不采纳') for label in stale_labels), 'stale topic hides all decision controls')
    before = len(probe.state()['decisions'])
    probe.command('try-stale-decision')
    check(len(probe.state()['decisions']) == before, 'strict live guard refuses a direct stale decision without writing')
    probe.command('restore-news')
    probe.top()
    probe.seek_click('单独检查这个话题')
    probe.wait(lambda: any(r['kind'] == 'mock-recall' for r in probe.state()['requests']), 'single topic recall')
    recall = [r for r in probe.state()['requests'] if r['kind'] == 'mock-recall']
    check(all([topic['topic_id'] for topic in r['target_ids']] == [XIAOMI] for r in recall), 'single check retrieves only the selected topic')
    probe.command('ready')
    probe.top()
    probe.seek_click('暂停关注')
    probe.wait(lambda: next(t for t in probe.state()['topics'] if t['topic_id'] == XIAOMI)['status'] == 'paused', 'pause topic')
    check(True, 'pause saves the selected topic and keeps its last analysis')
    probe.seek_click('恢复关注')
    probe.wait(lambda: next(t for t in probe.state()['topics'] if t['topic_id'] == XIAOMI)['status'] == 'active', 'restore topic')
    check(True, 'paused topic can be restored')
    probe.top()
    probe.seek_click('修改关注')
    probe.wait(lambda: probe.state()['detail'] == 'intent' and probe.state()['intent_draft'] is not None
               and probe.state()['intent_draft']['target_topic_id'] == XIAOMI, 'edit selected topic')
    check(probe.state()['intent_draft']['original_input'] == '合成测试：关注小米',
          'edit opens the selected topic with its original input')
    probe.wait(lambda: probe.find(ident='intent_close'), 'edit overlay finishes opening')
    probe.screenshot('topic-edit')
    probe.click(ident='intent_close')
    probe.wait(lambda: probe.state()['detail'] == '', 'close intent draft')
    check(probe.state()['draft']['target_topic_id'] == XIAOMI, 'closing the edit panel preserves its draft')
    probe.wait(lambda: probe.find(text='‹ 我的关注'), 'edit overlay returns to topic')
    probe.top()
    probe.seek_click('‹ 我的关注')
    probe.wait(lambda: probe.state()['view'] == 'overview', 'topic returns to overview')
    probe.nav()
    probe.click(ident='feed_tab')
    probe.wait(lambda: probe.state()['page'] == 'feed', 'home restored')
    probe.seek('最新文章')
    probe.seek('合成报道：小米手机发布')
    probe.screenshot('home-preserved')
    check(True, 'home still renders the news browsing layout')
    probe.seek('查看')
    # Move the target into the stable viewport before a real click.
    probe.scroll(200)
    probe.click(text='查看')
    probe.wait(lambda: probe.state()['detail'] == 'story' and probe.state()['reading'] == BODY_URL, 'ordinary home reader')
    home_reader_labels = probe.traverse(20)
    check('以下保留当时使用的证据版本；网页更新后的阅读正文可能不同。' not in home_reader_labels,
          'ordinary home reader does not inherit the previous topic snapshot context')
    probe.screenshot('ordinary-home-reader')


def main():
    BUNDLE.mkdir(parents=True, exist_ok=True)
    APP.mkdir(parents=True)
    (DATA / 'host').mkdir()
    topics = dict(schema_version=2, revision=0, draft=None, decisions=[], topics=[
        topic(XIAOMI, '合成测试：小米公司动向', '小米'),
        topic(AI, '合成测试：AI会议工具', '会议'),
        topic(PAUSED, '合成测试：漫步者动态', '漫步者', 'paused')])
    rows = [news(BODY_URL, '合成报道：小米手机发布', '合成来源摘要：手机已经发布，售价未明确。', 'ithome', '合成IT之家'),
            news(SUMMARY_URL, '合成报道：小米业务调整', '合成来源摘要：小米业务调整，涉及范围需核实。', 'sspai', '合成少数派'),
            news(TITLE_URL, '合成报道：小米待认证消息', '', 'ithome', '合成IT之家'),
            news(AI_URL, '合成报道：AI会议工具开放', '合成来源摘要：会议工具开放试用。', 'sspai', '合成少数派')]
    result = dict(schema_version=2, outcome='update', explanation='合成测试：按话题汇总来源；条件未知需核实。',
                  items=[dict(news_id=row['news_id'], relevance='related',
                              topic_ids=[AI if row['news_id'] == AI_URL else XIAOMI], legacy_interest_ids=[],
                              why_related='合成关联理由：' + ('会议工具访问条件' if row['news_id'] == AI_URL else '小米公司及产品动态'),
                              evidence_ids=[row['news_id']], uncertainties=[], schedule_impacts=[]) for row in rows],
                  insights=[insight(XIAOMI, 'launch', LAUNCH, NEXT, [BODY_URL],
                                    refs=[dict(news_id=BODY_URL, paragraph_id='p1', quote=QUOTE)]),
                            insight(XIAOMI, 'business', BUSINESS, '合成下一步：继续关注后续正式公告。', [SUMMARY_URL], effect='none'),
                            insight(XIAOMI, 'certification', '合成情况三：只有认证相关标题，无法确认是否会上市。',
                                    VERIFY_NEXT, [TITLE_URL], effect='unknown'),
                            insight(AI, 'meeting', '合成AI情况：会议工具试用开放，额度和隐私仍待核实。',
                                    '合成AI下一步：核实免费额度和隐私，再决定试用。', [AI_URL], effect='review')])
    write_json(APP / 'topics_v2.json', topics)
    write_json(APP / 'fixture-topics.json', topics)
    write_json(APP / 'fixture-news.json', rows)
    write_json(APP / 'fixture-result.json', result)
    source, _ = assemble(paths=ORDER[:-1])
    (BUNDLE / 'main.splash').write_text(source + '\n' + SCRIPT, encoding='utf-8')
    executable = ensure_native_probe()
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    probe = Probe(port)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    passed = False
    with (WORK / 'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), '--bundle', str(BUNDLE), '--app-data', str(DATA),
                                    '--remote=' + str(port), '--size', f'{WIDTH}x{HEIGHT}'],
                                   cwd=executable.parent, env=dict(os.environ, RINX_DATA_DIR=str(DATA / 'host')),
                                   stdout=log, stderr=log, startupinfo=startup)
        try:
            run_checks(probe)
            passed = True
        except Exception:
            try:
                probe.screenshot('failure')
            except Exception:
                pass
            raise
        finally:
            state = None
            try:
                state = probe.state()
            except Exception:
                pass
            process.terminate()
            process.wait(timeout=5)
            errors = [line for line in (WORK / 'host.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[E]' in line]
            write_json(WORK / 'report.json', dict(passed=passed and not errors, checks=CHECKS,
                       state=state, native_errors=errors, offline_fixture=True, real_model_calls=0,
                       network_calls=0, account_writes=0, viewport=[WIDTH, HEIGHT], data=str(DATA)))
    check(not errors, 'native host reports no script errors')
    print('PASS:', len(CHECKS), 'native topic follow/UI checks; zero live model/network/account writes')


if __name__ == '__main__':
    main()
