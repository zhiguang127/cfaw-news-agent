# 新闻刷新与 Rinx 白屏调查

日期：2026-10-03，追加调查 2026-10-04（Asia/Shanghai）。分支：`fix/news-refresh-white-screen`。

当前证据指向四条问题路径：MSDF 字体模式触发整窗停止绘制、单次刷新处理超过 64 ms、脚本堆预算耗尽后的回调连锁错误，以及快速切页时 Windows D3D11 缓冲区计账滞留后静默跳过绘制。第 7 节记录最新缓冲区复现和本地宿主修补；各自的验证范围不能合并为所有白屏已根治或真实导入流程已验收。

本报告记录本次诊断结果；当前运行方式和验收状态分别以 [README](../README.md)、[Windows 开发说明](../docs/windows-development.md) 和 [验收记录](../docs/acceptance.md) 为准。

## 1. 整个宿主窗口变白：MSDF 路径是已验证触发条件

用户反馈的现象包括 Rinx 侧栏和应用以外区域全部变白，等待主页自动加载和手动刷新均可能出现。原生截图变成纯白时，UI 树仍有新闻与控件，点击返回关闭应用、请求重绘或改变窗口大小也不能恢复。白屏开始时没有对应的脚本超时、堆预算错误或宿主 panic。

为了检验“数据读取太频繁”的猜测，拉取了上游 [My Notes 原始应用](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/tree/0e59346e810ed694702b1df48f4283dc8104358c/templates/script-app/bundle)。应用代码没有修改：启动时读取一次 `notes.json` 并渲染列表，随后静置，没有新闻轮询或应用网络请求。只有测试 manifest 的隔离 ID、名称和资源额度作了调整。

同一份代码放入一个短笔记可保持显示至少 125 秒；放入 186 条公开新闻标题后，25 秒截图正常，40 秒截图已为纯白，125 秒以及关闭应用后仍纯白。因此，频繁数据读取不是复现此白屏的必要条件。标题数量与字符多样性是已观察到的触发输入，不能单凭它们判定具体渲染缺陷。

| 宿主与对照 | 输入／操作 | 观察结果 | 本地证据 |
| --- | --- | --- | --- |
| 原始固定 Rinx `68afcf79` | 原始 My Notes，186 条公开标题，静置 | 40 秒整窗纯白，关闭应用后仍白 | `.test-state/rinx-import-a57080da4a06/` |
| 同一已编译 Rinx App，提前初始化 Fonts 并设 SDF | 同一原始 My Notes 和输入 | 65 秒仍正常，关闭应用后宿主正常 | `.test-state/rinx-import-34182a21c8e9/` |
| 同一初始化时机与诊断代码，保留 MSDF | 同一原始 My Notes 和输入 | 40 秒整窗纯白，关闭应用后仍白 | `.test-state/rinx-import-0110a89db60d/` |
| 同一 SDF 诊断宿主 | 完整 CFAW 应用 | 125 秒仍显示，退出应用后宿主正常 | `.test-state/rinx-import-58689c386149/` |
| 官方 Rinx 1.1.0 `4b89097d`，未增加 SDF 配置 | 同一原始 My Notes，186 条标题，静置 | 40 秒整窗纯白，125 秒和关闭应用后仍白 | `.test-state/rinx-import-6b6fe998ab32/` |

SDF／MSDF 对照使用同一编译库，并在同一时机初始化 Fonts，排除了“更早分配字体纹理改变资源顺序”这个混淆因素。证据将触发条件缩小到 MSDF 启用的行为；尚未定位到具体的 Makepad、Rinx 或驱动缺陷。

Windows 临时入口 [rinx_sdf.rs](../scripts/native/rinx_sdf.rs) 使用 `rinx::app::App` 和原有 `app_main!`，在应用初始化前将全局 outline rasterizer 设为 SDF。[构建脚本](../scripts/build_windows_sdf_host.py) 链接宿主已有库，复制同一构建的字体、Rinx 资源及配套 Octos；[启动脚本](../scripts/run_windows.ps1) 保留原始默认字体模式的诊断选项。它影响整个宿主的字体渲染，不是应用 bundle 内的渲染修复，也不是正式上游补丁。应在上游修复通过同一复现后删除绕过。

