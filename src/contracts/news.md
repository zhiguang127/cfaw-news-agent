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
| `source_summary` / `body_html` | 可选独立来源摘要 / 原始 RSS 或 Atom 正文 HTML；不能将正文描述当作独立摘要 |
| `body_origin` / `body_truncated` | 可选 `publisher_rss` 或 `publisher_atom` / 正文保留是否超限 |
| `publisher_byline` / `publisher_license` | 可选作者与许可文字，保留在详情页，单字段最多2000字节 |
| `timestamp_parser_revision` | 可选发布时间解析修订，当前仅为1；超能网简写时区修正后写入，旧缓存缺此标记须重新获取 |

去重保留首次收录的主记录与其他收录引用，不以重复收录推断独立证据。排序按来源时间降序，未知日期在后；相同时间保持输入顺序。

阅读主题是非持久的派生数据：`news_browse_topics(row)` 返回一个或多个 `browse_tech`、`browse_industry`、`browse_life` ID，分别显示科技、商业、生活。标题与摘要的内容匹配优先，来源回退仅用于无匹配时。`news_browse_matches` 支持新阅读主题及旧来源分类；旧关注与Agent类别仍保持原语义。`news_browse_prepare(rows, current, complete)` 逐片准备派生缓存，调用方generation失效时结束并交还控制，不发布旧筛选行。app在筛选前和准备展示后均核对generation。没有来源摘要时不使用正文或模型自动补摘要来分类。

若重复记录的抓取时间更新，则以新记录为主，同时保留两者引用。合并仅复制元数据对象和引用数组，不通过 JSON 再次复制不可变的整篇 HTML 字符串，避免扩展全文来源时耗尽32 MiB脚本堆。修改合并后的引用或标题不会污染来源缓存。

## 用户记录

- 收藏：`{schema_version: 1, items: [完整新闻快照]}`，最多 500 项。
- 追踪：`{schema_version: 1, items: [规则], enabled_source_ids: [...]}`，最多 50 条规则。规则包含 `interest_id`、`kind`（source/category/keyword）、`value`、`enabled`、`created_at`，标识为 `kind:value`。
- 检查状态：`{schema_version: 1, last_checked_at, seen_ids, unread_ids}`，保存最近 2000 个 ID。首次成功刷新只建立基线，后续从未见过且匹配当前规则的条目进入未读集合；打开详情移除未读标记。

source 匹配发布方名称，category 匹配目录分类，keyword 对标题和摘要作忽略英文大小写的字面匹配，特殊字符不会变成正则操作符。规则是筛选条件，不是 Agent 的重要性判断。滚动 ID 窗口不是永久历史；被淘汰的旧 ID 将来再次出现时可能被视为新条目。

## 接口与错误

`news_http_request(url, redirects, callback)` 回调 `{success: true, body}` 或 `{success: false, error, category}`，单次请求链总时限 15 秒，正文最多 2 MB，最多 3 次许可域名内的 HTTPS 重定向。超时或取消后忽略迟到响应，未实现物理中断原生 HTTP 工作线程。

`news_parse(body, source, retrieved_at)` 返回有效新闻数组（可为空），无法解析时为 `nil`。`feed_refresh` 最多并发 3 个来源，按代数拒绝过期完成；某来源失败保留该来源的缓存与错误。缓存单源最多 20 条，合并 feed 最多 240 条。

每个来源另有 `source_timeout_seconds`（30秒）截止，覆盖请求成功后的解析、缓存保存和完成回调。仅一次完成会减少 active、增加 completed、交付 on_update；下一轮忽略旧结果。安排下一来源早于界面更新，界面回调中断不会阻止队列继续。

全文 RSS/Atom 的联网刷新通过 `reading_feed_parse_async` 每片解析一个条目，最终一次交付；源配置可降低20条上限。取消后不交付部分旧数据。首页一次构建至多40条 UI 组件，分类、查询和切换页面回到第一页；分页不改变240条合并集合或 Agent 检索集合。

数据层负责获取与记录，`app/controller.splash` 连接用户动作与页面；数据代码不访问 widgets。`records.splash` 是用户记录的唯一写入入口，同步写入函数成功返回空字符串，否则返回可展示的错误，本次内存修改仍可使用但不宣称已保存。

`records_check_tracking(rows, interests, checked_at, current, complete)` 异步分批检查最多 240 条新闻和 2000 个历史 ID，沿用 64 条/8 ms 预算。`current()` 判断调用方任务仍然有效；失效或被后续检查替代时不提交、不回调。完整结果一次性替换检查状态，`complete(error)` 在保存后的独立回调中交付空字符串或写入错误。期间打开详情会改变记录版本，检查从最新已读状态重新开始，不能恢复已移除的未读标记。应用保持刷新状态直至这个回调完成。

