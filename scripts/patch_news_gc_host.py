"""Add pressure-based collection to the pinned Makepad sandbox heap."""
import argparse
from pathlib import Path
from patch_reader_host import replace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--makepad-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.makepad_root.resolve()
    evidence = Path(__file__).resolve().parents[1] / 'build/news-gc-host-patches'
    replace(root / 'platform/script/src/gc.rs',
            '    pub fn needs_gc(&self) -> bool {',
            '''    pub fn needs_gc(&self) -> bool {
        // A few large publisher strings can hit a byte cap without doubling
        // the number of objects. Keep headroom for the next native callback.
        if let Some(maximum) = self.max_heap_bytes() {
            if self.accounted_heap_bytes() >= maximum.saturating_mul(3) / 4 {
                return true;
            }
        }''', evidence)
    replace(root / 'platform/script/src/gc.rs',
            '''        self.reconcile_heap_bytes_if_limited();
    }

    /// Check if garbage collection should be triggered.''',
            '''        self.reconcile_heap_bytes_if_limited();
        // Sweep leaves strings in a reuse pool. Under a sandbox byte cap,
        // return that disposable capacity before the next entry allocates.
        if let Some(maximum) = self.max_heap_bytes() {
            if self.accounted_heap_bytes() >= maximum.saturating_mul(3) / 4 {
                self.strings_reuse.clear();
                self.shrink_to_fit();
            }
        }
    }

    /// Check if garbage collection should be triggered.''', evidence)


if __name__ == '__main__':
    main()
