# new.2 B 交付与验证指南

更新：2026-10-05。只针对本目录 new.2 的 B01–B08，未沿用 new.1 的任务边界。开发已接线；下表区分代码、固定输入验证与尚未完成的产品验收。**不能把本次交付当作所有 B 验收已通过。** 当前目录为无 `.git` 的快照，没有提交、推送或发布。

## 交付状态

| 任务 | 本次实现 | 当前验证与边界 |
| --- | --- | --- |
| B01 | 分阶段元数据、字节数、错误类型；真实进度；精简上下文；无候选不调用、有效结果复用；单队列与取消保护；前后基准包和汇总脚本 | 固定输入状态/保护通过。真实三类任务各冷/热 5 次、300ms 状态时延、20% 中位数降低均未实测，不声明达标 |
| B02 | 区分 goal 的决策核实项与 news 的话题变化；只用对应目标 ID/版本的历史 | 新契约与跨目标/跨版本检查通过；实际模型语义质量待 A 验收 |
| B03 | 每目标最多 3 条 issue；新增/更新/撤回/无变化；保留证据、决定、历史；同事实已处理不再提醒、新事实解释后重新提示 | 固定输入重复/修订/撤回检查通过；模型同事件归并须人工审查 |
| B04 | 独立正文缓存、有界补证据、段落引用校验、失败摘要回退、旧证据失效 | 日期有/无、失败、伪造引用、正文变化检查通过；真实页面、矛盾来源与事实支持程度待验收 |
| B05 | 日期/精确时段区别；主动查看才出现一项补充问题；确认才改版本；已有出行来源优先及覆盖提示 | 日期型及两周天气边界通过。没有新增抓取域名；不能保证某班次/区域覆盖；未新增自动天气联合推理 |
| B06 | 提案预览、明确确认、继续原计划、owner 版本/冲突检查、幂等、写前日志、恢复、撤回 | owner/校验固定输入通过。2026-10-06 按用户最新要求默认开启提案，仍需逐项产品验收及明确确认 |
| B07 | 应用拖动/吸附/归一化偏好/动画起点；固定 Makepad 原生 400ms 长按、释放和视口回调补丁；旧宿主能力检测 | 补丁原始 hash、幂等、未知源码拒绝、Rust 语法及真实 Rinx release 编译通过；产物 hash 已记录。430×860、360×860 拖动/重启验收待做。旧宿主仅可点击并提示限制 |
| B08 | 每目标水位和检查状态；近期行程优先；5/15/60 分钟、暂停、仅重要变化；同一前台队列 | 偏好、版本与队列固定输入通过。宿主未提供关闭后调度/推送接口，保持前台检查范围 |

运行产物是 `build/cfaw-news.zip`（未签名、本地导入），源文件在 `src/`，生成入口在 `bundle/main.splash`。ZIP 不包含宿主、登录信息、密钥或个人数据。基准包在 `build/agent-benchmark/`，不能当作正式应用替换用户数据。

## 已执行的检查

- 新版 insights 原生场景：33 项通过、0 失败；契约、引用、版本、决定记忆、改期 owner、取消保护、补证据上限均覆盖。
- 历史 tracking 兼容场景：84 项通过、0 失败。明确使用历史 v1.2 的固定模型回复；新版实时解析仍要求 schema 2。
- 入口组装检查：5 项通过。
- 六个固定输入基准应用：原生进入“准备就绪”，日志无 `[E]`；未点击真实调用按钮，未取得模型数据。
- 结果页原生 PNG 有文字像素，人工查看布局；参考 card-host 的实际逻辑尺寸 **412×892**。这不是目标 Rinx 430×860/360×860 验收。
- 正式 bundle 隔离启动及普通小球点击通过，首页和意图空间有原生截图，宿主日志无 `[E]`；未调用真实模型。这项使用参考 card-host，不能证明修补版 Rinx 字体/拖动已通过。

保留证据在 `reports/b-delivery/`，包括检查汇总、截图、像素结果、补丁源码检查、基准包启动检查、依赖与阻塞状态。固定输入使用隔离数据目录，不能替代真实模型、真实账户导入或真实网页事实审查。此前 acceptance.md 的历史模型记录不是本次 new.2 新契约的通过记录。

