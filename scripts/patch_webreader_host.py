"""Install the Windows WebReader backend into an explicitly selected Makepad host."""
import argparse
import json
import os
from pathlib import Path
import re
from patch_reader_host import replace


def webreader_manifest(contents, relative):
    """Retarget an existing backend without discarding dependency options."""
    header = "[target.'cfg(windows)'.dependencies.cfaw-windows-webreader]"
    path_line = 'path = ' + json.dumps(relative) + '\n'
    sections = list(re.finditer(
        r'''(?m)^\[target\.(?:'cfg\(windows\)'|"cfg\(windows\)")\.dependencies\.cfaw-windows-webreader\][ \t]*(?:\n|$)''',
        contents))
    if len(sections) > 1:
        raise SystemExit('Duplicate Windows WebReader dependency; preserve and inspect Cargo.toml')
    if not sections:
        if 'dependencies.cfaw-windows-webreader' in contents:
            raise SystemExit('Unexpected Windows WebReader dependency layout; preserve and inspect Cargo.toml')
        return contents.rstrip('\n') + '\n\n' + header + '\n' + path_line
    start = sections[0].end()
    following = re.search(r'(?m)^\[', contents[start:])
    end = start + following.start() if following else len(contents)
    body = contents[start:end]
    paths = list(re.finditer(r'(?m)^[ \t]*path[ \t]*=.*(?:\n|$)', body))
    if len(paths) > 1:
        raise SystemExit('Duplicate Windows WebReader paths; preserve and inspect Cargo.toml')
    if paths:
        path = paths[0]
        body = body[:path.start()] + path_line + body[path.end():]
    else:
        body = body.rstrip('\n') + '\n' + path_line
    return contents[:start] + body + contents[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--makepad-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.makepad_root.resolve()
    project = Path(__file__).resolve().parents[1]
    evidence = project / 'build/webreader-host-patches'
    relative = Path(os.path.relpath(project / 'native/windows-webreader', root / 'platform')).as_posix()
    manifest = root / 'platform/Cargo.toml'
    contents = manifest.read_text(encoding='utf-8')
    updated = webreader_manifest(contents, relative)
    if updated != contents:
        manifest.write_text(updated, encoding='utf-8', newline='\n')
    windows = root / 'platform/src/os/windows/windows.rs'
    replace(windows, '''        let mut geom_changes = Vec::new();
        while let Some(op) = self.platform_ops.pop_front() {''', '''        let mut geom_changes = Vec::new();
        // COM callbacks are queued, never re-enter a borrowed Makepad Cx.
        for event in cfaw_windows_webreader::drain_events() {
            match event {
                cfaw_windows_webreader::BrowserEvent::Navigation { id, url, title, loading } => {
                    crate::log!("WebReader navigation: id={} loading={} title={}", id, loading, title);
                    self.action(NativeSystemBrowserNavigation { browser_id: id, url, title, loading, error: None });
                }
                cfaw_windows_webreader::BrowserEvent::Error { id, url, message } => {
                    crate::log!("WebReader failed: {}", message);
                    self.action(NativeSystemBrowserPageError { browser_id: id, code: -1, description: message, url });
                }
            }
        }
        while let Some(op) = self.platform_ops.pop_front() {''', evidence)
    replace(windows, '''                e => {
                    crate::error!("Not implemented on this platform: CxOsOp::{:?}", e);
                }''', '''                CxOsOp::SpawnSystemBrowser { browser_id, url, navigable } => {
                    if let Some(window) = d3d11_windows.first() {
                        cfaw_windows_webreader::spawn(browser_id.get_value(), window.win32_window.hwnd.0 as usize, &url, navigable);
                    } else {
                        self.action(NativeSystemBrowserPageError {browser_id: browser_id.get_value(), code: -1, description: "网页窗口尚未就绪".into(), url});
                    }
                }
                CxOsOp::UpdateSystemBrowser { browser_id, area, visible } => {
                    let window_id = area.draw_list_id().and_then(|id| self.draw_lists[id].draw_pass_id)
                        .and_then(|pass| self.get_pass_window_id(pass));
                    if let Some(window_id) = window_id {
                        let rect = area.clipped_rect(self);
                        let dpi = self.windows[window_id].window_geom.dpi_factor;
                        cfaw_windows_webreader::update(browser_id.get_value(), [(rect.pos.x * dpi) as i32, (rect.pos.y * dpi) as i32,
                            ((rect.pos.x + rect.size.x) * dpi) as i32, ((rect.pos.y + rect.size.y) * dpi) as i32], visible);
                    } else {
                        cfaw_windows_webreader::update(browser_id.get_value(), [0, 0, 0, 0], false);
                    }
                }
                CxOsOp::DetachSystemBrowser { browser_id } => cfaw_windows_webreader::update(browser_id.get_value(), [0, 0, 0, 0], false),
                CxOsOp::CloseSystemBrowser { browser_id } => cfaw_windows_webreader::close(browser_id.get_value()),
                CxOsOp::SystemBrowserHistoryGo { browser_id, delta } => cfaw_windows_webreader::history(browser_id.get_value(), delta),
                e => {
                    crate::error!("Not implemented on this platform: CxOsOp::{:?}", e);
                }''', evidence)


if __name__ == '__main__':
    main()
