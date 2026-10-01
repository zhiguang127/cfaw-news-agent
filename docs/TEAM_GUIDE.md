# 队友上手与开发分工

先运行真实新闻与数据检查，再开发自己负责的部分；Agent 同学额外在 **来源 → Test Octos** 验证连通性。业务开发在本仓库完成；Rinx 是宿主，Octos 是 Agent 执行环境，普通业务功能不需要修改它们的源码。

开发约定见 [AGENTS.md](../AGENTS.md)，架构与当前状态见 [README](../README.md)，版本以 [依赖记录](../dev-dependencies.lock.json) 为准。

## 1. 先分清三个位置

| 位置 | 用途 | 在这里做什么 |
| --- | --- | --- |
| `cfaw-news-agent/` | 本项目 | 开发新闻、分析和日程功能，打包应用 |
| `../demo-workspace/vendor/Rinx/` | 官方宿主检出 | 编译、启动 Rinx，准备它配套的 Octos |
| Rinx 的应用数据目录 | 宿主管理的数据 | 通过 Rinx 界面配置模型；不提交其中的账号、密钥和个人数据 |

上面的相对路径从本项目根目录计算。其他机器可以使用不同路径；不要把个人绝对路径写进项目。依赖记录不会自动下载安装软件。

当前 Rinx 配套内核位于它自己的 `target/release/octos`，由 Rinx 管理，按需启动。它的配置独立于个人安装的 `~/.octos`；在个人 Octos 中配过模型，不代表 Rinx 已配置好。

## 2. 第一次跑起来

### 准备宿主（在 Rinx 目录）

