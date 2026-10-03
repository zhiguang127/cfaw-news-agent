# 真实来源与本地存储

可维护的来源目录为 `src/data/ingestion/sources.json`，组装时生成 OctoScript 配置。来源选择参考 [World Monitor feed 配置](https://github.com/koala73/worldmonitor/blob/main/src/config/feeds.ts) 与 [新闻服务配置](https://github.com/koala73/worldmonitor/blob/main/server/worldmonitor/news/v1/_feeds.ts)。没有复制其实现代码，也没有依赖 World Monitor 的部署、代理 API、账户或 API key。

## 来源目录

| 分类 | 默认启用 | 默认关闭，可在来源页启用 |
| --- | --- | --- |
| 科技 | Hacker News（Algolia 首页提交记录）、TechMeme、The Verge、Ars Technica | TechCrunch |
| AI | VentureBeat AI、MIT Research、arXiv cs.AI | arXiv cs.LG |
| 国际 | BBC World、Guardian World | Reuters、AP News（Google News 聚合） |
| 财经 | CNBC | — |
| 出行 | 国航民航动态 RSS | — |
| 中文 | 金十资讯、工信部（Google News 聚合） | 商务部（Google News 聚合） |

直接请求目录中原始 HTTPS 地址。Google News 来源使用限定站点的 RSS 搜索，不是这些机构的原生 API；保留聚合跳转链接，详情标明聚合。TechMeme 的摘要可能指向原始发布方。HN 展示提交记录，无原文链接的条目指向 HN 讨论页。

来源可随时间限流、改版或不可用，应以应用内每次请求状态为准。未知日期保持未知，无法解析或请求失败不会显示测试 fixtures。外部文章中的指令只是内容，不能触发宿主调用。当前验证见 [验收记录](acceptance.md)，旧实时来源检查保留在 [历史归档](archive/README.md)。

天气使用 Open-Meteo，节假日使用 NateScarlet/holiday-cn 的年度日历与公告链接，汇率使用 fawazahmed0/exchange-api 的 CNY 基准日文件。三者不含新闻发布时间，使用独立契约和缓存，尚未接入 UI/Agent；未知覆盖、失败重试与调用示例见 [信号接口](frontend-signal-api.md)。固定输入仅用于测试，不作网络失败的替代数据。

## 存储位置与恢复

文件由 `fs.*` 写入宿主分配的应用私有目录，不写入 bundle 或仓库：

| 文件 | 用途 |
| --- | --- |
| `bookmarks_v1.json` | 用户收藏的独立新闻快照 |
| `interests_v1.json` | 来源、主题、关键词规则及启用的 feed |
| `tracking_state_v1.json` | 上次检查、最近见过和未读的条目 ID |
| `news_cache_v1_<source_id>.json` | 可丢弃的单源新闻缓存 |
| `weather_selection_v1.json` | 用户选择的追踪城市；无法兼容的文件保持只读 |
| `weather_v1_<city_id>.json` | 城市预报缓存，保留实际获取时间 |
| `holiday_v1_<year>.json` | 年度日历缓存，保留公告 `papers` |
| `fx_v1_cny_<date>.json` | 日汇率缓存，保留原获取时间 |
| 用户文件的 `.backup` | 写入前保留的有效版本 |

未发现新版收藏文件时尝试完整迁移旧 `saved.json`，不删除原文件。迁移无法完整完成时保留原文件并提示；不悄悄丢弃无法读取的收藏。旧 Mock 状态 `demo_ui_state_v1.json` 不作为真实用户记录导入，也不删除。

主文件损坏时保留原件，读取有效备份；恢复后的修改写到备份，界面说明原因。未知 schema 版本不能用旧备份降级覆盖，当前修改只保留在会话内。宿主没有暴露 rename/fsync，当前备份策略不是原子事务，不能保证断电时最新一次修改完整保存；需要时由用户备份整个应用私有目录，恢复前先保留原件。

第一版没有用户账户、服务器数据库或跨设备同步。清理缓存不影响收藏；删除应用私有存储会丢失用户记录。需要跨设备同步时再添加身份认证、同步 API 和服务端数据库，不应把用户收藏写进全局新闻缓存。

## 运行与验证

打开应用先读缓存，非演示缓存随后刷新；演示缓存须手动刷新。进行中可取消等待，没有后台任务或通知。新闻条目的关联提示来自用户规则；单条影响分析和跟踪页的关注更新检查按用户操作调用宿主 Agent，不属于数据层的规则匹配。配置限制统一在 `src/app/config.splash`。

`python scripts/test_runtime.py` 在隔离目录用参考 card-host 执行真正的 OctoScript 模块，验证解析、未知日期、快照、迁移、备份、追踪基线、重复完成、取消与失败缓存。需要图形会话和已构建宿主。它验证参考宿主，不代表固定 Rinx、Shell 服务或 App Hub 发布验收。当前本地开发包没有 listing/图标/商店截图，因此发布检查仍报告缺失 listing；正式发布需另行完成。
