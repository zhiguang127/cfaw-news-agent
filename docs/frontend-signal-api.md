# 天气、节假日与汇率接口

这三个数据模块已进入组装入口，但尚未接入页面、应用启动流程或 Agent 上下文。它们不会自动抓取、修改日程或增加导航按钮。当前能力和验证统一见 [验收记录](acceptance.md)；本文件只说明调用与状态语义。

完整契约：[天气](../src/contracts/weather.md)、[节假日](../src/contracts/holiday.md)、[汇率](../src/contracts/fx.md)。这些记录保留生效日和获取时间，不属于 `news_record`；不得把获取时间显示成新闻发布时间。

## 时间与调用边界

天气、节假日的事件查询接收 `{start: <UTC Unix 秒>}`，日历换算使用固定 +08:00。应用日程的 `start` 是 RFC3339 字符串，接线时必须先通过 `schedule_instant()` 等已有转换得到秒值，不能直接传入日程记录。汇率加载接收 `YYYY-MM-DD`。

数据规则只报告覆盖与变化，不决定重要性、不授权执行。由 `app/` 组织关联上下文，Agent 提议，用户确认后才改变日程。当前天气查询遍历全部追踪城市，尚不表示某个日程与城市已经建立关联。

## 天气

目录 `src/data/ingestion/cities.json` 定义 30 城与 Open-Meteo 地址；组装器生成 `weather_cities`，不要修改生成副本。城市 ID 为 `w01`…`w30`，坐标支持有界 JSON 数值或数值文本；最多追踪 12 城。

```text
weather_load()                       // 恢复选择和缓存，再请求缺失或过期城市
weather_select(name)                 // 中文城市名；追加追踪、筛选并按需获取
weather_track(cid, generation)
weather_fetch_cities(cids, generation)
weather_refresh()                    // 强制刷新已追踪城市，使旧请求失效
weather_cancel()                     // 拒绝本批后续完成，保留已有缓存
weather_selection_write()            // 显式保存追踪城市，返回 true/false
weather_rows()                       // 当前筛选下的扁平预报数组
weather_event_risk(event)
```

`weather_select("全部")` 或空字符串只改变浏览筛选，不删除追踪城市。选择/追踪超过上限返回 false，保持原选择；它们只更新内存，调用方需显式保存。缓存有效期为 6 小时；失败可重试。`*_at` 版本接收显式检查时间，适合固定输入与回放。天气有独立的 `weather_pending`，不占用新闻的 `busy`。

每城状态为 `weather_status_by_city[cid] = {state, fetched_at, error, count}`，状态包括 `not_loaded/loading/cached/fresh/error`。状态为 fresh 仍需根据获取时间检查是否过期；过期数据可浏览，不能当作当前证据。用户选择保存失败见 `weather_warning`，不得显示“已保存”。

| 预报字段 | 语义 |
| --- | --- |
| `forecast_id`、`city_id`、`city_name` | 稳定记录 ID 与城市 |
| `day` | 预报生效日 `YYYY-MM-DD` |
| `code`、`condition` | WMO 码及映射文案；缺失码拒绝响应，不补成晴天 |
| `temp_min_c/temp_max_c` | 数值或 nil，nil 不显示成 0°C |
| `precipitation_mm` | 非负数；缺失/null 拒绝响应，不补成 0 |
| `fetched_at` | UTC Unix 秒，实际获取时间 |

有效事件的风险结果始终为 `{day, known, checked_cities, missing_cities, wet_cities, severe}`；nil 表示事件输入非法。

- `known: false`：没有追踪城市、缺某日或缓存过期。部分覆盖仍保留已观测风险。
- `known: true`：全部追踪城市覆盖该日且证据有效。只有 `wet_cities == 0` 且 `severe == nil` 才能说“本规则未发现风险”。
- `wet_cities` 是降水 ≥5 mm 的城市数，`severe` 是天气码 ≥95 的描述。浏览筛选不影响此查询。

