#!/usr/bin/env python3
"""Stamp and package the unsigned Rinx local-import bundle; not a Hub publish gate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import zipfile
from assemble import build, requested_hosts

root = Path(__file__).resolve().parents[1]
bundle = root / 'bundle'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, help='ZIP destination (default: build/cfaw-news.zip)')
args = parser.parse_args()
manifest = json.loads((bundle / 'manifest.json').read_text())
if manifest.get('publisher_signature') or manifest.get('integrity', {}).get('signature'):
    raise SystemExit('Refusing to restamp a signed bundle')
build()
expected_hosts = requested_hosts()
if not expected_hosts.issubset(set(manifest['network']['hosts'])):
    raise SystemExit('Source/signal hosts missing from bundle/manifest.json: ' + ', '.join(sorted(expected_hosts - set(manifest['network']['hosts']))))
lock = json.loads((root / 'dev-dependencies.lock.json').read_text())
repo = next(item for item in lock['repositories'] if item['name'] == 'OctoSense-App-Hub')
hub_name = 'hub.exe' if os.name == 'nt' else 'hub'
hub = Path(os.environ.get('OCTO_HUB', str(root / repo['relative_checkout'] / 'target/release' / hub_name))).expanduser()
if not hub.is_file():
    raise SystemExit('Hub tool not found; set OCTO_HUB to the pinned hub executable')
output = (args.output or root / 'build/cfaw-news.zip').resolve()
if output == bundle or bundle in output.parents:
    raise SystemExit('ZIP output must be outside bundle/')
files = sorted(bundle.rglob('*'))
if any(path.is_symlink() for path in files):
    raise SystemExit('Refusing symlinks in bundle/')
subprocess.run([str(hub.resolve()), 'stamp', str(bundle)], check=True)
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file():
            archive.write(path, Path('bundle') / path.relative_to(bundle))
    for name in ['LICENSE', 'NOTICE']:
        archive.write(root / name, name)
print(output)
