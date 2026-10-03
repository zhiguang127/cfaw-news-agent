#!/usr/bin/env python3
"""Prepare the project-locked checkouts without switching existing user work."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text(encoding='utf-8'))
    for repo in lock['repositories']:
        checkout = ROOT / repo['relative_checkout']
        if checkout.exists():
            revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
            dirty = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True).strip()
            if revision != repo['commit'] or dirty:
                raise SystemExit(f'Preserving existing checkout at {checkout}; prepare a clean copy at {repo["commit"]}.')
        else:
            checkout.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', '-c', 'core.longpaths=true', 'clone', '--no-checkout', '--depth', '1', repo['origin'], str(checkout)], check=True)
            subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth', '1', 'origin', repo['commit']], check=True)
            subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', repo['commit']], check=True)
        print(f'{repo["name"]}: {repo["commit"]}')


if __name__ == '__main__':
    prepare()