最小 `app_main!` SDF 入口运行完整 CFAW 的后续记录为 `.test-state/rinx-import-c28c4b0c2a7d/`：245 秒截图仍有正常绘制的内容，期间操作过详情、滚动及三次手动刷新。该运行另有下面第 3 项堆预算错误，且约 305 秒观察点时用户关闭了窗口，因此不能记作完整长时间运行通过，不能推断刷新始终成功，也没有退出 mini app 后继续观察宿主的完整证据。

## 2. 单次跟踪处理超过 64 ms：已分批处理

固定 Splash isolate 为一次脚本入口设置 64 ms 时间预算。原来的 `records_check_tracking` 同步遍历最多 240 条新闻和最多 2,000 个已见 ID，在满容量固定输入中可以复现 `script time budget exceeded`。将整个同步函数延后到一个定时器仍会超时，因为单次工作量没有减小。这不是上述静置 My Notes 整窗白屏的必要条件。

[records.splash](../src/data/storage/records.splash) 已改为异步分批处理，沿用每批最多 64 项、最多 8 ms 的工作片设置；旧结果、取消任务和读取期间的状态变化通过任务代号、generation 与 revision 检查拒绝或重建，完成后再原子提交并保存。[controller.splash](../src/app/controller.splash) 等完成回调后更新 loading 与 UI。[news_runtime.splash](../tests/unit/news_runtime.splash) 检查满容量、重复输入、持久化及读取竞态；此前该套件实测 51 通过、0 失败。

## 3. 32 MiB 脚本堆预算耗尽：回调错误是后续症状

上述最小 SDF 入口的完整应用日志中，首个脚本错误为绑定函数参数时耗尽堆预算：需要 40 字节，余量只有 2 字节。后面才出现 `cannot set property on immutable object`、`push_all_fn_args called without prototype object` 和 `call target is not a function`。因此不能将最后一个错误单独当作回调语法错误修复。32 MiB 是 isolate 的脚本堆计量上限，不是整个 Rinx 进程占用内存的上限。

源代码复核发现一个预算与回收调度之间的缺口：

