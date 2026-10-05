#!/usr/bin/env python3
"""Prepare the project-locked checkouts without switching existing user work."""
import hashlib
import json
from pathlib import Path
import subprocess
from patch_windows_bundle_digest import PATCHED_SHA256

ROOT = Path(__file__).resolve().parents[1]


def verify_checkout(checkout, repo, allow_unpatched=False):
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True).strip()
    patch = repo.get('cargo_lock_patch')
    expected_patch = False
    changes = [line.strip() for line in dirty.splitlines()]
    if patch and 'M Cargo.lock' in changes:
        digest = hashlib.sha256((checkout / 'Cargo.lock').read_text(encoding='utf-8').encode()).hexdigest()
        expected_patch = digest == patch['patched_sha256_normalized']
    unexpected = []
    contract_path = {'Rinx': 'vendor/octosense-app-contract/src/bundle.rs',
                     'OctoSense-App-Hub': 'crates/app-contract/src/bundle.rs'}.get(repo['name'])
    for change in changes:
        if change == 'M Cargo.lock' and expected_patch:
            continue
        if contract_path and change == 'M ' + contract_path:
            digest = hashlib.sha256((checkout / contract_path).read_text(encoding='utf-8').encode()).hexdigest()
            if digest == PATCHED_SHA256:
                continue
        # Restoring exact HEAD bytes can remain dirty under Git's Windows
        # newline/index rules. Accept exact pinned bytes, never arbitrary edits.
        if repo['name'] == 'Rinx' and change.startswith('M apps/') and '/bundle/' in change:
            name = change[2:]
            original = subprocess.check_output(['git', '-C', str(checkout), 'show', 'HEAD:' + name])
            if (checkout / name).read_bytes() == original:
                continue
        unexpected.append(change)
    if revision != repo['commit'] or unexpected:
        raise SystemExit(f'Preserving existing checkout at {checkout}; prepare a clean copy at {repo["commit"]}.')
    if patch and not expected_patch and not allow_unpatched:
        raise SystemExit('Prepare the recorded Cargo.lock correction first: python3 scripts/prepare_dev_dependencies.py')
    return expected_patch


def prepare():
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text(encoding='utf-8'))
    for repo in lock['repositories']:
        checkout = ROOT / repo['relative_checkout']
        if checkout.exists():
            verify_checkout(checkout, repo, allow_unpatched=True)
        else:
            checkout.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', '-c', 'core.longpaths=true', 'clone', '--no-checkout', '--depth', '1', repo['origin'], str(checkout)], check=True)
            subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth', '1', 'origin', repo['commit']], check=True)
            subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', repo['commit']], check=True)
        patch = repo.get('cargo_lock_patch')
        if patch:
            patch_file = ROOT / patch['path']
            patch_text = patch_file.read_text(encoding='utf-8')
            if hashlib.sha256(patch_text.encode()).hexdigest() != patch['patch_sha256_normalized']:
                raise SystemExit('Recorded Cargo.lock patch has changed: ' + str(patch_file))
            if not verify_checkout(checkout, repo, allow_unpatched=True):
                subprocess.run(['git', '-C', str(checkout), 'apply', '--check', '-'], input=patch_text, text=True, check=True)
                subprocess.run(['git', '-C', str(checkout), 'apply', '-'], input=patch_text, text=True, check=True)
            verify_checkout(checkout, repo)
        print(f'{repo["name"]}: {repo["commit"]}')


if __name__ == '__main__':
    prepare()
