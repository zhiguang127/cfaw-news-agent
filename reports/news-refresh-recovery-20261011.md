# 新闻刷新卡在 0/…：修复与验证

## 发现

真实公开 RSS 启动时，来源已经返回，但正文解析的临时字符串使原生脚本触及32 MiB堆上限，刷新没有完成。使用现有应用数据的隔离副本，还复现了历史结果集中核验与投影触及64 ms回调限制的问题。固定新闻样例的界面测试不足以覆盖这两条路径。

旧宿主的 GC 只按对象数量增长触发，少量大字符串不会及时触发回收。连续刷新还会出现回调分配失败及后续 prototype/immutable-object 错误。本次没有提高内存、时间或指令上限。

## 修改

- `reading_feeds.splash` 逐条解析并回收临时对象，限制保留的输入片段，完成后释放原始块。
- `feeds.splash` 每源增加30秒截止，覆盖 HTTP 成功后的解析和保存；超时结束该来源并保留可用数据。迟到结果仍受 generation 保护，完成只宣布一次；下一来源先安排再更新界面。
- 首页历史标注异步恢复，单轮有效性核验与单条投影分别执行。恢复时隐藏旧标注，新闻列表正常更新；当前来源行索引避免重复全表扫描。目标、决定、来源、正文修订与时效变化均使展示缓存失效，用户操作继续执行严格校验。
- `patch_news_gc_host.py` 为固定 Makepad 增加75%字节压力回收触发条件和接近上限时的容量释放。可重现构建入口为 `build_news_refresh_host.ps1`。新宿主文件为 `Rinx-main/target/release/rinx-news.exe`，SHA256：`b067ee76f801731a53246c8164a45ce44e0a30de241fc4a3fb505dbf17be52bd`。

## 验证

| 验证路径 | 结果 |
| --- | --- |
| 空数据启动，默认十来源，两轮真实联网刷新 | 158条；十来源均 fresh；busy=false；脚本错误0 |
| 现有关注、缓存和历史的隔离副本，八来源，两轮真实联网刷新 | 128条；八来源均 fresh；busy=false；脚本错误0 |
| 原生来源恢复固定场景 | 6项通过：解析回调丢失、超时完成、一次宣布、保留旧缓存、重试、拒绝旧代完成 |
| 正文证据、结果有效性及决定交互回归 | 30项通过；固定数据与模拟模型 |
| 结果页可见性与记录保留回归 | 6项通过 |
| Rust 字节压力场景 | 四条大字符串触发 GC；回收后降低占用；硬上限保持且超限分配被拒绝 |
| 新 standalone EXE 的空数据启动 | 启动正常，错误日志0；未替用户操作实际账号的 Review/Run |
| 组装、包检查 | 5项组装检查通过；ZIP CRC及8个文件字节核对通过；diff --check通过 |

真实刷新使用与最终 EXE 相同的 `librinx-f632403f98159b65.rlib`。原生界面快照确认新闻计数与“刷新新闻”按钮恢复，截图已检查。验证保持32 MiB沙箱上限；自动模型检查在诊断实例中关闭，没有使用用户模型或改写原始应用记录。

本地证据：

- 空数据：`.test-state/live-news-hn-1791656500991620600/report.json`、`feed.png`、`host.log`。
- 现有数据副本：`.test-state/live-news-hn-1791656601355280300/report.json`、`feed.png`、`host.log`。
- 恢复：`.test-state/news-refresh-recovery/report.json`。
- 正文/决定：`.test-state/tracking-evidence-flow/report.json`。
- 结果页：`.test-state/results-visibility/report.json`。
- 可执行文件启动：`.test-state/news-host-smoke/host.log`。

最终 unsigned bundle digest：`a7263863370c5f36d127203fa4773fff629c719824570fe19ed0907dccc60147`。包为 `build/cfaw-news.zip`。

## 使用

退出旧 Rinx，启动新的 `rinx-news.exe`，再 Review/Run 本项目的 `bundle` 目录。修复包含应用代码和本地宿主回收补丁，需同时更新；app ID和用户记录格式沿用原值。未修补的通用宿主与 App Hub 发布/评审不属于本次验证结论。
