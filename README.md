# CFAW News

用 OctoScript / Makepad 构建的紧凑新闻应用，运行在 Rinx。围绕一个问题：**这条新信息是否改变你下一步应该做什么？**

## 使用方式

- **首页**：只有一条新闻流，唯一的搜索框固定在页面底部。先按分类/搜索筛选，再把符合关注规则或有当前 Agent 建议的报道排到前面，各组保留原时间顺序。条目显示来源、时间、标题和关注/收藏/查看操作；上拉刷新，右侧箭头返回顶部。
- **关联提示**：新闻下最多一行。未分析时说明规则匹配；有当前有效的 Agent 结果时展示解释或具体日程影响，点击查看证据和建议。新闻、关注、日程或决定变化后，旧分析不作为当前提示；忽略、接受或撤回的建议不重复置顶。
- **关注管理**：菜单添加主题、来源、关键词；“关注动态”进入相关新闻列表，手动“检查关注更新”，由助手分析相关新闻对关注与日程的影响。自动分析与自然语言关注尚待接入。
- **日程**：顶部标签进入，仍使用现有表单录入和编辑应用内安排，支持北京/纽约时间、完成/取消。助手可以提议新增或改期，你确认后才保存；无表单的“我的计划”尚待接入。
- **收藏**：从菜单“我的收藏”重看已保存的新闻快照。
- **菜单**：品牌左侧的三横入口打开新闻来源、关注管理、关注动态、收藏、分析建议和天气；更新中可停止新闻请求。
- **天气**：品牌右侧小组件显示城市、今日天气与温度范围；点击查看 7 日预报、降水和选城。

新闻抓取与规则匹配不需要 AI。助手仅在你发起分析时使用实际可用的标题和摘要；没有候选新闻时不会调用模型，分析结果可能是建议、无需调整或证据不足。连接诊断位于菜单的“新闻来源”页。

导航为顶部“首页 / 日程”，收藏和关注列表从菜单进入；切页保留新闻筛选。首页不设置独立关注框，也不叠放关键词输入框；后续统一意图入口应展开独立面板，与新闻搜索区分。右上角天气组件、选城和预报页保留。当天目标和两人分工统一见[开发交接](docs/agent-integration-plan.md)。

当前有 18 个可选来源、13 个默认启用来源，本地保存关注、收藏、日程与决定。启动先展示缓存，仅更新缺失或超过 5 分钟的来源；手动刷新仍更新全部启用来源。天气独立加载，支持 30 城、最多保存 12 城，记住当前选城；使用城市参考坐标，不读取设备位置。固定 Rinx 尚未向脚本应用开放定位服务，自动定位不可用。节假日、汇率尚未接入页面；向量检索、天气联合分析、后台监测、通知、系统日历写入和跨设备同步尚未实现。当前包用于本地开发导入，正式 App Hub 发布仍需单独准备和验收。

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

在 Rinx 的 **Mini apps → Import an app** 选择本项目 `bundle/`，执行 **Review bundle → Run**。只浏览新闻无需模型；分析功能需在 Rinx 配置助手。修改运行代码后退出旧应用并重新导入，启动脚本会刷新未签名包。模型配置和故障处理见 [开发与运行说明](docs/development.md)。

Windows 启动使用同一固定 Rinx App 的临时 SDF 字体入口，并加载本地 D3D11 修补：复用缓冲区计账、持续刷新 GPU 完成状态并回收旧额度，修正快速切页时静默跳过绘制的路径。原生修补需要完整退出旧 Rinx 后重新启动，单独重跑 bundle 不会生效。应用侧仍合并切页重绘、回收脚本临时对象，日程页跳过隐藏新闻列表，保留 32 MiB 堆上限。对照与实测范围见 [调查报告](reports/FAILURE_ANALYSIS.md)；真实账户导入、模型业务和长期显示仍待验收。

## 开发与验证

业务源码维护在 `src/`，`scripts/assemble.py` 按固定顺序生成宿主入口 `bundle/main.splash`。新增执行模块须加入 `ORDER`，不要手工维护第二份入口。

```powershell
python scripts/test_runtime.py
python scripts/test_runtime.py --agent-only
python scripts/test_runtime.py --suites news weather
python scripts/test_runtime.py --suites feed
python -m unittest discover -s tests/unit -p "test_*.py"
python scripts/assemble.py --check
python scripts/package.py
```

可用 `--suites` 只检查受改动影响的数据模块；feed 控制器场景使用应用 UI，单独运行。原生测试使用独立 `.test-state/` 和固定输入，不调用真实模型，也不在应用启动时运行；通过这些检查不代表 Rinx 业务流程、实时抓取或 App Hub 发布通过。当前实现、已知问题、最近验证和人工验收清单统一见 [验收记录](docs/acceptance.md)。

## 开发交接

两人开工只看[两人一天开发交接](docs/agent-integration-plan.md)：你负责交互、存储和集成，队友负责 Agent、检索和校验；包含接口、八小时安排和共同验收。运行说明与验收记录按需查阅，不另维护一套分工。

开发约定在 [AGENTS.md](AGENTS.md)，宿主版本在 [依赖锁](dev-dependencies.lock.json)。日期报告和原始分阶段设计保存在 [历史归档](docs/archive/README.md)，不作为当前状态依据。保留 `LICENSE`、`NOTICE` 和上游署名；模型密钥与用户数据只交给宿主。
