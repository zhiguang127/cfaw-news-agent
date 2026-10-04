# CFAW News

用 OctoScript / Makepad 构建的紧凑新闻应用，运行在 Rinx。围绕一个问题：**这条新信息是否改变你下一步应该做什么？**

## 使用方式

- **首页**：顶部为彩色意图工作台，直接表达/继续意图、查看已确认关注和检查状态；下方保留紧凑新闻流，新闻搜索固定在页面底部。先按分类/搜索筛选，再把有效且未忽略的日程影响、关注相关报道、普通新闻分成三组，各组保留原时间顺序，同一报道只显示一次。条目显示来源、时间、标题和关注/收藏/查看操作；上拉刷新，右侧箭头返回顶部。
- **关联提示**：新闻下最多一行。只展示当前有效的 Agent 解释或具体日程影响，点击查看证据和建议；词法召回留在内部，不展示规则匹配提示。新闻、关注、日程或决定变化后，旧分析不作为当前提示；忽略、接受或撤回的建议不重复置顶。
- **关注管理**：菜单“表达关注 / 继续草稿”展开独立面板，提交原话、回答至多一个关键追问、查看理解并确认保存；可以补充、取消、重试、修改、暂停和恢复。用自然语言确认关注；条目上的关注来源仍可使用，旧关注词保留，但不显示规则编辑器。确认关注/日程、缓存恢复及整轮刷新结束触发有限检查，首页展示相关解释和已有日程影响。
- **日程**：顶部标签进入，仍使用现有表单录入和编辑应用内安排，支持北京/纽约时间、完成/取消。本轮助手仅提醒已有日程的新闻影响，不生成新增或改期动作；旧版已保存建议仍可读取。自然语言创建计划留到后续。
- **收藏**：从菜单“我的收藏”重看已保存的新闻快照。
- **菜单**：品牌左侧的三横入口打开新闻来源、关注管理、关注动态、收藏、分析建议和天气；更新中可停止新闻请求。
- **天气**：品牌右侧小组件显示城市、今日天气与温度范围；点击查看 7 日预报、降水和选城。

本版本不自动添加预设关注或日程。旧版未修改的预设不展示，也不参与检查；用户已编辑的记录保留，原文件不删除。

**新闻阅读**：点击新闻先显示标题、来源与正文阅读页。受支持来源通过宿主 HTTP 获取网页，提取文章/main 容器中的段落；最多 80 段、24 KB 文本，不执行网页脚本。加载中、失败、聚合跳转或未支持来源明确显示 RSS 摘要和可复制原文地址；阅读模式可能省略图片、表格及部分内容。Agent 分析折叠，点击关联提示直接打开分析；网页阅读内容不自动进入分析证据。

新闻抓取与规则匹配不需要 AI。一个应用 Agent 先整理关注目的、范围和偏好及召回词；BM25 对标题和有界摘要初筛，LLM 再判断逐条关系及已有日程影响。来源/分类规则作为精确召回门，英文词与中文二元词、k1=1.2、b=0.75；无向量索引。每轮最多检查 2 个目标、8 条候选，后续触发轮换目标并说明遗漏。没有候选不调用模型；状态区分无候选、无变化、证据不足、失败与过期。新闻内指令不能授权操作。连接诊断位于菜单的“新闻来源”页。

导航为顶部“首页 / 日程”，收藏和关注列表从菜单进入；切页保留新闻筛选。首页不设置独立关注框，也不叠放关键词输入框；意图入口展开独立确认面板，与新闻搜索区分。右上角天气组件、选城和预报页保留。当天目标和两人分工统一见[开发交接](docs/agent-integration-plan.md)。

当前有 18 个可选来源、13 个默认启用来源，本地保存关注、草稿、收藏、日程与决定。新关注/草稿/决定使用 topics_v2.json，分析结果独立缓存；失败不显示已保存，坏文件保留并尝试有效备份，旧 v1 文件保留原读取路径。启动先展示缓存，仅更新缺失或超过 5 分钟的来源；手动刷新仍更新全部启用来源。天气独立加载，支持 30 城、最多保存 12 城，记住当前选城；使用城市参考坐标，不读取设备位置。固定 Rinx 尚未向脚本应用开放定位服务，自动定位不可用。节假日、汇率尚未接入页面；向量检索、天气联合分析、后台监测、通知、系统日历写入和跨设备同步尚未实现。当前包用于本地开发导入，正式 App Hub 发布仍需单独准备和验收。

## 本地运行

依赖固定在 [依赖锁](dev-dependencies.lock.json)，默认放在项目 `.dev/vendor/`；旧共享检出保留。Linux 首次准备并运行，在项目根目录执行：

```bash
python3 scripts/run_linux.py --build
```

