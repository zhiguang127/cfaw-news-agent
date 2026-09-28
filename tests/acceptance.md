# MVP 验收记录

日期：2026-09-28。源码及二进制版本见 `dev-dependencies.lock.json`。目标 Rinx 与参考 card-host 分开记录，测试替身不计作真实服务成功。

## 已验证

| 项目 | 实际执行与结果 |
| --- | --- |
| 官方工具 | `tools/octo doctor` 全部 OK；项目 `scripts/doctor.py` 固定 SHA 一致，Rinx 已有脏文件明确提示 |
| 官方最小模板 | `octo new build/template-probe ...` → card-host admitted；原生输入 `Persistence probe`，点击 Add，退出重开仍显示记录。完整截图 `build/template-final.png` 已查看 |
| Rinx 探针 | 启动独立 RINX_DATA_DIR 实例，只观察到真实 Matrix 登录页；未复用用户正在运行的 Rinx 会话 |
| 应用内真实网络 | 独立 Splash 探针：Apple HTTP 200 / 20 条；NVIDIA HTTP 200 / 18 条。生产包每源显示最多 10 条，共 20 条；不是终端 curl 代替应用接入 |
| 原生完整可用部分 | 打开 → 加载真实新闻 → 详情显示来源 URL 与时间 → 点击真实 host.request 得不可用错误 → 保存关注 → 退出重开 → 关注仍显示同一来源 URL |
| UI 回归 | `python3 scripts/test-reference.py`：16 tests，26.434s，OK。以 Makepad 官方远程桥真实点击、滚动、重启；没有零测试/跳过 |
| 窄屏 / 宽屏 | 412×892 与 1000×820；列表、详情、保存、关注均实际操作。修复跨页面残留滚动位置后已重跑 16 项测试 |
| 目标政策 | `CARGO_NET_OFFLINE=true scripts/check-target-policy.sh`：目标 Rinx AppPolicy e8601b80 的 digest、manifest、权限解析和脚本入口 PASS。只读开发验证器，不是 Rust 应用后端，不代替 Rinx UI 验收 |
| Hub 检查 | `bash scripts/check-bundle.sh`：PASSED，仅 unsigned warning |
| Hub 扫描 | `hub scan bundle --packet build/review.json`：生成 7 问材料，回答见 `docs/review-answers.md`；没有配置外部 reviewer，没有任何审核批准或发布 |

最终检查的官方输出：

```text
cfaw-news-agent 0.1.0 — PASSED
  [warning] publisher-signature: unsigned: accountability rests on the hub alone
  grants: capabilities {"net", "octos.turn.interrupt", "octos.turn.start", "storage"}, hosts {"blogs.nvidia.com", "www.apple.com"}, storage 2097152 bytes, agent none
```

目标版本验证器输出：

```text
PASS target Rinx AppPolicy e8601b80: cfaw-news-agent 0.1.0 · 18680 script bytes · {"net", "octos.turn.interrupt", "octos.turn.start", "storage"}
```

## 16 项测试覆盖

1. 生产代码调用真实 card-host Octos 服务，返回 `no service answers "octos" on this device`；重试不写入伪造分析。
2. 重复保存一条记录、退出重开、读取 URL、移除、再重开保持空。
3. 请求失败、演示保留错误、刷新重试。
4. 空 RSS 与非 RSS 响应。
5. HTTP 503。
6. 迟到的刷新结果不能覆盖用户已选择的演示模式。
7. 两个存储副本不可用时保留原文件并阻止写入。
8. 一个副本损坏时恢复另一个有效副本。
9. **测试桩**完成回调保存分析、重启读回；检查新闻 JSON 和不可信输入约束进入 prompt。
10. **测试桩**中断后迟到的完成回调不得写入回答。
11. 在启动后阻塞保存路径，实际 fs.write 失败显示错误且关注未新增。
12. Apple CDATA 更新日期可解析，仍不作为首次发布时间。
13. 保留生产超时逻辑，只使测试传输不返回；超时退出加载态。
14. 非获准来源链接不进入结果。
15. **测试桩**分析期间切换另一新闻，回答只写回原条目。
16. 重新获取同 URL 的无分析条目后再次保存，不清空关注中已有的分析。

临时替身位于 `build/ui-tests/`，明确文本“测试桩回答：不是模型分析”。生产 `bundle/` 没有测试开关、成功模拟回答或模型凭据。

## 实际截图

均为最终生产包在参考 card-host 运行时的截图，已逐张查看。列表窄屏图保留了 Apple 已返回、NVIDIA 尚在加载的真实过程；宽屏图为两源完成后的状态。最终焦点样式调整另外进行了原生点击、导航、错误展示和无 Splash 错误日志检查。没有 Rinx 应用内截图。

- [新闻列表](../bundle/screenshots/01-news.png)：本次实际请求的官方 feed。
- [来源与时间详情](../bundle/screenshots/02-detail.png)：Apple 未提供首次发布时间，更新时间单列。
- [重开后的关注](../bundle/screenshots/03-watch.png)：真实来源记录恢复。
- [Agent 不可用](../bundle/screenshots/04-agent-unavailable.png)：滚动后的真实错误信息。
- [宽屏列表](../bundle/screenshots/05-wide.png)：1000×820 实际窗口。

Linux 的官方 `/g` 返回 `grab timeout`，所以使用 Xvfb 中的真实可见窗口，通过 ffmpeg 按宿主 `/s` 返回的窗口矩形采集。没有生成、合成或借用别的应用截图。

## 仍须在 Rinx 完成

用户已确认“先完成参考宿主验收，Rinx 登录后我手动验收”。以下项目 **未通过验收，不作兼容性成功声明**：

- [ ] 登录 Matrix → Mini apps → Import an app → 输入 `bundle` 全路径 → Review bundle → Run。
- [ ] Rinx 的实际 Splash 运行时显示中文界面；Apple / NVIDIA 网络请求成功，详情链接正确；Back 后重新打开。
- [ ] 在宿主配置 Octos 与模型；点击分析，收到真实模型五部分回答，并核对事实和推断边界。
- [ ] 分析运行时点击取消；以及直接 Back 退出，确认 Octos 停止、会话撤销和没有旧结果跨实例写入。
- [ ] 保存真实分析 → 关闭应用 → 重开 → 关注中仍有链接和该分析；重复收藏与移除正常。
- [ ] 切换 Matrix 账号确认宿主存储隔离（应用不自行实现账号逻辑）。

## 已知限制

- 参考宿主没有 Octos；真实 Agent 成功、宿主模型配置及服务中断未测。仅写提示词不能保证模型遵循，宿主工具批准仍需用户判断。
- Rinx 现有仓库有预先存在的 Hub 可见性修改，未动它；仅登录页探针使用其已有二进制。目标依赖与参考宿主不同。
- 两个来源聚焦公司自身叙述，不能代表全市场；无自动全文核验、翻译、排序评分或自动刷新。
- URL 以文本显示和复制，未实现一键内嵌浏览全文；拒绝其他域名链接。
- 日期可缺失；Apple 更新不等于首次发布；不承诺时区由所有宿主统一设为 UTC。
- 关注副本恢复可能回退最近一次修改；移除不是安全擦除。未做跨账号迁移或后台监控。
- listing 的隐私 URL 是明确标注的未发布占位。正式发布前需发布者给出真实支持/隐私页面、平台声明和签名；此次未进入发布流程。

日志：`build/tests.log`、`build/hub-check.log`、`build/target-policy.log`、`build/hub-scan.log`、`build/doctor.log`。原始诊断与本地状态被 Git 忽略。
