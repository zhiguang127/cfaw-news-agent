"""Drive isolated benchmark apps through Rinx's native test API.

Uses the already configured host. Never reads or changes credentials, models,
normal application records or account settings. Only synthetic benchmark inputs
reach the model. Each reopened VM makes two sequential cold/warm calls.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from test_live_minimax import RinxUI
from assemble import ROOT


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(port, data_dir, rounds):
    ui = RinxUI(port)
    out = ROOT / 'reports/b-delivery'
    out.mkdir(parents=True, exist_ok=True)
    cutoff = time.time()
    reference = int(cutoff)
    progress = {'stage': 'preparing', 'reference_time': reference, 'rounds': rounds,
                'model': 'unchanged existing Rinx host profile', 'inputs': 'explicit synthetic fixtures',
                'host_port': port, 'completed': [], 'failures': []}

    def checkpoint():
        save(out / 'live-benchmark-progress.json', progress)

    def samples(app_id):
        paths = list((data_dir / 'miniapps').glob('*/' + app_id + '/agent_metrics_v1.json'))
        if len(paths) > 1:
            raise RuntimeError('Multiple account stores for benchmark ID; refusing to mix samples')
        if not paths:
            return []
        value = json.loads(paths[0].read_text(encoding='utf-8'))
        return [s for s in value['samples'] if s['started_at'] >= cutoff]

    def leave_app():
        ws = ui.widgets()
        if any(w.get('ty') == 'Label' and w.get('t') == 'cfaw-news' for w in ws):
            ui.control('close')

    def import_app(folder):
        leave_app()
        ws = ui.widgets()
        if not any(w.get('i') == 'import_app' and w.get('ty') == 'Button' for w in ws):
            ui.control('octoscript_apps_button')
        ui.control('import_app')
        ui.fill('path', str(folder))
        ui.control('review')
        ui.control('run')
        ui.wait(lambda w: w.get('ty') == 'Label' and w.get('t', '').startswith('准备就绪；'),
                seconds=30, expected='isolated benchmark ready')

    try:
        for kind in ('parse_intent', 'parse_schedule_intent', 'tracking_update'):
            for variant in ('before', 'after'):
                subprocess.run([sys.executable, str(ROOT / 'scripts/package_agent_benchmark.py'),
                                '--kind', kind, '--variant', variant,
                                '--reference-time', str(reference)], cwd=ROOT, check=True,
                               stdout=subprocess.DEVNULL)
        checkpoint()
        for kind in ('parse_intent', 'parse_schedule_intent', 'tracking_update'):
            for iteration in range(rounds):
                # Alternate each before/after pair to reduce time drift.
                for variant in ('before', 'after'):
                    folder = ROOT / 'build/agent-benchmark' / (variant + '-' + kind) / 'bundle'
                    app_id = json.loads((folder / 'manifest.json').read_text())['id']
                    progress.update(stage='running', task=kind, variant=variant, iteration=iteration + 1)
                    checkpoint()
                    import_app(folder)
                    for call in range(2):
                        count = len(samples(app_id))
                        ui.button('开始下一次真实调用')
                        deadline = time.monotonic() + 210
                        while time.monotonic() < deadline:
                            rows = samples(app_id)
                            if len(rows) > count:
                                break
                            time.sleep(.5)
                        else:
                            raise RuntimeError('No terminal metric after 210 seconds: ' + kind + '/' + variant)
                        sample = rows[-1]
                        progress['completed'].append({'task': kind, 'variant': variant,
                            'iteration': iteration + 1, 'phase': sample['call_phase'],
                            'success': sample['success'], 'seconds': sample['total_seconds']})
                        save(out / f'live-{variant}-{kind}.json', {'samples': rows})
                        checkpoint()
                        print(json.dumps(progress['completed'][-1], ensure_ascii=False), flush=True)
                        if sample.get('error_category') in ('service_unavailable', 'cancelled', 'timeout'):
                            raise RuntimeError('Host cannot complete benchmark: ' + sample['error_category'])
                        # The metric flush follows validation/publication and layout.
                        time.sleep(.25)
                    if kind == 'tracking_update':
                        paths = list((data_dir / 'miniapps').glob('*/' + app_id + '/tracking_results_v1.json'))
                        if len(paths) == 1:
                            (out / f'live-{variant}-tracking-results.json').write_bytes(paths[0].read_bytes())
                    leave_app()
        progress['stage'] = 'complete'
        checkpoint()
        before = [str(out / f'live-before-{k}.json') for k in ('parse_intent','parse_schedule_intent','tracking_update')]
        after = [str(out / f'live-after-{k}.json') for k in ('parse_intent','parse_schedule_intent','tracking_update')]
        subprocess.run([sys.executable, str(ROOT / 'scripts/summarize_agent_benchmark.py'),
                        '--before', *before, '--after', *after, '--same-input-model-environment',
                        '--output', str(out / 'live-benchmark.json')], check=True)
    except Exception as error:
        progress['stage'] = 'failed'
        progress['failures'].append(str(error))
        checkpoint()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--rinx-data-dir', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=5, choices=range(1, 6))
    args = parser.parse_args()
    run(args.port, args.rinx_data_dir, args.rounds)
