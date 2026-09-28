#!/usr/bin/env python3
"""Verify recorded checkouts. This command never fetches or changes shared dependencies."""
import json, os, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
eco=Path(os.environ.get('ECO_ROOT',root.parent/'demo-workspace/vendor'))
lock=json.loads((root/'dev-dependencies.lock.json').read_text())
failed=False
for repo in lock['repositories']:
    path=Path(os.environ.get('RINX_REPO',root.parent/'Rinx-CFAW')) if repo['name']=='Rinx-CFAW' else eco/repo['name']
    try:
        head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True).strip()
        match=head==repo['commit'];failed|=not match
        print(('OK' if match else 'MISMATCH'),repo['name'],head, '(local changes; never overwritten)' if dirty else '')
    except subprocess.CalledProcessError: failed=True
result=subprocess.call([str(eco/'OctoScript-App-Design-Flow/tools/octo'),'doctor'])
raise SystemExit(1 if failed or result else 0)
