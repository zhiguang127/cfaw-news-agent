// Native graphics regression: pinned Rinx App/Modal with isolated script fixtures.
// No package admission or host-service lease; never use account data here.
use rinx::app::App;
use rinx::makepad_widgets::makepad_platform::windows::{
    Win32::Graphics::Direct3D11::*, core::Interface,
};
use rinx::makepad_widgets::*;
use std::{cell::RefCell, rc::Rc, time::Instant};

fn gpu_state(sec: u64, buffer: &ID3D11Buffer) {
    unsafe {
        let Ok(device) = buffer.GetDevice() else {
            return;
        };
        let Ok(context) = device.GetImmediateContext() else {
            return;
        };
        let removed =
            (Interface::vtable(&device).GetDeviceRemovedReason)(Interface::as_raw(&device));
        let mut rt = std::ptr::null_mut();
        let mut ds = std::ptr::null_mut();
        (Interface::vtable(&context).OMGetRenderTargets)(
            Interface::as_raw(&context),
            1,
            &mut rt,
            &mut ds,
        );
        let mut viewport = D3D11_VIEWPORT::default();
        let mut count = 1;
        (Interface::vtable(&context).RSGetViewports)(
            Interface::as_raw(&context),
            &mut count,
            &mut viewport,
        );
        println!(
            "[gpu-probe] t={sec} removed={removed:?} rt={rt:?} depth={ds:?} viewport={}x{} depth_range={}..{}",
            viewport.Width, viewport.Height, viewport.MinDepth, viewport.MaxDepth
        );
        if !rt.is_null() {
            drop(ID3D11RenderTargetView::from_raw(rt));
        }
        if !ds.is_null() {
            drop(ID3D11DepthStencilView::from_raw(ds));
        }
    }
}

