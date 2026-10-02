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
| `day` | 预报生效日 `YYYY-MM-DD`；月与日按取值范围校验，`2026-13-45` 这类会被拒绝 |
| `condition` | 由 WMO `code` 映射出的中文描述 |
| `code` | WMO 天气现象码，0–100；超出范围说明响应不是预报结构 |
| `temp_min_c` / `temp_max_c` | 当日最低/最高气温，可为 `null` |
| `precipitation_mm` | 当日累计降水（mm），非负 |
| `fetched_at` | 成功获取时间。**不是发布时间**，界面和 Agent 都不得称其为"发布于" |

## 城市目录

`src/data/ingestion/cities.json` 是唯一来源，`scripts/assemble.py` 生成
`weather_cities` 等常量。读取目录时校验：

- `cid` 唯一，且是 ASCII 标识符（`w01`，不是 `w北京`；原因见
  [splash 运行时笔记](../../docs/splash-runtime-notes.md)）
- 坐标为数值文本，且在 ±90 / ±180 内（由 `assemble.py` 在读取时校验）
- `endpoint` 必须是 https，域名进入 `weather_hosts`，并需在
  `bundle/manifest.json` 的 `network.hosts` 中声明

`weather_request_allowed` 与 `news_request_allowed` 形状一致但各自校验自己的
域名表；`news_request_allowed` 已放行两个表，因此 HTTP 层只有一份实现。

## 按需拉取

`tracked` 是当前实际请求过的城市，默认从空开始。`weather_select(name)` 首次
选中某城市时才追加并发起一次请求，因此应用不会为用户不会看的城市产生流量。
上限 `weather_max_cities`（默认 12）。

天气请求**不参与** `busy`，也不进入新闻的串行 `load_next`：一个慢城市不应拖住
信息流，30 个城市也不应变成 30 次串行往返。`weather_pending` 供状态行显示。

## 存储

- 缓存：`weather_v1_<city_id>.json`，`{schema_version, city_id, fetched_at, items}`，
  单源上限 `weather_days`。缓存损坏只降级为 `not_loaded`。
- 用户记录：`weather_selection_v1.json`，`{schema_version: 1, tracked: [...]}`。
  沿用 `records.splash` 的约定：单一写入口、返回警告字符串而不是抛错、
  写失败时内存值仍可用但**不宣称已保存**。存储的 `cid` 必须在目录内，
  否则整份文件不被采纳，原文件不覆盖。

## 与日程的关系

`weather_event_risk(event)` 是一条**规则**，不是重要性判断：给定事件的本地日期，
若当天有任一城市的预报降水 ≥ `weather_alert_precipitation`（mm）或天气码 ≥ 95，
返回 `{day, wet_cities, severe}`，否则返回 `nil`。它不判断这次天气是否重要到
该改期——那是 Agent 的职责，并且必须由用户确认。

本地日期由 `weather_day_stamp()` 从 UTC 时间戳换算，偏移固定为
`weather_utc_offset_seconds`（默认 +08:00）而非取运行时时钟，因此换算是确定的、
可单测的。测试覆盖闰日与世纪闰年边界。

预报缓存是 cache，不是用户记录：清除缓存不触碰用户选择。
