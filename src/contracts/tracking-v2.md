# tracking-v2.0 应用契约与 owner 交接

本说明补充 `analysis.md`，以 10.11 的实际执行代码为准。宿主接口仍是 `octos.session.open {}`、`octos.turn.start {text}`、`octos.turn.interrupt {}`，没有增加流式/并行/调度 API。意图理解和日程理解保持原 schema 1；**实时 tracking_update 要求 schema 2**。历史 schema 1 仍可读，依目标版本、证据和时间检查失效，不迁移或清空用户数据。

## 输出

顶层沿用 `items` 与 `explanation`，增加 `insights`（全轮最多 6 条、每目标最多 3 条）：

| 字段 | 校验与含义 |
| --- | --- |
| target_type / target_id / target_version | topic / schedule；必须在本轮快照，版本一致 |
| issue_key | 稳定事件键，同目标不能重复；URL/转载数不是独立新事实 |
| change_kind | new / updated / withdrawn / unchanged |
| summary | 非空，最多 600 字符 |
| evidence_ids | 实际候选 ID，须对应关联该目标的非无关条目；无相关新闻时可为空，但仅允许unknown + insufficient_evidence，无新增事实或改期 |
| evidence_refs | 最多 8 个 `{news_id, paragraph_id, quote}`，quote ≤400 字符且为原段落子串；摘要证据可空 |
| decision_effect | none / watch / review / unknown，不是执行授权 |
| next_step | null 或核实建议；goal + review 必须有，news 不强制 |
| uncertainties | 最多 6 条，每条 ≤300 字符 |
| compared_run_id | 首次为空；后续须为该目标同版本的实际历史 run |
| material_change | 更新/撤回须说明新增事实或撤回原因，最多 400 字符 |
| reschedule | 仅 schedule 精确时段、allow_reschedule 和全局开关通过时可有 `{start,end,timezone,reason,evidence_refs}`；仍须用户确认 |

日期/地点影响需正文段落引用、地点和起始日期文字匹配、合法 RFC3339 与行程交叠；日期型须声明未知实际时间/班次。改期更保守：引文包含地点及新起止 YYYY-MM-DDTHH:MM。格式不同的自然语言可因此被拒绝，不为提升通过率放松证据校验。确定性引用检查不能证明事实蕴含关系、来源独立性或引文真实性，真实案例须人工验收。`proposed_action` 继续拒绝。

## 输入、预算与证据

- 原生保留完整快照，送模型使用深复制后的投影：删冗余原话/规则字段、裁剪对应目标旧摘要，保留身份、版本、必要偏好、决定和证据。总提示 ≤32 KiB UTF-8，超限删完整候选并增加遗漏数；模型结果 ≤16 KiB UTF-8。
- 实时准备由 `app/tracking_preparation.splash` 逐篇生成证据及引文投影、逐目标保留同版本上次判断、逐项筛选决定，再分步核对大小、输入键与可复用历史。模型投影只复制必要上下文和单项字段，持久快照的正文、指纹与完整决定不因此改写。当前模型只比较 `previous_by_target`，新实时快照的旧 `previous_result` 字段为空；既有历史不迁移。超限同步移除快照与投影末尾整篇候选，保留短标识及段落/引文编号，遗漏数从保留条数推导，重试不重复累加。准备续步先排队，仍共用45秒截止；代次、上下文、决定变化和取消阻止迟到交接。同步 `tracking_snapshot` / `tracking_prompt_snapshot` 保留供有界同步调用和现有测试，实际关注检查不再在一个回调里整理全部材料。
- 分析正文缓存独立于 `article_state`，内存最多8条（与每轮候选上限一致）、有效期2小时；每轮最多2次网页请求，单篇15秒超时。失败结果自动重试冷却5分钟，主动核实可绕过该冷却。重启后重新补证据，不声称跨重启持久正文缓存。
- 阅读提取按 `article_config` 限96KB/260段；Agent证据独立限制最多前6个非空段落、每篇合计4KB UTF-8。过长首段保留最多1000个Unicode字符并标明截断，避免整篇失去证据。缓存保存 URL、抓取时间、内容键、正文校验和、p1…段落 ID、截断/失败原因。正文校验和不是密码学签名。
- 候选中的来源RSS/Atom正文均尝试提取，不占网页请求额度；目标关注优先补读没有摘要的候选，具备地点/日期的日程风险优先。失败明确标明当前仅有标题或标题与摘要，不生成虚构全文。网页正文提取携带来源URL，沿用阅读器的少数派SSR提取分支。内容指纹变化或过期使旧结论失效。网页内容不作为指令。
- `available_evidence` 为模型投影中的 title_only / title_summary / body_excerpt，正文片段不代表已读全文。`check_scope=targeted_verification` 是对上一轮候选的主动核实，保留同一目标与版本，不声称重新覆盖全部新闻；失败后证据无变化可复用原结论及原outcome，不统一标作no_change。
- `tracking-v2.4` 在原引用及结构校验之后增加判断约束：目标insight只引用标题时必须unknown、列出待核实项及具体next_step；全部目标判断仅有标题时须insufficient_evidence。用户说明字段不得含can_quote_body等内部诊断，违规则进入原最多一次修正。摘要可支持有限判断；结构约束无法证明语义真实性或完整适用条件。
- `tracking-v2.7` 将模型投影的正文段落改为 `quote_choices:[{quote_id,text}]`：按 Unicode 连续切成最多400字符的原文片段，不另发重复正文。模型引用优先只返回 `{news_id,paragraph_id,quote_id}`；应用先展开本轮 E 标识，再从不可变原段落以同一边界恢复真实 `quote`，模型附带的改写文字不作为引文来源。未知新闻、段落、片段编号均拒绝，不回退猜测。普通判断、日程影响与改期引用统一恢复后仍执行原逐字及日期/地点/时间校验。保存的引用含真实原句，历史校验不重新恢复或放松原规则。无片段编号的逐字引用仍可用于横跨分片边界的连续短句，最多400字符；翻译、改写和拼接继续拒绝。格式修正仍最多一次，并明确引导选择正确片段编号。片段选择及逐字校验只证明引用来自提供的正文，不证明 Agent 的解释必然正确。
- `previous_by_target` 只含对应 ID/版本的结果，模型不能把其他目标的最后一轮作为比较对象。原生决定以事实内容比较，URL/发布时间变化不重启已处理提醒。

