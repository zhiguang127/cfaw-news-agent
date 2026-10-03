# 城市预报契约

执行检查在 `weather.splash`。时间戳为 UTC Unix 秒。

## 为什么预报不是新闻记录

`news.md` 的 `news_record` 要求 `published_at`（可未知）、`timestamp_kind` 和
`evidence_kind`：它描述的是"某家媒体在某时刻发布了某篇报道"。预报不具备这些性质——
它没有发布时间，只有**生效日期**。把它塞进 `sources.json` 会让
`timestamp_kind` 变成谎言，或者引入一个"预报的发布时间戳"这种没人能说清的东西。

因此预报是独立的记录类型，走独立的源目录（`cities.json`）、独立的契约和独立的缓存。
两者的共同点只有宿主和权限，不共用记录形状。

## 预报记录

| 字段 | 说明 |
| --- | --- |
| `forecast_id` | `<city_id>:<day>`，例如 `w01:2026-10-02`；与 `city_id`、`day` 必须一致 |
| `city_id` / `city_name` | `cities.json` 中的城市 ID 与显示名 |
| `day` | 预报生效日 `YYYY-MM-DD`；完整日历往返校验，`2026-13-45`、`2026-02-31` 均拒绝 |
| `condition` | 由 WMO `code` 映射出的中文描述 |
| `code` | WMO 天气现象码，0–100 的整数；缺失或 null 拒绝响应，不补成晴天 |
| `temp_min_c` / `temp_max_c` | 当日最低/最高气温，可为 `null` |
| `precipitation_mm` | 当日累计降水（mm），非负；缺失或 null 拒绝响应，不补成 0 |
| `fetched_at` | 成功获取时间。**不是发布时间**，界面和 Agent 都不得称其为"发布于" |

## 城市目录

`src/data/ingestion/cities.json` 是唯一来源，`scripts/assemble.py` 生成
`weather_cities` 等常量。读取目录时校验：

- `cid` 唯一，且是 ASCII 标识符（`w01`，不是 `w北京`；原因见
  [splash 运行时笔记](../../docs/splash-runtime-notes.md)）
- 坐标可为 JSON 数值或数值文本，且在 ±90 / ±180 内；目录及执行检查都校验范围
- `endpoint` 必须是 https，域名进入 `weather_hosts`，并需在
  `bundle/manifest.json` 的 `network.hosts` 中声明

`weather_request_allowed` 与 `news_request_allowed` 形状一致但各自校验自己的
域名表；`news_request_allowed` 已放行两个表，因此 HTTP 层只有一份实现。

## 按需拉取

`tracked` 是需要预报的城市，默认从空开始。`weather_select(name)`、
`weather_track(cid, generation)` 都通过同一入口校验城市、去重和
`weather_max_cities`（默认 12）上限；拒绝时返回 false，保留原选择。
首次选择才追加城市；再次选择也会检查缓存是否需要重取。

`weather_cache_ttl_seconds = 21600`（6 小时）是证据的有效期，
`fetched_at` 在未来、为 0 或达到 TTL 时均不能作为当前判断依据。
`weather_fetch_cities(cids, generation)` 在缓存有效时跳过请求，过期或获取失败时重试。
`weather_refresh()` 明确刷新所有已追踪城市，即使缓存仍有效；它先使旧请求失效。
`weather_cancel()` 停止接收本批结果、清零待处理数，保留已有缓存；
旧 generation 的完成及重复完成不会覆盖新数据。

对应 `weather_select_at(name, checked_at)`、
`weather_track_at(cid, generation, checked_at)`、
`weather_fetch_cities_at(cids, generation, checked_at)` 使用显式 UTC 秒，
供固定输入测试和回放检查。普通包装使用 `time_now()`。

天气请求**不参与** `busy`，也不进入新闻的串行 `load_next`：一个慢城市不应拖住
信息流，30 个城市也不应变成 30 次串行往返。`weather_pending` 供状态行显示。

## 存储

- 缓存：`weather_v1_<city_id>.json`，`{schema_version, city_id, fetched_at, items}`，
  单源上限 `weather_days`，日期不能重复，行与文档的 `fetched_at` 必须一致。
  缓存损坏只降级为 `not_loaded`；过期缓存仍可供浏览，但不能支撑当前风险判断。
- 用户记录：`weather_selection_v1.json`，`{schema_version: 1, tracked: [...]}`。
  沿用 `records.splash` 的约定：单一写入口、返回警告字符串而不是抛错、
  写入口返回 true/false，失败时内存值仍可用但**不宣称已保存**。
  存储的 `cid` 必须在目录内、唯一且不超限，否则整份文件不被采纳。
  读取失败、未知 schema 或无效 ID 都将文件设为只读，原文件不会被默认值覆盖。
  写入前再次核对当前文件和内存文档，支持的上一份记录先保存到 `.backup`。
  启动恢复选择和缓存之后才请求过期或缺失的城市，避免缓存读入覆盖 loading 状态。

## 与日程的关系

`weather_event_risk_at(event, checked_at)` 是一条**规则**，不是重要性判断。
`event.start` 和 `checked_at` 是 UTC 秒；普通包装 `weather_event_risk(event)`
使用当前时间。有效事件返回：

```text
{day, known, checked_cities, missing_cities, wet_cities, severe}
```

- `known: true`：每个已追踪城市都有该日且未过期的预报。
- `known: false`：没有追踪城市，或某城缺该日/过期/缺测；不能展示成天气安全。
- `checked_cities` / `missing_cities`：当前证据覆盖的城市数与缺失数。
- `wet_cities`：已观测降水 ≥ `weather_alert_precipitation`（默认 5mm）的城市数。
- `severe`：已观测天气码 ≥ 95 的描述，否则 nil。部分覆盖也保留已观测风险。

只有全部覆盖且 `wet_cities == 0 && severe == nil` 才是“本规则未发现风险”；
低于 5mm 的实际降水仍属该情况，不把未知当晴天。非法事件返回 nil。
风险判断遍历全部已追踪城市，不受浏览页面的城市筛选影响；
它不建立日程与城市的具体关联，也不决定是否改期，最终判断仍需 Agent 与用户确认。

本地日期由 `weather_day_stamp()` 从 UTC 时间戳换算，偏移固定为
`weather_utc_offset_seconds`（默认 +08:00）而非取运行时时钟，因此换算是确定的、
可单测的。测试覆盖闰日与世纪闰年边界。

预报缓存是 cache，不是用户记录：清除缓存不触碰用户选择。