首次会构建 Rinx、配套 Octos 与打包工具，后续执行 `python3 scripts/run_linux.py`。需要图形会话、Rust 1.98.0 与原生构建依赖，安装命令见 [Linux 运行说明](docs/development.md#linux-本地运行)。只预览界面可执行 `python3 scripts/run_linux.py --mode Preview --build`；参考宿主没有 Octos 服务。

Windows 先按 [Windows 开发说明](docs/windows-development.md)准备工具和资源。已有环境时执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

在 Rinx 的 **Mini apps → Import an app** 选择本项目 `bundle/`，执行 **Review bundle → Run**。只浏览新闻无需模型；分析默认使用宿主管理的 MiniMax-M3；需要在 Rinx 配置提供方 `minimax`、模型 `MiniMax-M3`、Base URL `https://api.minimax.cn/v1` 和密钥。修改运行代码后退出旧应用并重新导入，启动脚本会刷新未签名包。模型配置和故障处理见 [开发与运行说明](docs/development.md)。

Windows 启动使用同一固定 Rinx App 的临时 SDF 字体入口，并加载本地 D3D11 修补：复用缓冲区计账、持续刷新 GPU 完成状态并回收旧额度，修正快速切页时静默跳过绘制的路径。原生修补需要完整退出旧 Rinx 后重新启动，单独重跑 bundle 不会生效。应用侧仍合并切页重绘、回收脚本临时对象，日程页跳过隐藏新闻列表，保留 32 MiB 堆上限。对照与实测范围见 [调查报告](reports/FAILURE_ANALYSIS.md)；Windows 真实账户导入、模型业务和长期显示仍待验收；本轮 Linux MiniMax 实测范围见下文。

## 开发与验证

业务源码维护在 `src/`，`scripts/assemble.py` 按固定顺序生成宿主入口 `bundle/main.splash`。新增执行模块须加入 `ORDER`，不要手工维护第二份入口。

```powershell
python scripts/test_runtime.py
python scripts/test_runtime.py --agent-only
python scripts/test_runtime.py --suites news weather
python scripts/test_runtime.py --suites feed
python scripts/test_runtime.py --suites tracking --inspect-ui --ui-size 430x860 --restart
python scripts/test_runtime.py --suites tracking --inspect-ui --ui-size 360x860 --restart
# Linux: 固定 Rinx 的隔离 App/Modal（固定回复，无账号准入或模型租约）
python scripts/test_runtime.py --suites tracking --rinx-runtime --inspect-ui --restart
python -m unittest discover -s tests/unit -p "test_*.py"
python scripts/assemble.py --check
python scripts/package.py
```

真实 MiniMax / Rinx 自动联调（需已有 Matrix 登录和已构建的固定宿主）：

```bash
python3 scripts/test_runtime.py --live-minimax
# 首次可从私有文件读取，或设置 MINIMAX_API_KEY；不要把密钥放在命令参数中。
python3 scripts/test_runtime.py --live-minimax --minimax-key-file /path/to/private-key-file
# 仅验证模型 API
python3 scripts/test_runtime.py --live-minimax --minimax-api-only
```

入口自动填写 bundle 地址、提供方、模型、Base URL 和密钥，执行 Use this device / Review / Run，再验证真实意图回复能通过应用校验；不会确认保存测试关注。已有非空用户草稿保留，跳过意图测试并在报告中说明。密钥只保存在宿主私有配置，报告和日志脱敏。M3.1 Flash Preview 可用 `--minimax-model MiniMax-M3.1-Flash-Preview` 明确选择；本次密钥实测 M3 可用，Flash Preview 返回 unknown model。该模式与固定输入 suites 分开，报告在 `.test-state/live-minimax-*/report.json`。

可用 `--suites` 只检查受改动影响的数据模块；feed 与 tracking 场景使用实际应用 UI，分别单独运行；tracking 执行实际 BM25、校验、存储和请求状态代码，只有宿主/模型回复替换为明确标记的固定输入。`--restart` 启动全新原生进程，核对关注、草稿、决定和旧记录恢复。原生测试使用独立 `.test-state/` 和固定输入，不调用真实模型，也不在应用启动时运行；通过这些检查不代表真实账户导入、实时模型或 App Hub 发布通过。软件渲染较慢时可明确使用 `--timeout-seconds 120`。当前实现、已知问题、最近验证和人工验收清单统一见 [验收记录](docs/acceptance.md)。

## 开发交接

两人开工只看[两人一天开发交接](docs/agent-integration-plan.md)：本分支已实施 A，并在未发现 B 交付的情况下承接 B 的意图解析、BM25＋LLM 追踪及请求保护；接口、覆盖范围和剩余真实服务联调见交接，实际检查见验收记录。运行说明与验收记录按需查阅，不另维护一套分工。

开发约定在 [AGENTS.md](AGENTS.md)，宿主版本在 [依赖锁](dev-dependencies.lock.json)。日期报告和原始分阶段设计保存在 [历史归档](docs/archive/README.md)，不作为当前状态依据。保留 `LICENSE`、`NOTICE` 和上游署名；模型密钥与用户数据只交给宿主。
