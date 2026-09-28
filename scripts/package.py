#!/usr/bin/env python3
"""Create a deterministic local-import archive after the official gate passes."""
import subprocess,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
subprocess.run([str(root/'scripts/check-bundle.sh')],check=True,cwd=root)
out=root/'build/cfaw-news-agent-0.1.0.zip';out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted((root/'bundle').rglob('*')):
        if p.is_file():
            info=zipfile.ZipInfo(str(Path('cfaw-news-agent')/p.relative_to(root/'bundle')),date_time=(2026,9,28,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644 << 16
            z.writestr(info,p.read_bytes())
print(out)
