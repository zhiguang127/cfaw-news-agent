"""Apply opt-in paragraph justification and Windows URL opening to pinned Makepad."""
import argparse
import difflib
from pathlib import Path


def replace(path, before, after, evidence):
    source = path.read_text(encoding='utf-8')
    if after in source:
        print('Already patched:', path)
        return
    if source.count(before) != 1:
        raise SystemExit('Unexpected upstream source: ' + str(path))
    result = source.replace(before, after)
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / (path.name + '.patch')).write_text(''.join(difflib.unified_diff(
        source.splitlines(True), result.splitlines(True), fromfile=path.name, tofile=path.name)), encoding='utf-8', newline='\n')
    path.write_text(result, encoding='utf-8', newline='\n')
    print('Patched:', path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--makepad-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.makepad_root.resolve()
    evidence = Path(__file__).resolve().parents[1] / 'build/reader-host-patches'
    replace(root / 'platform/src/os/windows/windows.rs', '''    fn open_url(&mut self, _url: &str, _in_place: OpenUrlInPlace) {
        crate::error!("open_url not implemented on this platform");
    }''', '''    fn open_url(&mut self, url: &str, _in_place: OpenUrlInPlace) {
        // Reader links are external HTTP(S) navigation, never a shell command.
        if !(url.starts_with("https://") || url.starts_with("http://")) || url.contains('\\0') {
            crate::error!("open_url: unsupported URL scheme");
            return;
        }
        #[link(name = "shell32")]
        unsafe extern "system" {
            fn ShellExecuteW(hwnd: *mut std::ffi::c_void, operation: *const u16,
                file: *const u16, parameters: *const u16, directory: *const u16,
                show: i32) -> isize;
        }
        let operation: Vec<u16> = "open".encode_utf16().chain(Some(0)).collect();
        let target: Vec<u16> = url.encode_utf16().chain(Some(0)).collect();
        let result = unsafe { ShellExecuteW(std::ptr::null_mut(), operation.as_ptr(),
            target.as_ptr(), std::ptr::null(), std::ptr::null(), 1) };
        if result <= 32 {
            crate::error!("open_url: Windows could not open the default browser (code {})", result);
        } else {
            crate::log!("open_url: dispatched HTTP(S) link to default browser");
        }
    }''', evidence)
    replace(root / 'draw/src/text/layouter.rs', 'impl LaidoutText {', '''impl LaidoutText {
    /// Justify soft-wrapped lines only. Keep final and explicit-newline rows ragged.
    /// Work on a caller-owned clone so the shared left-aligned cache is untouched.
    pub fn justify_to_width(&mut self, width: f32) {
        let last = self.rows.len().saturating_sub(1);
        for (index, row) in self.rows.iter_mut().enumerate() {
            if index == last || row.newline || width <= row.width_in_lpxs || !width.is_finite() {
                continue;
            }
            // The news reader currently justifies horizontal LTR text. Preserve
            // complex RTL/visual-order runs instead of corrupting their clusters.
            if row.glyphs.windows(2).any(|g| g[0].cluster > g[1].cluster) { continue; }
            let visible = row.text.trim_end();
            let chars: Vec<(usize, char)> = visible.char_indices().collect();
            let cjk = |c: char| matches!(c as u32, 0x3400..=0x9fff | 0x20000..=0x3134f);
            let mut gaps = Vec::new();
            for pair in chars.windows(2) {
                let (offset, current) = pair[0];
                let (_, next) = pair[1];
                if current.is_whitespace() || (cjk(current) && cjk(next)) {
                    gaps.push(offset + current.len_utf8());
                }
            }
            if gaps.is_empty() { continue; }
            let extra = (width - row.width_in_lpxs) / gaps.len() as f32;
            for glyph in &mut row.glyphs {
                let count = gaps.partition_point(|&gap| gap <= glyph.cluster);
                glyph.origin_in_lpxs.x += extra * count as f32;
            }
            row.width_in_lpxs = width;
            self.size_in_lpxs.width = self.size_in_lpxs.width.max(width);
        }
    }
''', evidence)
    replace(root / 'draw/src/shader/draw_text.rs', '    fn max_layout_width_for_walk(&self, cx: &mut Cx2d, walk: Walk) -> Option<f32> {', '''    pub fn draw_walk_justified(&mut self, cx: &mut Cx2d, walk: Walk, text: &str) -> Rect {
        let walk = cx.resolve_walk(walk, ResolveAt::BeforeBegin);
        let width = self.max_layout_width_for_walk(cx, walk);
        let laidout = self.layout(cx, 0.0, 0.0, width, true, Align::default(), text);
        let mut justified = (*laidout).clone();
        if let Some(width) = width { justified.justify_to_width(width); }
        self.draw_walk_laidout(cx, walk, &justified)
    }

    fn max_layout_width_for_walk(&self, cx: &mut Cx2d, walk: Walk) -> Option<f32> {''', evidence)
    replace(root / 'widgets/src/label.rs', '    pub align: Align,', '''    pub align: Align,
    /// Expand inter-word/CJK gaps on soft-wrapped paragraph rows. Off by default.
    #[live]
    pub justify: bool,''', evidence)
    replace(root / 'widgets/src/label.rs', '''        self.text_layout_rect = self.draw_text
            .draw_walk(cx, walk, self.align, self.text.as_ref());''', '''        self.text_layout_rect = if self.justify {
            self.draw_text.draw_walk_justified(cx, walk, self.text.as_ref())
        } else {
            self.draw_text.draw_walk(cx, walk, self.align, self.text.as_ref())
        };''', evidence)


if __name__ == '__main__':
    main()