## 1. 准备并打开应用

锁定依赖已拉到本项目 `.dev/vendor`。这一步有必要：bundle 不能独自修复原生字体/渲染或提供 Windows 长按事件。没有把依赖升级成未经核对的远端最新版。2026-10-05 用户安装 C++ 工具后已完成 Rinx release 编译，原生长按和 D3D11 补丁已记录匹配产物；首次构建的工具链、下载及内置应用摘要问题也已排障。不能保证“拉完依赖就绝不会白屏”。

本机已完成 All 构建并启动 SDF Rinx，登录页文字和图标实际可见；见 [构建启动记录](../reports/b-delivery/windows-build-run.json)。其他机器先安装 Visual Studio 的 **Desktop development with C++**（含 Windows SDK）并备齐项目运行说明要求的 Rust、CMake/Ninja。也可由队友在具备工具链的电脑构建锁定版本及本项目补丁。宿主必须完整退出后重开，重新导入 bundle 不会替换原生代码。

PowerShell 进入项目后执行（Python 已在 PATH 时可改为 `python`）：

```powershell
Set-Location 'D:\Hackathon_agenticapp\workspace\cfaw-news-agent-new.2'
$taskPython = 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:Path = (Split-Path $taskPython) + ';' + $env:Path
if (Test-Path 'build/git-safe-directories.config') {
    $env:GIT_CONFIG_GLOBAL = (Resolve-Path 'build/git-safe-directories.config').Path
}
& $taskPython scripts/prepare_dev_dependencies.py
& scripts/build_windows_tools.ps1 -Mode All
& scripts/run_windows.ps1 -Mode Rinx -Diagnostic
```

每步须成功才继续。构建会核对锁定提交，修补本项目私有 Cargo checkout，重新构建并记录手势和 D3D11 产物 hash。启动默认 SDF 字体入口；见 `docs/windows-development.md`。不要绕过 `patch_gesture_host.py --check-artifacts` 的失败。Rinx 中 **Mini apps → Import an app** 选择本目录 `bundle/`，然后 **Review bundle → Run**。若用 ZIP 导入入口则选择 `build/cfaw-news.zip`。需要分析时在 Rinx 本地配置模型并登录；不要把密钥写入项目、报告或聊天。

## 2. 复现本地自动检查

使用自己编好的 card-host；以下默认路径只有在构建成功后才存在：

```powershell
& $taskPython scripts/assemble.py
& $taskPython -m unittest discover -s tests/unit -p test_assembly.py
$taskHost = Join-Path (Get-Location) '.dev/vendor/OctoSense-App-Hub/target/release/card-host.exe'
& $taskPython scripts/test_runtime.py --host $taskHost --suites insights --inspect-ui --timeout-seconds 120
& $taskPython scripts/test_runtime.py --host $taskHost --suites tracking --timeout-seconds 120
```

预期分别为 5、33、84 项通过，0 失败。每次输出独立 `.test-state/runtime-*/combined-report.json`。截图和 `insights-pixels.json` 要同时看；控件存在不能证明字体已绘出。检查报告中的真实尺寸，不能靠命令中写了尺寸就声称检查了该尺寸。

此前 33/84 项固定输入记录使用 `D:\Hackathon_agenticapp\octosense-ws\OctoSense-App-Hub\target\release\card-host.exe`，仍是参考宿主的记录。本次新编译的本项目 card-host 已可用于重新验证；构建成功不能替代实际测试结果。

## 3. 手动产品验收

建议先备份宿主数据目录，以普通点击操作保存独立的测试关注/日程。不要直接编辑数据文件作为正常产品验证。

