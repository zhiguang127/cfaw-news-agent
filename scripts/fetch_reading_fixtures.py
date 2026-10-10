"""Download public publisher samples for isolated native integration checks."""
import concurrent.futures
import json
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from assemble import ROOT, source_catalog

directory = ROOT / '.test-state/reading-sources/samples'
directory.mkdir(parents=True, exist_ok=True)
def fetch(source):
    request = Request(source['url'], headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, timeout=25) as response:
        raw = response.read(2000000)
    (directory / (source['id'] + '.xml')).write_bytes(raw)
    root = ET.fromstring(raw)
    first = root.find('.//item')
    article = first.findtext('link')
    report = dict(source=source['id'], bytes=len(raw), items=len(root.findall('.//item')), article=article)
    if source['id'] == 'sspai':
        with urlopen(Request(article, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
            page = response.read(2000000)
        (directory / 'sspai.html').write_bytes(page)
        report['page_bytes'] = len(page)
    return report
sources = [s for s in source_catalog()['sources'] if s.get('reading_feed')]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(fetch, sources))
(directory / 'fetch-report.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False))
