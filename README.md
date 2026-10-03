# CFAW News

用 OctoScript / Makepad 构建的紧凑新闻应用，运行在 Rinx。围绕一个问题：**这条新信息是否改变你下一步应该做什么？**

## 使用方式

- **动态**：浏览真实新闻，按分类或关键词筛选，点击标题查看摘要和来源，关注来源或收藏。
- **跟踪**：管理关注的主题、来源、关键词；手动“检查关注更新”，由助手分析相关新闻对关注与日程的影响。
- **日程**：录入和编辑应用内安排，支持北京/纽约时间、完成/取消。助手可以提议新增或改期，你确认后才保存。
- **收藏**：重看已保存的新闻快照。
- **建议**：有待处理建议时首页显示数量；也可从跟踪页查看分析、依据和历史决定。

新闻抓取与规则匹配不需要 AI。助手仅在你发起分析时使用实际可用的标题和摘要；没有候选新闻时不会调用模型，分析结果可能是建议、无需调整或证据不足。来源管理和连接诊断位于“更多”。

当前有 17 个可选来源、12 个默认启用来源，本地保存关注、收藏、日程与决定。向量检索、天气联合分析、后台监测、通知、系统日历写入和跨设备同步尚未实现。当前包用于本地开发导入，正式 App Hub 发布仍需单独准备和验收。

## 本地运行

先按 [Windows 开发说明](docs/windows-development.md) 准备固定宿主、配套 Octos、打包工具和资源。已有环境时，在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

在 Rinx 的 **Mini apps → Import an app** 选择本项目 `bundle/`，执行 **Review bundle → Run**。只浏览新闻无需模型；分析功能需在 Rinx 配置助手。修改运行代码后退出旧应用并重新导入，启动脚本会刷新未签名包。Linux 运行、模型配置和故障处理见 [开发与运行说明](docs/development.md)。

## 开发与验证

业务源码维护在 `src/`，`scripts/assemble.py` 按固定顺序生成宿主入口 `bundle/main.splash`。新增执行模块须加入 `ORDER`，不要手工维护第二份入口。

```powershell
python scripts/test_runtime.py
python scripts/test_runtime.py --agent-only
python -m unittest discover -s tests/unit -p "test_*.py"
python scripts/assemble.py --check
python scripts/package.py
```

原生测试使用独立 `.test-state/` 和固定输入，不调用真实模型；通过这些检查不代表 Rinx 业务流程、实时抓取或 App Hub 发布通过。当前实现、已知问题、最近验证和人工验收清单统一见 [验收记录](docs/acceptance.md)。

## 文档入口

完整导航和文档职责见 [文档索引](docs/README.md)。

| 要做的事 | 阅读 |
| --- | --- |
| 首次参与、确定模块负责人 | [团队指南](docs/TEAM_GUIDE.md) |
| 搭建环境、理解架构和宿主调用 | [开发与运行说明](docs/development.md)、[Windows 环境](docs/windows-development.md) |
| 确认当前能力、复现问题、验收 | [验收记录](docs/acceptance.md) |
| 查看仍需完成的工作 | [实施计划](docs/agent-integration-plan.md) |
| 修改共享接口 | [新闻契约](src/contracts/news.md)、[分析契约](src/contracts/analysis.md)、[运行接口](docs/agent-a-interface.md) |

开发约定在 [AGENTS.md](AGENTS.md)，宿主版本在 [依赖锁](dev-dependencies.lock.json)。日期报告和原始分阶段设计保存在 [历史归档](docs/archive/README.md)，不作为当前状态依据。保留 `LICENSE`、`NOTICE` 和上游署名；模型密钥与用户数据只交给宿主。
