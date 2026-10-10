# Windows WebReader backend

This host-side crate implements Makepad `SpawnSystemBrowser`, bounds/visibility updates, close and history for an embedded WebView2 controller. It is compiled into the Rinx host; an OctoScript bundle cannot install native browser support by itself.

The application opens a public HTTPS page after its normal Splash policy check. Native navigation preserves the `navigable` grant, keeps new-window links inside the reader, rejects non-HTTPS/local targets and never exposes a JavaScript host bridge. Site permission requests and downloads are denied. COM completion callbacks enqueue events; the Makepad UI dispatches them without reentering a borrowed Cx. Close destroys the controller and discards pending events; weak references prevent stale creation callbacks from resurrecting closed readers.

Website cookies live in `webreader-v1` under `RINX_DATA_DIR` (or the host's normal application data directory). Matrix credentials are not read by this crate. These browser cookies do not become cookies of the news HTTP retriever. Human verification remains an interaction in the website itself.

Dependencies are pinned to `webview2-com 0.39.1` and `windows 0.62.2`; the standalone Cargo.lock is included. The wrapper follows the [maintainer's callback API](https://github.com/wravery/webview2-rs) and Microsoft's [WebView2 initialization model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/get-started/win32).

`CFAW_WEBREADER_PROBE_DIR` enables developer PNG captures after a successful native navigation. It is unset during normal use and creates no JavaScript bridge. `examples/page_probe.rs` loads one explicit public URL in an isolated window; `scripts/test_webreader_ui.py` exercises the application route and the actual Rinx native backend.