1. **目标与新闻的区别**：分别输入“我想选择支持离线部署的开源 Agent 框架，少看融资新闻”与“关注 Agent 行业动态”。预览确认后打开菜单的关注页，执行检查，再进入“分析与建议”。前者应解释对选型目标的影响并给核实项，后者可只有话题变化；不能强行替用户安排动作。无证据应显示未知。
2. **历史与决定**：先只检查目标一，再切换目标二，再检查目标一。确认不引用目标二的比较记录。对变化点“已处理”或“忽略”，重检同证据不应重新提醒；新增事实应写明新增了什么。撤回旧判断必须能看到原因。修改目标后当前卡片失效，最近检查历史仍保留。
3. **正文**：打开受支持来源的新闻详情，再检查对应目标或该条新闻。点“查看来源与引用段落”，逐字核对引文、段落、日期、地点、来源和抓取时间。分别检查摘要无日期但正文有日期、正文也无日期、抓取失败、来源相互矛盾、正文变更五类。矛盾内容不能悄悄择一当事实；旧正文失效后应要求重新检查。不可把来源不支持误当完整正文读取成功。
4. **上海行程**：首次预设应保留原日期，重开不顺延。主动点行程核对前不应弹追问；主动查看才出现一项缺失信息。日期型应提示具体时间待补充。编辑并确认真实出发/结束时间、交通或区域，日程版本才改变，旧提醒失效。用明确覆盖行程日期的公告、普通上海新闻、过期/无日期消息和未知班次分别审查。两周后的天气只能显示覆盖不足；近期预报仍需天气页核对时间与不确定性。
5. **输入优先与失败**：自动检查期间打开小球提交新的关注；应先停止新闻任务，再整理输入，不发并行 turn。点击停止后确认取消状态。断网、模型错误、读取失败时仍能读缓存新闻和打开记录，不能显示保存成功。约 300ms 的即时状态需在目标宿主录屏或测量，未测量不能只凭感觉写达标。
6. **前台持续检查**：关注页切换 5/15/60 分钟，暂停后不再启动自动新闻任务，手动输入仍能使用。重开核对偏好和成功水位。一次最多检查选中的目标，不应把所有目标的时间一起更新。失败保留上次成功水位。“仅重要变化”过滤重要提醒而不替用户删除历史。关闭应用后应停止，不应承诺推送。

受支持来源目前不能保证真实机场、铁路、场馆公告覆盖。请 A 准备上述真实报道 URL/发布日期和对应行程；新增来源若需要，必须单独同步数据层配置、网络 allowlist 和宿主网络验证。

## 4. 长按移动专项验收

只在加载本项目手势补丁的 Rinx 上进行；未修补宿主会保留可点击球并提示限制。先将应用实际视口设为 **430×860**，再重复 **360×860**，记录实际控件/像素尺寸。Rinx 的总窗口尺寸不等于 mini-app 的内容视口；按该宿主实际布局调整并核对诊断快照。

依次验证：普通短点击打开 → 关闭 → 按住约 400ms 再拖动 → 四边/四角越界 → 松手吸附最近左右边 → 再点击打开。拖动期间应跟随；松开不能打开面板或底下新闻。顶部导航、底部搜索仍可点击。随后输入并确认保存，动画应从新球位展开并收回同一位置；退出 mini-app、重开和完整重启 Rinx，位置应恢复且不越界。位置保存在 `agent_preferences_v1.json` 的 0..1 坐标，不应进入模型上下文。

如果不能取得 PNG，只记录控件与事件结果，并标明像素未覆盖。原生补丁已编译。2026-10-06 修复能力误判和拖动控件重建问题，隔离原生专项验证见 reports/b-delivery/ui-followup/ 中的报告；需区分记录中的实际应用内容尺寸与宿主总窗口尺寸。

## 5. 改期专项验收（B04/B05 产品验收之后）

2026-10-06 按用户最新要求，`src/app/config.splash` 的 `tracking_config.enable_reschedule_proposals` 默认 `true`；新建日程默认启用 `allow_reschedule`，仍可手动取消选择，旧日程保留原设置。提案仍必须具有精确时段、明确地点与正文依据，保存前需要用户确认。旧 `proposed_action` 仍拒绝，本链路使用 `insights[].reschedule`。

准备有明确地点及新起止时间引文的案例：打开提案应看到原/新安排、理由、引文、未知项；“继续原计划并记录决定”保持日程、记录已处理。再次生成独立提案，明确点击确认才写入。连续确认应只改变一次版本。预览后编辑日程、制造时间冲突、让证据过期，应拒绝变更并保留提案。成功后撤回恢复原安排但增加版本；改期后又手动编辑时撤回必须拒绝覆盖。存储失败时不得声称成功，写前日志可用“恢复已确认的改期记录”完成同一提案的审计恢复。只涉及应用内部记录。

