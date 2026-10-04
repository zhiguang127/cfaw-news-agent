// Mount isolated fixtures in the pinned Rinx App/Modal on Linux.
// Uses actual target VM/UI, without account login, admission or model lease.
use rinx::app::App;
use rinx::makepad_widgets::*;
use std::{cell::RefCell, rc::Rc};
fn main() {
    Cx::init_log();
    if Cx::pre_start() { return; }
    let mut app = _app_main_event_closure!(App);
    let mut mounted = false;
    let cx = Rc::new(RefCell::new(new_cx_with_font_set(Box::new(move |cx, event| {
        app(cx, event);
        if !mounted && matches!(event, Event::Draw(_)) {
            let tree = cx.widget_tree();
            let ui = tree.widget(tree.root_uid());
            if !ui.widget(cx, ids!(card)).is_empty() {
                mounted = true;
                let args: Vec<String> = std::env::args().collect();
                let arg = |key: &str| args.iter().position(|s| s == key).map(|i| args[i+1].clone()).unwrap();
                let size: Vec<f64> = arg("--size").split('x').map(|v| v.parse().unwrap()).collect();
                ui.window(cx, ids!(main_window)).resize(cx, dvec2(size[0], size[1]));
                use rinx::miniapps::{MiniAppsAction, MiniAppsPanelWidgetRefExt};
                ui.view(cx, ids!(home_screen_view)).set_visible(cx, true);
                ui.view(cx, ids!(login_screen_view)).set_visible(cx, false);
                ui.mini_apps_panel(cx, ids!(octoscript_apps_modal.content)).action(cx, ui.modal(cx, ids!(octoscript_apps_modal)), &MiniAppsAction::Open);
                ui.view(cx, ids!(octoscript_apps_modal.content.catalog)).set_visible(cx, false);
                ui.view(cx, ids!(octoscript_apps_modal.content.import_form)).set_visible(cx, false);
                ui.view(cx, ids!(octoscript_apps_modal.content.app_content)).set_visible(cx, true);
                let root = std::path::PathBuf::from(arg("--app-data")).join("dev.cfaw.runtime-tests");
                std::fs::create_dir_all(&root).unwrap();
                let splash = ui.splash(cx, ids!(card));
                splash.set_sandbox_dir(cx, Some(root));
                splash.set_storage_quota(cx, Some(8_388_608));
                splash.set_host_caps(cx, vec!["storage".into()]);
                splash.set_host_prompts(cx, false);
                splash.set_policy(cx, Some(vec![]), Some(16_000_000));
                splash.set_memory_bytes(cx, Some(33_554_432));
                splash.set_text(cx, &std::fs::read_to_string(std::path::PathBuf::from(arg("--bundle")).join("main.splash")).unwrap());
                println!("[tracking-probe] actual pinned Rinx App mounted; isolated fixtures, 32 MiB heap");
            }
        }
    }), FontSet::International)));
    let studio_http = resolve_studio_http();
    cx.borrow_mut().init_websockets(&studio_http);
    cx.borrow_mut().init_cx_os();
    remote::start_if_requested();
    Cx::event_loop(cx);
}
