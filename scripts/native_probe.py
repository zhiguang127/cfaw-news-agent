"""Build tracking probes against the current installed Rinx host library."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from assemble import ROOT


def ensure_native_probe():
    # Pin a verified probe while Cargo is replacing artifacts in the shared
    # release directory; never infer readiness from an in-progress rlib mtime.
    configured = os.environ.get('CFAW_NATIVE_PROBE')
    if configured:
        executable = Path(configured).resolve()
        if not executable.is_file():
            raise RuntimeError('Configured native probe does not exist: ' + str(executable))
        return executable
    release = ROOT.parent.parent / 'Rinx-main/target/release'
    libraries = list((release / 'deps').glob('librinx-*.rlib'))
    if not libraries:
        raise RuntimeError('Build the Rinx host before running native tracking checks')
    library = max(libraries, key=lambda p: p.stat().st_mtime_ns)
    native = ROOT / '.test-state/intent-context/native'
    native.mkdir(parents=True, exist_ok=True)
    executable = native / 'intent-probe.exe'
    source = ROOT / 'tests/scenarios/rinx_render_probe.rs'
    signature = dict(library=str(library), library_mtime_ns=library.stat().st_mtime_ns,
                     source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    record = native / 'probe-runtime.json'
    previous = json.loads(record.read_text(encoding='utf-8')) if record.is_file() else None
    if not executable.is_file() or previous != signature:
        args = ['rustc', '+1.98.0', '--edition=2024', '-C', 'opt-level=2',
                '--crate-name', 'cfaw_presentation_probe', '--extern', 'rinx=' + str(library),
                '-L', 'dependency=' + str(release / 'deps'), str(source), '-o', str(executable)]
        for output in (release / 'build').glob('*/output'):
            for line in output.read_text(encoding='utf-8', errors='replace').splitlines():
                if line.startswith('cargo:rustc-link-search='):
                    args += ['-L', line.split('=', 1)[1]]
        print('Native tracking runtime:', library.name, flush=True)
        subprocess.run(args, check=True)
        for resources in ('makepad_widgets/resources', 'rinx/resources'):
            shutil.copytree(release / resources, native / resources, dirs_exist_ok=True)
        record.write_text(json.dumps(signature, indent=2), encoding='utf-8')
    return executable
