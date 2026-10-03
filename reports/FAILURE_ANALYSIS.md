# 新闻刷新与 Rinx 白屏调查

日期：2026-10-03（Asia/Shanghai）。分支：`fix/news-refresh-white-screen`。

当前证据指向三个独立问题：MSDF 字体路径触发整窗停止绘制、单次刷新处理超过 64 ms，以及脚本堆预算耗尽后产生回调连锁错误。已有两项应用改动和一项 Windows 宿主临时绕过，但不能据此宣称白屏根治或最新宿主完成 UI 验收。

本报告记录本次诊断结果；当前运行方式和验收状态分别以 [README](../README.md)、[Windows 开发说明](../docs/windows-development.md) 和 [验收记录](../docs/acceptance.md) 为准。上游问题的可审阅英文草稿见 [RINX_WHITE_SCREEN_ISSUE.md](RINX_WHITE_SCREEN_ISSUE.md)，尚未发布。

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

[feed_runtime.splash](../tests/scenarios/feed_runtime.splash) 已扩展为 12 轮满容量刷新，每轮 13 个启用来源、最终保留 240 条新闻；还检查来源合并、失败保留缓存、取消／迟到结果和重复新闻的未读状态。[测试报告](../.test-state/runtime-102207b54f35/combined-report.json) 为 **34 通过、0 失败**。最新参考宿主的截图交互记录位于 `.test-state/runtime-102207b54f35/`；它不能替代目标 Rinx 实测。

修改 GC 时机后没有重启 Rinx 做实机复测，遵照用户明确不需要重新启动 GUI 验证的要求。固定输入回归通过不等于实时抓取、长时间驻留或整个宿主渲染问题全部通过。

## 4. 版本升级与交付边界

[依赖锁](../dev-dependencies.lock.json) 已记录 2026-10-03 核实的官方 main：Rinx `3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9`，App Hub `2bcb8985bc1d2c8856f2a61e65baa7ed443ae817`。各自遵循上游 Cargo.lock：Rinx 的 Makepad／bridge／Octos 随宿主一起更新；App Hub 参考宿主使用另一组 sibling 依赖，不能混用。隔离检出位于项目开发目录，已有共享 upstream 检出没有被切换或修改。

截至本报告记录时，最新宿主、配套内核、SDF 入口及参考工具的升级构建已完成。没有新宿主 UI 重启验收；历史 SDF 对照和 Rinx 1.1.0 的失败记录均保留其实际版本，不能移记到最新 main。当前结论是“已识别 MSDF 触发条件，并修正应用的两条预算压力路径”，不是“所有白屏已修复”。

## 5. 可分享证据

英文 issue 文件仅为待审阅草稿，没有发送或创建上游 issue。可分享材料为原始 Notes bundle、公开标题构成的 `notes.json` 和必要的正常／纯白 PNG。诊断产物留在 Git 忽略目录；不复制完整 Rinx 日志、登录状态、Matrix 账号字段、模型配置或用户数据到报告或 issue 附件。

最短原始复现对照为 [25 秒正常截图](../.test-state/rinx-import-a57080da4a06/run-25.png) 与 [40 秒纯白截图](../.test-state/rinx-import-a57080da4a06/run-40.png)。Rinx 1.1.0 对照为 [25 秒正常](../.test-state/rinx-import-6b6fe998ab32/run-25.png) 与 [40 秒纯白](../.test-state/rinx-import-6b6fe998ab32/run-40.png)。这些链接指向本次工作区的本地产物，不表示附件已发布或上传。
