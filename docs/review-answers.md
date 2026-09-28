# Hub scan 七问回答（本地自查，不是审核批准）

材料由固定版本 `hub scan bundle --packet build/review.json` 生成，没有调用外部 reviewer、签名或提交。

1. **名称与描述是否属实？** `main.splash` 中 `sources`、`refresh_news`、`analyze`、`save_watch`、`load_watches` 对应读取新闻、请求研究和保存关注。列表明确区分 demo / live，未承诺自动监控。listing 明示 Rinx 与真实模型待验收。
2. **平台和分类是否合适？** news 分类；仅列本次实际运行的 Linux。Linux card-host 不等于 Rinx 已通过，说明中明确区分；未宣称 Android/macOS/Windows 已测。
3. **能力和域名是否必要？** net 只为 `www.apple.com` 和 `blogs.nvidia.com` 官方 feed；storage 保存关注；octos.turn.start 与 interrupt 对应分析/取消。没有未使用的 session/history、Matrix、web 或后台权限。UI 素材为包内 SVG。
4. **界面是否冒充系统或诱骗？** CFAW 标识清楚，无账号/密钥表单，不仿造系统许可或付款；原始机构名称仅表示新闻来源。演示标题和摘要明示虚构。
5. **是否包含给助手的指令？** 是：`analyze` 中应用自己编写的研究提示词，发送到用户主动授权的 Octos 调用；不是来源内容偷偷注入指令。JSON 新闻字段标为不可信数据，要求不执行工具/交易/发送消息；用户仍需核对模型行为。此项应由人工确认是产品必要功能，不能因为静态扫描通过就称 prompt 安全性已获审核。
6. **是否含侮辱或针对个人内容？** 应用静态文案及演示不含。远端 feed 未预审、不可保证今后内容；按原始来源文本展示，不执行。
7. **Route？** **human-review（发布前）**。可用于本地开发导入；真实 Rinx/Octos 成功尚未验收，隐私 URL 是公开说明的保留域名占位，正式发布者支持信息、平台声明、签名未确认。本次用户禁止发布，不推进这些步骤，不冒称获得人工批准。
