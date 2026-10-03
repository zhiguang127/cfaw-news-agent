#!/usr/bin/env python3
"""Link the pinned Rinx App with a Windows SDF startup configuration.

This uses the existing host build, including its services and dependency pins.
It writes only project build output; upstream checkouts and binaries stay intact.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(dev_root, force=False):
    if os.name != 'nt':
        raise SystemExit('The SDF host workaround is only verified on Windows.')
    lock = json.loads((ROOT / 'dev-dependencies.lock.json').read_text(encoding='utf-8'))
    pinned = next(repo for repo in lock['repositories'] if repo['name'] == 'Rinx')
    checkout = dev_root.resolve() / pinned['name']
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != pinned['commit']:
        raise SystemExit('Build the recorded Rinx revision before using the SDF workaround.')
    release = checkout / 'target/release'
    libraries = list((release / 'deps').glob('librinx-*.rlib'))
    if len(libraries) != 1:
        raise SystemExit('Expected one compiled Rinx library. Rebuild the pinned host in a clean target directory.')
    library = libraries[0]
    host = release / 'rinx.exe'
    kernel = release / 'octos.exe'
    for required in (host, kernel, release / 'makepad_widgets/resources', release / 'rinx/resources'):
        if not required.exists():
            raise SystemExit(f'Build/package the pinned host and stage its resources first; missing: {required}')
    source = ROOT / 'scripts/native/rinx_sdf.rs'
    output = ROOT / 'build/windows-rinx-sdf'
    output.mkdir(parents=True, exist_ok=True)
    executable = output / 'rinx-sdf.exe'
    metadata_path = output / 'build-info.json'
    inputs = {
        'rinx_revision': revision,
        'rust_channel': lock['toolchain']['rinx_rust_channel'],
        'source_sha256': digest(source),
        'rinx_library_sha256': digest(library),
        'original_host_sha256': digest(host),
        'octos_sha256': digest(kernel),
        'text_rasterizer': 'Sdf',
    }
    previous = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    cached = not force and executable.exists() and previous.get('inputs') == inputs and previous.get('executable_sha256') == digest(executable)
    # Restore deleted or damaged staging even when the native link is cached.
    for resource in ('makepad_widgets/resources', 'rinx/resources'):
        shutil.copytree(release / resource, output / resource, dirs_exist_ok=True)
    shutil.copy2(kernel, output / kernel.name)
    if cached:
        print(f'SDF host ready: {executable}')
        return executable
    args = ['rustc', '+' + inputs['rust_channel'], '--edition=2024', '-C', 'opt-level=2',
            '--crate-name', 'cfaw_rinx_sdf', '--extern', 'rinx=' + str(library),
            '-L', 'dependency=' + str(release / 'deps'), str(source), '-o', str(executable)]
    for build_output in (release / 'build').glob('*/output'):
        for line in build_output.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('cargo:rustc-link-search='):
                search = line.split('=', 1)[1]
                # Build scripts may record the temporary Windows drive. Resolve
                # native output directories against the staged release tree.
                kind, separator, location = search.partition('=')
                path = location if separator else kind
                normalized = path.replace('\\', '/')
                if not Path(path).exists():
                    if '/release/build/' in normalized:
                        path = str(release / 'build' / normalized.split('/release/build/', 1)[1])
                    elif '/cargo-home/' in normalized:
                        path = str(dev_root.resolve() / 'cargo-home' / normalized.split('/cargo-home/', 1)[1])
                    if not Path(path).exists():
                        raise SystemExit(f'Native link directory missing; rebuild the pinned host: {path}')
                    search = kind + '=' + path if separator else path
                args.extend(['-L', search])
    subprocess.run(args, check=True)
    metadata_path.write_text(json.dumps({'inputs': inputs, 'executable_sha256': digest(executable)}, indent=2) + '\n', encoding='utf-8')
    print(f'Built SDF host: {executable}')
    return executable


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-root', type=Path, default=ROOT / '.dev/vendor')
    parser.add_argument('--force', action='store_true')
    options = parser.parse_args()
    build(options.dev_root, options.force)
