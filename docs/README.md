# 文档索引

[项目首页](../README.md)说明产品与启动入口。当前文档按职责维护，避免多处重复记录状态和命令。

| 文档 | 维护什么 |
| --- | --- |
| [开发与运行说明](development.md) | 目录、层间职责、Octos 边界、宿主准备、打包、导入和模型配置 |
| [Windows 环境](windows-development.md) | Windows 工具链、构建、资源准备与本地数据路径 |
| [团队指南](TEAM_GUIDE.md) | 新成员阅读顺序、模块分工、日常交接流程 |
| [验收记录](acceptance.md) | 当前实现、已知缺口、验证结果与人工验收步骤；当前能力的唯一详细记录 |
| [实施计划](agent-integration-plan.md) | 尚未完成的工作及优先顺序，不重复记录已实现功能 |
| [运行接口](agent-a-interface.md) | 运行器应遵守的调用、状态、超时和取消契约；要求不等于已验收 |
| [数据来源与存储](data-sources.md) | 来源、证据字段、用户记录和缓存的职责 |
| [天气、节假日与汇率接口](frontend-signal-api.md) | 数据模块调用、时间单位、覆盖与未知状态；不代表页面或 Agent 已接入 |
| [Splash 运行时笔记](splash-runtime-notes.md) | 实际验证的语言约束与绕行方式 |
| [Fixture 预期规则](fixture-expectations.md) | 固定样例的 expected 字段与测试语义 |
| [共享契约](../src/contracts/analysis.md) | 生产方和消费方共同使用的输入、结果与动作结构 |
| [历史归档](archive/README.md) | 日期审查、旧验证、原始计划；保留依据，不指导当前开发 |
| [白屏调查](../reports/FAILURE_ANALYSIS.md) | 本机故障对照、临时宿主保护和复现证据；当前验证状态仍以验收记录为准 |

更新功能时同步相关契约、调用方和验收记录。改变启动方式时更新对应运行说明。旧报告不追写成最新状态，也不在 README 为每次开发追加一份审查。
