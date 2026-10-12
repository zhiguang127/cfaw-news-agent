"""Native Rinx presentation checks with synthetic records, no accounts or model calls."""
import json
import os
import socket
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from assemble import ROOT, ORDER, assemble
from native_probe import ensure_native_probe


def main():
    work = ROOT / '.test-state/results-visibility'
    bundle = work / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    source, _ = assemble(paths=ORDER[:-1])
    source += '''
start_timeout(0.1, || {
    records_load() schedules_load() topics_load() agent_preferences_load() feed_initialize()
    let row = news_normalize({title: "Synthetic retained Chinese news" link: "https://example.org/retained"},
        {id: "fixture" label: "Synthetic source" kind: "rss" category: "china" language: "zh" url: "https://example.org/feed"}, time_now())
    app_feed_rows = [row]
    records_toggle_bookmark(row)
    enabled_source_ids = ["bbc"]
    news_http_request = fn(url, redirects, callback){ callback({success: false error: "Synthetic source unavailable" category: "network"}) }
    analysis_history = [{analysis_id: "fixture-analysis" news_id: row.news_id outcome: "no_change"
        explanation: "Synthetic archived analysis" created_at: time_now() news_snapshot: row prompt_revision: "obsolete"}]
    suggestion_history = [
        {suggestion_id: "fixture-accepted" analysis_id: "fixture-analysis" news_id: row.news_id state: "accepted" change_summary: "Synthetic archived accepted suggestion"}
        {suggestion_id: "fixture-pending" analysis_id: "fixture-analysis" news_id: row.news_id state: "pending" change_summary: "Synthetic pending suggestion" rationale: "Synthetic pending rationale" uncertainties: [] proposed_action: nil}
    ]
    tracking_cache.runs = [{checked_at: time_now() snapshot: {prompt_revision: "obsolete" topics: [] legacy_interests: [] schedules: []}
        result: {explanation: "Synthetic archived target check" items: [] insights: []}}]
    schedule_actions.items = [{action_id: "fixture-applied" state: "applied" original: {title: "Synthetic archived reschedule"
        start: "2030-10-06T12:00:00+08:00" end: "2030-10-06T13:00:00+08:00" timezone: "Asia/Shanghai"}
        start: "2030-10-06T14:00:00+08:00" end: "2030-10-06T15:00:00+08:00"}]
    let previous = {target_type: "topic" target_id: "fixture-goal" target_version: 1 issue_key: "fixture-terms"
        summary: "上次已知：漫步者 Lolli Spark 正在推进认证，上市日期未确认。" next_step: "Synthetic previous check"}
    tracking_cache.runs.push({task_id: "fixture-comparison" checked_at: time_now() - 60
        snapshot: {prompt_revision: "obsolete" topics: [] schedules: [] legacy_interests: [] evidence: []}
        result: {insights: [previous] items: [] explanation: "Synthetic previous check"}})
    let edifier = {news_id: "edifier-news" title: "漫步者 Lolli Spark 通过 OpenHarmony 认证" summary: "来源摘要：通过认证，上市日期待确认。" source_url: "https://www.ithome.com/1/011/538.htm" retrieved_at: time_now() paragraphs: [] body_error: "正文尚未读取" body_truncated: false}
    let irrelevant = {news_id: "unrelated-news" title: "Estimating suicide risk from text" summary: "Unrelated research" paragraphs: []}
    let edifier_row = news_normalize({title: edifier.title link: edifier.source_url description: edifier.summary},
        {id: "ithome" label: "固定来源" kind: "rss" category: "tech" language: "zh" url: "https://www.ithome.com/rss"}, time_now())
    edifier_row.news_id = edifier.news_id
    edifier_row.body_html = "<p>固定测试原文：耳机已通过认证，上市日期与售价尚未披露。</p>" edifier_row.body_origin = "publisher_rss"
    tracking_current_row = fn(id){ if id == edifier.news_id { return edifier_row } if id == row.news_id { return row } nil }
    article_http_request = fn(url, redirects, callback){
        start_timeout(0.01, || callback({success: true body: "<article><p>固定测试原文：耳机已通过认证，上市日期与售价尚未披露。</p></article>"}))
    }
    let current = {title: "漫步者新品与产品动向跟踪" state: "pending" run: {task_id: "fixture-current" checked_at: time_now()
        result: {items: [{news_id: "edifier-news" relevance: "related" topic_ids: ["fixture-goal"]} {news_id: "unrelated-news" relevance: "unrelated" topic_ids: []}]}
        snapshot: {evidence: [edifier irrelevant] topics: [{topic_id: "fixture-goal" version: 1 purpose: "持续了解漫步者音频产品与功能更新，作为日常参考" preferences: ["先看产品进展，不强行推荐购买"]}]}}
        insight: {target_type: "topic" target_id: "fixture-goal" target_version: 1 issue_key: "fixture-terms" compared_run_id: "fixture-comparison"
            change_kind: "updated" summary: "漫步者 Lolli Spark 已通过 OpenHarmony 认证。目前获得的是认证进展，上市时间与最终售价仍未确认。" material_change: "本期取得了通过 OpenHarmony 认证的消息，仍无上市信息。"
            uncertainties: [] evidence_ids: ["edifier-news"] evidence_refs: [] next_step: "继续跟踪正式发布或上架信息，确认上市时间。" decision_effect: "review"}}
    current.run.ui_fixture_current = true
    // Synthetic presentation fixture; real stale/version guards have separate tests.
    tracking_run_current = fn(run){ run["ui_fixture_current"] == true }
    let handled = current.to_json().parse_json()
    handled.title = "Synthetic handled target" handled.state = "handled" handled.insight.issue_key = "fixture-handled" handled.insight.summary = "Synthetic archived handled change"
    let withdrawn = current.to_json().parse_json()
    withdrawn.title = "Synthetic withdrawn target" withdrawn.state = "withdrawn"
    withdrawn.insight.issue_key = "fixture-withdrawn"
    withdrawn.insight.change_kind = "withdrawn" withdrawn.insight.summary = "Synthetic withdrawn interpretation"
    current_insights = fn(){ [current handled withdrawn] }
    render_main()
    start_timeout(0.1, || refresh())
    start_interval(0.2, || fs.write("record-counts.json", {analyses: analysis_history.len() suggestions: suggestion_history.len()
        runs: tracking_cache.runs.len() actions: schedule_actions.items.len() bookmarks: user_bookmarks.len()}.to_json()))
    start_interval(0.2, || fs.write("plan-state.json", {draft: intent_draft schedules: user_schedules.len() error: intent_error}.to_json()))
    start_interval(0.2, || fs.write("navigation-state.json", {page: page section: tracking_section detail: detail_kind}.to_json()))
    let empty_shown = false
    start_interval(0.2, || {
        if empty_shown || !fs.exists("show-empty-news.txt") { return }
        empty_shown = true
        current.run.result.items[0].relevance = "unrelated" current.run.result.items[0].topic_ids = []
        current.insight.evidence_ids = [] current.insight.evidence_refs = [] current.insight.material_change = ""
        current.insight.change_kind = "unchanged" current.insight.decision_effect = "unknown"
        current.insight.summary = "本期候选没有找到漫步者相关更新，尚不能确认产品是否有新进展。"
        results_tab = "todo" results_expanded = {} ui.results_content.render()
    })
})
'''
    (bundle / 'main.splash').write_text(source, encoding='utf-8', newline='\n')
    executable = ensure_native_probe()
    native = executable.parent
    data = work / ('data-'+str(time.time_ns()))
    (data/'host').mkdir(parents=True)
    env = os.environ.copy(); env['RINX_DATA_DIR'] = str(data/'host')
    sock = socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
    def get(route, **params):
        with urlopen(f'http://127.0.0.1:{port}{route}?'+urlencode(params), timeout=8) as response: return response.read()
    def widgets(): return json.loads(get('/snap'))['s']
    def texts(): return [w.get('t','') for w in widgets() if w.get('ty')!='Splash']
    def find(label=None, ident=None):
        items=widgets(); nav_ids=('feed_tab','tracking_tab','schedule_tab','account_tab')
        limit=860 if ident in nav_ids else min((w['r'][1] for w in items if w.get('i') in nav_ids),default=840)
        return next(w for w in items if w.get('ty')!='Splash' and (label is None or w.get('t')==label) and (ident is None or w.get('i')==ident)
                    and w['r'][3]>0 and 0<=w['r'][1] and w['r'][1]+w['r'][3]<=limit)
    def click(label=None, ident=None):
        x,y,w,h=find(label,ident)['r']; get('/click',x=x+w/2,y=y+h/2,wait=1); time.sleep(.25)
    def seek(label):
        for _ in range(50):
            try: return find(label)
            except StopIteration: get('/m',k='scroll',x=200,y=650,dy=100,wait=1)
        raise AssertionError('Missing visible result: '+label)
    def top(): get('/m',k='scroll',x=200,y=650,dy=-10000,wait=1)
    def nav_state():
        return json.loads((data/'dev.cfaw.runtime-tests/navigation-state.json').read_text(encoding='utf-8'))
    def no_orb():
        assert not any(w.get('ty')!='Splash' and w.get('t')=='AI' for w in widgets()), 'floating orb covers advice or detail content'
    def bottom_navigation():
        tabs=[find(ident=ident) for ident in ('feed_tab','tracking_tab','schedule_tab','account_tab')]
        assert [w.get('t','').split(' ·')[0] for w in tabs]==['首页','关注','日程','我的'],tabs
        assert len({round(w['r'][1]) for w in tabs})==1,tabs
        return tabs
    def orb_above_navigation():
        tabs=bottom_navigation(); orb=find('AI')
        assert orb['r'][1]+orb['r'][3]<=min(w['r'][1] for w in tabs), (orb,tabs)
    def no_archives():
        labels=texts()
        assert not any('历史' in text or 'Synthetic archived' in text or text in ('最近分析','旧版建议记录') for text in labels),labels
    checks=[]
    startup=subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow=0
    with (work/'host.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(executable),'--bundle',str(bundle),'--app-data',str(data),'--remote='+str(port),'--size','430x860'],cwd=native,env=env,stdout=log,stderr=log,startupinfo=startup)
        try:
            for _ in range(100):
                try:
                    if find(ident='status').get('t')=='1 条新闻': break
                except (OSError,StopIteration): pass
                time.sleep(.1)
            else: raise RuntimeError('Fixture feed did not finish refresh')
            time.sleep(.4)
            assert '中文' not in texts()
            assert not any('部分来源暂时不可用' in text for text in texts())
            find('Synthetic retained Chinese news')
            bottom_navigation(); orb_above_navigation()
            (work/'feed.png').write_bytes(get('/g',raw=1))
            checks.append('failed-source refresh completes without partial-source banner; Chinese category absent, article retained')
            click(ident='schedule_tab'); assert nav_state()['page']=='schedule',nav_state()
            bottom_navigation()
            click(ident='account_tab'); find('收藏与阅读偏好'); click('查看收藏')
            assert '中文' not in texts()
            find('Synthetic retained Chinese news')
            assert nav_state()['page']=='saved',nav_state(); bottom_navigation()
            (work/'bookmarks.png').write_bytes(get('/g',raw=1))
            checks.append('four bottom tabs route to schedule and account; saved news is reached through account without removing the bookmark')
            click(ident='tracking_tab'); click(ident='tracking_dynamic_button')
            assert nav_state()['page']=='tracking' and nav_state()['section']=='dynamic',nav_state()
            bottom_navigation(); click(ident='suggestions_button')
            assert nav_state()=={'page':'tracking','section':'suggestions','detail':''},nav_state()
            bottom_navigation(); no_orb(); top()
            seek('相关新闻'); seek('漫步者 Lolli Spark 通过 OpenHarmony 认证'); seek('当前情况')
            seek('漫步者 Lolli Spark 已通过 OpenHarmony 认证。目前获得的是认证进展，上市时间与最终售价仍未确认。'); no_archives()
            assert 'Estimating suicide risk from text' not in texts(), texts()
            (work/'product-overview.png').write_bytes(get('/g',raw=1))
            seek('建议下一步')
            seek('继续跟踪正式发布或上架信息，确认上市时间。')
            assert not any('上次已知：漫步者 Lolli Spark 正在推进认证，上市日期未确认。' in t or '持续了解漫步者音频产品与功能更新，作为日常参考' in t for t in texts())
            top(); find('待办 3'); find('观察 0'); find('记录 1')
            seek('查看判断依据'); click('查看判断依据')
            top(); seek('漫步者 Lolli Spark 已通过 OpenHarmony 认证。目前获得的是认证进展，上市时间与最终售价仍未确认。')
            seek('改变判断的新事实：本期取得了通过 OpenHarmony 认证的消息，仍无上市信息。')
            seek('对应我的目标：持续了解漫步者音频产品与功能更新，作为日常参考')
            seek('上次已知：漫步者 Lolli Spark 正在推进认证，上市日期未确认。')
            (work/'tracking-results.png').write_bytes(get('/g',raw=1))
            seek('查看来源与引用段落'); click('查看来源与引用段落')
            find('新闻详情'); no_orb()
            assert nav_state()=={'page':'tracking','section':'suggestions','detail':'story'},nav_state()
            find('漫步者 Lolli Spark 通过 OpenHarmony 认证')
            (work/'advice-news-detail.png').write_bytes(get('/g',raw=1))
            click('‹ 返回'); no_orb(); bottom_navigation()
            assert nav_state()=={'page':'tracking','section':'suggestions','detail':''},nav_state()
            top(); seek('当前情况')
            checks.append('advice opens its referenced news detail and returning preserves the suggestions section while keeping the orb hidden')
            seek('Synthetic withdrawn interpretation')
            (work/'withdrawn.png').write_bytes(get('/g',raw=1))
            seek('Synthetic pending suggestion'); no_archives(); top()
            checks.append('related news and current situation precede advice; unrelated suicide research excluded; exact previous interpretation and goal unfold on demand; withdrawals remain visible')
            click('记录 1')
            find('Synthetic handled target')
            assert not any(t in ('已处理','不采纳','继续观察') for t in texts()),texts()
            seek('查看判断依据'); click('查看判断依据')
            seek('Synthetic archived handled change')
            top(); click('待办 3'); top(); no_archives()
            checks.append('record tab exposes saved decisions without reopening actions or erasing history')
            seek('把核实安排到日程'); click('把核实安排到日程'); time.sleep(.8)
            plan=json.loads((data/'dev.cfaw.runtime-tests/plan-state.json').read_text(encoding='utf-8'))
            assert plan['draft']['intent_kind']=='schedule' and '继续跟踪正式发布或上架信息，确认上市时间。' in plan['draft']['original_input'],plan
            assert plan['schedules']==0,plan
            (work/'plan-check.png').write_bytes(get('/g',raw=1))
            seek('取消并保留草稿'); click('取消并保留草稿'); time.sleep(.6)
            top(); seek('把核实安排到日程'); click('把核实安排到日程'); time.sleep(.8)
            blocked=json.loads((data/'dev.cfaw.runtime-tests/plan-state.json').read_text(encoding='utf-8'))
            assert blocked['draft']['draft_id']==plan['draft']['draft_id'] and '已有草稿已保留' in blocked['error'],blocked
            assert blocked['schedules']==0,blocked
            seek('取消并保留草稿'); click('取消并保留草稿'); time.sleep(.6)
            checks.append('next check becomes an unsaved schedule draft; existing draft is preserved on repeat entry')
            click(ident='feed_tab'); orb_above_navigation()
            click(ident='tracking_tab'); click(ident='tracking_dynamic_button')
            assert nav_state()['section']=='dynamic',nav_state()
            click(ident='suggestions_button'); no_orb(); bottom_navigation()
            seek('继续跟踪正式发布或上架信息，确认上市时间。'); no_archives()
            get('/m',k='scroll',x=200,y=650,dy=550,wait=1); no_archives()
            (work/'bottom-nav-results.png').write_bytes(get('/g',raw=1))
            counts=json.loads((data/'dev.cfaw.runtime-tests/record-counts.json').read_text())
            assert counts=={'analyses':1,'suggestions':2,'runs':2,'actions':1,'bookmarks':1},counts
            checks.append('returning home restores orb above navigation; dynamic and suggestions switch inline; archives remain excluded and record counts are unchanged')
            (data/'dev.cfaw.runtime-tests/show-empty-news.txt').write_text('fixture',encoding='utf-8')
            time.sleep(.5); top()
            seek('本期未找到与此目标有关的报道，不代表没有产品进展。')
            seek('上次已知：漫步者 Lolli Spark 正在推进认证，上市日期未确认。')
            assert not any('有新依据' in t or 'Estimating suicide risk from text' in t for t in texts()), texts()
            (work/'empty-product-news.png').write_bytes(get('/g',raw=1))
            checks.append('no relevant product news reports no confirmed change and labels last-known situation separately without a foreign source')
        except Exception:
            try:
                (work/'failure-snapshot.json').write_bytes(get('/snap')); (work/'failure.png').write_bytes(get('/g',raw=1))
            except OSError: pass
            raise
        finally:
            try: get('/quit'); process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired): process.terminate();process.wait(timeout=5)
    assert '[E]' not in (work/'host.log').read_text(encoding='utf-8',errors='replace')
    (work/'report.json').write_text(json.dumps({'checks':checks,'records':counts},indent=2),encoding='utf-8')
    print(work)


if __name__=='__main__': main()
