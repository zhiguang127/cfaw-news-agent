#!/usr/bin/env python3
"""Build and run the locked Linux Rinx host or the card-host preview."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from prepare_dev_dependencies import verify_checkout

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd=ROOT, env=None):
    print('+ ' + ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('Rinx', 'Preview'), default='Rinx')
    parser.add_argument('--build', action='store_true', help='Prepare sources and build before launching')
    parser.add_argument('--build-only', action='store_true', help='Prepare, build and package without opening a window')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Use scripts/run_windows.ps1 on Windows; this entry targets Linux.')

    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text(encoding='utf-8'))
    checkouts = {repo['name']: ROOT / repo['relative_checkout'] for repo in lock['repositories']}
    if args.build or args.build_only:
        run([sys.executable, ROOT / 'scripts/prepare_dev_dependencies.py'])
    required_repos = [repo for repo in lock['repositories'] if args.mode == 'Preview' or repo['name'] in ('Rinx', 'OctoSense-App-Hub')]
    for repo in required_repos:
        checkout = checkouts[repo['name']]
        if not (checkout / '.git').exists():
            raise RuntimeError('Missing dependency checkout; run with --build first: ' + str(checkout))
        verify_checkout(checkout, repo)

    env = os.environ.copy()
    env['RUSTUP_TOOLCHAIN'] = lock['toolchain']['rinx_rust_channel']
    env.setdefault('CARGO_BUILD_JOBS', '4')
    # Linux source builds load resources from the compiled-in checkout paths.
    # Windows staging flags would instead point at unstaged adjacent resources.
    env.pop('MAKEPAD_PACKAGE_DIR', None)
    env.pop('MAKEPAD', None)
    hub_checkout = checkouts['OctoSense-App-Hub']
    host_checkout = checkouts['Rinx'] if args.mode == 'Rinx' else hub_checkout
    hub = hub_checkout / 'target/release/hub'
    host = host_checkout / 'target/release' / ('rinx' if args.mode == 'Rinx' else 'card-host')
    if args.build or args.build_only:
        env['CARGO_TARGET_DIR'] = str(hub_checkout / 'target')
        command = ['cargo', 'build', '--locked', '--release', '-p', 'octosense-app-hub', '--bin', 'hub']
        if args.mode == 'Preview':
            command += ['-p', 'octosense-card-host', '--bin', 'card-host']
        run(command, hub_checkout, env)
        if args.mode == 'Rinx':
            env['CARGO_TARGET_DIR'] = str(host_checkout / 'target')
            run(['cargo', 'build', '--locked', '--release', '--bin', 'rinx', '--features', 'agent_chat'], host_checkout, env)
            run([sys.executable, 'tools/package-octos.py', 'desktop', '--app-binary', host], host_checkout, env)

    for binary in (hub, host):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError('Build the pinned tools with --build first; missing executable: ' + str(binary))
    if args.mode == 'Rinx' and not (host.parent / 'octos').is_file():
        raise RuntimeError('Matching Octos is missing; run with --build to package the host runtime.')
    env['OCTO_HUB'] = str(hub)
    run([sys.executable, ROOT / 'scripts/package.py'], env=env)
    print('Bundle folder: ' + str(ROOT / 'bundle'), flush=True)
    if args.build_only:
        return
    if not env.get('DISPLAY') and not env.get('WAYLAND_DISPLAY'):
        raise RuntimeError('A Linux graphical session is required; build only with --build-only.')
    command = [host]
    if args.mode == 'Preview':
        command += ['--bundle', ROOT / 'bundle', '--allow-unsigned', '--app-data', ROOT / '.local-state/linux-preview', '--size', '430x860']
    elif not env.get('RINX_DATA_DIR') and not env.get('ROBRIX_DATA_DIR'):
        data = ROOT / '.local-state/rinx'
        data.mkdir(parents=True, exist_ok=True)
        env['RINX_DATA_DIR'] = str(data)
    run(command, host_checkout, env)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
    except KeyboardInterrupt:
        raise SystemExit(130)
