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
from patch_windows_render_host import artifacts_match

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def link_rinx_entry(dev_root, source, executable, rust_channel, crate_name):
    release = dev_root.resolve() / 'Rinx/target/release'
    libraries = list((release / 'deps').glob('librinx-*.rlib'))
    if len(libraries) != 1:
        raise SystemExit('Expected one compiled Rinx library.')
    library = libraries[0]
    args = ['rustc', '+' + rust_channel, '--edition=2024', '-C', 'opt-level=2',
            '--crate-name', crate_name, '--extern', 'rinx=' + str(library),
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
    render_metadata_path = release / 'cfaw-render-patch.json'
    if not render_metadata_path.exists():
        raise SystemExit('Build the Windows D3D11 fix first: scripts/build_windows_tools.ps1 -Mode Rinx')
    render_metadata = json.loads(render_metadata_path.read_text(encoding='utf-8'))
    render_patch = ROOT / 'scripts/patches/makepad-d3d11-buffer-accounting.patch'
    if (not artifacts_match(dev_root.resolve())
            or render_metadata.get('makepad_revision') != lock['target_pins']['makepad']
            or render_metadata.get('patch_sha256') != digest(render_patch)
            or render_metadata.get('rinx_library_sha256') != digest(library)):
        raise SystemExit('The host library does not match the recorded D3D11 fix; rebuild scripts/build_windows_tools.ps1 -Mode Rinx')
    host = release / 'rinx.exe'
    kernel = release / 'octos.exe'
    for required in (host, kernel, release / 'makepad_widgets/resources', release / 'rinx/resources'):
        if not required.exists():
            raise SystemExit(f'Build/package the pinned host and stage its resources first; missing: {required}')
    source = ROOT / 'scripts/native/rinx_sdf.rs'
    output = ROOT / 'build/windows-rinx-sdf'
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = output / 'build-info.json'
    inputs = {
        'rinx_revision': revision,
        'rust_channel': lock['toolchain']['rinx_rust_channel'],
        'source_sha256': digest(source),
        'rinx_library_sha256': digest(library),
        'original_host_sha256': digest(host),
        'octos_sha256': digest(kernel),
        'text_rasterizer': 'Sdf',
        'render_patch_sha256': digest(render_patch),
    }
    # A running Windows image is locked. Keep the user's current process intact
    # and give each set of inputs a separate executable for the next launch.
    build_id = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:12]
    version_output = output / build_id
    version_output.mkdir(exist_ok=True)
    executable = version_output / ('rinx-sdf-' + build_id + '.exe')
    previous = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    cached = not force and executable.exists() and previous.get('inputs') == inputs and previous.get('executable_sha256') == digest(executable)
    # Restore deleted or damaged staging even when the native link is cached.
    for resource in ('makepad_widgets/resources', 'rinx/resources'):
        shutil.copytree(release / resource, version_output / resource, dirs_exist_ok=True)
    staged_kernel = version_output / kernel.name
    if not staged_kernel.exists() or digest(staged_kernel) != inputs['octos_sha256']:
        shutil.copy2(kernel, staged_kernel)
    if cached:
        print(f'SDF host ready: {executable}')
        return executable
    link_rinx_entry(dev_root, source, executable, inputs['rust_channel'], 'cfaw_rinx_sdf')
    metadata_path.write_text(json.dumps({'inputs': inputs, 'build_id': build_id, 'executable': executable.name,
                                         'executable_sha256': digest(executable)}, indent=2) + '\n', encoding='utf-8')
    print(f'Built SDF host: {executable}')
    return executable


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-root', type=Path, default=ROOT / '.dev/vendor')
    parser.add_argument('--force', action='store_true')
    options = parser.parse_args()
    build(options.dev_root, options.force)
