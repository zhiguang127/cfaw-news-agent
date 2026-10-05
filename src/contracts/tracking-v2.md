# tracking-v2.0 应用契约与 owner 交接

本说明补充 `analysis.md`，以 new.2 的实际执行代码为准。宿主接口仍是 `octos.session.open {}`、`octos.turn.start {text}`、`octos.turn.interrupt {}`，没有增加流式/并行/调度 API。意图理解和日程理解保持原 schema 1；**实时 tracking_update 要求 schema 2**。历史 schema 1 仍可读，依目标版本、证据和时间检查失效，不迁移或清空用户数据。

## 输出

顶层沿用 `items` 与 `explanation`，增加 `insights`（全轮最多 6 条、每目标最多 3 条）：

| 字段 | 校验与含义 |
| --- | --- |
| target_type / target_id / target_version | topic / schedule；必须在本轮快照，版本一致 |
| issue_key | 稳定事件键，同目标不能重复；URL/转载数不是独立新事实 |
| change_kind | new / updated / withdrawn / unchanged |
| summary | 非空，最多 600 字符 |
| evidence_ids | 实际候选 ID，不能引用未提供新闻 |
| evidence_refs | 最多 8 个 `{news_id, paragraph_id, quote}`，quote ≤400 字符且为原段落子串；摘要证据可空 |
| decision_effect | none / watch / review / unknown，不是执行授权 |
| next_step | null 或核实建议；goal + review 必须有，news 不强制 |
| uncertainties | 最多 6 条，每条 ≤300 字符 |
| compared_run_id | 首次为空；后续须为该目标同版本的实际历史 run |
| material_change | 更新/撤回须说明新增事实或撤回原因，最多 400 字符 |
| reschedule | 默认不开启；仅 schedule 精确时段、allow_reschedule 和全局开关通过时可有 `{start,end,timezone,reason,evidence_refs}` |

日期/地点影响需正文段落引用、地点和起始日期文字匹配、合法 RFC3339 与行程交叠；日期型须声明未知实际时间/班次。改期更保守：引文包含地点及新起止 YYYY-MM-DDTHH:MM。格式不同的自然语言可因此被拒绝，不为提升通过率放松证据校验。确定性引用检查不能证明事实蕴含关系、来源独立性或引文真实性，真实案例须人工验收。`proposed_action` 继续拒绝。

## 输入、预算与证据

- 原生保留完整快照，送模型使用深复制后的投影：删冗余原话/规则字段、裁剪对应目标旧摘要，保留身份、版本、必要偏好、决定和证据。总提示 ≤32 KiB UTF-8，超限删完整候选并增加遗漏数；模型结果 ≤16 KiB UTF-8。
- 分析正文缓存独立于 `article_state`，内存最多 4 条、有效期 2 小时；每轮最多补 2 篇、单篇 15 秒超时。重启后重新补证据，不声称跨重启持久正文缓存。
- 阅读提取限 24 KiB/80 段；模型投影最多前 6 个段落、每篇合计约 4KB。缓存保存 URL、抓取时间、内容键、正文校验和、p1…段落 ID、截断/失败原因。正文校验和不是密码学签名。
- 只有用户主动详情或具备地点/日期的高影响候选才补正文；失败标明摘要范围，不生成虚构全文。内容指纹变化或过期使旧结论失效。网页内容不作为指令。
- `previous_by_target` 只含对应 ID/版本的结果，模型不能把其他目标的最后一轮作为比较对象。原生决定以事实内容比较，URL/发布时间变化不重启已处理提醒。

## 存储与模块

| 文件/owner | 责任 |
| --- | --- |
| topics_v2.json / topics_commit | 原关注、草稿和决定；增加 kind=insight，watch/handled/dismissed、issue_key、target/version、事实基线 |
| 原 tracking cache / tracking_publish | 有界 run 历史，schema 1/2 兼容与当前性判断；不重复建立模型结果缓存 |
| schedules_v1.json / schedule_update_options | 当前日程、版本、冲突、allow_reschedule；只有用户确认才更新 |
| schedule_actions_v1.json / schedule_actions_commit | ≤32 条 prepared/applied/undone，原日程、提案证据、决定、审计；同 action_id 幂等，撤回检查当前版本 |
| agent_preferences_v1.json / agent_preferences_commit | 暂停、5/15/60m、仅重要、归一化球位置；不进模型上下文 |
| target_checks_v1.json / check_states_record | ≤28 目标状态，成功水位只在实际检查完成后前移，失败保留旧水位 |
| agent_metrics_v1.json / agent_metrics_record | ≤120 元数据样本；launch/coldwarm、阶段、字节、类别；不记录原话、正文、凭据 |

非关键水位/耗时写入合并到下一计时回调，避免叠加同步文件写超出宿主单事件预算。关键决定、日程和改期日志仍通过 owner 的版本检查/备份写入。错误不得显示保存成功，损坏用户记录保留原文件。

相关执行模块：`src/agent/results/insights.splash`（结构与引用）、`src/app/insights.splash`（展示与决定）、`src/data/ingestion/analysis_evidence.splash`（正文）、`src/app/reschedule.splash`（预览确认）、`src/app/continuous_tracking.splash`（前台队列）、`src/app/orb_drag.splash`（原生手势接线）。均已加入 assemble.ORDER。

## 宿主边界

固定 Rinx 每应用实例有独立 Octos context，包含自己的 transcript。重复 open 不能假定会清空历史；应用保留 open/start，提示当前任务仅采用当轮 INPUT/SNAPSHOT，并未引入未经验证的 reset/reuse 优化。只检查固定源码可证明的接口，不声称 runtime 历史隔离策略已完成真实模型测量。

宿主没有应用关闭后的定时/推送服务，所以 B08 使用可暂停的前台 timer，经现有单队列和用户输入优先级触发。应用重新打开恢复偏好和水位；未完成任务可能仍显示待检查，下一次实际触发会覆盖状态。未来后台能力需要宿主新增生命周期、通知授权、重复触发/停止机制，再单独接线和验收。