需要 Rust/Cargo、Python 3、图形桌面，以及对应系统的原生构建依赖。Linux 依赖命令见 [README](../README.md#1-准备官方-rinx)。使用依赖记录中固定提交的官方 Rinx，避免直接跟随 main。

已有检出时，从本项目根目录打开一个终端：

```bash
cd ../demo-workspace/vendor/Rinx
cargo build --locked --release --features agent_chat
python3 tools/package-octos.py desktop --app-binary target/release/rinx
./target/release/octos --version
./target/release/rinx
```

首次需要下载和编译依赖。没有检出的队友，先从 `https://github.com/hagency-org/Rinx.git` 克隆到自己的工作目录，再检出依赖记录中 `Rinx.commit` 对应的提交。不要覆盖已有工作目录。

构建完成后，日常只需在 Rinx 目录运行 `./target/release/rinx`。无需另外启动一份 Octos 服务。当前锁定内核版本为 `2.0.3-rc.13`，提交 `a6ea850`。

### 准备应用（在本项目根目录）

另开一个终端，在 `cfaw-news-agent/` 执行：

```bash
python3 scripts/package.py
realpath bundle
```

打包需要与依赖记录对应的 `hub` 可执行文件，默认查找 `../demo-workspace/vendor/OctoSense-App-Hub/target/release/hub`。缺少时先准备该工具；安装位置不同时用 `OCTO_HUB` 指定，例如：

```bash
OCTO_HUB=/path/to/hub python3 scripts/package.py
```

`/path/to/hub` 要替换为实际路径。可由队友提供适配本机平台的固定版本开发工具，或按 App Hub 上游构建说明准备；仅克隆仓库不会生成可执行文件。

脚本按 `scripts/assemble.py` 中的 `ORDER` 组装 `src/`，生成 `bundle/main.splash` 与 `build/source-map.json`，再刷新摘要并生成 `build/cfaw-news.zip`；不构建 Octos，也不发布到 App Hub。

### 配置和导入（在 Rinx 界面）

1. 登录 Matrix 账号，进入 **Mini apps → Import an app**。
2. 配置 **Rinx 自带的本地 Octos**：填写 Provider、Model、API key；使用自定义模型端点时再填写 Base URL，点击 **Use this device**。例如 Provider 填 `deepseek`，Model 填账号可用的模型 ID（如 `deepseek-chat`），默认端点的 Base URL 留空，API key 填模型提供方控制台获取的密钥。完整字段说明见 [README 配置步骤](../README.md#5-配置-rinx-自带-octos-并测试)。
3. **OctoSense bundle folder** 填 `realpath bundle` 输出的绝对路径，Room 留空。
4. 点击 **Review bundle**，核对 `CFAW News`、新闻网络域名以及 `storage`、`net`、`images` 和三个 `octos.*` 服务权限，然后点击 **Run**。
5. 新闻浏览无需模型。需要连通性测试时进入 **来源**，滚动到底部点击 **Test Octos**；看到 `Octos replied: ...` 和实际模型回复才算本次调用完成。

**密钥配置注意：**当前宿主保存后会清空密钥输入框。如果保留 Provider、Model，又空着密钥重复点击 **Use this device**，会覆盖掉原密钥。要修改配置时重新填写密钥；只是打开应用时不必重复保存模型配置。密钥只输入宿主，不写入代码、截图或提交记录。

本项目由 Rinx 启动并管理配套 Octos，无需另外启动 HTTP 服务。导入页的 **Octos server URL / Octos profile / Octos access token** 留空，无需点击 **Connect Octos**。本地 Octos 仍可使用云端模型 API；模型 Base URL 是模型端点。

### 演示新版界面

默认自动请求真实新闻；来源页管理 17 个公开来源并显示各来源的实际状态。切换“与你有关”、跟踪来源、收藏条目，再在“管理追踪”添加主题与关键词，重开应用验证状态恢复。收藏、规则和已读记录分别保存在宿主私有 JSON 文件中，旧 `saved.json` 可迁移。新闻失败显示失败或旧缓存，详情展示 feed 摘要与来源链接。

当前关联提示是规则匹配，没有 Agent 推理。日程页是空状态，真实 Agent 分析、日程管理、跨设备同步和后台监测仍需开发；Test Octos 只在手动点击时调用宿主。

## 3. 每个人在哪个目录做什么

**业务源码维护在 `src/`，宿主执行自动生成的 `bundle/main.splash`。** `scripts/package.py` 调用组装器，按固定顺序拼接 OctoScript 文件与 JSON 来源目录。新增可执行文件要加入 `ORDER`；文档和提示词不会自动执行。不要手工修改生成入口。

| 负责人 | 目录 | 负责的交付 |
| --- | --- | --- |
| 前端同学 | `src/frontend/pages/` | 动态、详情、跟踪、日程、收藏页面及其交互状态 |
| 前端同学 | `src/frontend/components/` | 多页面复用的新闻条目、Agent 提示、建议确认 UI；样式先放 frontend 层 |
| Agent 同学 A（建议分工） | `src/agent/runtime/` | 上下文组装、Octos 调用、任务状态、超时、取消、旧响应处理；接口见 [Agent A runtime interface](agent-a-interface.md) |
| Agent 同学 B（建议分工） | `src/agent/prompts/`、`src/agent/results/` | 分析提示词、结果解析、证据与日期核验、建议去重和变化判断 |
| 数据同学 | `src/data/ingestion/` | 新闻源请求、解析、统一字段、来源保留与去重 |
| 数据同学 | `src/data/retrieval/` | 关键词和语义召回、融合排序、不可用时的降级；明确索引的运行位置 |
| 数据同学 | `src/data/storage/` | 新闻缓存、用户关注、日程与决策历史；版本和迁移 |
| 共同维护，每项改动指定一个集成人 | `src/app/` | 初始化、导航、用户动作到各层的连接 |
| 共同维护 | `src/contracts/` | 各层共享字段、错误与状态约定；现有入口是 [analysis.md](../src/contracts/analysis.md) |
| 各功能负责人 | `tests/fixtures/`、`tests/unit/`、`tests/scenarios/` | 固定样例、实际 OctoScript 数据测试与业务场景；运行 `python scripts/test_runtime.py` |

Agent 两位同学共同实现**一个业务 Agent**。A/B 是协作侧重点，不是两套 Agent。后续 Agent 模块须加入已验证的组装顺序并连接调用方；bundle 不执行任意 Rust、Python，也不自动读取提示词文件。

各层只维护自己的源文件，`app/` 连接数据和页面，`contracts/` 对齐共享结构。生成入口不能成为第二份手工业务源码。

其他目录：`bundle/manifest.json` 声明真实需要的权限和域名；`bundle/assets/` 放实际资源；`bundle/screenshots/` 放实际运行截图；`scripts/` 放开发和打包工具；`docs/` 放协作说明；`build/` 是忽略提交的生成产物。空资源目录在新克隆中可能不存在。

## 4. App 如何使用 Agent

目标业务流程：

```text
用户关注 / 日程 → 数据层检索证据 → Agent 组织上下文
                                  ↓
                         Rinx → Octos → 模型
                                  ↓
             结果核验 → 页面展示 → 用户确认 → 日程更新
```

后续 Agent 集成可先由应用获取候选新闻，再提交给 Octos 分析。当前第一版只获取和匹配新闻，不提交分析。数据层代码不会自动注册为 Octos 工具。

实际可参考 `src/agent/runtime/connectivity.splash` 中的 `test_octos()`：

- `host.request("octos.session.open", {}, callback)` 打开应用作用域上下文。
- `host.request("octos.turn.start", {text: ...}, callback)` 发送任务文本，回调检查 `is_ok`，读取 `data.text` 或 `error`。
- `host.request("octos.turn.interrupt", {}, callback)` 请求中断。现有按钮设置了超时和重复点击保护。

`text` 必须非空且不超过 32768 字节。业务数据应按 [分析契约](../src/contracts/analysis.md) 组织进文本；返回文本需要应用自行解析和核验。契约目前是设计文档，不是已实现的序列化器或验证器。

一次业务联调先用一组明确标注的固定样例：一个关注、一条带来源的新闻、一个日程，验证“有变化则建议、无变化则说明”。随后覆盖重复新闻、缺日期、AI 不可用、已拒绝建议和过期日程版本。真实新闻失败不能偷偷换成演示数据，模型输出不能直接修改日程。

## 5. 日常开发与交接

1. 开工先看 Git 状态和 [AGENTS.md](../AGENTS.md)，确认本次涉及的字段、模块及入口集成人。
2. 变更共享接口时同步修改生产方、消费方和固定样例；先确定代码在哪执行，再决定语言与后缀。
3. 修改运行源码或 manifest 后执行 `python3 scripts/package.py`。然后退出旧应用，重新 **Review bundle → Run**。数据逻辑修改执行 `python scripts/test_runtime.py`；仅文档修改不必重打包。
4. 验证受影响的交互；改 Agent 时保留一次真实调用验证，改数据处理时验证来源、日期、去重和失败状态。
5. 交接写清“改了什么、如何运行、实际测了什么、还有什么没做”。只提交有关文件；ZIP、密钥、个人模型配置和私人日程不入库。

Rinx 本地导入、打包、App Hub 准入和正式上架是不同步骤。当前先完成本地业务闭环，发布另按 README 和官方契约准备。

## 6. 常见问题

| 现象 | 处理 |
| --- | --- |
| `The assistant is off` | 在导入页配置本地模型并点击 Use this device，再重新打开应用 |
| `failed to create LLM provider`、API key 为空 | 在 Rinx 重新填写完整模型配置和密钥；个人 Octos 登录不会自动带入 |
| 找不到配套 Octos | 在实际运行的 Rinx 检出中执行内核打包命令，确认 `octos` 与 `rinx` 位于同一目录 |
| 按钮不存在或权限缺失 | 确认导入本项目最新 bundle，重打包并重新 Review，而不是沿用旧快照 |
| 测试超时 | 查看按钮反馈并检查模型/服务状态；中断未确认时关闭再打开应用 |
| Matrix 账户数据 404 | 这不是 Octos 接口错误；用 Test Octos 的具体错误继续排查 |
| `src/` 改了但界面没变化 | 重新打包并导入；新增执行文件加入 assemble.py 的 ORDER，运行 --check 检查生成入口 |

2026-09-29：开发者已反馈本机 Test Octos 连通成功；这不代表完整业务 Agent、所有机器或 App Hub 安装路径已验收。每位队友应在自己的环境完成一次测试。