## 6. 真实模型前后耗时与质量

基准构建脚本不调用模型。它创建隔离 ID 的 before/after 应用，固定公开合成输入，使用真实适配器和原生校验；before 使用保留的 tracking-v1.2 提示模板，after 为 v2.0。两者业务目标相同，输入字段按各版本的实际策略组织，after 减少冗余并提供新版证据。测量的是这个明确场景，不能推出所有业务必然提速。

包中的追踪时间有两小时有效期，所以实际测量前重新生成六个包，共用一个时间值：

```powershell
$env:OCTO_HUB = Join-Path (Get-Location) '.dev/vendor/OctoSense-App-Hub/target/release/hub.exe'
$taskReference = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
foreach ($taskKind in @('parse_intent','parse_schedule_intent','tracking_update')) {
    foreach ($taskVariant in @('before','after')) {
        & $taskPython scripts/package_agent_benchmark.py --kind $taskKind --variant $taskVariant --reference-time $taskReference
        if ($LASTEXITCODE -ne 0) { throw '基准包生成失败' }
    }
}
```

在**同一锁定宿主、账户、模型、参数、网络与电脑**导入各个 `build/agent-benchmark/<variant>-<kind>/bundle/`，开启对应基准应用的结果页。每次点击“开始下一次真实调用”只执行一次调用，需等终态后再次点击，共 2 次。每个 kind/variant 真正销毁应用实例后重开 5 次，得到首次 cold 5 条、后续 warm 5 条；**共 60 次真实调用，会使用宿主的模型额度**。交替 before/after 降低时间漂移。关闭面板可能仅隐藏实例：要核对 `launch_id` 确实改变，每轮只运行这一种任务。这里 cold 指应用实例中该任务的首次调用，不代表模型服务器必然冷启动。

在宿主实际 app 数据目录查找 `agent_metrics_v1.json`，按隔离应用 ID 区分 six files；记录非敏感模型/宿主/环境信息，不导出凭据。基准各应用独立存储，不保存正常用户关注/日程。追踪两小时失效后重建同一对包，并重新收集相应组样本，不混用旧输入。

复制六份元数据为 `reports/b-delivery/live-before-*.json` / `live-after-*.json` 后执行：

```powershell
$taskBefore = @(Get-ChildItem reports/b-delivery/live-before-*.json | ForEach-Object FullName)
$taskAfter = @(Get-ChildItem reports/b-delivery/live-after-*.json | ForEach-Object FullName)
& $taskPython scripts/summarize_agent_benchmark.py --before $taskBefore --after $taskAfter --same-input-model-environment --output reports/b-delivery/live-benchmark.json
```

只有确认条件相同才加 `--same-input-model-environment`。脚本排除 `sample_origin=fixture`，不足 5 条的组不出达标结论，报告总耗时中位数/范围、分阶段中位数、通过结构校验比例与成功比例。逐组看 `median_reduction` 是否 ≥0.2 和 `quality_preserved`；同时人工核对正文事实、目标/新闻区别、负面偏好。schema 通过不证明事实正确。没有测到 20% 就记录实际结果与瓶颈。300ms 本地状态另测，不能拿模型中位数代替。

## 给 A 的交接

B 接线不需要等 A 的开发任务。A 返回后负责产品验收，需要提供或确认：真实模型可用环境、真实业务偏好及预期、日期/地点明确的原始公告、矛盾来源案例、实际行程班次/活动区域、目标视口下的交互结果。只须把模型配置留在 Rinx 本地，不向 B 发送密钥。

B 已提供：`tracking-v2.0` / schema 2 契约（`src/contracts/tracking-v2.md`）、旧 schema 1 历史读取策略、模块/owner 与持久文件清单、未签名 ZIP、固定输入证据、真实基准包与汇总工具、手势补丁和构建校验、B06 开关与验收门槛、前台范围及宿主依赖。A 不要重写共享接线或清空历史来适配新输出。需要修订契约时同时更新 prompt、校验器、调用者、固定场景与组装顺序。

2026-10-06 跟进：小球不能移动的能力判断已修复，正式运行须使用项目修补版宿主；原先的脚本原型字段检测不能判断 Rust live 字段是否存在，不再据此退回普通按钮。
