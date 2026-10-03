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
| `false` | `nil` | 没有特殊日期条目；是否覆盖该年份另查 `holiday_year_known` |

目标年份尚未加载或发布时，应用不能据此判断某日是否放假。契约禁止把这种状态
当成"普通工作日"；应报告年份未覆盖，避免给用户虚构的工作日信息。

`holiday_event_conflict(event)` 沿用同一纪律：未覆盖的年份返回
`{known: false, kind: ""}`，而不是 `{known: true, kind: "working_day"}`。
目标年份未加载、正在加载或获取失败都属于未覆盖；加载了其他年份不改变这一点。
`holiday_on()` 查询的是日历里的特殊日期，已加载年份中没有特殊条目的普通日期也
返回 `known: false`；普通日期是否已覆盖须看 `holiday_year_known(year)`。

## 日历记录

| 字段 | 说明 |
| --- | --- |
| `date` | `YYYY-MM-DD`，且必须能通过日历换算往返（见 `weather_day_stamp`） |
| `is_off_day` | 布尔；上游若不是布尔则归一为 `nil` 并**拒绝该年份**，不强行转换 |
| `name` | 节假日名，非空，≤40 字符 |
| `year` | 归一化文档的年份，必须等于每条日期的年份前缀 |

文档级校验（`holiday_catalog_valid`）：`schema_version` 为 1、年份为四位数字、
天数在 1–60 之间、每天合法且属于目录年份、日期不重复、`papers` 为 ≤8 条 URL。
混年目录和重复日期整份拒绝，不用后到记录覆盖矛盾的放假/补班值。

## 上游结构与归一化

上游 `NateScarlet/holiday-cn`（MIT）的 `<year>.json` 是对象：

```json
{ "year": 2026, "papers": ["https://www.gov.cn/…"], "days": [ { "name": "元旦", "date": "2026-01-01", "isOffDay": true } ] }
```

两处必须归一化，不能直接当我们的记录用：

- `year` 是 **JSON 数字**，而运行时没有整数解析，无法与请求的年份字符串比较。
  改为**用请求的年份**建目录，再由 `holiday_catalog_valid` 要求所有日期年份前缀
  一致——文件放错年份照样被拒。
- `days` 用驼峰 `isOffDay`，我们的字段是 `is_off_day`。`holiday_normalize_days`
  负责转换，**并且必须把归一化后的数组传下去**：直接传上游数组会让
  `holiday_ingest` 的校验因 `is_off_day` 缺失而整份拒绝（这个 bug 发生过）。

## 出处

国务院公告链接随目录一起保留在缓存文件 `holiday_v1_<year>.json` 的 `papers`
里。改写日程的数据必须能被追查来源，所以出处保留在磁盘上，冷启动后仍可查询。
界面展示的许可为 `holiday_attribution`。

## 与日程的关系

`holiday_event_conflict(event)` 是**规则，不是重要性判断**：把事件起始时间
换算成本地日期，查该日是放假日还是补班日，返回
`{day, known, kind, name}`，其中 `kind` 为 `off_day` / `makeup_workday` / `""`。
它不判断这一天是否重要到该改期——那是 Agent 的职责，且必须由用户确认。
`nil` 仅表示**目标年份已加载**，且该日不在放假/补班目录中。不能用总条数判断
某个目标年份是否已覆盖；加载了 2026 年，不代表 2027 年普通日期已知。

## 缓存

`holiday_v1_<year>.json`，每年一份，格式与文档校验同源。缓存损坏只降级为
"未加载"并重取，绝不影响用户记录。响应结构不符时该年份记入
`holiday_years_missing`，状态行说明"未发布或获取失败"，而不是静默当作无数据。

`holiday_years_missing` 是最近获取失败的标记，不是永久重试禁令。再次显式调用
`holiday_load_year(year)` 可重试，成功后移除标记。加载中的同年份请求去重，每个
请求标识拒绝重复或被替换的完成；成功响应只解析并摄入一次。

`holiday_status_by_year[year]` 为 `{state, error, cache_error}`，`state` 是
`not_loaded / loading / cached / fresh / error`；`holiday_pending` 是进行中请求数。
`holiday_status` 汇总各年份错误，其他年份的晚到成功不能抹去已有失败原因。有效
缓存必须匹配请求年份；缓存异常在重新获取并成功保存该年份后清除。
`holiday_http_request(url, redirects, callback)` 默认调用共享 HTTP 层，固定测试可
替换函数变量回放请求结果。当前加载到有效年度缓存后不主动刷新已覆盖年份，
没有后台检查或通知能力。