fn main() {
    Cx::init_log();
    if Cx::pre_start() {
        return;
    }
    let mut host = _app_main_event_closure!(App, |cx: &mut Cx| {
        CxDraw::lazy_construct_fonts(cx);
        cx.get_global::<Rc<RefCell<rinx::makepad_widgets::text::fonts::Fonts>>>()
            .borrow_mut()
            .set_outline_rasterization_mode(
                rinx::makepad_widgets::text::rasterizer::OutlineRasterizationMode::Sdf,
            );
    });
    let mut mounted = false;
    let mut test_cap_applied = false;
    let started = Instant::now();
    let mut last = 0;
    let cx = Rc::new(RefCell::new(new_cx_with_font_set(
        Box::new(move |cx, event| {
            host(cx, event);
            if !test_cap_applied
                && std::env::args().any(|arg| arg == "--upload-limit-test")
                && cx.draw_lists.1.allocations.has_device_limit()
            {
                test_cap_applied = true;
                cx.draw_lists
                    .1
                    .allocations
                    .set_device_limit(64 * 1024 * 1024);
                println!("[probe] test-only upload limit = 64 MiB");
            }
            if !mounted && matches!(event, Event::Draw(_)) {
                let tree = cx.widget_tree();
                let ui = tree.widget(tree.root_uid());
                if !ui.widget(cx, ids!(card)).is_empty() {
                    mounted = true;
                    let resize_args: Vec<String> = std::env::args().collect();
                    let requested = resize_args.iter().position(|s| s == "--size")
                        .map(|i| resize_args[i + 1].clone()).unwrap_or("430x860".into());
                    let size: Vec<f64> = requested.split('x').map(|v| v.parse().unwrap()).collect();
                    ui.window(cx, ids!(main_window))
                        .resize(cx, dvec2(size[0], size[1]));
                    use rinx::miniapps::{MiniAppsAction, MiniAppsPanelWidgetRefExt};
                    ui.view(cx, ids!(home_screen_view)).set_visible(cx, true);
                    ui.view(cx, ids!(login_screen_view)).set_visible(cx, false);
                    ui.mini_apps_panel(cx, ids!(octoscript_apps_modal.content))
                        .action(
                            cx,
                            ui.modal(cx, ids!(octoscript_apps_modal)),
                            &MiniAppsAction::Open,
                        );
                    ui.view(cx, ids!(octoscript_apps_modal.content.catalog))
                        .set_visible(cx, false);
                    ui.view(cx, ids!(octoscript_apps_modal.content.import_form))
                        .set_visible(cx, false);
                    ui.view(cx, ids!(octoscript_apps_modal.content.app_content))
                        .set_visible(cx, true);
                    let args: Vec<String> = std::env::args().collect();
                    let arg = |key: &str| {
                        args.iter()
                            .position(|s| s == key)
                            .map(|i| args[i + 1].clone())
                            .unwrap()
                    };
                    let root =
                        std::path::PathBuf::from(arg("--app-data")).join("dev.cfaw.runtime-tests");
                    std::fs::create_dir_all(&root).unwrap();
                    let splash = ui.splash(cx, ids!(card));
                    splash.set_sandbox_dir(cx, Some(root));
                    splash.set_storage_quota(cx, Some(8388608));
                    let network_host = args.iter().position(|s| s == "--network-host")
                        .map(|i| args[i + 1].clone());
                    let mut caps = vec!["storage".into()];
                    if network_host.is_some() { caps.push("net".into()); }
                    splash.set_host_caps(cx, caps);
                    splash.set_host_prompts(cx, false);
                    splash.set_policy(cx, Some(network_host.iter().cloned().collect()), Some(16000000));
                    if let Some(mut inner) = splash.borrow_mut() {
                        inner.set_allow_net(network_host.is_some());
                    }
                    splash.set_memory_bytes(cx, Some(33554432));
                    let text = std::fs::read_to_string(
                        std::path::PathBuf::from(arg("--bundle")).join("main.splash"),
                    )
                    .unwrap();
                    splash.set_text(cx, &text);
                    println!("[probe] isolated app mounted in pinned Rinx App");
                }
            }
            let sec = started.elapsed().as_secs();
            if sec >= last + 1 {
                last = sec;
                println!(
                    "[serial-probe] t={sec} submitted={} completed={}",
                    cx.frame_submission_serial(),
                    cx.frame_completed_serial()
                );
                println!(
                    "[upload-probe] t={sec} bytes={} limit={} refusals={} retirements={} records={}",
                    cx.draw_lists.1.allocations.bytes(),
                    cx.draw_lists.1.allocations.limit(),
                    cx.draw_lists.1.allocations.refusals(),
                    cx.draw_lists.1.allocations.has_pending_retirements(),
                    cx.draw_lists.1.allocations.record_count()
                );
                for id in cx.passes.id_iter() {
                    let pass = &cx.passes[id];
                    let Some(root) = pass.main_draw_list_id else {
                        continue;
                    };
                    let lists = cx.attached_draw_lists_from([root]);
                    let mut calls = 0;
                    let mut floats = 0;
                    let mut buffers = 0;
                    let mut missing_shaders = 0;
                    let mut z_min = f32::MAX;
                    let mut z_max = f32::MIN;
                    let mut first_buffer = None;
                    for list in lists.iter().copied() {
                        for i in 0..cx.draw_lists[list].draw_items.len() {
                            let item = &cx.draw_lists[list].draw_items[i];
                            if let Some(dc) = item.kind.draw_call() {
                                calls += 1;
                                floats += item.instances.as_ref().map_or(0, |v| v.len());
                                buffers += usize::from(item.os.inst_vbuf.buffer.is_some());
                                if first_buffer.is_none() {
                                    first_buffer = item.os.inst_vbuf.buffer.as_ref();
                                }
                                missing_shaders += usize::from(
                                    cx.draw_shaders.shaders[dc.draw_shader_id.index]
                                        .os_shader_id
                                        .is_none(),
                                );
                                z_min = z_min.min(dc.draw_call_uniforms.zbias);
                                z_max = z_max.max(dc.draw_call_uniforms.zbias);
                            }
                        }
                    }
                    println!(
                        "[draw-probe] t={sec} pass={id:?} root={root:?} lists={} calls={calls} floats={floats} gpu_buffers={buffers} dirty={} rect={:?} shift={:?} scale={:?}",
                        lists.len(),
                        pass.paint_dirty,
                        pass.pass_rect,
                        pass.view_shift,
                        pass.view_scale
                    );
                    println!(
                        "[shader-probe] t={sec} missing={missing_shaders} z={z_min}..{z_max} camera={:?} depth={:?}",
                        pass.pass_uniforms.camera_projection, pass.pass_uniforms.depth_projection
                    );
                    if let Some(buffer) = first_buffer {
                        gpu_state(sec, buffer);
                    }
                }
            }
        }),
        FontSet::International,
    )));
    let studio_http = resolve_studio_http();
    cx.borrow_mut().init_websockets(&studio_http);
    cx.borrow_mut().init_cx_os();
    remote::start_if_requested();
    Cx::event_loop(cx);
}
