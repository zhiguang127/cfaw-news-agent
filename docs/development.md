# 官方方式与兼容性核验

2026-09-28 先检查当前目录及 `/home/juvenile/Development/Hackathon` 向上的适用 `AGENTS.md`：初始读取时当前项目及这些父目录未发现该文件；工作期间新增根 AGENTS.md，发现后已完整阅读并保留。已阅读设计流程根 AGENTS、script-app 模板 AGENTS、QUICKSTART、SCRIPT-API、AI-SERVICES、script-app FLOW、Hub FIRST-APP/PUBLISHING 和目标 Rinx AGENTS、examples/miniapps/README、matrix-octos-script 示例。

采用本地现有提交，未更新依赖。官方源码链接固定到本次版本：

- [开发规范](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/ec0fa223f29800fdf02ee54311c4e309b9ca913d/AGENTS.md)
- [脚本 API](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/ec0fa223f29800fdf02ee54311c4e309b9ca913d/docs/SCRIPT-API.md)
- [Hub FIRST-APP](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/a72989ff2e4d51562693d05210b68e11f3bf3fcd/docs/FIRST-APP.md)
- [Hub 发布规范](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/a72989ff2e4d51562693d05210b68e11f3bf3fcd/docs/PUBLISHING.md)
- [Rinx Octos 适配器](https://github.com/hagency-org/Rinx/blob/68afcf796d303aaf646eeb832d65c450a56c92b5/src/host/octos.rs)
- [Rinx 导入与回调分发](https://github.com/hagency-org/Rinx/blob/68afcf796d303aaf646eeb832d65c450a56c92b5/src/miniapps/ui.rs)

官方同提交 `src/host/octos.rs` 已从 raw.githubusercontent.com 下载，与目标仓库 `cmp` 相同。通用设计文档早期写“脚本不能调用 Agent”，其 AI-SERVICES 页与 Rinx 代码明确给出了 Rinx 例外。本项目依据目标代码，只发送 `octos.turn.start {text}` 和 `octos.turn.interrupt {}`。Rinx 运行时已创建实例上下文，无需声明未使用的 session/history 能力。

Rinx `host/octos.rs` 限制 prompt 为 32 KiB，只接受 text，不允许应用传入会话、模型、workspace 或批准决定。`miniapps/ui.rs` 仅对 Complete 事件交付脚本回调，流式事件/批准由宿主处理；因此应用显示“分析中”直至最终结果。宿主服务约 185 秒超时，应用 190 秒兜底并请求中断。取消增加 generation，拒收旧回答；Back 关闭应用会撤销 lease 并关闭上下文。

目标仓库已有 `src/miniapps/ui.rs` 的 `View → Widget` Hub 可见性修复，本项目未修改，未依赖新增接口。既存二进制可能包含该修复，不能称为干净官方构建的 UI 验收。官方开发导入的独立 Mini apps 入口与核心服务已存在于固定提交。

## 脚本 API 来源

- `net.http_request` + `net.HttpEvents`：公开 SCRIPT-API 和 Makepad `platform/script/std/src/net.rs`。回调式超时 18 秒，序号保护旧响应；每源最多 10 条，解析前拒绝超过 1 MB 的响应。
- `parse_feed`：Makepad `platform/script/src/mod_feed.rs`。CDATA 时间是兼容性缺口：只标准化 `<updated>` 的 CDATA 包装，不改宿主。
- `is_string/is_array/is_number` 等：`platform/script/src/native.rs`；`try … {error handler}`：`platform/script/test/src/main.rs` 运行时测试。
- `fs.*`：受宿主约束的 `widgets/src/splash_storage.rs`，不读写任意主机路径；无 rename，因此交替写两个有序号的 JSON 副本，并回读校验。
- `on_render/render`：`widgets/src/view.rs`。各页面用独立 ScrollYView，避免滚动位置跨页面遗留。没有未公开脚本滚动调用。

## 实施中发现并处理的问题

- `tools/octo new` 必须新目录：先在 `build/template-probe/` 生成官方最小模板，原生输入并保存 `Persistence probe`。现有 README 在改写前备份到 build；没有整目录覆盖。
- Rinx 隔离实例显示 Matrix 登录页，用户确认先完成参考宿主验证，所以没有导入或模型成功回答的 Rinx 声明。
- 参考 runtime 中，计时器 resolve 的 promise 配合 await 曾导致错误路径停在加载中。改成纯回调传输后，失败/超时/空数据原生测试全部通过。
- Linux `/g?raw=1` 返回 `grab timeout (is this backend rendering?)`，无论 hidden 与否。使用独立 Xvfb + Mesa，ffmpeg 按 `/s` 返回的实际窗口位置采集。没有修改宿主、生成图片或拼接界面。
- 参考宿主与目标 Rinx 的依赖版本不同，现有成功测试不覆盖 Rinx 的完整 UI、网络和存储实现。

## 可重复检查

`python3 scripts/test-reference.py` 创建自己的虚拟显示，在真实 card-host 上通过 `/snap`、`/click`、`/m` 驱动，生成隔离的 `build/ui-tests/<case>/`。生产不可用场景调用真实 host.request；其他明确模拟的服务场景只替换临时测试包的传输函数。

`bash scripts/check-bundle.sh` 先拒绝已签名包，执行官方 stamp + check --allow-unsigned。`hub scan` 是扫描材料，不等于审核批准。修改任何包字节（包括截图）后必须重 stamp/check；导入需重新 Review。

目标仓库的旧 `tools/miniapp-package` 自己固定的是 AppPolicy `b0591e2c`，与当前 Rinx 主程序 `e8601b80` 不同，且没有现成二进制。因此另提供只读 `tests/policy-check`，使用主程序的精确政策 revision，复验同样的 manifest/digest/policy/script_source 步骤；不冒充完整 Package::load 或 UI 运行。
