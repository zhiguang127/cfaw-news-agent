# 架构、宿主接入与运行

产品入口见 [README](../README.md)，Windows 构建与资源准备见 [Windows 开发说明](windows-development.md)，当前能力和验证只在 [验收记录](acceptance.md) 维护。

## 目录结构

目录用于稳定的职责分组，具体功能用文件区分。已实现的 OctoScript 文件由组装器按固定顺序拼接，在同一脚本作用域执行；Markdown 契约、提示词与分析 fixtures 不会自动加载为运行代码。

```text
cfaw-news-agent/
├── README.md                      # 产品与启动入口
├── AGENTS.md                      # 开发约定
├── dev-dependencies.lock.json     # 工具与宿主版本
├── LICENSE / NOTICE
├── .gitignore
├── docs/
│   ├── TEAM_GUIDE.md              # 队友上手、目录分工与联调
│   ├── README.md                  # 文档索引与维护职责
│   ├── development.md             # 架构、宿主接入与运行
│   ├── acceptance.md              # 当前能力、缺口与验证
│   ├── agent-integration-plan.md  # 尚未完成的工作
│   ├── windows-development.md    # Windows 本地环境与已验证的运行边界
│   ├── fixture-expectations.md    # 固定样例 expected 字段契约
│   ├── agent-a-interface.md       # Agent A runtime 接口交接
│   ├── frontend-signal-api.md     # 天气、节假日与汇率调用速查
│   ├── splash-runtime-notes.md    # 实测语言约束
│   └── archive/                   # 旧计划与日期报告
├── src/
│   ├── app/                       # 启动、导航、三层连接
│   ├── contracts/                 # 三层共享的数据结构与接口
│   ├── frontend/                  # 前端：1 人；样式文件直接放本层
│   │   ├── pages/                 # 动态、详情、跟踪、日程、收藏
│   │   └── components/            # 新闻条目、Agent 提示、建议卡片
│   ├── agent/                     # 单 Agent：2 人共同开发
│   │   ├── runtime/               # Octos 宿主适配、任务生命周期
│   │   ├── prompts/               # 新闻分析与日程建议提示词
│   │   └── results/               # 结果解析、证据核验、变化识别
│   └── data/                      # 数据与检索：1 人
│       ├── ingestion/             # 新闻源、天气、节假日、汇率请求与解析
│       ├── retrieval/             # 查询、关键词/语义召回、融合排序
│       └── storage/               # 新闻、关注、日程、城市选择及历史存储
├── bundle/                        # 运行与交付包
│   ├── main.splash                # 自动生成的宿主入口；不要手工编辑
│   ├── manifest.json
│   ├── assets/                    # 真实本地资源，暂空
│   └── screenshots/               # 真实截图，暂空
├── scripts/
│   ├── assemble.py                # 分层源码组装及源行映射
│   ├── test_runtime.py            # 隔离存储下执行实际数据与 Agent 模块检查
│   ├── package.py                 # 组装、摘要刷新与 ZIP 打包
│   ├── stage_windows_resources.ps1 # 将宿主资源放到二进制旁
│   └── run_windows.ps1            # 启动已准备的 Windows 参考宿主或 Rinx
├── tests/
│   ├── fixtures/                  # 明确标注的固定样例
│   ├── unit/                      # 数据处理、检索、接口约定等检查
│   └── scenarios/                 # 新闻变化到日程确认的完整场景
└── build/                         # 本地生成产物，Git 忽略
```

维护时遵循以下约定：

- 一个页面、一个组件或一项小职责优先对应一个文件，不再为 `feed`、`news_post`、`workflow` 等单独建目录。
- `agent/runtime/` 只做应用侧适配，不实现 Octos 内核；提示词与结果核验分别放在 `prompts/`、`results/`。两个人共同维护同一个 Agent。
- `contracts/` 用文件定义新闻、关注、日程、分析结果与三类信号，生产方和消费方共同维护。
- 某组实现需要多个相关文件、在同一目录中难以查找时，再增加子目录。语言和文件后缀在运行方式确定后选择。
- 添加真实实现后移除对应 `.gitkeep`；不预建空代码文件。

