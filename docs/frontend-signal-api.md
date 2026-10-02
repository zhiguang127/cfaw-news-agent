# 三个信号子系统的前端接口清单

给前端同学。天气、法定节假日、汇率是三个**平行子系统**，各自有契约、缓存和存储，
只共用宿主和 HTTP 层。UI 归你，这篇只讲"数据长什么样、什么时候是真的不知道"。

契约全文在 `src/contracts/{weather,holiday,fx}.md`，这篇是接线用的速查。
**没有** UI 也没有接线，`app_view.splash` 里现在只有 feed / tracking / schedule / saved 四个导航项。

---

## 先读这一条：三个子系统的时间语义都和新闻不同

新闻有发布时间。天气预报只有生效日期，节假日只有日历日期，汇率只有牌价日。
所以它们**不进 `news_record`**，也别试图把它们塞进新闻列表复用 `NewsList`。

| 子系统 | 有发布时间吗 | 拿不到数据时 |
| --- | --- | --- |
| 天气 | **没有**，只有 7 天预报 | 状态是 `not_loaded` / `loading` / `error`，不是"晴天" |
| 节假日 | 没有，年度日历 | `{known: false}`，**不是**"普通工作日" |
| 汇率 | 没有，牌价日 | `change_ratio: nil`，**不是** 0 |

渲染这三块页面时，"不知道"必须显示成"不知道"。把未知显示成默认值等于造数据。

---

## 一、天气

数据源 Open-Meteo（CC BY 4.0，非商业），30 城 7 天。
调用方给的是**日程上的城市名**（"上海"），模块自己按 `cities.json` 解析。

### 城市目录

`cities.json` 由 `assemble.py` 生成成 `weather_cities` 数组，**别手改**：

```
北京 上海 广州 深圳 成都 重庆 杭州 南京 武汉 西安
天津 苏州 郑州 长沙 青岛 沈阳 大连 哈尔滨 长春 济南
合肥 福州 厦门 南昌 昆明 贵阳 南宁 海口 三亚 兰州
```

`cid` 是 ASCII 的 `w01`…`w30`（Splash 的 map 键必须是 ASCII 标识符，中文键解析不过）。
城市名的 `lat`/`lon` 在目录里**是字符串**，不是数字——上游坐标是文本，运行时没有浮点解析。
上限 `weather_max_cities = 12`。

### 拉取

```
weather_select(name)        // 选城市并立即拉取；name 传 "全部" 或 "" 表示不筛选
weather_fetch_cities(cids, generation)
weather_track(cid, generation)
weather_load_cache()        // 启动时读缓存，先出数据再出网络
```

`weather_select` 会把城市加进追踪列表**并**触发一次拉取，所以「切换城市」这个交互
不需要你再调一次 fetch。切到"全部"只改筛选，不清空已追踪城市。

多城市是**并行**的，且**不占 `busy`**：切城市时顶部的 loading 指示器不会跟着转，
天气区域自己要显示自己的状态。

### 每城状态（渲染 loading/error 用）

```
weather_status_by_city[cid] = {state: "not_loaded" | "loading" | "fresh" | "error"
                              fetched_at: <epoch>  error: ""  count: <条数>}
```

`state` 是字符串不是枚举，`error` 是**中文句子，可直接显示**，不要自己拼错误文案。

### 预报行

`weather_rows()` 返回**扁平数组**，按城市加入顺序、再按天排。一趟多站的行程从上往下读就是对的。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `forecast_id` | string | `"<cid>:<day>"`，可直接当 key |
| `city_id` | string | `w01`…`w30` |
| `city_name` | string | 中文名，**直接显示** |
| `day` | string | `YYYY-MM-DD`，日历日，不是时间戳 |
| `code` | number | WMO 码 0–100 |
| `condition` | string | 中文文案，**已由 `weather_condition` 映射好，直接显示** |
| `temp_min_c` / `temp_max_c` | number \| **nil** | 上游缺值时是 nil，别当 0 显示 |
| `precipitation_mm` | number | 降水量，缺值归 0 |
| `fetched_at` | number | 取回时刻。**不是发布时间**，预报没有发布时间 |

