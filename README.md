# CFAW News

使用官方 OctoSense News 的 Makepad / Splash 页面，在 Rinx 中运行。唯一入口是 `bundle/main.splash`。保留来源标签、搜索、新闻卡片、摘要阅读和本地收藏，界面沿用官方英文文案。


## 产品方向与当前状态

目标是一个接入单个新闻 Agent 的 OctoScript 应用：跟踪用户关注的新闻，呈现重要变化，并依据新闻证据提供日程建议。前端采用 Makepad，首页采用 Threads 式紧凑信息流，一页连续展示多条新闻。

当前运行代码仍在 `bundle/main.splash`。本次只建立开发目录骨架，未迁移业务逻辑，也未实现 Agent、混合检索、日程或后台推送。`src/` 暂按职责分组，后续依据真实运行位置和宿主接口确定实现文件的语言、后缀及加载方式；尚未建立 `src/` 到运行包的组装流程。

### 已确认的界面设计

- 首页每条新闻展示来源、发布时间、短摘要，以及跟踪、收藏和查看操作。
- Agent 默认仅显示一行关联提示，例如“可能影响你周五的调研计划”；点击后查看证据与解释。
- 重要日程建议可作为紧凑提醒插入信息流，并从顶部待处理入口访问。
- 应用导航包括动态、跟踪、日程和收藏；新闻详情与建议确认是独立页面。
- 新闻事实、Agent 判断和用户确认状态分别呈现。日程建议经用户确认后才更新应用内日程。

## 分层与人员分工

| 层次 | 人数 | 职责 |
| --- | --- | --- |
| 前端层 | 1 人 | Makepad 页面、公共组件、交互与状态展示 |
| Agent 层 | 2 人 | 共同开发同一个 Agent，负责上下文、任务编排、分析、核验与变化识别 |
| 数据接入与检索层 | 1 人 | 新闻接入、规范化、去重、混合检索与持久化 |

`app/` 和 `contracts/` 是三层共同维护的集成边界。人员数量不决定 Agent 数量；Agent 内部的多个步骤也不代表多个智能体。

## 目录结构

目录只用于稳定的职责分组，具体功能优先用文件区分。当前保留 11 个末级目录，用 `.gitkeep` 纳入 Git；这些目录仍是开发骨架，不代表功能已实现。

```text
cfaw-news-agent/
├── README.md                      # 架构、协作与运行说明
├── AGENTS.md                      # 开发约定
├── dev-dependencies.lock.json     # 工具与宿主版本
├── LICENSE / NOTICE
├── .gitignore
├── src/
│   ├── app/                       # 启动、导航、三层连接
│   ├── contracts/                 # 三层共享的数据结构与接口
│   ├── frontend/                  # 前端：1 人；样式文件直接放本层
│   │   ├── pages/                 # 动态、详情、跟踪、日程、收藏
│   │   └── components/            # 新闻条目、Agent 提示、建议卡片
│   ├── agent/                     # 单 Agent：2 人共同开发
│   └── data/                      # 数据与检索：1 人
│       ├── ingestion/             # 新闻源、请求、解析、去重
│       ├── retrieval/             # 查询、关键词/语义召回、融合排序
│       └── storage/               # 新闻、关注、日程及历史结果存储
├── bundle/                        # 运行与交付包
│   ├── main.splash                # 当前唯一业务入口
│   ├── manifest.json
│   ├── assets/                    # 真实本地资源，暂空
│   └── screenshots/               # 真实截图，暂空
├── scripts/
│   └── package.py                 # 摘要刷新与 ZIP 打包
├── tests/
│   ├── fixtures/                  # 明确标注的固定样例
│   ├── unit/                      # 数据处理、检索、接口约定等检查
│   └── scenarios/                 # 新闻变化到日程确认的完整场景
└── build/                         # 本地生成产物，Git 忽略
```

维护时遵循以下约定：

- 一个页面、一个组件或一项小职责优先对应一个文件，不再为 `feed`、`news_post`、`workflow` 等单独建目录。
- `agent/` 内用文件区分流程、宿主调用、提示词和结果核验；两个人协作不需要两套目录或两个 Agent。
- `contracts/` 初期用少量文件集中定义新闻、关注、日程及分析结果，避免接口定义散落各层。
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

Agent 的两个开发者可以分别侧重流程与宿主适配、提示词与结果核验，具体分工按任务确定，不拆成两个运行时 Agent。

## 当前运行与演示

当前代码仍是官方 News 页面的 Rinx 适配版；已讨论的 Threads 风格首页、Agent 和日程建议尚未接入。编辑 `src/` 中的占位目录暂不会改变应用行为。

### 1. 准备官方 Rinx