展示预报时保留 Open-Meteo 署名。数据的 CC BY 4.0 许可与免费 API 的非商业服务条件是两件事；使用条件见 [Open-Meteo 官方说明](https://open-meteo.com/en/pricing)。

## 节假日

```text
holiday_load(["2026" "2027"])
holiday_load_year(year)              // 未加载/失败的年份可再次显式请求
holiday_year_known(year)             // 查询目标年份的覆盖，不能用总条数代替
holiday_on(day)                      // 只查询放假与补班条目
holiday_event_conflict(event)
```

`holiday_on(day)` 返回 `{date, known, is_off_day, name}`，命中特殊条目时另含 `year`。放假条目为 true/true，补班为 true/false；没有特殊条目为 false/nil。这也可能是已覆盖年份中的普通日期，须结合 `holiday_year_known(year)`，不能仅凭 known 判断全年未发布。

`holiday_event_conflict(event)` 对未覆盖的目标年份返回 `{day, known: false, kind: "", name: ""}`；特殊日期返回 `off_day` 或 `makeup_workday`；nil 表示目标年份已覆盖且没有特殊条目，或输入非法。正在加载、请求失败和未发布不等于普通工作日。

`holiday_status_by_year[year]` 的 `{state, error, cache_error}` 区分 `not_loaded/loading/cached/fresh/error`；`holiday_pending` 与 `holiday_status` 用于展示进行中与原因。加载中去重；失败记录不禁止重试，其他年份成功不会抹去失败。有效年度缓存目前不主动刷新，没有后台检查。

国务院公告 URL 保留在年度缓存 `papers` 中；展示出处与 `holiday_attribution`（NateScarlet/holiday-cn，MIT）。

## 汇率

```text
fx_load(today)                       // 最近三个日历日，先恢复缓存再补缺失日期
fx_load_from(today, days)             // days 只能为 1–3 的整数
fx_rate(currency)
fx_movers(currencies)                // 调用方选择币种，最多 8 个
fx_reset()                           // 清内存并拒绝旧完成，不删除缓存
```

支持小写集合 `cny usd eur jpy krw gbp chf aud cad thb sgd hkd nzd`；不是完整 ISO 4217 目录。大写、未支持代码和加密资产返回无数据，不自动改写输入。

`fx_rate()` 返回 `{currency, rate_date, per_cny, previous_per_cny, change_ratio, fetched_at}`。方向是 **1 CNY = per_cny 单位外币**；比较使用最新日及最近的较早可用日，与响应顺序无关，同日更新不能充当比较日。

| 数据 | 展示含义 |
| --- | --- |
| `per_cny` 与 `change_ratio` 有值 | 变动已知；0.0075 显示为 +0.75% |
| 只有 `per_cny` 有值 | 有报价但没有可比日，变动未知 |
| 两者 nil | 无该币种数据，不能显示为 0 或 0% |

`fx_movers()` 返回绝对变动达到 2% 的项及没有可比日的未知项。空数组也可能来自未加载、非法币种或超过上限；不能仅用 `fx_status == ""` 加空数组宣称“无显著变化”。先检查请求完成、目标币种、牌价日期和可比值。

`fx_status_by_date[day] = {state, error, cache_error}` 使用 `not_loaded/loading/cached/fresh/error`，配合 `fx_pending` 和汇总 `fx_status`。缓存保留原 `fetched_at`；缓存损坏可重取修复，同日并发去重，重复或 reset 前的完成被拒绝。当前没有日程目的地/币种关联或汇率动作建议。

展示 `fx_attribution`，说明来源为 fawazahmed0/exchange-api，非央行中间价。日期 fixtures 是固定输入，不能称为当天实时行情。

## 接线注意

用方括号读取动态 map 键和可选字段，避免不存在字段的点访问触发运行时错误。三个请求边界 `weather_http_request/fx_http_request/holiday_http_request` 默认委托共享 HTTP 层；测试替换函数回放，不联网。

未来接入由 `src/app/` 连接模块、页面与 Agent。当前导航和精简信息流继续由 `src/frontend/app_view.splash` 与 `src/app/controller.splash` 管理；本次没有增加信号页面。
