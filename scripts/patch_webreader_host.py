"""Install the Windows WebReader backend into an explicitly selected Makepad host."""
import argparse
import os
from pathlib import Path
from patch_reader_host import replace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--makepad-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.makepad_root.resolve()
    project = Path(__file__).resolve().parents[1]
    evidence = project / 'build/webreader-host-patches'
    relative = Path(os.path.relpath(project / 'native/windows-webreader', root / 'platform')).as_posix()
    manifest = root / 'platform/Cargo.toml'
    dependency = f'\n[target.\'cfg(windows)\'.dependencies.cfaw-windows-webreader]\npath = "{relative}"\n'
    contents = manifest.read_text(encoding='utf-8')
    if 'dependencies.cfaw-windows-webreader' not in contents:
        manifest.write_text(contents + dependency, encoding='utf-8', newline='\n')
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
