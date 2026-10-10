#!/usr/bin/env python3
"""Stamp and package the unsigned Rinx local-import bundle; not a Hub publish gate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from assemble import build, requested_hosts

root = Path(__file__).resolve().parents[1]
bundle = root / 'bundle'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, help='ZIP destination (default: build/cfaw-news.zip)')
parser.add_argument('--hub', type=Path, help='Compatible Hub tool (also OCTO_HUB; successful choice is cached in build/)')
args = parser.parse_args()
manifest = json.loads((bundle / 'manifest.json').read_text())
if manifest.get('publisher_signature') or manifest.get('integrity', {}).get('signature'):
    raise SystemExit('Refusing to restamp a signed bundle')
expected_hosts = requested_hosts()
if not expected_hosts.issubset(set(manifest['network']['hosts'])):
    raise SystemExit('Source/signal hosts missing from bundle/manifest.json: ' + ', '.join(sorted(expected_hosts - set(manifest['network']['hosts']))))
lock = json.loads((root / 'dev-dependencies.lock.json').read_text())
repo = next(item for item in lock['repositories'] if item['name'] == 'OctoSense-App-Hub')
hub_name = 'hub.exe' if os.name == 'nt' else 'hub'
tool_record = root / 'build/package-tool.json'
configured_hub = args.hub or os.environ.get('OCTO_HUB')
default_hub = root / repo['relative_checkout'] / 'target/release' / hub_name
if configured_hub:
    hub = Path(configured_hub).expanduser()
elif default_hub.is_file():
    hub = default_hub
elif tool_record.is_file():
    hub = root / json.loads(tool_record.read_text(encoding='utf-8'))['hub_path']
else:
    hub = default_hub
if not hub.is_file():
    raise SystemExit('Hub tool not found; set OCTO_HUB to the pinned hub executable')
hub = hub.resolve()
# Older Windows tools hashed backslashes and produced a package that passed
# their own check but was rejected by Rinx. Check a fixed nested-file vector
# against the portable '/' contract BEFORE touching the application's bytes.
build_dir = (root / 'build').resolve()
build_dir.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='digest-probe-', dir=build_dir) as directory:
    probe = Path(directory).resolve()
    if not probe.is_relative_to(build_dir):
        raise SystemExit('Digest probe escaped build directory')
    (probe / 'nested').mkdir()
    (probe / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (probe / 'main.splash').write_bytes(b'CFAW digest probe')
    (probe / 'nested/probe.txt').write_bytes(b'portable paths')
    subprocess.run([str(hub), 'stamp', str(probe)], check=True, capture_output=True)
    probe_digest = json.loads((probe / 'manifest.json').read_text(encoding='utf-8'))['integrity']['bundle_blake3']
    if probe_digest != '24e70521db74b78d6b4c6e37bdc11897021f4988438f35333dadb6bf0bebb20f':
        raise SystemExit('Hub uses an incompatible bundle digest algorithm; select a portable-path Hub with --hub or OCTO_HUB. Application bundle was not changed.')
build()
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
try:
    recorded_hub = os.path.relpath(hub, root)
except ValueError:  # Explicitly configured tool may be on another Windows drive.
    recorded_hub = str(hub)
tool_record.write_text(json.dumps({'hub_path': recorded_hub,
                                  'digest_paths': 'portable-slash'}, indent=2) + '\n', encoding='utf-8')
