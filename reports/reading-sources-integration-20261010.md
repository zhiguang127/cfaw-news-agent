# 五个阅读来源与手动全文摘要

已更新 `src/` 并通过 `scripts/package.py` 组装、刷新未签名开发包摘要。未推送 GitHub、发布或修改用户账户中的宿主配置。

## 当前行为

- 默认五个来源：36氪、IT之家、少数派、MIT Research、Solidot。MIT复用原ID，其余旧来源暂时关闭。
- 旧 `interests_v1.json` 的来源选择一次性迁移到五个新来源，保留用户关注、收藏和日程。保存 `reading_sources_revision: 2`；以后尊重手动选择，包括全部关闭。
- MIT与少数派直接显示来源摘要。36氪、IT之家、Solidot的RSS描述是正文，保存到 `body_html`，不当作独立摘要。
- 正文优先来自RSS；少数派公开SSR页面提取文章区域文字并保留段落，嵌入图片、视频使用应用内原文页阅读。Solidot正文为自身短报道。
- 没有来源摘要时显示“Agent 摘要提取”。手动点击才调用宿主已配置的Octos助手，不存储或另配模型密钥。
- Unicode正文分为至多10KB片段。各分段都进入模型后再汇总；更多分段采用有界中间汇总。正文未获取或被截断时显示原因，不生成全文摘要。
- 摘要支持取消、重试、切换文章取消和过期回包拒绝。结果最多缓存本次会话20篇，刷新后的新闻不会复用旧获取版本的摘要。
- 追踪证据缓存保持六段/4KB并标注节选，与手动全文摘要数据分开。

## 实际验证

1. 官方公开RSS样本：MIT 20条、36氪20条、IT之家20条、少数派10条、Solidot20条，共90条；抽查每个来源首条新闻正文。少数派原文使用真实公开HTML样本。
2. Windows隔离Rinx宿主：66项通过，0失败。包括五个来源实际 `article_load` 路径、来源摘要与正文分离、来源迁移、保留用户关注、全部关闭后重读、摘要按钮真实点击、Unicode分段无丢字/末尾保留、分段合并、取消和截断拒绝。
3. Agent回包使用明确标注的合成回复，`sample_origin` 为 `synthetic_fixture`。没有调用用户的真实LLM，也不将此测试声明为真实模型质量或服务验收。
4. 实际联网启动：五个来源均为fresh，90条新闻，`completed: 5`、`active: 0`、`busy: false`，旧来源均not_loaded。日志无脚本错误。记录位于 `.test-state/live-news-mit-1791567303096946400/`。
5. `tests/unit/test_assembly.py`：5项通过。修复其临时工作区未复制独立提示词模板的问题。
6. `scripts/package.py` 通过可移植路径摘要探针并刷新包；bundle digest为 `79e14e863815b37f6f0c6eea0736f6aba1de04731097135d1bd196471f0f7ddb`。

运行记录：`.test-state/reading-sources/report.json`，按钮截图：`.test-state/reading-sources/summary-before.png`。详细检查使用真实RSS/HTML样本与合成模型回包，两个范围分别标明。

## 限制

- 正文提取上限96KB / 260段，RSS单条HTML保留上限160KB；不保证所有文章、付费内容或改版页面都可提取。
- 实际用户LLM服务的连通性、摘要事实质量与响应耗时尚未在本轮实测。运行时沿用已存在的宿主服务边界，真实服务错误会显示。
- 当前Windows Hub的 `check bundle --allow-unsigned` 因 `assets\\icon.svg` 被识别为不可移植路径而失败。这是工具在Windows枚举路径的限制；包已按项目工作流stamp，但本轮不能声明Hub发布检查通过，也未执行发布。

导入 `bundle/` 或 `build/cfaw-news.zip` 前退出旧应用实例，并重新Review/Run以使新增网络域名和脚本生效。无需清空用户应用私有数据。