- [isolate GC 调度](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/widgets/src/widget_async.rs#L1515) 在 async pump 末尾，按 round-robin 给一个 isolate 回收机会。
- [needs_gc](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/platform/script/src/gc.rs#L737) 按对象、字符串等数量达到上次回收后的两倍触发，不检查堆额度压力。
- [堆额度计量](https://github.com/OctoSense-org/makepad/blob/6cf03859630761f5cb99ce7fcdfd8c30475d9ab8/platform/script/src/heap.rs#L240) 在回收或显式 reconcile 时重新计算 retained capacity；两次 reconcile 之间累积逻辑分配额。复用对象槽和释放瞬时 scope 不会相应退回每次参数绑定产生的计量，因此预算可能先耗尽，数量翻倍条件却未满足。

此调度代码在原 Makepad `6cf0385`、Rinx 1.1.0／当前 Rinx main 配套的 `1f3b1de`，以及 2026-10-03 核实的 Makepad main `c155f61d` 中没有实质差异。更新这些版本不能自动证明该问题已经消失。

应用目前的临时处理是在 `render_feed()` 中合并重复请求，安排一个短定时器；定时器先执行 `mod.gc.run()`，随后调用 `render_feed_now()`，保留 32 MiB 上限。该接口在目标 Splash isolate 中可用。选择独立事件是为了避免在列表生成中途，或同一 UI 回调仍有临时待处理参数时同步收集。当前线程状态、Widget 的 source 与函数引用由 VM 标记根保留。这是应用侧回收时机绕过，不是宿主 GC 根因补丁，也不能保证任意超过额度的真实存活数据都可运行。

[feed_runtime.splash](../tests/scenarios/feed_runtime.splash) 已扩展为 12 轮满容量刷新，每轮 13 个启用来源、最终保留 240 条新闻；还检查来源合并、失败保留缓存、取消／迟到结果和重复新闻的未读状态。测试报告（本地历史证据，未随仓库分发） 为 **34 通过、0 失败**。最新参考宿主的截图交互记录位于 `.test-state/runtime-102207b54f35/`；它不能替代目标 Rinx 实测。

修改 GC 时机后没有重启 Rinx 做实机复测，遵照用户明确不需要重新启动 GUI 验证的要求。固定输入回归通过不等于实时抓取、长时间驻留或整个宿主渲染问题全部通过。

## 4. 版本升级与交付边界

[依赖锁](../dev-dependencies.lock.json) 已记录 2026-10-03 核实的官方 main：Rinx `3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9`，App Hub `2bcb8985bc1d2c8856f2a61e65baa7ed443ae817`。各自遵循上游 Cargo.lock：Rinx 的 Makepad／bridge／Octos 随宿主一起更新；App Hub 参考宿主使用另一组 sibling 依赖，不能混用。隔离检出位于项目开发目录，已有共享 upstream 检出没有被切换或修改。

最初依赖升级时，最新宿主、配套内核、SDF 入口及参考工具已构建，没有重启当前账户实例。第 7 节为之后的独立原生窗口调查。历史 SDF 对照和 Rinx 1.1.0 的失败记录均保留其实际版本，不能移记到最新 main；各次验证不代表所有白屏已修复。

## 5. 可分享证据

英文 issue 文件仅为待审阅草稿，没有发送或创建上游 issue。可分享材料为原始 Notes bundle、公开标题构成的 `notes.json` 和必要的正常／纯白 PNG。诊断产物留在 Git 忽略目录；不复制完整 Rinx 日志、登录状态、Matrix 账号字段、模型配置或用户数据到报告或 issue 附件。

最短原始复现对照为 25 秒正常截图（本地历史证据，未随仓库分发） 与 40 秒纯白截图（本地历史证据，未随仓库分发）。Rinx 1.1.0 对照为 25 秒正常（本地历史证据，未随仓库分发） 与 40 秒纯白（本地历史证据，未随仓库分发）。这些链接指向本次工作区的本地产物，不表示附件已发布或上传。

## 6. 快速切页后内容区变白（2026-10-04）

用户补充的触发操作是应用内快速切换动态、跟踪、日程、收藏。新截图中 Rinx 底部导航和图标仍显示，但包括内容头部在内的上方区域为空白。它不同于第 1 节整窗白屏，不能用字体对照或截图直接认定是 GPU 缓冲区泄漏。

应用没有申请、映射或释放 GPU 缓冲区的代码；这些资源由 Makepad 宿主管理。脚本对象也由 VM 回收，现有 `mod.gc.run()` 只影响脚本堆，不是释放显存的接口。截图中的当前 Rinx 进程使用 SDF 入口，未启用 `--remote` 或日志文件重定向；因此本轮没有取得用户这次白屏的首条错误，也没有接管或退出该实例。

本轮先用 card-host 满容量回归确认原有 34 项断言与交互通过。另用固定 Rinx 的已编译库链接隔离 Splash/SDF 诊断窗口，沿用 32 MiB、16,000,000 manifest 指令额度和独立存储，不登录 Matrix，不提供模型服务。240 条合成新闻下，空关注列表的 320 次切页、1 个主题加 1 个关键词的 320 次切页，以及 12 轮刷新期间的 320 次切页（等待帧／连续排队两种方式）均未复现截图。该窗口验证 Rinx 配套 Makepad 的行为，不能当成完整 Rinx 页面与 mini-app 模态层验收。

同时发现另一条可重复的渲染额度问题：1 个主题加 10 个关键词时，新闻列表 `on_render` 达到宿主固定的 200,000 条 widget 回调指令上限，日志出现 `script instruction limit exceeded` 和 `on_render closure failed; discarding its output`。它与 manifest 的 16,000,000 条额度不是同一个限制，也没有在这个对照中出现堆额度或 GPU 错误。当时此缺口尚未修正；不能将它认定为用户截图的根因。失败日志与截图在 `.test-state/navigation-49e65347a18a/`，空关注正常对照在 `.test-state/navigation-2136afb82815/`。后续首页适配把关注匹配移出绘制回调，同一容量和规则数量的参考宿主及 Rinx 回归通过，记录见 [首页适配验收](../docs/acceptance.md#首页适配与天气保留验证2026-10-04)。

应用侧已减少切页重复工作：`render_main()` 合并到独立事件，在回收后按当前页面重建；进入日程只重建日程控件，不再刷新隐藏新闻列表；首次进入日程只构建一次编辑器。新增场景检查最后一次切页生效、未保存草稿保留、隐藏列表跳过和返回新闻恢复。此改动是减压保护，未证明截图白屏已修复。完整宿主的下一次复现应通过 `run_windows.ps1 -Mode Rinx -Diagnostic` 保留首条错误和原生截图／UI 树，再区分回调额度失败、挂载状态异常与实际渲染资源错误。

最终 card-host 回归 38 通过、0 失败，430×860 的 80 次快速切页及四页恢复检查通过，记录在 `.test-state/runtime-80d85de05844/`。最终 Rinx 配套库隔离窗口的刷新期间 320 次切页通过，记录在 `.test-state/navigation-42def4f3e141/`。本地未签名包已刷新摘要并通过 ZIP CRC／四个交付文件一致性检查；商店 `hub check` 因现有 bundle 缺少 `listing.json` 拒绝准入，本轮没有发布。


## 7. 无报错白屏：D3D11 计账滞留与静默拒绝（2026-10-04）

用户随后用 Diagnostic 模式再次复现。该模式将 stdout/stderr 重定向到 `.local-state/diagnostics/`，所以宿主的控制台空白是预期行为。直接检查该实例的文件和原生日志后，确实没有脚本时间、堆、widget 指令额度、`on_render` 失败、panic 或设备错误。远程点击能完成，UI 树仍含新闻、应用导航和宿主导航。临时隐藏/恢复应用内容不恢复绘制；把 pass 清屏色临时改红，原生截图变为整张红色。实验后已恢复所有值并关闭 Tweaker，没有退出用户实例。这证明该采样中的清屏执行了、控件仍在，不能把无日志误判为没有故障。

为追踪绘制资源，使用固定 Rinx 的同一编译库和真实 `rinx::app::App` 入口，带 SDF、完整宿主 Modal 结构、430×860 窗口，直接挂载满容量脚本 fixture。实例使用独立存储，不登录 Matrix，不接模型；跳过包审查/服务租约，因此仍不等于实际导入流程验收。新闻全为合成输入，保留 32 MiB 脚本堆。诊断每秒读取缓冲区计账、拒绝数、绘制树与设备状态。

原始设备额度约 1,369,964,544 字节。连续排队切换四页时，计账从几 MiB 增至上限；约 117 秒后产生 46,335 次额度拒绝，随后超过 114,000 次，原生截图纯白，控件树仍有页面。全过程没有 `[E]` 错误，设备移除 HRESULT 为 0，shader 缺失数为 0。证据在 `.test-state/navigation-72cde028f3c3/`。另把**仅测试实例**的绘制计账额度设为 64 MiB，约 40 轮时复现同样的纯白和无错误日志，证据在 `.test-state/navigation-0f934262d4a5/`。生产额度未调高。

源码与分步对照证实三个相连的问题：

1. D3D11 普通即时实例每次脏数据上传都申请新计账 lease，但 `create_buffer_or_update` 在尺寸未变时复用同一个 COM buffer。旧 lease 的回收每帧只检查最多 64 条，快速重绘产生大量重复计账。这个数字是宿主资源计账，不能等同于测量到的实际显存泄漏。
2. 通常的 Windows 重绘路径不调用 `poll_texture_lifetimes()`；渲染端只读取 GPU 已完成帧的旧快照。当页面切换只替换 buffer 而没有释放纹理时，完成序号停止更新，即使额外扫描也不能回收需要 GPU 完成确认的旧 lease。只修复复用/可见绘制的版本能保持画面，但 4,000 次切页后的计账仍约 386 MiB；增加有限扫描后的对照仍约 374 MiB（`.test-state/runtime-a1f0d3bc0d72/`），因此没有将这些中间版本判为修复通过。补充非阻塞完成状态刷新后，800 次切页短程对照稳定在约 1.5 MiB（`.test-state/navigation-7497a3301813/`）；该短程探针主动刷新只用于定位，最终回归探针只读取序号。
3. 计账 `reserve()` 失败后，旧路径直接 `continue` 跳过该 draw call，并要求下一帧重试，没有打印错误。下一帧仍遇到同一额度拒绝，就形成有控件树、无内容、无错误的白屏。相比之下，同一 Makepad 的 Metal/OpenGL 对可见 backing 使用 `reserve_visible()`，源码明确说明拒绝可见绘制会造成空帧或半帧。

[本地修补](../scripts/patches/makepad-d3d11-buffer-accounting.patch) 在普通 buffer 未重建时保留其计账 lease；每次重绘在回收前非阻塞轮询真实 D3D11 event query，并增加最多 1,024 条记录/额外 200 µs 的扫描，释放仍交给 worker。只有 query 的 BOOL 完成标志有效时才推进完成序号。可见上传使用与 Metal/OpenGL 相同的 `reserve_visible()`，使计账回收延迟不会静默删掉本帧内容。真实 `CreateBuffer`/`Map` 失败仍走宿主的错误处理，保留原沙箱额度。它属于 Windows 宿主修补，不是应用调用显存释放，也不提高生产内存限制；第 6 节的 widget 指令额度缺口由后续应用改动单独修正，不归于此宿主补丁。

构建脚本只修改项目私有 Cargo cache 内固定 Makepad 的 D3D11 文件，验证原始/修补后源码摘要。Cargo 对 Git 依赖默认假定不可变，单改文件会复用旧库，因此修补变更时显式清理 `makepad-platform` 产物并重编译依赖；编译库必须含 `CFAW D3D11 buffer accounting v3` 标记才记录补丁与库摘要。SDF 入口校验该记录，并按输入摘要生成新文件名，避免改写用户当前运行的旧程序。没有推送补丁或上游 issue。

最终修补后的完整 App/Modal 回归：`python scripts/test_runtime.py --suites feed --rinx-render-probe --navigation-rounds 1000`，38 项业务场景通过、0 失败。连续排队 4,000 次切页后，品牌与动态、跟踪、日程、收藏的标题 PNG 像素检查通过，四页截图人工检查正常。64 MiB 测试额度下，计账峰值 3,134,128 字节（约 2.99 MiB），结束值 1,679,072 字节（约 1.60 MiB），拒绝数 0，日志无 `[E]`，设备移除 HRESULT 始终为 0。GPU 完成序号持续跟进，最后采样 submitted/completed 为 11,545/11,543；探针没有执行完成状态刷新。报告与截图在 `.test-state/runtime-ac3a83ff5ba7/`。这表明此压力输入下的计账不再累积至额度上限，不表示整个进程或所有显存仅占 3 MiB。

最终 SDF 启动程序为构建 `d40b6bda538c`，独立空数据目录的真实入口登录页像素检查通过，记录在 `.test-state/sdf-smoke-451e42f5ef3e/`；缓存复用和可执行文件/配套内核摘要校验通过。用户的旧白屏实例仍运行旧代码，需完整退出 Rinx 后通过项目脚本启动才能加载原生补丁。没有替用户重启、访问登录数据或执行真实模型验收；直接 fixture 挂载不证明包导入审查、宿主服务租约或长期运行通过。
