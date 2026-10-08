# CFAW News 提交审核说明

仓库：https://github.com/zhiguang127/cfaw-news-agent

应用：`dev.cfaw.news`，版本 `1.0.0`，bundle 路径 `bundle/`。
发布者展示名称采用仓库所有者 `zhiguang127`。首次提交未签名。

## 展示与平台

作品是 Windows Rinx 中运行的 OctoScript 新闻应用。源码提供新闻刷新、阅读、收藏、自然语言关注、变化分析和用户确认的应用内日程操作。模型能力依赖宿主 Octos 服务与用户配置的提供方，团队使用 MiniMax。当前两张截图由作者提供：新闻首页和意图输入页面；后者是输入表单，不能证明已成功执行模型理解或分析。首页中初始化的关注和日程带“演示预设”标签，不是缓存演示新闻。

分类为 news，只声明 windows。暂定年龄标识 12+，新闻由第三方提供，没有逐条年龄审核。正文、配图受来源权限和提取能力限制；无后台推送、系统日历写入或云同步。

## 权限及域名

- storage：关注、日程、草稿、新闻及正文缓存、收藏、分析与决定等应用记录，最多 8 MiB。
- net：真实来源、正文、天气请求。
- images：首页与正文远程配图。
- web：通过 LinkLabel 打开新闻原文到系统浏览器。
- octos.session.open / octos.turn.start / octos.turn.interrupt：宿主助手会话、执行与取消。不直接收集模型密钥。

新闻请求域名：`feeds.arstechnica.com`、`news.google.com`、`feeds.bbci.co.uk`、`hn.algolia.com`、`export.arxiv.org`、`rss.arxiv.org`、`www.airchinagroup.com`、`www.techmeme.com`、`techcrunch.com`、`venturebeat.com`、`news.mit.edu`、`www.theguardian.com`、`www.cnbc.com`、`www.theverge.com`，具体启用状态见来源配置。

正文及跳转支持：`arstechnica.com`、`arxiv.org`、`www.bbc.com`、`www.bbc.co.uk`、`news.ycombinator.com`，以及与上述来源重合的正文域名。图片：`cdn.arstechnica.net`、`cdn.vox-cdn.com`、`duet-cdn.vox-cdn.com`、`i.guim.co.uk`、`ichef.bbci.co.uk`。天气：`api.open-meteo.com`，使用预设城市坐标。

`cdn.jsdelivr.net` 是源码保留的节假日及汇率辅助模块请求域名，当前主界面没有直接触发入口，是额外授权，需要维护者评估是否移除。应用没有提供任意域名请求授权。

## 提示词与内容审核

应用名称及图标为 CFAW News，不仿冒登录、支付或系统授权界面；宿主授权由宿主管理。README 和 NOTICE 保留上游归属与许可证。

`main.splash` 是源码组装产物，包含本应用的意图理解、分析及结果修复提示词。这些确实是对助手的指令，位于脚本字符串而非独立 AGENT.md，需人工审核。用途限于本应用关注、日程和给定新闻证据；模型输出经结构、引用及版本校验，日程变更仍需用户确认。新闻输入作为不可信证据处理，不能授权更改其他应用或系统。没有额外工具执行器或自带原生代码。

应用自身文案未发现侮辱或针对私人个体的内容；新闻会持续从第三方来源获取，不能声明未来全部内容已审核。

建议审核路由：human-review。此文件是作者说明，不是官方 scan 判定。

## 本地检查边界

`hub check bundle --allow-unsigned` 通过，保留首次未签名警告。`hub scan --packet` 已生成问题包，没有运行独立审查器，不能声称 scan 已通过。

本地 Hub 工具使用当前源码的隔离构建，并修复 Windows 路径分隔符的摘要及目录检查兼容问题；维护者应使用官方环境重新校验最终 tag/commit。工具生成的摘要使用跨平台 `/` 路径，不绕过摘要校验。

添加或修改截图、图标、listing 或程序后，必须重新运行 package.py 更新摘要。旧 manifest 配合新增截图会导致 Review bundle 报 digest mismatch。
