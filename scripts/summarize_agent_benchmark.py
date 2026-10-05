#!/usr/bin/env python3
"""Summarize private-content-free app stage journals; never invent live samples."""
import argparse
import json
from pathlib import Path
from statistics import median

KINDS = ('parse_intent', 'parse_schedule_intent', 'tracking_update')


def summarize(paths):
    samples = []
    for path in paths:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        samples.extend(s for s in value['samples'] if s.get('sample_origin') == 'live_host')
    groups = {}
    for kind in KINDS:
        for phase in ('cold', 'warm'):
            rows = [s for s in samples if s['task_type'] == kind and s.get('call_phase') == phase]
            totals = [r['total_seconds'] for r in rows]
            stages = {stage: median([r[stage] for r in rows]) if rows else None for stage in
                      ('recall_seconds', 'enrichment_seconds', 'session_seconds', 'model_seconds', 'validation_seconds', 'publish_seconds')}
            groups[kind + ':' + phase] = {'count': len(rows), 'enough_samples': len(rows) >= 5,
                'median_seconds': median(totals) if totals else None, 'range_seconds': [min(totals), max(totals)] if totals else None,
                'valid_json_ratio': sum(r.get('valid_json', False) for r in rows) / len(rows) if rows else None,
                'success_ratio': sum(r['success'] for r in rows) / len(rows) if rows else None,
                'stage_medians_seconds': stages}
    return groups


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--after', type=Path, nargs='+', required=True)
    p.add_argument('--before', type=Path, nargs='+')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--same-input-model-environment', action='store_true', help='Attest identical fixtures, model and environment for comparison')
    args = p.parse_args()
    report = {'after': summarize(args.after), 'measured_target': None}
    if args.before:
        report['before'] = summarize(args.before)
        enough = all(g['enough_samples'] for side in ('before', 'after') for g in report[side].values())
        report['measured_target'] = {'eligible': enough and args.same_input_model_environment, 'groups': {}}
        if report['measured_target']['eligible']:
            for group, after in report['after'].items():
                before = report['before'][group]['median_seconds']
                reduction = 1 - after['median_seconds'] / before if before > 0 else None
                report['measured_target']['groups'][group] = {'median_reduction': reduction, 'at_least_20_percent': reduction is not None and reduction >= .2,
                    'quality_preserved': after['valid_json_ratio'] >= report['before'][group]['valid_json_ratio'] and after['success_ratio'] >= report['before'][group]['success_ratio']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