## 存储与模块

| 文件/owner | 责任 |
| --- | --- |
| topics_v2.json / topics_commit | 原关注、草稿和决定；增加 kind=insight，watch/handled/dismissed、issue_key、target/version、事实基线 |
| 原 tracking cache / tracking_publish_async | 有界 run 历史，schema 1/2 兼容与当前性判断；核验写入后确认完成，不重复建立模型结果缓存 |
| schedules_v1.json / schedule_update_options | 当前日程、版本、冲突、allow_reschedule；只有用户确认才更新 |
| schedule_actions_v1.json / schedule_actions_commit | ≤32 条 prepared/applied/undone，原日程、提案证据、决定、审计；同 action_id 幂等，撤回检查当前版本 |
| agent_preferences_v1.json / agent_preferences_commit | 暂停、5/15/60m、仅重要、归一化球位置；不进模型上下文 |
| target_checks_v1.json / check_states_record | ≤28 目标状态，成功水位只在实际检查完成后前移，失败保留旧水位 |
| agent_metrics_v1.json / agent_metrics_record | ≤120 元数据样本；launch/coldwarm、阶段、字节、类别；不记录原话、正文、凭据 |

非关键水位/耗时写入合并到下一计时回调，避免叠加同步文件写超出宿主单事件预算。关键决定、日程和改期日志仍通过 owner 的版本检查/备份写入。错误不得显示保存成功，损坏用户记录保留原文件。

实时 `tracking_update` 使用 `agent_task_start(..., async_publication=true)`：模型返回后仍保持队列忙碌，owner 在持久化成功或明确失败后调用 acknowledgement。其他任务默认同步回调；旧 `tracking_publish` 仅保留给原同步场景和基准接口。`tracking_cache_save` 每回调校验一轮，序列化、磁盘解析、备份、写入及读取核验分别执行，操作前安排续跑以承受原生预算中断。写前重新比对磁盘字节，写后必须与已校验候选的序列化字节完全一致。备份恢复模式更新有效备份，保留损坏主文件。最多12轮，未提高宿主内存或执行预算。

生产启动使用 `topics_load_async`：关注文档与追踪历史分别读取、解析、头校验，再逐条核对话题、决定或分析结果。完整校验后才发布该文档；无效主文件仍尝试有效备份，不发布未经校验的历史。每份文档最多15秒，续步预先安排；超时保留文件并限制写入，已恢复的关注不受后续缓存失败影响，随后继续新闻启动。启动路径不调用同步全历史 `topics_load`；后者保留给轻量同步调用与原有测试。

本地保存15秒截止；适配器另有16秒兜底，覆盖 owner 回调丢失。失败不前移成功水位，结果保留在当前会话供无模型重试。相同 task_id 的已落盘结果可幂等确认，禁止重复追加或覆盖不同结果；取消保存不向已完成的宿主模型轮次发送 interrupt。

tracking_update 连接阶段70秒、每次模型轮次190秒、连接和两轮模型总阶段470秒。单次修正获得独立模型期限；非追踪任务仍使用90秒原期限。阶段计时器核对 task_id 与 wait_generation，结束/取消同时清理总、阶段、进度和中断计时器；迟到回调不得保存或重新占用队列。模型返回的 Service timed out 归类timeout并保留阶段，不能误报存储故障。指标增加 error_phase 与 repair_count，记录中断前实际模型等待秒数，不记录提示词或正文。每5秒更新可见等待进度。

