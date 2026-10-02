# 法定节假日契约

执行检查在 `holiday.splash`。这是目前**最强的日程信号**，而且它不是新闻：一次
调休补班会把普通工作日变成工作日，放假日则相反，两者都会改写没有任何一篇报道
提到过的安排。

## 未知就是未知

`holiday_on(date)` 的唯一公开出口是三态：

| `known` | `is_off_day` | 含义 |
| --- | --- | --- |
| `true` | `true` | 放假日 |
| `true` | `false` | **调休补班日**（是工作日） |
| `false` | `nil` | 该年份尚未发布，日历不覆盖这一天 |

国务院通常在 11 月公布次年安排。10 月运行时，`2027-01-01` 是否放假**确实未知**，
契约禁止把它当成"普通工作日"——那等于往日程里塞进虚构的工作日。宁可回答
"不知道"，也不要给一个假的 `false`。

`holiday_event_conflict(event)` 沿用同一纪律：未覆盖的年份返回
`{known: false, kind: ""}`，而不是 `{known: true, kind: "working_day"}`。

## 日历记录

| 字段 | 说明 |
| --- | --- |
| `date` | `YYYY-MM-DD`，且必须能通过日历换算往返（见 `weather_day_stamp`） |
| `is_off_day` | 布尔；上游若不是布尔则归一为 `nil` 并**拒绝该年份**，不强行转换 |
| `name` | 节假日名，非空，≤40 字符 |
| `year` | 归一化文档的年份，必须等于首日的年份前缀 |

文档级校验（`holiday_catalog_valid`）：`schema_version` 为 1、年份为四位数字、
天数在 1–60 之间、每天合法、`papers` 为 ≤8 条 URL。

## 上游结构与归一化

上游 `NateScarlet/holiday-cn`（MIT）的 `<year>.json` 是对象：

```json
{ "year": 2026, "papers": ["https://www.gov.cn/…"], "days": [ { "name": "元旦", "date": "2026-01-01", "isOffDay": true } ] }
```

两处必须归一化，不能直接当我们的记录用：

- `year` 是 **JSON 数字**，而运行时没有整数解析，无法与请求的年份字符串比较。
  改为**用请求的年份**建目录，再由 `holiday_catalog_valid` 要求首日年份前缀
  一致——文件放错年份照样被拒。
- `days` 用驼峰 `isOffDay`，我们的字段是 `is_off_day`。`holiday_normalize_days`
  负责转换，**并且必须把归一化后的数组传下去**：直接传上游数组会让
  `holiday_ingest` 的校验因 `is_off_day` 缺失而整份拒绝（这个 bug 发生过）。

## 出处

国务院公告链接随目录一起保留在缓存文件 `holiday_v1_<year>.json` 的 `papers`
里。改写日程的数据必须能被追查来源，所以出处落在磁盘上而不是只在内存里——
全局 map 追加并不可靠（见 [splash 运行时笔记](../../docs/splash-runtime-notes.md)）。
界面展示的许可为 `holiday_attribution`。

## 与日程的关系

`holiday_event_conflict(event)` 是**规则，不是重要性判断**：把事件起始时间
换算成本地日期，查该日是放假日还是补班日，返回
`{day, known, kind, name}`，其中 `kind` 为 `off_day` / `makeup_workday` / `""`。
它不判断这一天是否重要到该改期——那是 Agent 的职责，且必须由用户确认。

## 缓存

`holiday_v1_<year>.json`，每年一份，格式与文档校验同源。缓存损坏只降级为
"未加载"并重取，绝不影响用户记录。响应结构不符时该年份记入
`holiday_years_missing`，状态行说明"未发布或获取失败"，而不是静默当作无数据。
