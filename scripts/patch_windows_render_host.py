#!/usr/bin/env python3
"""Apply and record the project D3D11 fix against Rinx's pinned Makepad.

Only the project's private Cargo checkout is patched. Never update its revision
or change the reference host's independent dependency graph.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'platform/src/os/windows/d3d11.rs'
ORIGINAL = 'ef65f7925c453e425b6e48f1f51214ceb2d5a57bc57dfdec58b2b606630f42e1'
PATCHED = 'b99c6f07a3db1a087317f2250287a24aa999f6b24fd23199a9d1dfd5070a0400'
PATCH = ROOT / 'scripts/patches/makepad-d3d11-buffer-accounting.patch'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def artifacts_match(dev_root):
    release = dev_root / 'Rinx/target/release'
    path = release / 'cfaw-render-patch.json'
    executable = release / 'rinx.exe'
    if not path.is_file() or not executable.is_file():
        return False
    try:
        metadata = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    if not isinstance(metadata, dict):
        return False
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text(encoding='utf-8'))
    libraries = list((release / 'deps').glob('librinx-*.rlib'))
    platforms = list((release / 'deps').glob('libmakepad_platform-*.rlib'))
    return (len(libraries) == 1 and len(platforms) == 1
            and metadata.get('makepad_revision') == lock['target_pins']['makepad']
            and metadata.get('source_sha256_normalized') == PATCHED
            and metadata.get('patch_sha256') == digest(PATCH)
            and metadata.get('rinx_library_sha256') == digest(libraries[0])
            and metadata.get('platform_library_sha256') == digest(platforms[0])
            and metadata.get('rinx_executable_sha256') == digest(executable)
            and b'CFAW D3D11 buffer accounting v3' in platforms[0].read_bytes())


def prepare(dev_root, record=False):
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text(encoding='utf-8'))
    revision = lock['target_pins']['makepad']
    candidates = []
    for path in (dev_root / 'cargo-home/git/checkouts').glob('makepad-*/' + revision[:7]):
        head = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if head == revision:
            candidates.append(path)
    if len(candidates) != 1:
        raise SystemExit('Expected one pinned Makepad checkout in the private Cargo cache; run cargo fetch --locked first.')
    checkout = candidates[0]
    source = checkout / SOURCE
    normalized_hash = hashlib.sha256(source.read_text(encoding='utf-8').encode()).hexdigest()
    if normalized_hash == ORIGINAL and not record:
        subprocess.run(['git', '-C', str(checkout), 'apply', '--ignore-space-change', '--check', str(PATCH)], check=True)
        subprocess.run(['git', '-C', str(checkout), 'apply', '--ignore-space-change', str(PATCH)], check=True)
        normalized_hash = hashlib.sha256(source.read_text(encoding='utf-8').encode()).hexdigest()
    if normalized_hash != PATCHED:
        raise SystemExit('Makepad D3D11 source differs from the recorded original/fix; preserve it and inspect before rebuilding.')
    if record:
        release = dev_root / 'Rinx/target/release'
        libraries = list((release / 'deps').glob('librinx-*.rlib'))
        if len(libraries) != 1:
            raise SystemExit('Expected one compiled Rinx library to record.')
        platforms = list((release / 'deps').glob('libmakepad_platform-*.rlib'))
        if len(platforms) != 1 or b'CFAW D3D11 buffer accounting v3' not in platforms[0].read_bytes():
            raise SystemExit('Cargo reused an unpatched Git dependency; clean makepad-platform and rebuild before recording.')
        metadata = {'makepad_revision': revision, 'patch_sha256': digest(PATCH),
                    'source_sha256_normalized': PATCHED, 'rinx_library_sha256': digest(libraries[0]),
                    'platform_library_sha256': digest(platforms[0]),
                    'rinx_executable_sha256': digest(release / 'rinx.exe')}
        (release / 'cfaw-render-patch.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        print('Recorded compiled D3D11 buffer fix')
    else:
        print('Pinned Makepad D3D11 buffer fix ready')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-root', type=Path, default=ROOT / '.dev/vendor')
    parser.add_argument('--record', action='store_true', help='Record artifacts after a successful host build')
    parser.add_argument('--check-artifacts', action='store_true', help='Exit 1 when patched artifacts need rebuilding')
    args = parser.parse_args()
    if args.check_artifacts:
        raise SystemExit(0 if artifacts_match(args.dev_root.resolve()) else 1)
    prepare(args.dev_root.resolve(), args.record)