相关执行模块：`src/agent/results/insights.splash`（结构与引用）、`src/app/insights.splash`（展示与决定）、`src/app/results.splash`（结果分组与保存后反馈）、`src/data/ingestion/analysis_evidence.splash`（正文）、`src/app/reschedule.splash`（预览确认）、`src/app/continuous_tracking.splash`（前台队列）和 `src/app/intent_motion.splash`（意图空间过渡）。均已加入 assemble.ORDER。

结果页分组不改变持久化格式：撤回优先进入待办；用户决定 handled/dismissed 进入记录，watch 进入观察；未决定的 unknown/review 进入待办，其他判断进入观察。unknown 即使 unchanged 也继续保留核实入口。分组由当前有效判断与持久化决定派生，只有 topics_commit 成功才反馈保存并切换入口。证据展开键包含检查任务、目标、版本及问题，不串用别的判断。记录页展示当前有效判断的决定，不是完整历史档案。

## 话题总览、详情与依据（10.11）

`app/follow_topics.splash` 从原有保存结果派生话题卡：按 topic_id/version 选择最近判断，最多3个独立事件；没有新增全话题摘要字段，也不重新请求模型。候选数与实际引用的依据数分开，未找到候选不能被转述成没有新进展。旧版本或已失效结果标为历史，检查中和失败保留上次情况并标注；已暂停话题折叠，只供回顾或恢复。结果缓存最多12轮，逐话题检查每项占一轮；已完成检查但详情未保留时，成功水位只显示检查时间，不能冒充分析快照，卡片提供单独重查入口。

目前情况来自已校验的 insight.summary；建议保留原 next_step，用户决定单独显示。撤回、待核实优先于普通观察；handled/dismissed 不作为新安排，但原建议仍可回顾。详情的决定、补证和日程草稿仍调用原 owner 严格检查当前目标、证据及版本，不把展示投影当成写入许可。

`app/follow_navigation.splash` 管理 overview/topic/evidence 入口和手动逐话题队列。每次传入原 tracking_start 的单话题 target_override，不新增 Agent 或宿主任务接口；每项各召回最多8个候选、分析并完成保存，再继续下一项。一项失败继续其他项，暂停不参与；停止、目标上下文变化、未保存结果或未确认中断终止后续项。队列阻止自动检查插入，并在刷新、意图编辑、摘要或连接探测间隙等待；进度不得把尚未启动的话题算作失败或完成。

独立依据页只列该话题判断引用的 evidence_ids，并再次核对 items 对同一目标的关联；uncertain 标为待核实。标题、摘要、来源、段落和 quote 来自对应 run 的快照。读取旧报道使用快照构造合法 news 行，不依赖它还在当前首页；当前站点读取状态与保存段落各自展示。普通首页阅读清除旧证据上下文；退出阅读返回原话题依据入口及滚动位置。导航不改持久化结构。

## 宿主边界

首页 `tracking_current_values()` 只读恢复已有标注，单轮核验、单条投影分别使用独立回调；恢复期间返回空标注，新闻浏览与来源刷新不等待。缓存键覆盖目标/决定上下文、来源版本、新闻集合、检查任务、正文缓存修订和证据到期时间，变化后隐藏旧投影。新闻事实时效与严格校验一致，采用当前来源行的获取时间，正文仍采用被引用证据的时间。`analysis_current_row` 和 `tracking_current_row` 复用来源/合并索引。结果详情与用户决定、正文重试和日程确认仍直接执行当前输入校验，不能将展示缓存当写入许可。

固定 Rinx 每应用实例有独立 Octos context，包含自己的 transcript。重复 open 不能假定会清空历史；应用保留 open/start，提示当前任务仅采用当轮 INPUT/SNAPSHOT，并未引入未经验证的 reset/reuse 优化。只检查固定源码可证明的接口，不声称 runtime 历史隔离策略已完成真实模型测量。

宿主没有应用关闭后的定时/推送服务，所以 B08 使用可暂停的前台 timer，经现有单队列和用户输入优先级触发。应用重新打开恢复偏好和水位；未完成任务可能仍显示待检查，下一次实际触发会覆盖状态。未来后台能力需要宿主新增生命周期、通知授权、重复触发/停止机制，再单独接线和验收。

`tracking-v2.5`：目标引用与逐条相关性对齐，允许无相关新闻的空引用（不是空候选时调用模型）。空引用不能改变决定，unchanged 不得带 material_change；no_change 不得含 updated/withdrawn。结果按相关新闻、当前情况与未知项、下一步展示；历史情况单独标记，不充当当前证据。完整关键词匹配在有界召回中优先，仍是词法匹配，不保证语义相关或全面覆盖。

