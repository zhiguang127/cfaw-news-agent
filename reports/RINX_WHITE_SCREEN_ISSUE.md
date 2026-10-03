# Windows: mini app with 186 stored text items turns the entire Rinx window white after 25–40 seconds

Reviewable issue draft, prepared on 2026-10-03. **Not submitted.** This file
contains only public inputs and diagnostic conclusions; private Rinx/Matrix
logs and host state are excluded. The local investigation report is
[FAILURE_ANALYSIS.md](FAILURE_ANALYSIS.md).

Running the unmodified upstream **My Notes** example with 186 public news
headlines in its `notes.json` causes the entire Rinx window to become pure white
after 25–40 seconds. This includes the host UI. Closing the mini app through
the still-responsive native controls does not restore rendering.

The same My Notes code with one short note stays rendered for at least 125
seconds, including adding another note. This reproduces the problem outside
the original CFAW News app and does not require a news refresh or app network
request. The underlying cause is not confirmed; text diversity / amount is a
trigger demonstrated by the control experiments.

## Versions and environment

- Rinx: `68afcf796d303aaf646eeb832d65c450a56c92b5`
  ([source](https://github.com/hagency-org/Rinx/tree/68afcf796d303aaf646eeb832d65c450a56c92b5)).
- Resolved Makepad: `6cf03859630761f5cb99ce7fcdfd8c30475d9ab8`.
- Octoscript-Makepad: `6881fb6c3c3220e407633b0ba5211c3d42c7e625`.
- Octoscript: `68f6a9df55692b5d8ef8873a12721e279a3f40d6`.
- App policy: `e8601b80ce104db2e48208094714bdcffdce6b5a`.
- Clean Rinx source checkout; shared upstream sources were not modified.
- Tested native `rinx.exe` SHA-256:
  `cf2bebeaca9f9be5e10512e715a10cd8a012e52c5b6880e13828c12964484a9d`.
- Additional unmodified host tested: official Rinx **1.1.0**,
  [`4b89097d8791a7190d01de1c576979c93df0013d`](https://github.com/hagency-org/Rinx/tree/4b89097d8791a7190d01de1c576979c93df0013d),
  with its own locked Makepad `1f3b1dedfbb81424eb8dbf69e5e2c634fa73dc54`,
  bridge `cb66de073469063abeb2a5ab2a2bbf3cdb365745`, and OctoScript
  `dbd48cfb799551c11e30970c393777d29644a605`. It reproduces the same Notes
  white screen by 40 seconds; this upgrade alone did not resolve the repro.
- Windows 11 Pro, build `26100`, D3D11 renderer.
- Installed adapters: Intel UHD Graphics (`32.0.101.7085`) and NVIDIA GeForce
  RTX 3060 Laptop GPU (`32.0.16.1074`). Virtual Display Driver and ToDesk virtual
  display drivers are also installed. Which physical adapter handles this
  window has not yet been checked.
- Tested window: 1536 × 816 logical pixels, 1920 × 1020 physical pixels.
  The original app failure was also observed at a smaller window size.

## Reproduction

1. Obtain the upstream My Notes bundle from
   [OctoScript-App-Design-Flow, commit `0e59346e810ed694702b1df48f4283dc8104358c`](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/tree/0e59346e810ed694702b1df48f4283dc8104358c/templates/script-app/bundle).
   The `main.splash` used in this test is byte-identical to that file
   (SHA-256 `74533a10f1e64769fc9257cf365ab826b8cfd7183f2fa14cfd6dc4ff2dfcbc45`).
2. For isolated local import, set a unique manifest ID/name and use 16 million
   instructions, 32 MiB memory, and 8 MiB app storage. The only requested
   capability is `storage`; no script code changes are necessary. Refresh
   unsigned bundle integrity with `hub stamp`.
3. Populate that app's storage file `notes.json` with the attached array of
   186 public headline strings. It contains 600 distinct characters, including
   Chinese characters. Do not replace or share the Rinx host data directory.
4. Launch the pinned Rinx, go to **Discover → Mini apps → Import an app**,
   select the bundle, then **Review bundle → Run**.
5. Wait without interacting. At 3, 15, and 25 seconds the notes and host UI
   render normally. By 40 seconds the whole window is white and remains white
   at 65, 95, and 125 seconds.
6. Use the native remote API to click Back twice and close the mini app.
   The host remains white. In the original app experiment, clicking controls
   to request a redraw and maximizing the window did not restore rendering.

Expected: The scrollable text list and Rinx host continue rendering.

Actual: The app and entire host window become a single white color, while the
process and UI tree remain responsive.

## Controls and observations

| Experiment | Observed result |
| --- | --- |
| Unmodified My Notes, one short note; add another | Renders through 125 seconds |
| Unmodified My Notes, same 186 public titles | Entire window white by 40 seconds; remains white through 125 seconds and after app close |
| Minimal CFAW list, 186 repetitive synthetic titles | Renders through 65 seconds |
| Same minimal list, real title/source/id strings only, one initial render | Entire window becomes white within 25–40 seconds |
| CFAW app with news and weather HTTP callbacks explicitly disabled | Still reproduces |
| CFAW app with weather UI removed | Still reproduces |
| CFAW app with news list removed | Renders through 65 seconds |
| 4096 × 4096 text atlas in the real-title minimal repro | Still reproduces |
| Native diagnostic Rinx wrapper, early global SDF mode, same unchanged My Notes with 186 titles | Renders through 65 seconds; host renders after app close |
| Identical early Font initialization wrapper, global MSDF mode, unchanged My Notes with same 186 titles | Entire window white by 40 seconds and after app close |
| Same global SDF wrapper, full CFAW app | Renders through 125 seconds; host renders after app close |
| Official unmodified Rinx 1.1.0, same unchanged My Notes and 186 titles | Entire window white by 40 seconds; remains white through 125 seconds and after app close |
| Minimal `app_main!` SDF entry, full CFAW app on original Rinx library | Content still rendered in 245-second capture; details, scrolling, and three manual refresh attempts exercised; separate heap errors occurred, and user closed the window at about 305 seconds |
| Standalone card-host probe using the exact Rinx Makepad/bridge pins | Full app renders through 70 seconds, including a Modal root and forced main-VM GC |

The reference card-host and Rinx are different host integrations. The passing
standalone result is a useful control, not proof that Rinx integration works.

In additional native Rinx diagnostic runs:

- Native `/g?raw=1` captures become exactly one white color. The capture is
  copied before `Present`, so this is not solely a desktop capture artifact.
- `/snap` continues to report the populated UI with titles and status text.
- CPU draw trees, approximately 1200 draw calls, GPU instance buffers, shader
  handles, and quad geometry remain present after rendering fails.
- Recorded zbias values stay around 0–33, and the pass projection stays valid.
- D3D11 `GetDeviceRemovedReason` returns success (`HRESULT(0)`), with no
  recorded device-loss or allocation error.
- No script timeout, script budget error, or panic is reported at white-screen
  onset. A font-atlas UI stall occurs early but rendering initially recovers
  from it; the stall alone does not identify the later cause.

These diagnostics have not established whether the fault is in Rinx, shared
Makepad state, the font path, or a driver interaction. No verified host upgrade
or renderer fix is claimed here.

The SDF and MSDF diagnostic wrappers initialize Fonts at the same point and use
the same compiled Rinx library and instrumentation. Only the rasterizer mode
differs; this controls for the texture allocation order change caused by early
Font initialization. The result isolates the failure to behavior enabled by the
MSDF font path, while the exact renderer defect remains unidentified. A native
SDF mode change is a validated short-term workaround in these bounded runs;
the script app currently has no public rasterizer-mode option.

## Minimal SDF entry and its validation limits

The production-oriented local workaround removes the diagnostic instrumentation
and links the same compiled Rinx `App` through the existing Makepad entry macro:

```rust
use rinx::app::App;
use rinx::makepad_widgets::*;
use rinx::makepad_widgets::text::{fonts::Fonts, rasterizer::OutlineRasterizationMode};
use std::{cell::RefCell, rc::Rc};

app_main!(App, configure: |cx: &mut Cx| {
    CxDraw::lazy_construct_fonts(cx);
    cx.get_global::<Rc<RefCell<Fonts>>>()
        .borrow_mut()
        .set_outline_rasterization_mode(OutlineRasterizationMode::Sdf);
});
```

The `configure` hook runs before `App::script_mod`. It retains the existing
International font set, Rinx services, and App implementation. The executable
has the same build's Makepad/Rinx resources and locked Octos companion beside
it. Shared upstream sources and the original `rinx.exe` are unchanged. Project
implementation: [SDF entry](../scripts/native/rinx_sdf.rs),
[build/staging helper](../scripts/build_windows_sdf_host.py), and
[launcher](../scripts/run_windows.ps1).

The minimal entry's full CFAW run is recorded at
`.test-state/rinx-import-c28c4b0c2a7d/`. Its native capture still contains rendered
content at 245 seconds. A detail view, scrolling, return to top, and three
manual refresh attempts were exercised. However, this run reported a separate
32 MiB isolate heap-budget failure, followed by immutable-object and
`call target is not a function` errors. The user closed the window at about the
305-second checkpoint. This is bounded rendering evidence, **not a complete
application pass**, not proof that every refresh completed successfully, and
not evidence of a clean mini-app exit followed by continued host rendering.
The earlier instrumented SDF wrapper did render the full CFAW app through 125
seconds and the host after app close.

## Separate script-budget failures

The original CFAW app also exposed two independent script-runtime issues:

- A synchronous tracking check over 240 news items and up to 2,000 seen IDs
  exceeded the host's 64 ms entry budget. Splitting the check into bounded
  asynchronous batches resolved the fixed-input reproducer. This error was
  absent at the static My Notes white-screen onset.
- In the later minimal SDF-entry run, the first script error was a heap
  allocation limit failure while binding a function argument: 40 bytes needed,
  2 bytes left. The subsequent callback errors appeared after that failure.
  The heap's persistent budget accumulates logical allocation charges between
  reconciliations; the isolate's automatic GC checks object-count growth, not
  remaining byte headroom. Reused transient scopes can therefore consume the
  recorded allowance before the growth heuristic asks for a collection.

Relevant source: [isolate maintenance](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/widgets/src/widget_async.rs#L1515),
[GC heuristic](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/platform/script/src/gc.rs#L737),
[heap accounting](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/platform/script/src/heap.rs#L240),
and [public GC method](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/platform/script/src/mod_gc.rs#L23).
The corresponding GC scheduling/accounting files are unchanged in substance
in Makepad `1f3b1de` and the main revision checked on 2026-10-03,
[`c155f61d0e1600d2ec474209374444a38a09a470`](https://github.com/OctoSense-org/makepad/tree/c155f61d0e1600d2ec474209374444a38a09a470).

CFAW now coalesces feed-render requests into a short timer, runs `mod.gc.run()`
at the start of that event, and then rebuilds the list. Its 32 MiB limit is
retained. A 12-round full-capacity fixture returned 34 passed / 0 failed on
the reference runtime. This app-side workaround has not been retested by
restarting Rinx; the user explicitly requested no further GUI restart. It
cannot establish that the separate whole-host rendering fault is fixed.

## Latest-host upgrade status

On 2026-10-03, official Rinx main was
[`3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9`](https://github.com/hagency-org/Rinx/tree/3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9).
Its dependency graph still selects Makepad `1f3b1de`, bridge `cb66de073`, and
OctoScript `dbd48cfb`, with its own locked Octos companion. The project has
recorded this upgrade in [its dependency lock](../dev-dependencies.lock.json)
and is building isolated upstream checkouts. App Hub uses a separate reference
runtime graph; its newer sibling Makepad must not be substituted into the
Rinx graph implicitly.

No new-host GUI restart acceptance has been performed. The Rinx 1.1.0 failure
and original-host SDF controls above retain their actual version labels.
Neither an upstream renderer fix nor elimination of all white screens is
claimed for current main.

## Safe attachments

Attach only the isolated My Notes bundle, public `notes.json`, and before/after
PNG captures. Full Rinx logs/state can contain Matrix account details and are
deliberately excluded from this draft.

Local evidence for this draft: `.test-state/rinx-import-a57080da4a06/` contains
My Notes captures at 3/15/25/40/65/95/125 seconds and `after-close.png`.
Use `run-25.png` and `run-40.png` as the shortest before/after pair.
Mode controls: SDF `.test-state/rinx-import-34182a21c8e9/`, identical-initialization
MSDF `.test-state/rinx-import-0110a89db60d/`, and full CFAW SDF
`.test-state/rinx-import-58689c386149/`.
Official Rinx 1.1.0 Notes evidence: `.test-state/rinx-import-6b6fe998ab32/`
(`run-25.png` normal, `run-40.png` pure white, `after-close.png` still white).
Minimal SDF entry/full-app evidence: `.test-state/rinx-import-c28c4b0c2a7d/`;
use only selected PNGs and a sanitized error excerpt, never its full host log.

This is a prepared issue draft only; it has not been posted.
