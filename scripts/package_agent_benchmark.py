#!/usr/bin/env python3
"""Build isolated before/after apps that make real host calls on fixed inputs.

No credentials, mocked replies or domain writes to the normal application.
Each explicit Start runs one call, capped at two per instance; reopen five times.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
from assemble import ROOT, ORDER, assemble


def string(value):
    return json.dumps(value, ensure_ascii=False)


def build(kind, variant, reference):
    source, _ = assemble(paths=ORDER[:-1])
    prompts = (ROOT / 'src/agent/prompts/tracking.splash').read_text(encoding='utf-8')
    names = {'parse_intent': 'intent_prompt', 'parse_schedule_intent': 'schedule_intent_prompt', 'tracking_update': 'tracking_prompt'}
    prompt = json.loads(re.search(r'^let ' + names[kind] + r' = (.*)$', prompts, re.M).group(1))
    if variant == 'before':
        prompt = prompt.replace('This is a separate task: use only the current INPUT/SNAPSHOT, ignore unrelated earlier turns. ', '')
        if kind == 'tracking_update':
            prompt = (ROOT / 'tests/fixtures/tracking-prompt-baseline.txt').read_text(encoding='utf-8')
    understanding = json.loads((ROOT / 'tests/fixtures/tracking-intent-ready.json').read_text(encoding='utf-8'))['understanding']
    topic = dict(understanding, topic_id='benchmark-goal', version=1, intent_kind='goal', status='active', original_input='固定验证输入：选开源 Agent 框架，关注离线部署，少看融资新闻', supplement='', created_at=reference, updated_at=reference)
    schedule = {'schedule_id': 'benchmark-trip', 'version': 1, 'title': '固定验证输入：上海行程', 'content': '需核对交通安排', 'location': '上海', 'start': '2026-11-03T09:00:00+08:00', 'end': '2026-11-03T18:00:00+08:00', 'timezone': 'Asia/Shanghai', 'status': 'active', 'allow_reschedule': False, 'time_precision': 'exact'}
    revision = 'tracking-v1.2' if variant == 'before' else 'tracking-v2.0'
    setup = f'''\ntracking_prompt_revision = {string(revision)}
let benchmark_kind = {string(kind)}
let benchmark_prompt = {string(prompt)}
let benchmark_variant = {string(variant)}
let benchmark_reference = {reference}
let benchmark_topic = {string(topic)}.parse_json()
let benchmark_schedule = {string(schedule)}.parse_json()
let benchmark_snapshot = nil let benchmark_text = "" let benchmark_calls = 0 let benchmark_status = "尚未开始；固定测试输入，调用真实宿主模型"
'''
    # JSON objects use the native JSON parser, not the Splash object literal DSL.
    setup = setup.replace(string(topic) + '.parse_json()', string(json.dumps(topic, ensure_ascii=False)) + '.parse_json()')
    setup = setup.replace(string(schedule) + '.parse_json()', string(json.dumps(schedule, ensure_ascii=False)) + '.parse_json()')
    harness = '''
fn benchmark_initialize(){
    agent_metrics_load()
    topic_records.topics = [benchmark_topic] user_schedules = [benchmark_schedule]
    if benchmark_kind == "parse_intent" {
        benchmark_snapshot = {intent_kind: "goal" original_input: benchmark_topic.original_input supplement: "" current_topic: nil previous_question: "" prompt_revision: tracking_prompt_revision}
    } else if benchmark_kind == "parse_schedule_intent" {
        benchmark_snapshot = {intent_kind: "schedule" original_input: "固定验证输入：2026年11月3日北京时间14点到15点线上讨论新闻应用" supplement: "" current_topic: nil previous_question: "" timezone: "Asia/Shanghai" reference_now: "2026-10-05T00:00:00Z" reference_date: "2026-10-05" prompt_revision: schedule_intent_prompt_revision}
    } else {
        let row = news_normalize({title: "固定验证输入：开源 Agent 离线部署更新" summary: "发布本地部署支持，需核对机器内存与资源条件。" link: "https://example.invalid/benchmark/agent"}, news_sources[0], benchmark_reference)
        row.published_at = benchmark_reference app_feed_rows = [row]
        analysis_article_store(row, {paragraphs: ["固定验证输入：该 Agent 框架支持本地部署，资源要求应按官方安装文档核对。"] truncated: false}, "")
        benchmark_snapshot = tracking_snapshot([row], {topics: [benchmark_topic] schedules: [] legacy_interests: [] omitted_targets: 0})
        // Fix acquisition time as well as article data for a same-input pair.
        benchmark_snapshot.evidence[0].body_retrieved_at = benchmark_reference
    }
    let payload = benchmark_snapshot
    if benchmark_kind == "tracking_update" {
        payload = tracking_prompt_snapshot(benchmark_snapshot)
        if benchmark_variant == "before" {
            payload = benchmark_snapshot.to_json().parse_json()
            payload.previous_by_target = nil
            for e in payload.evidence { e.paragraphs = nil e.body_key = nil e.body_error = nil e.body_retrieved_at = nil }
        }
    }
    benchmark_text = benchmark_prompt + payload.to_json()
    benchmark_status = "准备就绪；点击后执行两次真实调用，不确认真实关注或日程"
    ui.benchmark_panel.render()
}
fn benchmark_run(){
    if analysis_busy || analysis_needs_reopen { return }
    if benchmark_calls >= 2 { benchmark_status = "本次两次调用完成；关闭此验证应用后重新打开以取得下一组冷/热样本" ui.benchmark_panel.render() return }
    benchmark_calls = benchmark_calls + 1
    if benchmark_kind == "tracking_update" { tracking_started_at = time_now() tracking_recall_seconds = 0 tracking_enrichment_seconds = 0 }
    benchmark_status = "真实调用 " + benchmark_calls + "/2；等待模型返回"
    let error = agent_task_start(benchmark_kind, benchmark_snapshot, benchmark_text, || true, fn(reply){
        benchmark_status = if reply.success {"结构与引用校验通过"} else {reply.category + "：" + reply.error}
        if reply.success && benchmark_kind == "tracking_update" {
            let error = tracking_publish(benchmark_snapshot, tracking_input_key(benchmark_snapshot), reply.result, reply.task_id)
            if error != "" { benchmark_status = error analysis_state = "failed" analysis_error_category = "storage_error" }
        }
        ui.benchmark_panel.render()
    })
    if error != "" { benchmark_status = error }
    ui.benchmark_panel.render()
}
// Use the normal app widgets so host services, task budget and storage quotas
// remain the actual application boundary. Only fixed input data is synthetic.
fn benchmark_show(){
    records_load() feed_initialize() weather_initialize() weather_app_ready = true
    render_main() show_analysis_results()
    start_timeout(0.02, || benchmark_initialize())
}
start_timeout(0.05, || benchmark_show())
'''
    # Add a stable panel to the existing results page; no unsupported native APIs.
    anchor = '        Section{text: "本轮目标变化"}'
    panel = '''        benchmark_panel := View{width: Fill height: Fit flow: Down spacing: 8 on_render: || {
            Section{text: "真实模型固定输入验证"}
            Small{text: benchmark_kind + " / " + benchmark_variant}
            Text{text: benchmark_status}
            Primary{text: "开始下一次真实调用" on_click: || benchmark_run()}
            SecondaryButton{text: "停止本次调用" on_click: || agent_task_stop("cancelled", "验证已停止", "cancelled")}
        }}
'''
    # Definitions must exist before the UI is evaluated, while execution waits
    # until widget references are mounted.
    insertion = source.index('// BEGIN src/frontend/styles.splash')
    source = source[:insertion] + setup + harness.replace('start_timeout(0.05, || benchmark_show())', '') + source[insertion:]
    source = source.replace(anchor, panel + anchor, 1) + '\nstart_timeout(0.05, || benchmark_show())\n'
    folder = ROOT / 'build/agent-benchmark' / (variant + '-' + kind)
    bundle = folder / 'bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / 'main.splash').write_text(source, encoding='utf-8')
    manifest = json.loads((ROOT / 'bundle/manifest.json').read_text())
    manifest['id'] = 'dev.cfaw.benchmark.' + variant + '.' + kind.replace('_', '-')
    manifest['name'] = 'CFAW fixed-input benchmark ' + variant + ' ' + kind
    manifest['network']['hosts'] = []
    manifest['integrity']['bundle_blake3'] = ''
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    hub = Path(os.environ.get('OCTO_HUB', str(ROOT / '.dev/vendor/OctoSense-App-Hub/target/release/hub.exe')))
    if not hub.is_file():
        raise SystemExit('Set OCTO_HUB to an available bundle stamp tool')
    subprocess.run([str(hub), 'stamp', str(bundle)], check=True)
    archive_path = folder / 'benchmark.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in bundle.iterdir():
            archive.write(path, 'bundle/' + path.name)
        for name in ('LICENSE', 'NOTICE'):
            archive.write(ROOT / name, name)
    print(archive_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('parse_intent', 'parse_schedule_intent', 'tracking_update'), required=True)
    parser.add_argument('--variant', choices=('before', 'after'), required=True)
    parser.add_argument('--reference-time', type=float, required=True, help='Use the same recent Unix timestamp for before and after; tracking input expires after 2h')
    args = parser.parse_args()
    build(args.kind, args.variant, args.reference_time)