## tracking-v2.8 标题初筛与输出恢复

逐话题检查先用标题的完整关键词做初筛，再用 BM25 排序。新闻话题优先使用同时出现在关注名称中的具体关键词；实用目标保留具体任务关键词的并集，允许多个任务和显式别名，宽泛 AI 等词不替代具体任务。来源、分类、摘要和范围的零散二元词不单独放行话题候选。正文与摘要仍由 Agent 再核对实际关联，并按相关新闻内容、目前情况、下一步顺序生成反馈。这是词法初筛，标题未提及的报道可能漏召回；日程和旧显式来源/分类关注保留独立召回路径。普通新闻话题也可读取正文，缺少摘要的候选优先，网页请求仍最多两篇。

输出截断时最多缩减候选并简短重试一次，与格式纠正共享额度；沿用原任务/会话和总期限，保留实际范围与遗漏数。半截回复不发布，保存完整、严格校验后的新结果才更新成功水位；失败保留旧情况。完整验证及包记录见 reports/tracking-output-retry-20261012.md。

## tracking-v2.9 标题证据可用性提示

实时解析先通过所有结构、引用、目标及版本检查，再执行证据充分性检查。针对单一 goal 话题，无日程或旧关注混入，若模型的目标结论只有标题且违反 unknown/核实步骤/insufficient_evidence 契约，且该话题全部关联候选确实无摘要与正文，则构造新的系统证据可用性提示。丢弃原模型的结论和建议，关联改为 uncertain，决策影响 unknown，提供实际新闻标题及补读路线，无正文引文或日程动作。保留稳定问题标识及同目标历史比较；已有问题记 unchanged，material_change 为空，不重开用户决定。新提示再次通过完整结构与证据检查后经原异步 owner 保存。

judgment_origin=evidence_gap 标识系统提示；实时输入中的同名模型字段先被清除，模型不能自行声明此来源。关注卡显示“正文待补”和“尚未完成内容判断”。这不表示完成了内容核实，也不表示网站验证已被解决。可用摘要/正文仍用于正常模型分析；错引用、错版本、目标或其他校验失败不使用回退。旧提示词版本仍按原契约读取，不重新解释历史，也不更改已有用户记录。

## tracking-v2.10 宿主超时恢复与前置材料检查

固定 app-peers 宿主默认模型轮次180秒；超时分支发送 interrupt 请求、清理该轮本地 waiter 后返回明确错误，底层是否成功停止仍取决于服务响应。应用只对明确的 assistant turn timed out 返回执行一次轻量重试，普通服务/网络 timeout、应用自有阶段或总期限不触发此分支。重试沿用相同任务及会话，最多保留两篇候选，使用 tracking-timeout-retry-prompt.txt，范围 reduced_timeout_retry；E 标识、input_key、遗漏数与实际新快照一致。格式纠正、输出截断及宿主超时共享 repair_count<=1，原70/190/470秒期限不提高；再次失败保存旧判断，不接纳残缺或迟到结果。缩减轮次只给信息与核实建议，不生成日程影响或改期动作。

模型分析前使用 tracking_preflight_notice：只针对单一 goal、无日程/旧关注混入、非空候选且所有候选无摘要/正文，构造明确的系统证据可用性提示并通过完整校验后由原 owner 保存。连接仍由宿主建立，但不会调用 octos.turn.start；可用摘要/正文、普通话题和混合目标继续模型路径。检查前安排续步，原生预算中断不能丢失后续执行；原任务的当前性、取消、总期限、引用及存储核验保护保留。

## tracking-v2.11 无关联报道结果

空关联的保护按每个目标执行：effect unknown、无 material_change/改期；全轮 outcome 仅在全部 insight 没有引用依据时须为 insufficient_evidence。有当前依据的其他话题可继续 update/no_change。目标判断的“只有标题”检查不再把空 evidence_ids 当成一篇只有标题的相关报道。

空关联决策规则的错误先暂存，继续检查完整的引用、目标版本、历史比较、日程权限等，其他错误优先拒绝。仅当所有话题均没有相关或待核实关联，且无日程/旧关注混入时，实时解析可以基于这些已校验的有限分类构造新的 no_related_evidence 系统反馈，丢弃模型无依据的行动结论。新的反馈再次通过全部规则并经原 owner 保存；它说明本轮尚无新依据、覆盖有限和已有决定保留，不宣称全网无进展。混合目标有有效依据时不构造全轮空关联反馈。旧契约不重新解释或迁移。

关注卡为“暂未确认新进展”，依据页区分已完成但无引用与尚未检查；系统空关联反馈进入观察、不产生新行动提醒，已有 handled/dismissed 决定仍按原规则展示。