`condition` 的全部取值（`weather_condition` 映射，UI 直接用，不要自己再转）：

```
晴 多云 阴 雾 毛毛雨 冻毛毛雨 小雨 中雨 大雨 冻雨
小雪 中雪 大雪 阵雨 暴雨 阵雪 雷暴 天气变化
```

最后那个 `天气变化` 是 code 落在表外时的兜底，能显示出来就说明上游出了意外，值得上报。

### 事件风险（给日程页用）

```
weather_event_risk(event) -> nil | {day: "YYYY-MM-DD" wet_cities: <n> severe: "雷暴" | nil}
```

`event` 只需要 `start`（epoch 秒）。返回 `nil` 表示"这天已知没有雨也没有恶劣天气"，
**不是**"没数据"。当天有 ≥5 mm 降水（`weather_alert_precipitation`）才算 `wet_cities`；`code >= 95` 记 `severe`。
这是**规则不是判断**——它只报告事实，"要不要改期"是 Agent 的事，UI 别替它下结论。

---

## 二、法定节假日

数据源 NateScarlet/holiday-cn（MIT），年粒度，前瞻 `holiday_lookahead_years = 2` 年。

### 三态：这是整个子系统的重点

```
holiday_on(day) -> {date: "YYYY-MM-DD" known: bool is_off_day: bool|nil name: "" year: "YYYY"}
```

| `known` | `is_off_day` | 含义 | UI 该显示 |
| --- | --- | --- | --- |
| `true` | `true` | 放假日 | 节假日名 + 休息 |
| `true` | `false` | **调休补班日，是工作日** | 节假日名 + 班 |
| `false` | `nil` | 该年份未发布 | "日历未覆盖" |

第三种状态是这一整节存在的理由。国务院通常 11 月公布次年安排，10 月运行时
`2027-01-01` 是否放假**确实未知**。渲染成"工作日"等于往日程里塞虚构的工作日，
用户会照着它安排会议。

`is_off_day: false` 的补班日同样要显式提示：它把普通工作日变成工作日，
只看"不是假期"会漏掉这一天的加班。

### 拉取与状态

```
holiday_load(years)        // 数组，例：["2026" "2027"]
holiday_days_known()       // 已加载的天数，可用于「日历是否就绪」
holiday_status             // 中文状态串，可直接显示
holiday_attribution        // "MIT, NateScarlet/holiday-cn"，必须随数据展示
```

`holiday_load` 对未发布年份**不报错**，会记进内部 missing 列表并继续。
所以「加载完成」和「覆盖到哪一年」是两件事，UI 上如果要显示"覆盖到 2026 年底"
用 `holiday_days_known()` 判断，不要自己猜。

### 事件冲突（给日程页用）

```
holiday_event_conflict(event) -> nil | {day: "YYYY-MM-DD" known: bool kind: "" | "off_day" | "makeup_workday" name: string}
```

只需要 `event.start`。三种 `kind` 对应上面表格的前两行；第三种是
`{known: false, kind: "", name: ""}`，表示**该年份未发布**。`nil` 表示"已知这天是普通工作日"。

**优先级高于新闻**：一次调休补班会把没有任何一篇报道提到的普通工作日改写成工作日。
它是确定性的，新闻不是。日程页的判断顺序应该是 节假日 → 天气 → 新闻。

---

## 三、汇率

数据源 fawazahmed0/exchange-api。按 **1 CNY 等于多少外币** 报。

### 按 1 CNY 报价，不要自己求倒数

`per_cny: 23.61` 读作"1 人民币 = 23.61 日元"。用户问的是"100 块能换多少日元"，
展示层乘 100 就行。把乘法搞反是这类界面最常见的错误来源，而且它是静默的。

### 拉取

```
fx_load(today)             // today 是 "YYYY-MM-DD"，内部取最近 fx_window_days = 3 天
fx_load_from(today, days)
```

`fx_load` 收**日**不收时间戳，模块不读运行时时钟，测试和回放可以钉住某一天。
一天一次请求覆盖全部币种，跟追踪几个币种无关。

