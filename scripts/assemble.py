#!/usr/bin/env python3
"""Assemble ordered OctoScript sources for the host's single Splash entry."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ORDER = [
    'src/app/config.splash',
    'src/contracts/news.splash',
    'src/contracts/weather.splash',
    'src/contracts/holiday.splash',
    'src/contracts/fx.splash',
    'src/data/ingestion/sources.json',
    'src/data/ingestion/cities.json',
    'src/data/ingestion/normalize.splash',
    'src/data/storage/records.splash',
    'src/data/storage/schedules.splash',
    'src/data/storage/schedule_time.splash',
    'src/data/storage/weather.splash',
    'src/data/retrieval/interests.splash',
    'src/data/ingestion/http.splash',
    'src/data/ingestion/feeds.splash',
    'src/data/ingestion/weather.splash',
    'src/data/ingestion/holidays.splash',
    'src/data/ingestion/fx.splash',
    'src/agent/context.splash',
    'src/agent/history.splash',
    'src/agent/results/feed_hint.splash',
    'src/agent/results/validator.splash',
    'src/agent/results/change.splash',
    'src/agent/runtime/connectivity.splash',
    'src/agent/runtime/analysis.splash',
    'src/app/controller.splash',
    'src/app/feed_presentation.splash',
    'src/app/weather.splash',
    'src/frontend/styles.splash',
    'src/frontend/components/news_list.splash',
    'src/frontend/components/weather_widget.splash',
    'src/frontend/components/menu.splash',
    'src/frontend/pages/feed.splash',
    'src/frontend/pages/tracking.splash',
    'src/frontend/pages/bookmarks.splash',
    'src/frontend/pages/schedule.splash',
    'src/frontend/pages/detail.splash',
    'src/frontend/pages/results.splash',
    'src/frontend/pages/settings.splash',
    'src/frontend/pages/weather.splash',
    'src/frontend/app_view.splash',
    'src/app/startup.splash',
]


def source_catalog(root=ROOT):
    catalog = json.loads((root / 'src/data/ingestion/sources.json').read_text(encoding='utf-8'))
    ids = set()
    for source in catalog['sources']:
        if source['id'] in ids:
            raise ValueError(f"Duplicate source: {source['id']}")
        ids.add(source['id'])
        url = urlsplit(source['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError(f"Invalid source URL: {source['id']}")
        if source['kind'] not in {'rss', 'google', 'digest', 'hn'}:
            raise ValueError(f"Unsupported source kind: {source['id']}")
    return catalog


def catalog_script(catalog):
    def value(v):
        return json.dumps(v, ensure_ascii=False)
    rows = ['    {' + ' '.join(f'{key}: {value(v)}' for key, v in source.items()) + '}'
            for source in catalog['sources']]
    hosts = sorted({urlsplit(source['url']).hostname for source in catalog['sources']}
                   | set(catalog.get('redirect_hosts', [])))
    return 'let news_sources = [\n' + '\n'.join(rows) + '\n]\nlet news_hosts = ' + value(hosts) + '\n'


def city_catalog(root=ROOT):
    catalog = json.loads((root / 'src/data/ingestion/cities.json').read_text(encoding='utf-8'))
    if catalog.get('schema_version') != 1:
        raise ValueError('cities.json schema_version must be 1')
    ids = set()
    for city in catalog['cities']:
        if city['cid'] in ids:
            raise ValueError(f"Duplicate city id: {city['cid']}")
        ids.add(city['cid'])
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', city['cid']):
            # Splash map keys must be ASCII identifiers; see
            # docs/splash-runtime-notes.md.
            raise ValueError(f"City id is not an ASCII identifier: {city['cid']}")
        for axis, limit in (('lat', 90.0), ('lon', 180.0)):
            if not -limit <= float(city[axis]) <= limit:
                raise ValueError(f"City coordinate out of range: {city['cid']} {axis}")
    return catalog


def cities_script(catalog):
    def value(v):
        return json.dumps(v, ensure_ascii=False)
    rows = ['    {' + ' '.join(f'{key}: {value(city[key])}' for key in ('cid', 'name', 'lat', 'lon')) + '}'
            for city in catalog['cities']]
    ids = sorted(city['cid'] for city in catalog['cities'])
    endpoint = urlsplit(catalog['endpoint'])
    if endpoint.scheme != 'https' or not endpoint.hostname or endpoint.username or endpoint.password:
        raise ValueError('Invalid forecast endpoint')
    return (
        'let weather_cities = [\n' + '\n'.join(rows) + '\n]\n'
        'let weather_cities_ids = ' + value(ids) + '\n'
        'let weather_endpoint = ' + value(catalog['endpoint']) + '\n'
        'let weather_hosts = ' + value(sorted({endpoint.hostname})) + '\n'
        'let weather_days = ' + value(int(catalog['days'])) + '\n'
        'let weather_max_cities = ' + value(int(catalog.get('max_tracked', 12))) + '\n'
        'let weather_utc_offset_seconds = ' + value(int(catalog.get('utc_offset_seconds', 8 * 3600))) + '\n'
        'let weather_alert_precipitation = ' + value(float(catalog.get('alert_precipitation_mm', 5.0))) + '\n'
        'let weather_all_label = ' + value(catalog.get('all_label', '全部')) + '\n'
    )


def requested_hosts(root=ROOT):
    """Declared news and signal hosts that the bundle must admit."""
    catalog = source_catalog(root)
    hosts = {urlsplit(source['url']).hostname for source in catalog['sources']} | set(catalog.get('redirect_hosts', []))
    cities = city_catalog(root)
    cities_script(cities)  # Validate the configured endpoint before admitting it.
    hosts.add(urlsplit(cities['endpoint']).hostname)
    for module, name in (('holidays', 'holiday_hosts'), ('fx', 'fx_hosts')):
        source = (root / f'src/data/ingestion/{module}.splash').read_text(encoding='utf-8')
        declaration = re.search(r'\blet\s+' + name + r'\s*=\s*(\[[^\]]*\])', source)
        if not declaration:
            raise ValueError(f'Missing host declaration: {name}')
        values = json.loads(declaration.group(1))
        if not values or any(not isinstance(host, str) or not re.fullmatch(r'[a-z0-9.-]+', host) for host in values):
            raise ValueError(f'Invalid host declaration: {name}')
        hosts.update(values)
    return hosts


def assemble(root=ROOT, paths=None):
    chunks = ['// GENERATED by scripts/assemble.py; edit src/, never this file.\n'
              '// Derived UI/runtime: OctoSense News; Apache-2.0, see LICENSE and NOTICE.\n']
    spans = []
    next_line = 3
    for relative in paths or ORDER:
        if relative.endswith('sources.json'):
            content = catalog_script(source_catalog(root))
        elif relative.endswith('cities.json'):
            content = cities_script(city_catalog(root))
        else:
            content = (root / relative).read_text(encoding='utf-8').replace('\r\n', '\n')
        chunk = f'\n// BEGIN {relative}\n{content.rstrip()}\n// END {relative}\n'
        spans.append({'source': relative, 'generated_start': next_line + 2,
                      'generated_end': next_line + 1 + len(content.rstrip().splitlines()),
                      'source_start': 1, 'generated_catalog': relative.endswith('.json')})
        next_line += chunk.count('\n')
        chunks.append(chunk)
    return ''.join(chunks), spans


def build(root=ROOT, check=False):
    output, spans = assemble(root)
    target = root / 'bundle/main.splash'
    if check:
        if not target.exists() or target.read_text(encoding='utf-8').replace('\r\n', '\n') != output:
            raise SystemExit('bundle/main.splash is stale; run python scripts/assemble.py')
        return
    target.write_text(output, encoding='utf-8', newline='\n')
    (root / 'build').mkdir(exist_ok=True)
    (root / 'build/source-map.json').write_text(json.dumps(spans, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    build(check=args.check)
    print('Source assembly checked' if args.check else 'Assembled bundle/main.splash')
