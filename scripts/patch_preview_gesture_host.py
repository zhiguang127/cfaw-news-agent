"""Prepare and verify card-host's pinned gesture patch independently of Rinx."""
import argparse
import json
import hashlib
import subprocess
from pathlib import Path

from patch_gesture_host import ROOT, ORIGINAL_SHA256, digest, patch_text


def prepare(dev_root):
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    revision = next(repo['commit'] for repo in lock['repositories'] if repo['name'] == 'makepad')
    checkout = dev_root / 'makepad'
    head = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if head != revision:
        raise ValueError('Wrong Makepad revision')
    base = subprocess.check_output(['git', '-C', str(checkout), 'show', 'HEAD:widgets/src/gesture_view.rs']).decode()
    if hashlib.sha256(base.encode()).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Pinned original source hash differs')
    path = checkout / 'widgets/src/gesture_view.rs'
    patched = patch_text(base)
    if path.read_text(encoding='utf-8') not in (base, patched):
        raise ValueError('Gesture source has other edits; preserve checkout')
    if path.read_text(encoding='utf-8') != patched:
        path.write_text(patched, encoding='utf-8')
    metadata = {'revision': revision, 'source_sha256': hashlib.sha256(patched.encode()).hexdigest(), 'native_build_required': True}
    (dev_root / 'cfaw-preview-gesture-source.json').write_text(json.dumps(metadata, indent=2))


def artifacts(dev_root):
    release = dev_root / 'OctoSense-App-Hub/target/release'
    widgets = list((release / 'deps').glob('libmakepad_widgets-*.rlib'))
    if len(widgets) != 1:
        raise ValueError('Expected one compiled Makepad widgets library')
    source = json.loads((dev_root / 'cfaw-preview-gesture-source.json').read_text())
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())
    revision = next(repo['commit'] for repo in lock['repositories'] if repo['name'] == 'makepad')
    if source['revision'] != revision:
        raise ValueError('Preview gesture record targets a different Makepad revision')
    path = dev_root / 'makepad/widgets/src/gesture_view.rs'
    if hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest() != source['source_sha256']:
        raise ValueError('Gesture source differs from the recorded patch')
    return {
        'source': source,
        'patch_script_sha256': digest(ROOT / 'scripts/patch_gesture_host.py'),
        'widgets_sha256': digest(widgets[0]),
        'executable_sha256': digest(release / 'card-host.exe'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-root', type=Path, default=ROOT / '.dev/vendor')
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--check-artifacts', action='store_true')
    args = parser.parse_args()
    dev_root = args.dev_root.resolve()
    record = dev_root / 'OctoSense-App-Hub/target/release/cfaw-preview-gesture-patch.json'
    if args.check_artifacts:
        try:
            return 0 if json.loads(record.read_text()) == artifacts(dev_root) else 1
        except (OSError, ValueError, KeyError):
            return 1
    if args.record:
        record.write_text(json.dumps(artifacts(dev_root), indent=2))
    else:
        prepare(dev_root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