### 为什么有 assets 和 screenshots

- `assets/` 放随应用分发的静态资源，例如图标、插图或字体；它不是业务代码目录，也不要求当前应用必须使用本地图片。正式上架的图标由 `listing.json` 引用，常规路径是 `assets/icon.svg`。
- `screenshots/` 放实际运行应用后截取的界面，供商店展示和审核。真实截图让用户和审核者看到实际产品；设计稿、生成图或概念预览不能代替运行截图。截图本身也不能证明所有交互已经通过测试。
- **当前 Rinx 本地开发导入无需 listing、图标和截图。** 这两个目录可以为空；不要为了凑齐目录放假资源。正式 App Hub 上架需要 listing、图标和至少一张截图，具体要求以[官方发布契约](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.md#the-listing)为准。

这两个目录名是资源组织惯例，实际引用路径由应用及 listing 指定。空目录不放 `.gitkeep`，也不会随 Git 克隆保留；新增真实资源时再创建即可。

## 层间职责与协作边界

1. **前端发起操作并展示状态。** 页面通过应用集成接口发起刷新、跟踪、分析或日程确认，不直接承担检索和模型调用逻辑。
2. **数据层负责提供证据。** 接入层保留来源和时间，检索层返回候选及其匹配信息；Agent 负责判断候选是否影响用户关注或日程。
3. **混合检索需要明确实现。** 不同召回路径及结果融合统一放在 `data/retrieval/`，需要时再拆成不同文件。语义召回依赖的模型、索引及运行位置尚未选定；仅由模型判断候选相关性时，该逻辑归 Agent 层，不宣称已经实现向量检索。
4. **建议与执行分开。** Agent 输出带证据的建议；应用处理用户确认后更新日程，避免模型回复直接修改用户安排。
5. **跟踪状态与触发方式分开。** 先支持打开应用或手动刷新时检查；后台运行、系统通知和推送须依据目标宿主的实际能力另行接入。
6. **共享接口先对齐。** 修改 `contracts/`、`app/`、manifest 或打包流程时，由相关负责人共同核对字段、错误状态和调用关系。各层通过固定样例验证后再联调。

固定分析样例的 `expected` 字段和 `constraints.scope` 规则见
[fixture expectation schema](fixture-expectations.md)。`scope` 是可选的
测试域标注，不要求所有 fixture 为了对齐而添加；没有模型输出的 fixture
仍须遵守文档中对 `usable` 和 `outcome` 三态语义的说明。

Agent A 的 runtime 适配边界、Octos 调用顺序、状态机、超时取消和失败映射
见 [Agent A runtime interface](agent-a-interface.md)。

Agent 的两个开发者可以分别侧重流程与宿主适配、提示词与结果核验，具体分工按任务确定，不拆成两个运行时 Agent。

## Octos 接入边界

目标调用关系：`Makepad UI → app → agent/runtime → Rinx octos.* 服务 → 宿主管理的 Octos`。数据层先提供候选证据，Agent 适配层组织上下文并提交分析，结果经应用核验后展示。数据层代码不会因放入 bundle 就自动成为 Octos 工具。

- **应用负责**关注、新闻证据、日程、提示词、结果核验和用户决策记录；Octos 承担 Agent 推理执行。
- **宿主负责**模型配置、凭据、服务连接、运行时生命周期与工具审批。独立 Rinx 使用配套 Octos 可执行文件；OctoSense 模块模式使用 Shell 注入的 app-peer 服务，不给每个应用另起内核。
- **版本成套固定**：Rinx `3bedeadf`、`octosense-app-peers` `98666deb`、Octos `fe08d8e6`。完整提交与来源见 `dev-dependencies.lock.json` 的 `host_runtime_dependencies`；这些是宿主依赖，不是打入新闻应用 ZIP 的依赖。

当前固定 Rinx 的接口如下（已核对宿主源码；开发者已反馈本应用的连通性测试成功，history 和超时中断仍未完成实测）：

| 服务 | 参数 | 用途 |
| --- | --- | --- |
| `octos.session.open` | `{}` | 打开应用作用域上下文 |
| `octos.turn.start` | `{"text":"..."}` | 提交分析，text 非空且不超过 32768 字节 |
| `octos.turn.interrupt` | `{}` | 中断当前分析 |
| `octos.session.history` | `{}` | 按需读取上下文历史 |

`turn.start` 的返回包含 `turn_id` 和 `text`；业务 JSON 需要从文本中解析并核验，不是宿主保证的结构化结果。应用请求与结果约定见 [analysis.md](../src/contracts/analysis.md)。适配层应串行管理当前分析，并处理取消、超时、迟到响应和解析失败。

当前 manifest 已声明连接测试和业务分析使用的 `octos.session.open`、`octos.turn.start`、`octos.turn.interrupt` 权限；未申请 history 权限。该版本 Rinx 拒绝 bundle 的 `agent` 配置，不应通过增加 Agent 描述文件绕过宿主服务。`session.history` 也不能替代应用自己的日程与决策存储。

落地顺序：真实宿主调用与取消 → 新闻证据分析及核验 → 用户确认日程建议 → 验证后台触发与通知支持。App Hub 安装路径仍需在实际 Shell 上单独验证，Rinx 本地成功不代表上架后的服务已可用。


## 运行与导入


当前界面默认请求公开新闻源。维护 `src/` 中的源码后重新组装与打包；新增执行文件也要加入 `scripts/assemble.py` 的 `ORDER`。生成的 `build/source-map.json` 将宿主报错行映射回源码；不要维护两份手工同步的业务实现。

### 1. 准备官方 Rinx

目标宿主已改为[官方 hagency-org/Rinx](https://github.com/hagency-org/Rinx)，固定提交 `3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9`。当前干净检出位于 `.dev/vendor/Rinx`，原共享目录保留不动。完整宿主、参考工具、配套内核和实际构建摘要见依赖锁。

`dev-dependencies.lock.json` 固定本次官方 main 的提交。执行 `python scripts/prepare_dev_dependencies.py` 创建缺失检出，Windows 编译使用 `scripts/build_windows_tools.ps1`；已有不同提交或修改不会自动切换。Rinx 与参考 App Hub 各自的运行时依赖分别核对，最新 Rinx 的实际 UI 重启验收本轮未执行。

若已经安装官方 Rinx，可以直接启动，但应核对版本。若使用上述源码检出，从本项目根目录在单独终端执行：

```bash
cd .dev/vendor/Rinx
cargo run --locked --release --features agent_chat
```

该命令按照[固定版本的官方 README](https://github.com/hagency-org/Rinx/blob/3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9/README.md#build-and-run)的构建方式启动，增加 `--release` 用于演示；首次运行会编译和下载依赖。构建并打包配套内核后可直接运行 `./target/release/rinx`。Rust 工具链由宿主的 `rust-toolchain.toml` 固定为 `1.98.0`。

Linux 需要图形会话和原生构建依赖。Debian/Ubuntu 可按照[固定版本的 Linux 构建说明](https://github.com/hagency-org/Rinx/blob/3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9/docs/robrix-upstream-readme.md#building--running-robrix-on-desktop)准备：

```bash
sudo apt-get update
sudo apt-get install libssl-dev cmake llvm clang libclang-dev libsqlite3-dev pkg-config binfmt-support libxcursor-dev libx11-dev libasound2-dev libpulse-dev libwayland-dev libxkbcommon-dev
```

其他机器可从官方仓库克隆并检出上述提交，再使用同样的构建命令；检出位置不同时替换相对路径。`agent_chat` 是官方构建示例启用的宿主功能，本新闻应用不依赖其协作服务；新闻浏览无需模型配置，新闻分析和连接测试需要配置可用的模型。

### 准备独立 Rinx 的 Octos

当前新闻浏览无需模型配置。要准备独立 Rinx 的本地 Agent 运行环境，在 Rinx 检出目录执行以下命令（参考其 [Octos 打包说明](https://github.com/hagency-org/Rinx/blob/3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9/packaging/README-octos.md)）：

```bash
cargo build --locked --release --features agent_chat
python3 tools/package-octos.py desktop --app-binary target/release/rinx
cargo run --locked --release --features agent_chat
```

宿主脚本构建匹配版本的 Octos 并放到 Rinx 旁边，检查其版本与宿主 Cargo.lock 一致；本项目的 `scripts/package.py` 不承担这一步。OctoSense 模块模式使用 Shell 提供的服务，不运行这套独立宿主打包步骤。

本项目使用 **Rinx 自带、由 Rinx 管理的本地 Octos**，无需另外启动 HTTP 服务。模型字段与密钥的填写步骤见下方“配置 Rinx 自带 Octos 并测试”。`agent_chat` 构建特性不等同于 mini-app 的 `octos.*` 权限；应用通过宿主服务发起新闻分析，实际接入验收见 [验收记录](acceptance.md)。

### Windows 本地运行

Windows 环境与固定版本构建步骤见 [Windows 开发说明](windows-development.md)。已准备的工具放在项目内隔离的 `.dev/vendor/` 中，与依赖锁中的相对路径一致；在本项目根目录可直接执行：

```powershell
# 启动真实新闻界面；无需 Matrix 或模型密钥
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1

# 启动官方 Rinx，登录后按下方步骤导入 bundle
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

脚本核对宿主检出的固定提交、重新打包，再打开可交互窗口；不下载或编译工具。参考宿主的数据保存在 `.local-state/windows-preview/`，Rinx 的数据和缓存默认保存在 `.local-state/rinx/`；已设置 `RINX_DATA_DIR` 或 `ROBRIX_DATA_DIR` 时沿用该配置。直接运行 `rinx.exe` 会使用宿主自身的默认数据目录，建议通过脚本启动以沿用迁移后的登录状态。使用其他开发依赖目录时传入 `-DevRoot`。

固定宿主限制每次脚本回调为 64 ms。缓存只恢复启用源；列表按最多 64 条/8 ms 分批，app 合并同时到达的更新，避免反复取消全量排序。启动只更新缺失或达到 5 分钟的来源，手动刷新仍覆盖全部启用源。关键词匹配器复用，页面每次渲染只筛选一次。Windows 宿主提供 `User-Agent`，应用不能自行覆盖。参考宿主依赖与 Rinx 的依赖不同；运行与验证范围见 [验收记录](acceptance.md)。

### 2. 打包当前应用

在本项目根目录执行：

```bash
python3 scripts/package.py
realpath bundle
```

脚本从依赖记录的相对路径查找 `hub`；工具位于其他位置时，可用 `OCTO_HUB` 指定真实可执行文件路径。它先组装 `src/` 并核对源目录与 manifest 的请求域名，再执行 `hub stamp`，生成 `build/cfaw-news.zip`；拒绝重写已签名包。它不执行 `hub check` 或 `hub scan`。

数据与组装验证：

```powershell
python scripts/test_runtime.py
python scripts/test_runtime.py --suites news weather
python scripts/test_runtime.py --suites feed
python -m unittest discover -s tests/unit -p "test_*.py"
python scripts/assemble.py --check
```

原生数据测试需要已经准备好的参考 card-host、资源与图形会话，可用 `--host` 指定可执行文件。测试将实际数据模块与明确标记的 fixtures 组装到 `.test-state/runtime-*/`，在独立存储 jail 内运行，不调用模型或公开新闻源，不修改用户数据。报告与日志留在该目录；测试宿主自动退出。

### 3. 导入并运行

1. 在 Rinx 中登录 Matrix 账号，服务器须支持宿主要求的原生 Sliding Sync。账号凭据只在 Rinx 登录界面输入。
2. 打开 **Mini apps**（桌面导航中的入口；窄屏布局可在 Discover / 发现中找到），点击 **Import an app**。
3. 将 `realpath bundle` 的输出填入 **OctoSense bundle folder**，Room 留空。仅浏览新闻无需模型；使用分析或连接测试前按下方说明配置助手。
4. 点击 **Review bundle**，核对 `CFAW News`、ID `dev.cfaw.news`、`storage` / `net` / `images` 和三个 `octos.*` 权限；请求域名与来源选择及允许的重定向域名见 manifest 和来源目录。
5. 点击 **Run**。Rinx 使用审核后的应用快照；修改源文件后需重新打包，并退出应用重新 **Review bundle → Run**。

Rinx 导入的是 `bundle/` 文件夹，不是 ZIP。分享 `build/cfaw-news.zip` 后，接收方先解压，再选择其中的 `bundle/`。

### 4. 演示当前界面

1. 打开应用读取启用来源的缓存；未检测到演示缓存时自动刷新缺失或达到 5 分钟的来源。若用 `scripts/seed_demo_cache.py` 生成了演示缓存，启动只展示缓存和演示提示，需要上拉新闻区域才能请求真实新闻。在 **左上角三横菜单 → 新闻来源** 启用/关闭来源、查看各来源的真实错误，再返回首页上拉刷新。刷新中再次上拉不会取消或重启任务，菜单可停止新闻更新。桌面滚轮仍用于浏览；新闻连续展示，无加载更多按钮或刷新提示，右侧箭头返回顶部。新闻刷新使用宿主 `net.http_request`，不依赖 Octos 或模型配置；支持网络权限的参考 card-host 也能抓取，固定样例测试通过不代表运行机器的联网刷新已验证。
2. 在 **动态** 按分类或搜索筛选，或切换底部 **跟踪** 查看关注的新闻；失败时显示错误与旧缓存，不替换为虚构新闻。
3. 点击条目的 **关注来源**，或在 **跟踪** 页点击 **添加关注**（已有关注时为 **管理关注**）添加主题、关键词。相关条目明确显示规则匹配原因。
4. 点击 **收藏** 后重开应用，到 **收藏** 查看新闻快照；清理新闻缓存不会删除收藏。
5. 查看详情中的摘要、时间与链接。HN 时间是提交时间；未知日期保持未知；摘要不代表文章全文。点击“分析影响”请求单条新闻分析。若出现日程建议，先点击“接受”查看确认区，再核对时间、冲突与版本，点击“确认并保存”；不点击确认不会修改日程。
6. 后续刷新出现新相关新闻时显示“新”。打开详情记为已读，重复抓取不会再次标记。

在 **日程** 页面依次填写标题、内容、地点，再选择北京时间（默认）或美国东部时间（纽约）。日期默认所选时区的今天，可选明天或指定日期；开始时间和预计结束时间只需分别填写“时、分”，采用 24 小时制（时 0–23、分 0–59）。跨午夜选择次日结束。纽约时间自动处理 2007 年起的美国夏令时规则；切换日不存在或重复的小时会提示重新选择，避免保存含糊时间。保存后可编辑，旧日程仍可读取；Agent 改期保留内容和地点。同时间冲突或旧版本会拒绝写入。重开应用确认日程和建议状态保持。点击跟踪页的“检查关注更新”只分析未分析或内容已变化的新闻，不自动执行建议。可选 **菜单 → 新闻来源 → 连接诊断 → 测试连接** 仅测试固定宿主调用；天气联合分析尚未开放。

品牌右侧天气小组件或菜单的“天气预报”可打开预报。先手动选择所在城市或目的地，可输入目录内的城市名并点击“使用城市”；之后恢复所选城市和缓存，独立补取缺失/过期预报。最多保存 12 城，可切换或移除。组件展示今日预报的最低/最高温度，页面显示 7 日预报、降水和更新错误；位置说明卡片已移除。参考坐标属于城市，不是设备当前位置；固定 Rinx 尚未提供脚本定位服务。天气不参与新闻 busy，也没有进入 Agent 上下文。

当前包仅用于本地开发导入。包摘要、App Hub 准入检查和真实官方 Rinx UI 验收分别验证不同事项，不能互相替代。

### 5. 配置 Rinx 自带 Octos 并测试

本项目通过 **Use this device** 使用 Rinx 配套 Octos 来执行和管理 Agent。先完成上面的配套内核准备，再启动 Rinx；后续由 Rinx 管理 Octos 的启动和生命周期。“本地”指 Octos 在本机运行，模型仍可调用云端 API。

1. 在 Rinx 登录 Matrix，进入 **Mini apps → Import an app**。
2. 填写本地助手的四个字段。以下是使用 DeepSeek 的填写示例；其他提供方按其实际支持的 Provider 和模型 ID 配置。

| Rinx 字段 | 填写内容 |
| --- | --- |
| `Assistant on this device: provider (e.g. deepseek)` | `deepseek`，填写提供方标识 |
| `Model` | 提供方为该账号开放的模型 ID；不是模型显示名称 |
| `Base URL (optional)` | 使用默认 DeepSeek 官方端点时留空；自定义端点时填写模型 API 基地址 |
| `API key (kept in Rinx's own runtime)` | 在模型提供方控制台获取的 API key；不要填 Matrix 密码 |

3. 点击 **Use this device**。配置保存到 Rinx 自己的 Octos profile；个人 `~/.octos` 中的登录或配置不会自动带入。**Octos server URL / Octos profile / Octos access token** 留空，本项目无需点击 **Connect Octos**。
4. 在 **OctoSense bundle folder** 填入本项目 `bundle/` 的绝对路径，Room 留空，执行 **Review bundle → Run**。修改模型配置或应用代码后，退出旧应用再重新打开。
5. 在新闻 App 点击 **左上角菜单 → 新闻来源**，滚动到底部展开 **连接诊断** 后点击 **测试连接**。状态依次显示打开上下文、等待模型，然后显示 `Octos replied: ...` 和真实回复（请求模型回复 `OCTOS_OK`）；仅打开上下文不算完成验证。

**保存密钥时注意：**点击 **Use this device** 后，密钥输入框会清空，这是界面行为。当前固定宿主版本中，保留 Provider、Model 却空着密钥再次保存，会覆盖掉原密钥；修改配置时请重新填写密钥，日常打开应用无需重复保存。密钥只交给 Rinx，不写入应用代码、bundle、截图或 Git。

应用通过 `host.request("octos.session.open", {}, callback)` 和 `host.request("octos.turn.start", {text: ...}, callback)` 调用宿主，由 Rinx 转交给本地 Octos。应用不配置 Octos HTTP 地址或持有模型密钥。测试按钮只发送固定测试语句，不发送新闻或日程；重复点击不会并发发起测试。90 秒未完成会请求中断，迟到结果会被忽略；未确认中断时需关闭再打开应用。

| 反馈 | 处理 |
| --- | --- |
| `The assistant is off` | 回到 Rinx 导入页配置本地模型并点击 **Use this device**，再重新打开应用 |
| `failed to create LLM provider`、API key 为空 | 在 Rinx 重新填写 Provider、Model 和密钥后保存；无需对个人 Octos 执行登录命令 |
| `no packaged assistant runtime` | 在实际运行的 Rinx 检出中执行上面的内核打包命令，确保 `octos` 与 `rinx` 在同一目录 |
| 模型鉴权或请求失败 | 根据按钮下的真实错误核对密钥、模型 ID、模型 Base URL 和网络 |

Matrix 的 `m.secret_storage.default_key` / `moments.preferences` 账户数据 404 并非 Octos 调用错误；应依据测试按钮反馈继续诊断。

参考 card-host 没有 Octos 服务，已验证新版连接页显示其真实错误。开发者曾反馈 Rinx / Octos 连通测试成功；新版界面的成功回复、超时中断与完整业务流程仍待在实际宿主验证。