### 单币种

```
fx_rate(currency) -> {currency: "jpy" rate_date: "YYYY-MM-DD"
                      per_cny: number|nil previous_per_cny: number|nil
                      change_ratio: number|nil fetched_at: <epoch>}
```

`currency` 是**小写三字母**，只校验不折叠大小写——运行时没有字符串小写方法，
而且悄悄改写用户输入比拒绝更糟。传 `"JP"` 或 `"JPY"` 返回 `per_cny: nil`，不返回日元的值。

| `per_cny` | `change_ratio` | 含义 |
| --- | --- | --- |
| 数字 | 数字 | 有可比日，变动已知（**可正可负**，跌也是变动） |
| 数字 | `nil` | 有汇率但只有一个观测点，**是否变动未知** |
| `nil` | `nil` | 没有这个币种的数据 |

上线第一天所有币种都是第二行。契约禁止把 `nil` 渲染成 `0%`——0 是真实可上报的观测
（汇率一整天没动），拿它当"没得比"的占位符，会在汇率陈旧时显示"汇率平稳"的假安心。

`change_ratio` 是**比率不是百分数**：`0.0075` 要显示成 `+0.75%`。

### 变动告警

```
fx_movers(currencies) -> [{currency: "jpy" known: bool change_ratio: number|nil
                          per_cny: number rate_date: "YYYY-MM-DD"}]
```

`currencies` 是**你传进来的数组**，数据层不维护追踪列表（哪个币种重要是产品决策）。
上限 `fx_max_currencies = 8`，超了直接返回空数组——不截断，因为悄悄丢掉一个币种比明确拒绝更坏。

阈值 `fx_alert_change_ratio = 0.02`（2%）。**今天真实数据的答案是空数组**：
usd/jpy/eur/krw 里最大波动是日元 +0.75%，低于阈值。

所以汇率区的默认形态是**「今日无显著变动」**，不是空状态。空状态和"没有变动"长得
不一样，文案要分开：`fx_status` 为空 + `fx_movers` 为空 = 无显著变动；
`fx_status` 非空才是错误。别把两者画成同一个空页面。

`fx_attribution` = `"fawazahmed0/exchange-api, not central bank data"`，
**必须随数据展示**。这不是央行中间价，把它当官方牌价呈现是误导。

---

## 接线时你要注意的四件事

1. **`weather_status_by_city[cid]` 用方括号读，不要用点。** 点访问读未声明字段会 trap
   （`[E] splash:… property not found in prototype chain`），方括号返回 nil。这是运行时
   规则，三个子系统的记录字段都是全量声明的，缺字段就用方括号。

2. **`known` / `change_ratio` 的 nil 要单独渲染分支。** 这是三处最容易出错的地方，
   而且错了不会报错——只会显示假信息。

3. **状态串和文案都是中文的，直接显示。** `weather_status_by_city[cid].error`、
   `holiday_status`、`fx_status` 都是成句的中文，不要自己拼错误文案，也不要试图翻英文。

4. **许可串不能省。** `holiday_attribution`、`fx_attribution`、
   `cities.json` 的 `attribution`（Open-Meteo, CC BY 4.0, **非商业**）都要出现在页面上。
   CC BY 4.0 的署名和非商用限制是硬要求。

### 页面挂载点

`app_view.splash` 的导航数组在第 43 行，`render_main()` 在 `src/app/controller.splash:131`
按 `page == "..."` 切显隐。加一页要改这两处 + 一个 `SelectPage` 分支，模式看
`select_page()`（`controller.splash:144`）里 `schedule` 那一支。

`on_render` 回调只在显式调 `render()` 时跑，所以新页面的 `on_render` 要在
`render_main()` 里加一行 `.render()`，跟 `ui.navigation.render()` 一样的道理。

### 还没做的，别替它做了

汇率**尚未**接入日程冲突判断——`holiday_event_conflict` 没有 `fx_event_conflict` 对应物。
前提是行程记录里得有目的地和币种，目前没有。所以在日程页里放一个"汇率影响建议"
是接到了不存在的数据上。
