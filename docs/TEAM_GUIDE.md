# 队友上手与开发分工

先阅读 [项目首页](../README.md)、[当前能力与验收](acceptance.md) 和 [AGENTS.md](../AGENTS.md)。运行环境见 [开发与运行说明](development.md) 与 [Windows 环境](windows-development.md)，版本以 [依赖锁](../dev-dependencies.lock.json) 为准。

## 工作位置

业务功能在本仓库 `src/` 开发。Rinx 是宿主，Octos 是宿主管理的执行环境；普通业务改动不需要修改它们。依赖锁中的相邻 vendor 检出用于编译和运行，不自动下载，也不要覆盖已有工作目录。模型与密钥只在 Rinx 配置，个人 Octos 配置不会自动带入。

## 模块分工

| 区域 | 交付与边界 |
| --- | --- |
| `src/frontend/pages/`、`components/` | 紧凑新闻流、跟踪、日程、详情和建议交互；面向用户说明结果 |
| `src/agent/runtime/`、`context.splash` | 单个 Agent 的宿主调用、快照、请求关联、超时取消与失败映射 |
| `src/agent/prompts/`、`results/`、`history.splash` | 提示词、结果与证据校验、变化识别和建议生命周期 |
| `src/data/ingestion/`、`retrieval/`、`storage/` | 新闻、候选证据、用户记录及恢复；不决定建议是否执行 |
| `src/app/`、`contracts/` | 集成、导航、用户确认和共享数据契约；变更时同步生产方与消费方 |
| `tests/fixtures/`、`unit/`、`scenarios/` | 标记固定输入，验证证据、状态和完整业务流程 |

两位 Agent 开发者共同维护一个运行时 Agent，可分别侧重运行器和结果正确性。每项跨层改动指定一位集成人，不维护两套执行流程。

## 日常交接

1. 查看 Git 状态、当前能力与有关代码，保留其他人的修改。
2. 确定本次输入、输出、状态 owner 和调用边界。
3. 修改源码及受影响契约；新增执行模块加入组装器 `ORDER`。
4. 执行有关检查；修改运行代码或 manifest 后通过 `scripts/package.py` 刷新未签名包，再退出旧应用重新 **Review bundle → Run**。
5. 在 [验收记录](acceptance.md) 写明实际检查和未覆盖项，在 [实施计划](agent-integration-plan.md) 更新待办。仅文档修改无需重打包。

连接诊断位于 **更多 → 连接诊断 → 测试连接**，只证明一次宿主调用；新闻详情分析与跟踪页的关注更新检查才验证业务行为。用户日程必须再次确认后才能保存。

日期报告进入 `archive/`，不再新增与当前 README 竞争的状态文档。ZIP、登录数据、密钥、私人日程和个人模型配置不提交。
