"""Undo Git's Windows newline conversion for pinned, digest-checked bundles.

Never restamp manifests or replace edits: only CRLF conversions of HEAD blobs
are accepted. All files are checked before any write.
"""
import argparse
import json
from pathlib import Path
import subprocess


def restore(root: Path) -> None:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(root), *args])

    catalog = json.loads((root / "system-apps.json").read_text(encoding="utf-8"))
    updates = []
    for app in catalog["apps"]:
        prefix = f"apps/{app['directory']}/bundle/"
        for raw in git("ls-files", "-z", "--", prefix).split(b"\0"):
            if not raw:
                continue
            name = raw.decode("utf-8")
            path = root / name
            original = git("show", f"HEAD:{name}")
            current = path.read_bytes()
            if current == original:
                continue
            if current.replace(b"\r\n", b"\n") != original:
                raise SystemExit(f"Refusing to overwrite modified bundle file: {name}")
            updates.append((path, original))
    for path, original in updates:
        path.write_bytes(original)
        print(f"Restored pinned bundle bytes: {path.relative_to(root)}")
    print(f"System bundle newline check complete; restored {len(updates)} files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rinx-root", type=Path, required=True)
    restore(parser.parse_args().rinx_root.resolve())
