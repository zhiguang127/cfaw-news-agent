# 第一版新闻与用户记录契约

执行检查在 `news.splash`。所有时间为 UTC Unix 秒，可包含小数；未知发布时间为 `nil`，序列化为 JSON `null`。不存在的日期不能以抓取时间代替。

## 新闻记录

| 字段 | 说明 |
| --- | --- |
| `news_id` | 条目 URL 去掉 `#fragment` 的稳定标识；目前不归一化查询参数或识别同一事件 |
| `source_url` / `feed_url` | 原条目链接 / 实际请求的 feed URL |
| `title` / `summary` | 来源标题 / 宿主解析的纯文本 feed 摘要；不代表原文全文 |
| `source` / `source_id` | 发布方显示名 / 本地来源目录 ID；Google News 可能解析到实际发布方 |
| `category` / `language` | 本地来源目录分类 / feed 语言标注；分类不是模型判定 |
| `published_at` / `retrieved_at` | 来源提供的发布时间（可未知）/ 成功获取时间 |
| `timestamp_kind` | `published` 或 HN 的 `submitted`，提交时间不等于文章发布时间 |
| `evidence_kind` | `rss_summary` 或 `hn_submission` |
| `references` | 相同链接的收录来源数组，每项保留 source、source_id、source_url、feed_url |
| `bookmarked_at` | 仅收藏快照必需；旧收藏迁移时为 0，表示未知历史收藏时间 |

去重保留首次收录的主记录与其他收录引用，不以重复收录推断独立证据。排序按来源时间降序，未知日期在后；相同时间保持输入顺序。

## 用户记录

- 收藏：`{schema_version: 1, items: [完整新闻快照]}`，最多 500 项。
- 追踪：`{schema_version: 1, items: [规则], enabled_source_ids: [...]}`，最多 50 条规则。规则包含 `interest_id`、`kind`（source/category/keyword）、`value`、`enabled`、`created_at`，标识为 `kind:value`。
- 检查状态：`{schema_version: 1, last_checked_at, seen_ids, unread_ids}`，保存最近 2000 个 ID。首次成功刷新只建立基线，后续从未见过且匹配当前规则的条目进入未读集合；打开详情移除未读标记。

source 匹配发布方名称，category 匹配目录分类，keyword 对标题和摘要作忽略英文大小写的字面匹配，特殊字符不会变成正则操作符。规则是筛选条件，不是 Agent 的重要性判断。滚动 ID 窗口不是永久历史；被淘汰的旧 ID 将来再次出现时可能被视为新条目。

## 接口与错误

`news_http_request(url, redirects, callback)` 回调 `{success: true, body}` 或 `{success: false, error, category}`，单次请求链总时限 15 秒，正文最多 2 MB，最多 3 次许可域名内的 HTTPS 重定向。超时或取消后忽略迟到响应，未实现物理中断原生 HTTP 工作线程。

`news_parse(body, source, retrieved_at)` 返回有效新闻数组（可为空），无法解析时为 `nil`。`feed_refresh` 最多并发 3 个来源，按代数拒绝过期完成；某来源失败保留该来源的缓存与错误。缓存单源最多 20 条，合并 feed 最多 240 条。

数据层负责获取与记录，`app/controller.splash` 连接用户动作与页面；数据代码不访问 widgets。`records.splash` 是用户记录的唯一写入入口，写入函数成功返回空字符串，否则返回可展示的错误，本次内存修改仍可使用但不宣称已保存。

`feed_build_rows(enabled_ids, complete)` 分批去重与排序，每批最多处理配置中的 `work_batch_items` 条记录，以适配参考宿主的 64 ms 回调限制。新的构建或取消刷新使旧构建失效，回调只发布完整的新列表。关键词匹配器按规则 ID 复用，规则变化时清理；它不存储用户记录。