Windows 宿主临时回收保护：应用合并同一事件中的列表渲染请求，下一短定时器先调用宿主提供的 `mod.gc.run()` 再更新列表。保持 manifest 的 32 MiB 上限；这是对当前宿主仅按对象数量增长触发 GC 的保护，待上游实现内存压力回收并通过连续刷新复现后移除。

开发宿主补丁 `scripts/patch_news_gc_host.py` 在固定 Makepad 的已计入堆字节达到硬上限的75%时允许维护回收；回收后仍接近上限时释放可复用字符串缓冲和多余容量。硬上限继续生效，未放宽单次脚本时间/指令限制。通过 `scripts/build_news_refresh_host.ps1` 构建并使用 `rinx-news.exe`；该本地补丁不代表未修补的通用宿主已有相同能力。

`feed_build_rows(enabled_ids, complete)` 分批去重与排序，每批最多处理 `work_batch_items` 条，同时以 `work_slice_seconds` 的时间预算让出执行，以适配宿主的 64 ms 回调限制。当前配置为最多 64 条/8 ms；单个操作仍需适配宿主预算。新的数据层构建或取消刷新使旧构建失效，回调只发布完整的新列表。app 合并同一来源选择、同一 refresh generation 内的更新：完成当前快照后展示，再重建累计新数据，避免每次来源完成都取消排序；来源选择或 generation 改变仍拒绝旧结果。

首页展示准备由 `app/feed_presentation.splash` 负责，沿用 64 条/8 ms 切片；每片最多检查 `feed_hint_batch_items`（当前 4）份已有分析。新渲染请求增加 generation，旧批次放弃提交，完整批次一次性提交筛选行与提示。首页对筛选结果做稳定分组：当前关注匹配或有有效待处理 Agent 建议的报道优先，其余报道保持原顺序。数据层的时间排序不被改写。Agent 提示只复用当前输入指纹、提示词版本和证据时效都匹配的结果，不产生模型调用。

`feed_restore_cache(enabled_ids, index, generation, complete)` 只恢复启用源；`feed_refresh_needed_ids(enabled_ids, checked_at)` 返回缺失、未来获取时间或达到 `startup_refresh_seconds`（300 秒）的来源。有效空结果也受该时限保护；手动刷新绕过时限。`feed_data_revision` 只标记已接受缓存/网络数据变化，不代表新闻内容有实质变化。刷新的最终完成在各来源的 on_update 都交付后发出，失败不触发无必要的全量排序。关键词匹配器按规则 ID 复用，规则变化时清理；它不存储用户记录。


## 正文阅读

配图保持 HTTPS 主机许可，每张下载不超过 2 MB，累计不超过 6 MB，超时 15 秒。提取器支持 data-srcset/srcset、data-src/data-original/data-lazy-src/src；宽度候选限制为 320–1600，优先接近 900 的网页阅读尺寸。封面通过文件名匹配网页实际提供的衍生图，排除明确小于 640 的缩略图；不猜测 CDN 转换地址。请求声明可解码的 JPEG/PNG/WebP/GIF 格式并可携带获许可原站 origin 的 Referer。

图片状态为 loading/ready/failed，失败保留 error；article_retry_image 只重试失败图片，仍检查文章 generation，过期完成不能写入当前详情。配图失败不清空正文，页面提供重试和应用内原文入口，不把网页验证响应当图片。resource 仅用于当前 UI，不写入存储或 Agent 证据。

`article_load(row, complete)` 是只读的网页阅读边界。仅接受 `article_hosts` 中的 HTTPS 原文地址；HTTP 请求沿用 15 秒、2 MB 和 3 次许可重定向限制。`article_state` 的单一 owner 在数据层，状态为 idle/loading/ready/unavailable/failed；新的加载或离开详情增加 generation，迟到与重复完成不发布。`article_extract` 使用宿主 HTML 解析器，只读取 article/main 或明确文章容器的 p 段落，最多 80 段、24 KB，不把整页导航/同意页面当文章。状态回调由 app 层触发页面渲染。

阅读文本不替换 summary/content_version 或收藏快照。未知发布日期保持未知。结构化阅读可能省略非段落内容；“打开图文原文”改用应用内 WebReader，关闭原文页后回到详情。识别人机验证响应时，设置 requires_verification 并自动进入原文页；网页中的验证和阅读由用户完成。WebReader 中的正文不会自动回填到抓取器或 Agent snapshot，验证失败也不会被当成已取得全文。Windows WebReader 的宿主后端见 native/windows-webreader 和 scripts/patch_webreader_host.py；阅读页不显示平台说明，保留可复制原文地址。
