# 配图加载修复（2026-10-09）

## 复现与修复

真实 MIT 新闻 `https://news.mit.edu/2026/shape-sensing-sheet-digitally-tracks-movement-bends-twists-1008` 正文读取成功，但配图失败。其 og:image JPEG 为 3,641,551 字节，超过应用每图 2,000,000 字节上限。网页同时提供 width=900 的图集配图，JPEG 为 755,962 字节。

提取器优先选择网页提供的阅读尺寸封面，支持懒加载与响应式地址。srcset 按 URL/宽度标记解析，保留 CDN 查询中的逗号与紧凑分隔符。没有提升应用内存或图片下载上限，没有使用代理、模拟图片或猜测 CDN 转换地址。

配图请求增加图片 Accept、获许可原站 origin Referer 和 15 秒超时；失败保留 HTTP、超时、域名、超限或格式原因。删除旧的泛化失败文案，增加“重试配图”和“在应用内查看原图”。旧文章的图片回调继续被 generation 拒绝。

## 验证

- 新闻数据回归 73 项通过、0 失败：`.test-state/runtime-a051fb1c8fce/combined-report.json`。覆盖尺寸选择、懒加载、查询逗号、权限与 HTML 挑战响应拒绝，以及既有新闻行为。
- 原生应用 430×860 配图重试通过：`.test-state/reader-430x860-retry/report.json`。明确标记的合成 HTTP 503 首次失败，点击重试后真实 PNG 解码显示；正文顺序、排版、返回、无摘要与过期图片回调检查通过，日志无 `[E]`。
- 真实 MIT 新闻与 JPEG 配图通过原生应用下载、解码和像素检查：`.test-state/reader-430x860-live/report.json`、`reader.png`。页面正文与图片来自新闻网站；测试标题/条目由隔离测试创建，不修改用户数据、不调用模型。
- 初始真实 MIT 加载已复现失败，修复后成功。开发期间发现并替换了目标宿主 regex.exec 分组偏移/复用异常的实现；最终源码使用标记解析。一次并行测试触发宿主 64 ms 回调限制，随后独立回归通过。

打包、源码组装一致性与实际 Rinx contract 摘要校验通过。最终 digest：`ba96d8dbcc1feeb62418e513d3bd00c9926b38083a7e8a93bc23bc9eadf74f2b`；交付 `build/cfaw-news.zip`。

## 使用与边界

重新 Review / Run 更新后的 bundle；本次修复仅修改应用源码，无需重新编译宿主。应用内原文仍需此前提供的 rinx-webreader.exe。网站拒绝访问、需登录/验证、未提供阅读尺寸或仍超限的图片可能失败，此时可重试或进入应用内原文页。没有证明所有新闻图片可获取，也没有自动绕过验证。运行与测试没有关闭原用户宿主或清除账户、关注、收藏、日程数据。
