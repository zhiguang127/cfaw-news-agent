//! Isolated public-page probe; writes a native preview only when requested.
use cfaw_windows_webreader::{self as browser, BrowserEvent};
use windows::{core::w, Win32::{Foundation::*, System::Com::*, UI::WindowsAndMessaging::*}};

unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    if msg == WM_DESTROY { unsafe { PostQuitMessage(0); } return LRESULT(0) }
    unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
}
fn main() -> windows::core::Result<()> {
    let url = std::env::args().nth(1).expect("public HTTPS page URL required");
    unsafe {
        CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok()?;
        let class = WNDCLASSW {lpfnWndProc: Some(window_proc), lpszClassName: w!("CFAWWebReaderProbe"), ..Default::default()};
        assert_ne!(RegisterClassW(&class), 0);
        let hwnd = CreateWindowExW(Default::default(), w!("CFAWWebReaderProbe"), w!("CFAW isolated WebReader probe"), WS_OVERLAPPEDWINDOW,
            100, 100, 650, 1000, None, None, None, None)?;
        let _ = ShowWindow(hwnd, SW_SHOW);
        browser::spawn(1, hwnd.0 as usize, &url, true);
        browser::update(1, [0, 0, 620, 940], true);
        SetTimer(Some(hwnd), 1, 50, None);
        let started = std::time::Instant::now();
        let mut loaded = false;
        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).as_bool() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
            for event in browser::drain_events() {
                println!("{event:?}");
                match event {
                    BrowserEvent::Navigation{loading: false, ..} => loaded = true,
                    BrowserEvent::Error{..} => { browser::close(1); let _ = DestroyWindow(hwnd); return Err(windows::core::Error::from(E_FAIL)); }
                    _ => {}
                }
            }
            let captured = std::env::var_os("CFAW_WEBREADER_PROBE_DIR").is_some_and(|path| std::path::PathBuf::from(path).join("1.png").is_file());
            if loaded && captured { browser::close(1); let _ = DestroyWindow(hwnd); break }
            if started.elapsed().as_secs() > 60 { browser::close(1); let _ = DestroyWindow(hwnd); return Err(windows::core::Error::from(E_FAIL)) }
        }
        CoUninitialize();
    }
    Ok(())
}
