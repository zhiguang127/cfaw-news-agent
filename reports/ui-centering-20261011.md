# 首页标签与回顶按钮修正

目标版本：`cfaw-news-agent-10.11`。

“今日精选”、新闻分类标签和圆形字标继承了 Makepad Label 默认的四边内边距，容器又添加上下内边距，导致文字在小尺寸徽章中偏下。回顶按钮沿用 Primary 的左右 14px 内边距，40px 宽度内绘制 20px 字号箭头，造成挤压与偏移。

本次仅修改前端三份源码，并重新装配 bundle：

- `styles.splash`：共用的 `EditorialBadgeText` 清除 padding/margin，按文字墨迹居中；分类容器显式水平/垂直居中，只保留左右内边距。
- `news_list.splash`：“今日精选”、分类标签和 22px 圆形字标使用同一文字规则，保留各自字体与配色。
- `app_view.splash`：回顶按钮改用 32×32 的 `EditorialBackToTop`，淡紫色圆底、细线矢量箭头，保留原生按钮的点击、悬停、焦点反馈与原有回顶逻辑。

验证使用隔离的原生 Rinx 探针：430×860 和 568×914 两个窗口尺寸，固定样例检查科技、商业与生活组合标签及三种圆形字标；截图核对居中，实际点击回顶成功，两次均无原生脚本错误。另一次 IT 之家真实公开新闻验证取得 20 条新闻及配图，核对实际精选标签显示，原生错误 0。未调用模型或修改用户数据。

界面证据：`.test-state/ui-centering/430x860/`、`.test-state/ui-centering/568x914/` 与 `.test-state/live-news-ithome-1791692927098248700/feed.png`。固定样例明确标注“合成界面样例”，未进入交付 bundle。

最终 bundle digest：`0cfd52ae43205742ac3ac7c04dd59d40deca7bd46442d849678dbd13eb67023e`。

源文件装配一致性、本地 unsigned Hub 结构检查和 ZIP 的 8 文件清单、CRC、逐字节一致性均通过。记录：`build/ui-centering-verification.json`。该结构检查不代表官方发布或评分。

重新 Review/Run `cfaw-news-agent-10.11/bundle`，替换当前运行中的旧应用快照即可看到更新。