目标宿主已改为[官方 hagency-org/Rinx](https://github.com/hagency-org/Rinx)，固定提交 `68afcf796d303aaf646eeb832d65c450a56c92b5`。本机已有的干净检出位于 `../demo-workspace/vendor/Rinx`；依赖记录不再指向个人 fork，也不再记录原定制宿主的二进制摘要。

`dev-dependencies.lock.json` 只记录版本和路径，不自动下载、切换或编译宿主。源码提交与其 AppPolicy、Makepad、OctoScript-Makepad 依赖已核对；**此应用在干净官方宿主上的 UI 验收仍待完成**。原定制宿主及其未提交修改保留不动。

若已经安装官方 Rinx，可以直接启动，但应核对版本。若使用上述源码检出，从本项目根目录在单独终端执行：

```bash
cd ../demo-workspace/vendor/Rinx
cargo run --locked --release --features agent_chat
```

该命令按照[固定版本的官方 README](https://github.com/hagency-org/Rinx/blob/68afcf796d303aaf646eeb832d65c450a56c92b5/README.md#build-and-run)的构建方式启动，增加 `--release` 用于演示；首次运行会编译和下载依赖。本次未执行宿主编译，也未在该检出的默认 `target/debug` 或 `target/release` 目录发现 `rinx` 二进制。Rust 工具链由宿主的 `rust-toolchain.toml` 固定为 `1.98.0`。

Linux 需要图形会话和原生构建依赖。Debian/Ubuntu 可按照[固定版本的 Linux 构建说明](https://github.com/hagency-org/Rinx/blob/68afcf796d303aaf646eeb832d65c450a56c92b5/docs/robrix-upstream-readme.md#building--running-robrix-on-desktop)准备：

```bash
sudo apt-get update
sudo apt-get install libssl-dev cmake llvm clang libclang-dev libsqlite3-dev pkg-config binfmt-support libxcursor-dev libx11-dev libasound2-dev libpulse-dev libwayland-dev libxkbcommon-dev
```

其他机器可从官方仓库克隆并检出上述提交，再使用同样的构建命令；检出位置不同时替换相对路径。`agent_chat` 是官方构建示例启用的宿主功能，本新闻应用不依赖其协作服务，也不需要模型或 API key。

### 2. 打包当前应用

在本项目根目录执行：

```bash
python3 scripts/package.py
realpath bundle
```

脚本从依赖记录的相对路径查找 `hub`；工具位于其他位置时，可用 `OCTO_HUB` 指定真实可执行文件路径。它执行 `hub stamp` 并生成 `build/cfaw-news.zip`，不组装 `src/`、不执行 `hub check` 或 `hub scan`，也不改写已签名包。

### 3. 导入并运行

1. 在 Rinx 中登录 Matrix 账号，服务器须支持宿主要求的原生 Sliding Sync。账号凭据只在 Rinx 登录界面输入。
2. 打开 **Mini apps**（桌面导航中的入口；窄屏布局可在 Discover / 发现中找到），点击 **Import an app**。
3. 将 `realpath bundle` 的输出填入 **OctoSense bundle folder**，Room 留空。当前应用无需配置导入页中的助手提供方、模型或密钥。
4. 点击 **Review bundle**，核对 `CFAW News`、ID `dev.cfaw.news`、`storage` / `net` / `images` 权限，以及 `hn.algolia.com`、`www.techmeme.com`、`news.google.com` 三个请求域名。
5. 点击 **Run**。Rinx 使用审核后的应用快照；修改源文件后需重新打包，并退出应用重新 **Review bundle → Run**。

Rinx 导入的是 `bundle/` 文件夹，不是 ZIP。分享 `build/cfaw-news.zip` 后，接收方先解压，再选择其中的 `bundle/`。

### 4. 演示当前已有能力

建议用以下顺序完成一次短演示：

1. 打开 **Today**，等待真实新闻加载，再切换 **HN / TechMeme / Google** 来源。
2. 在 **Search stories** 中输入当前列表里存在的关键词，展示筛选，再清空输入。
3. 点击一条新闻阅读 feed 摘要，展示来源 URL；不要将摘要称为全文。
4. 点击 **Save**，返回 **Saved** 标签查看收藏，再进入阅读页取消收藏。
5. 点击 **Refresh** 展示重新请求。来源失败时如实展示失败或旧缓存，不替换为虚构新闻。

当前可演示的是新闻浏览、搜索、摘要阅读和收藏。新信息流设计、持续关注分析和日程建议仍属于后续开发范围；应用内刷新也不等同于后台推送。

当前包仅用于本地开发导入。包摘要、App Hub 准入检查和真实官方 Rinx UI 验收分别验证不同事项，不能互相替代。
