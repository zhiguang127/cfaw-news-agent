//! Windows-only WebReader backend. No JavaScript-to-host bridge is installed.
use std::{cell::RefCell, collections::HashMap, rc::{Rc, Weak}};
use windows::{core::{PCWSTR, PWSTR, BOOL}, Win32::{Foundation::{HWND, RECT}, System::Com::{*, StructuredStorage::CreateStreamOnHGlobal}}};
use webview2_com::{Microsoft::Web::WebView2::Win32::*, *};

#[derive(Debug)]
pub enum BrowserEvent {
    Navigation { id: u64, url: String, title: String, loading: bool },
    Error { id: u64, url: String, message: String },
}
struct Browser {
    controller: Option<ICoreWebView2Controller>,
    webview: Option<ICoreWebView2>,
    bounds: RECT,
    visible: bool,
    url: String,
    navigable: bool,
    closed: bool,
}
thread_local! {
    static BROWSERS: RefCell<HashMap<u64, Rc<RefCell<Browser>>>> = RefCell::new(HashMap::new());
    static EVENTS: RefCell<Vec<BrowserEvent>> = const { RefCell::new(Vec::new()) };
}
fn fail(id: u64, url: &str, error: impl std::fmt::Display) {
    EVENTS.with(|events| events.borrow_mut().push(BrowserEvent::Error {id, url: url.into(), message: error.to_string()}));
}
unsafe fn capture_probe(view: &ICoreWebView2, id: u64) -> windows::core::Result<()> {
    let Some(directory) = std::env::var_os("CFAW_WEBREADER_PROBE_DIR") else { return Ok(()) };
    let path = std::path::PathBuf::from(directory).join(format!("{id}.png"));
    let stream = unsafe { CreateStreamOnHGlobal(Default::default(), true)? };
    let output = stream.clone();
    unsafe {
        view.CapturePreview(COREWEBVIEW2_CAPTURE_PREVIEW_IMAGE_FORMAT_PNG, &stream,
            &CapturePreviewCompletedHandler::create(Box::new(move |result| {
                result?;
                let mut stat = STATSTG::default();
                output.Stat(&mut stat, STATFLAG_NONAME)?;
                if stat.cbSize > 20 * 1024 * 1024 { return Ok(()) }
                output.Seek(0, STREAM_SEEK_SET, None)?;
                let mut bytes = vec![0; stat.cbSize as usize];
                let mut read = 0;
                output.Read(bytes.as_mut_ptr().cast(), bytes.len() as u32, Some(&mut read)).ok()?;
                bytes.truncate(read as usize);
                if let Some(parent) = path.parent() { let _ = std::fs::create_dir_all(parent); }
                let _ = std::fs::write(path, bytes);
                Ok(())
            })))?;
    }
    Ok(())
}
pub fn drain_events() -> Vec<BrowserEvent> { EVENTS.with(|e| std::mem::take(&mut *e.borrow_mut())) }
fn allowed(url: &str, initial: &str, navigable: bool) -> bool {
    let Ok(parsed) = url::Url::parse(url) else { return false };
    if parsed.scheme() != "https" || !parsed.username().is_empty() || parsed.password().is_some() { return false }
    let Some(host) = parsed.host_str() else { return false };
    // Native web pages cannot launch local files, executables or private endpoints.
    if host == "localhost" || host.ends_with(".localhost") || host.ends_with(".local") || !host.contains('.') { return false }
    if let Ok(ip) = host.trim_matches(['[', ']']).parse::<std::net::IpAddr>() {
        let public = match ip {
            std::net::IpAddr::V4(ip) => !ip.is_private() && !ip.is_loopback() && !ip.is_link_local() && !ip.is_unspecified() && !ip.is_multicast(),
            std::net::IpAddr::V6(ip) => !ip.is_loopback() && !ip.is_unspecified() && !ip.is_unique_local() && !ip.is_unicast_link_local() && !ip.is_multicast() && ip.to_ipv4_mapped().is_none(),
        };
        if !public { return false }
    }
    navigable || url::Url::parse(initial).is_ok_and(|p| p.origin() == parsed.origin())
}
unsafe fn uri(args: &ICoreWebView2NavigationStartingEventArgs) -> windows::core::Result<String> {
    let mut value = PWSTR::null();
    unsafe { args.Uri(&mut value)?; }
    Ok(CoTaskMemPWSTR::from(value).to_string())
}
unsafe fn wire(id: u64, weak: Weak<RefCell<Browser>>, view: &ICoreWebView2) -> windows::core::Result<()> {
    let mut token = 0;
    let weak_navigation = weak.clone();
    unsafe {
        view.add_NavigationStarting(&NavigationStartingEventHandler::create(Box::new(move |_, args| {
            let (Some(state), Some(args)) = (weak_navigation.upgrade(), args) else { return Ok(()) };
            let target = uri(&args)?;
            let mut state = state.borrow_mut();
            if state.closed || !allowed(&target, &state.url, state.navigable) {
                args.SetCancel(true)?;
                fail(id, &target, "网页跳转地址未获许可");
                return Ok(())
            }
            state.url = target.clone();
            EVENTS.with(|events| events.borrow_mut().push(BrowserEvent::Navigation{id, url: target, title: String::new(), loading: true}));
            Ok(())
        })), &mut token)?;
        let weak_completed = weak.clone();
        view.add_NavigationCompleted(&NavigationCompletedEventHandler::create(Box::new(move |sender, args| {
            let (Some(state), Some(sender), Some(args)) = (weak_completed.upgrade(), sender, args) else { return Ok(()) };
            if state.borrow().closed { return Ok(()) }
            let url = state.borrow().url.clone();
            let mut success = BOOL::default();
            args.IsSuccess(&mut success)?;
            if !success.as_bool() {
                let mut status = COREWEBVIEW2_WEB_ERROR_STATUS::default();
                args.WebErrorStatus(&mut status)?;
                fail(id, &url, format!("网页加载失败 ({})", status.0));
            } else {
                let mut title = PWSTR::null();
                sender.DocumentTitle(&mut title)?;
                let title = CoTaskMemPWSTR::from(title).to_string();
                EVENTS.with(|events| events.borrow_mut().push(BrowserEvent::Navigation{id, url, title, loading: false}));
                capture_probe(&sender, id)?;
            }
            Ok(())
        })), &mut token)?;
        // Keep site links in the same application pane. Never dispatch to a browser.
        let weak_popup = weak.clone();
        view.add_NewWindowRequested(&NewWindowRequestedEventHandler::create(Box::new(move |sender, args| {
            let (Some(state), Some(sender), Some(args)) = (weak_popup.upgrade(), sender, args) else { return Ok(()) };
            args.SetHandled(true)?;
            let mut target = PWSTR::null();
            args.Uri(&mut target)?;
            let target = CoTaskMemPWSTR::from(target).to_string();
            let state = state.borrow();
            if !state.closed && allowed(&target, &state.url, state.navigable) {
                let target = CoTaskMemPWSTR::from(target.as_str());
                sender.Navigate(*target.as_ref().as_pcwstr())?;
            }
            Ok(())
        })), &mut token)?;
        view.add_PermissionRequested(&PermissionRequestedEventHandler::create(Box::new(|_, args| {
            if let Some(args) = args { args.SetState(COREWEBVIEW2_PERMISSION_STATE_DENY)?; }
            Ok(())
        })), &mut token)?;
        let view4: ICoreWebView2_4 = windows::core::Interface::cast(view)?;
        view4.add_DownloadStarting(&DownloadStartingEventHandler::create(Box::new(|_, args| {
            if let Some(args) = args { args.SetCancel(true)?; }
            Ok(())
        })), &mut token)?;
        let settings = view.Settings()?;
        settings.SetAreDevToolsEnabled(false)?;
        settings.SetIsWebMessageEnabled(false)?;
        settings.SetAreHostObjectsAllowed(false)?;
    }
    Ok(())
}
pub fn spawn(id: u64, parent: usize, url: &str, navigable: bool) {
    close(id);
    if !allowed(url, url, navigable) { fail(id, url, "网页地址未获许可"); return }
    let browser = Rc::new(RefCell::new(Browser{controller: None, webview: None, bounds: RECT::default(), visible: false, url: url.into(), navigable, closed: false}));
    BROWSERS.with(|b| b.borrow_mut().insert(id, browser.clone()));
    let weak = Rc::downgrade(&browser);
    let initial = url.to_owned();
    // Preserve site verification cookies across reader closes, independently
    // from Matrix credentials. Isolated probes set RINX_DATA_DIR explicitly.
    let profile = std::env::var_os("RINX_DATA_DIR").map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::path::PathBuf::from(std::env::var_os("APPDATA").unwrap_or_default()).join("octosense/rinx/data"))
        .join("webreader-v1");
    if let Err(error) = std::fs::create_dir_all(&profile) { fail(id, url, error); return }
    let profile: Vec<u16> = profile.as_os_str().to_string_lossy().encode_utf16().chain(Some(0)).collect();
    unsafe {
        let initialized = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
        if initialized.is_err() { fail(id, url, initialized); return }
        let result = CreateCoreWebView2EnvironmentWithOptions(PCWSTR::null(), PCWSTR(profile.as_ptr()), None,
            &CreateCoreWebView2EnvironmentCompletedHandler::create(Box::new(move |result, environment| {
                let Some(state) = weak.upgrade() else { return Ok(()) };
                if state.borrow().closed { return Ok(()) }
                if let Err(error) = result { fail(id, &initial, error); return Ok(()) }
                let Some(environment) = environment else { fail(id, &initial, "浏览器环境不可用"); return Ok(()) };
                let controller_weak = weak.clone();
                let target = initial.clone();
                let started = environment.CreateCoreWebView2Controller(HWND(parent as *mut _),
                    &CreateCoreWebView2ControllerCompletedHandler::create(Box::new(move |result, controller| {
                        let Some(state) = controller_weak.upgrade() else { if let Some(controller) = controller { controller.Close()?; } return Ok(()) };
                        if state.borrow().closed { if let Some(controller) = controller { controller.Close()?; } return Ok(()) }
                        if let Err(error) = result { fail(id, &target, error); return Ok(()) }
                        let Some(controller) = controller else { fail(id, &target, "网页窗口不可用"); return Ok(()) };
                        let result = (|| -> windows::core::Result<()> {
                            let view = controller.CoreWebView2()?;
                            wire(id, controller_weak.clone(), &view)?;
                            let mut state = state.borrow_mut();
                            controller.SetBounds(state.bounds)?;
                            controller.SetIsVisible(state.visible)?;
                            let target = CoTaskMemPWSTR::from(state.url.as_str());
                            view.Navigate(*target.as_ref().as_pcwstr())?;
                            state.webview = Some(view);
                            state.controller = Some(controller.clone());
                            Ok(())
                        })();
                        if let Err(error) = result { controller.Close()?; fail(id, &target, error); }
                        Ok(())
                    })));
                if let Err(error) = started { fail(id, &initial, error); }
                Ok(())
            })));
        // Balance only this CoInitializeEx call; the host owns its apartment.
        CoUninitialize();
        if let Err(error) = result { fail(id, url, error); }
    }
}
pub fn update(id: u64, rect: [i32; 4], visible: bool) {
    BROWSERS.with(|b| {
        let state = b.borrow().get(&id).cloned();
        if let Some(state) = state {
            let mut state = state.borrow_mut();
            state.bounds = RECT{left: rect[0], top: rect[1], right: rect[2], bottom: rect[3]};
            state.visible = visible;
            if let Some(controller) = &state.controller { unsafe {
                if let Err(error) = controller.SetBounds(state.bounds).and_then(|_| controller.SetIsVisible(visible)) { fail(id, &state.url, error); }
            } }
        }
    });
}
pub fn close(id: u64) {
    EVENTS.with(|events| events.borrow_mut().retain(|event| match event {
        BrowserEvent::Navigation{id: event_id, ..} | BrowserEvent::Error{id: event_id, ..} => *event_id != id,
    }));
    let state = BROWSERS.with(|b| b.borrow_mut().remove(&id));
    if let Some(state) = state {
        let mut state = state.borrow_mut();
        state.closed = true;
        if let Some(controller) = state.controller.take() { unsafe { let _ = controller.Close(); } }
        state.webview = None;
    }
}
pub fn history(id: u64, delta: i32) {
    let view = BROWSERS.with(|b| b.borrow().get(&id).and_then(|s| s.borrow().webview.clone()));
    if let Some(view) = view { unsafe { let _ = if delta < 0 {view.GoBack()} else {view.GoForward()}; } }
}

#[cfg(test)]
mod tests {
    use super::allowed;
    #[test]
    fn navigation_respects_public_https_and_grant() {
        for url in ["file:///C:/secret", "javascript:alert(1)", "https://127.0.0.1/x", "https://10.0.0.1/x", "https://localhost/x", "https://[::1]/x", "https://user:pass@example.com/x"] { assert!(!allowed(url, "https://example.com", true), "{url}"); }
        assert!(allowed("https://example.com/new", "https://example.com/old", false));
        assert!(!allowed("https://other.example/new", "https://example.com/old", false));
        assert!(allowed("https://other.example/new", "https://example.com/old", true));
    }
}
