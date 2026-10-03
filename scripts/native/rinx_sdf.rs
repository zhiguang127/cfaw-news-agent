// Temporary Windows workaround for the pinned host's MSDF white-screen trigger.
// Use Rinx's own entry point and compiled App; only the shared font mode changes.
// Remove this launcher after the upstream text-rendering fix passes the repro.
use rinx::app::App;
use rinx::makepad_widgets::*;
use rinx::makepad_widgets::text::{fonts::Fonts, rasterizer::OutlineRasterizationMode};
use std::{cell::RefCell, rc::Rc};

app_main!(App, configure: |cx: &mut Cx| {
    CxDraw::lazy_construct_fonts(cx);
    cx.get_global::<Rc<RefCell<Fonts>>>()
        .borrow_mut()
        .set_outline_rasterization_mode(OutlineRasterizationMode::Sdf);
    println!("[cfaw-host] Windows text workaround: SDF (pinned Rinx App)");
});
