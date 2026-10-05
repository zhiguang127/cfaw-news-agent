#!/usr/bin/env python3
"""Narrow, fail-closed GestureView patch in the project-private pinned cache."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MARKER = '// CFAW viewport pan and long-press release v1'
ORIGINAL_SHA256 = '633d633ed521e4d4dc2e4a6ac5d2ccf39984751d425df0629e9eaa83cc810ec3'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifacts_match(dev_root):
    release = dev_root / 'Rinx/target/release'
    try:
        metadata = json.loads((release / 'cfaw-gesture-patch.json').read_text())
        source = json.loads((dev_root / 'cfaw-gesture-source.json').read_text())
        widgets = list((release / 'deps').glob('libmakepad_widgets-*.rlib'))
        rinx = list((release / 'deps').glob('librinx-*.rlib'))
        return (len(widgets) == len(rinx) == 1 and metadata['source'] == source
                and metadata['patch_script_sha256'] == digest(Path(__file__))
                and metadata['widgets_sha256'] == digest(widgets[0])
                and metadata['rinx_sha256'] == digest(rinx[0])
                and metadata['executable_sha256'] == digest(release / 'rinx.exe'))
    except (OSError, ValueError, KeyError):
        return False


def patch_text(source):
    if MARKER in source:
        return source
    needles = [
        '    on_pan: ScriptFnRef,',
        '    fn local(&self, cx: &Cx, abs: DVec2) -> DVec2 {',
        '                // The press is spent on the long press: its release is no tap.\n                self.live = false;',
        '            Hit::FingerUp(e) if self.live => {',
        '                TouchState::Stop => {\n                    let Some(press) = self.touch.filter(|p| p.uid == t.uid) else { continue };',
    ]
    if any(source.count(n) != 1 for n in needles):
        raise ValueError('Pinned GestureView differs; preserve source and review patch')
    source = source.replace(needles[0], needles[0] + '\n    #[live]\n    on_pan_viewport: ScriptFnRef,\n    #[live]\n    on_release: ScriptFnRef,\n    #[live]\n    on_press: ScriptFnRef,\n    #[live]\n    on_viewport: ScriptFnRef,\n    #[rust]\n    viewport_sent: DVec2,')
    source = source.replace('    live: bool,', '    live: bool,\n    #[live(0.0)]\n    long_press_seconds: f64,\n    #[rust]\n    hold_timer: Timer,\n    #[rust]\n    hold_origin: DVec2,\n    #[rust]\n    hold_fired: bool,', 1)
    helper = '''    // CFAW viewport pan and long-press release v1
    fn pan(&self, cx: &mut Cx, dx: f64, dy: f64, phase: f64) {
        self.call(cx, &self.on_pan.clone(), &[dx.into(), dy.into(), phase.into()]);
        let size = cx.windows[CxWindowPool::id_zero()].window_geom.inner_size;
        self.call(cx, &self.on_pan_viewport.clone(), &[dx.into(), dy.into(), phase.into(), size.x.into(), size.y.into()]);
    }

    fn begin_hold(&mut self, cx: &mut Cx, abs: DVec2) {
        cx.stop_timer(self.hold_timer);
        self.hold_fired = false;
        self.hold_origin = abs;
        self.call(cx, &self.on_press.clone(), &[]);
        if self.long_press_seconds > 0.0 {
            self.hold_timer = cx.start_timeout(self.long_press_seconds.max(0.1));
        }
    }

'''
    source = source.replace(needles[1], helper + needles[1])
    source = source.replace('        self.view.draw_walk(cx, scope, walk)', '''        let step = self.view.draw_walk(cx, scope, walk);
        let size = self.view.area().rect(cx).size;
        if size.x > 0.0 && size.y > 0.0 && size != self.viewport_sent {
            self.viewport_sent = size;
            self.call(cx, &self.on_viewport.clone(), &[size.x.into(), size.y.into()]);
        }
        step''', 1)
    source = source.replace('        self.view.handle_event(cx, event, scope);', '''        self.view.handle_event(cx, event, scope);
        if self.on_viewport.as_object() != ScriptObject::ZERO
            && self.on_tap.as_object() == ScriptObject::ZERO
            && self.on_pan.as_object() == ScriptObject::ZERO
            && self.on_pan_viewport.as_object() == ScriptObject::ZERO
            && self.on_long_press.as_object() == ScriptObject::ZERO {
            return;
        }
        if self.hold_timer.is_event(event).is_some() && !self.hold_fired {
            let stationary_touch = self.touch.is_some_and(|p| !p.panning && !p.spent);
            if self.view.visible && !self.pinched && ((self.live && !self.panning) || stationary_touch) {
                self.hold_fired = true;
                if let Some(press) = self.touch.as_mut() { press.spent = true; }
                let at = self.local(cx, self.hold_origin);
                self.call(cx, &self.on_long_press.clone(), &[at.x.into(), at.y.into()]);
            }
        }''', 1)
    source = source.replace('                self.panning = false;\n                self.pan_sent = DVec2::default();', '                self.panning = false;\n                self.pan_sent = DVec2::default();\n                if self.live { self.begin_hold(cx, e.abs); }', 1)
    touch_start = '                    self.touch = Some(TouchPress {'
    if source.count(touch_start) != 1:
        raise ValueError('Pinned touch start differs')
    source = source.replace(touch_start, '                    self.begin_hold(cx, t.abs);\n' + touch_start)
    source = source.replace('Hit::FingerLongPress(e) if self.live && !self.panning && !self.pinched', 'Hit::FingerLongPress(e) if self.live && !self.panning && !self.pinched && !self.hold_fired')
    source = source.replace(needles[2], '                self.hold_fired = true;\n                // Keep capture live for a drag; FingerUp excludes held taps.')
    source = source.replace(needles[3], needles[3] + '\n                self.call(cx, &self.on_release.clone(), &[]);')
    source = source.replace(needles[4], needles[4] + '\n                    self.call(cx, &self.on_release.clone(), &[]);')
    # Only existing pan emission sites, not the forwarding call in our helper.
    for args in ('0.0.into(), 0.0.into(), 0.0.into()', 'delta.x.into(), delta.y.into(), 1.0.into()',
                 'delta.x.into(), delta.y.into(), 2.0.into()', 'at.x.into(), at.y.into(), 2.0.into()'):
        values = args.replace('.into()', '')
        source = source.replace('self.call(cx, &self.on_pan.clone(), &[' + args + ']);', 'self.pan(cx, ' + values + ');')
    # Release must be queued after pan end so the app saves the final position.
    source = source.replace('                self.call(cx, &self.on_release.clone(), &[]);\n                self.live = false;', '                self.live = false;')
    source = source.replace('                    self.call(cx, &self.on_release.clone(), &[]);\n                    self.touch = None;', '                    self.touch = None;')
    source = source.replace('                    } else if !press.spent', '                    } else if !press.spent')
    source = source.replace('                        self.tap(cx, t.abs, t.time);\n                    }', '                        self.tap(cx, t.abs, t.time);\n                    }\n                    self.call(cx, &self.on_release.clone(), &[]);')
    source = source.replace('                    return;\n                }\n                if e.is_over', '                    self.call(cx, &self.on_release.clone(), &[]);\n                    return;\n                }\n                if e.is_over')
    source = source.replace('                    self.tap(cx, e.abs, e.time);\n                }', '                    self.tap(cx, e.abs, e.time);\n                }\n                self.call(cx, &self.on_release.clone(), &[]);')
    source = source.replace('&& !e.has_long_press_occurred {', '&& !e.has_long_press_occurred && !self.hold_fired {')
    source = source.replace('                self.live = false;\n                if self.pinched', '                cx.stop_timer(self.hold_timer);\n                self.live = false;\n                if self.pinched', 1)
    return source


def prepare(dev_root, record=False):
    dev_root = dev_root.resolve()
    if not dev_root.samefile(ROOT / '.dev/vendor'):
        raise SystemExit('Use this project private .dev/vendor; shared Cargo caches are never patched')
    revision = json.loads((ROOT / 'dev-dependencies.lock.json').read_text())['target_pins']['makepad']
    candidates = list((dev_root / 'cargo-home/git/checkouts').glob('makepad-*/' + revision[:7]))
    if len(candidates) != 1:
        raise SystemExit('Expected one pinned checkout in this project private Cargo cache')
    checkout = candidates[0]
    head = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if head != revision:
        raise SystemExit('Wrong Makepad revision; no patch applied')
    path = checkout / 'widgets/src/gesture_view.rs'
    base = subprocess.check_output(['git', '-C', str(checkout), 'show', 'HEAD:widgets/src/gesture_view.rs']).decode()
    if hashlib.sha256(base.encode()).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit('Pinned original source hash differs; preserve checkout')
    original = path.read_text(encoding='utf-8')
    patched = patch_text(base)
    if original not in (base, patched):
        raise SystemExit('Gesture source has other edits; preserve checkout and review them')
    if original != patched:
        path.write_text(patched, encoding='utf-8')
    metadata = {'revision': revision, 'source_sha256': hashlib.sha256(patched.encode()).hexdigest(), 'native_build_required': True}
    (dev_root / 'cfaw-gesture-source.json').write_text(json.dumps(metadata, indent=2))
    if record:
        release = dev_root / 'Rinx/target/release'
        widgets = list((release / 'deps').glob('libmakepad_widgets-*.rlib'))
        rinx = list((release / 'deps').glob('librinx-*.rlib'))
        if len(widgets) != 1 or len(rinx) != 1:
            raise SystemExit('Build the pinned patched host before recording gesture artifacts')
        (release / 'cfaw-gesture-patch.json').write_text(json.dumps({'source': metadata,
            'patch_script_sha256': digest(Path(__file__)), 'widgets_sha256': digest(widgets[0]),
            'rinx_sha256': digest(rinx[0]), 'executable_sha256': digest(release / 'rinx.exe')}, indent=2))
    print('Gesture source prepared; rebuild makepad-widgets before claiming native drag support')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-root', type=Path, default=ROOT / '.dev/vendor')
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--check-artifacts', action='store_true')
    args = parser.parse_args()
    if args.check_artifacts:
        raise SystemExit(0 if artifacts_match(args.dev_root.resolve()) else 1)
    prepare(args.dev_root, args.record)
