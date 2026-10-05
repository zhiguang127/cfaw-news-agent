"""Keep the locked Rinx and Hub bundle digests identical across platforms."""
import argparse
import hashlib
from pathlib import Path


def patch(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    before = '    files.sort();'
    after = '''    // Canonical bundle paths use '/', including on Windows.
    files.sort_by_cached_key(|p| p.to_string_lossy().replace('\\\\', "/"));'''
    hash_before = '        hasher.update(relative.to_string_lossy().as_bytes());'
    hash_after = '''        let canonical = relative.to_string_lossy().replace('\\\\', "/");
        hasher.update(canonical.as_bytes());'''
    if after in source and hash_after in source:
        original = source.replace(after, before).replace(hash_after, hash_before)
        if hashlib.sha256(original.encode()).hexdigest() != ORIGINAL_SHA256:
            raise SystemExit(f"Unexpected modified bundle digest source: {path}")
        print(f"Canonical bundle path patch already present: {path}")
        return
    if source.count(before) != 1 or source.count(hash_before) != 1:
        raise SystemExit(f"Unexpected bundle digest source: {path}")
    # Both private copies are the same locked implementation.
    digest = hashlib.sha256(source.encode()).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise SystemExit(f"Unexpected bundle digest hash: {path}: {digest}")
    path.write_text(source.replace(before, after).replace(hash_before, hash_after),
                    encoding="utf-8", newline="\n")
    print(f"Patched canonical bundle paths: {path}")


ORIGINAL_SHA256 = "09a8df2cf5b5208194757b20016169f8bbfa35fc62eeb66f8749c798d4c44f81"
PATCHED_SHA256 = "557a8a07ddeea9ba0a87be53bc5a71646291ce5d58f1436cdb293acf6af94d3a"
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-root", type=Path, required=True)
    root = parser.parse_args().dev_root
    patch(root / "Rinx/vendor/octosense-app-contract/src/bundle.rs")
    patch(root / "OctoSense-App-Hub/crates/app-contract/src/bundle.rs")
