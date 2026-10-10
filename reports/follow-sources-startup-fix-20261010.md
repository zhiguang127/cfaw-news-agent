# 关注话题、扩展来源与启动卡住修复（2026-10-10）

## 修改结果

- 新闻列表与阅读页的“关注来源”改为“关注话题”。填入文章标题和原文地址，打开可编辑话题草稿；不自动调用模型，不创建媒体范围规则。用户整理并确认后才保存具体话题。既有输入、补充信息、修改关注草稿和日程提醒草稿优先恢复，避免被新闻按钮覆盖。旧来源规则仍可在关注管理页删除。
- 新增爱范儿与 NASA 官方新闻发布 RSS。独立 description 摘要直接显示，content:encoded HTML 用于正文；源摘要不调用模型。新安装/旧来源方案迁移默认七源，revision 2 的第一批配置保留原选择，新源可通过“新闻来源”开启；全部关闭的选择仍保留。原先其他来源保持默认关闭。
- 修复保存来源设置后的启动中断。恢复来源选择使用独立函数和集合过滤，避免宿主在嵌套遍历中出现空栈异常；检查空记录并保留用户记录/备份。启动显示当前加载阶段，12 秒未完成时显示阶段与重新 Run 的指引，不会一直只显示初始占位提示。

## 复现与定位

实际账户数据位于 Rinx 分配的 dev.cfaw.news 私有目录，包含来源设置、新闻缓存、关注、日程与分析历史。本次全部复制到 .test-state 隔离目录执行，原账户文件未修改。

修复前：.test-state/live-news-hn-1791569006813075100/host.log 记录 `pop_stack_value on empty stack`；0 行新闻、0 完成来源，尚未执行网络请求。后续调用阶段标记确认中断发生在已保存来源选择的恢复分支。首次空数据启动走默认选择而绕过该分支，因此空数据成功不能证明再次 Run 成功。最初日志行落在后续收藏清理附近；空数组保护本身没有解决问题，以阶段定位和修复后的同副本验证为准。

## 验证证据

| 检查 | 实际结果 | 记录 |
| --- | --- | --- |
| 真实账户副本，恢复第一批五源 | 90 条新闻；完成 5/5；busy=false、active=0；无脚本错误 | .test-state/live-news-hn-1791569562706680200 |
| 首次启动，七个官方公开来源真实网络 | 120 条新闻；完成 7/7；各启用源 fresh，旧源 not_loaded；无脚本错误 | .test-state/live-news-hn-1791569628386021000 |
| 已有新闻缓存再次启动 | 120 条新闻；七源 cached；无需新请求；busy=false；无脚本错误 | .test-state/live-news-hn-1791569914575660700 |
| 原生界面点击关注话题 | 可见文章标题草稿，0 自动模型调用，0 自动来源订阅；恢复草稿；明确确认后仅一条关键词范围话题 | .test-state/follow-topic/report.json、article-draft.png |
| 七源样本解析、article_load、来源设置重载、摘要按钮显示、长文与取消回归 | 87 passed / 0 failed；无宿主错误 | .test-state/reading-sources/report.json、summary-after.png |
| 组装单元检查 | 5 passed | python -m unittest discover -s tests/unit -p test_assembly.py |

爱范儿首篇样本正文 43 段，NASA 首篇 25 段；全部七源首篇通过完整阅读路径。样本来自各机构公开 RSS/网页；全文与独立摘要保持区分。模型摘要和话题确认的回包为明确标注的合成测试数据，未验证用户当前真实模型配置的生成质量。本次在锁定 Rinx 的隔离原生运行入口验证，与用户账户数据复现结合；未操作真实账户的 Review 按钮，也不声称 App Hub 接纳或发布验证。

缓存重启测试会先移除隔离目录中复制的旧 probe 报告，要求由本次进程重新生成状态，避免旧报告被误当本次启动完成。测试长文从预生成文件读取，不在脚本循环内强制 GC 干扰宿主异步回调。

## 交付

Review 目录仍为 `D:/Hackathon_agenticapp/workspace/cfaw-news-agent-10.9/bundle`。重新 Review 后 Run，使用新 bundle；已有五源选择可在菜单 → 新闻来源启用爱范儿/NASA。ZIP 为 `build/cfaw-news.zip`。

bundle digest：`a13030f4a339236806d64bd00274b5e9e0213463f74d275617f72ff2e8faa411`。bundle/main.splash 从 src 和组装目录生成；ZIP 的 main.splash、manifest.json 与 bundle 逐字节一致。打包完成仅证明本地包已刷新，不代表商店验收。
