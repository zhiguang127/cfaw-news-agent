# 阅读来源扩展验证（2026-10-10）

本次增加超能网、极客公园和 Popular Science 环境栏目，默认阅读来源由七个扩展为十个。已有 reading_sources_revision 2/3 用户保留自己的选择，在菜单“新闻来源”手动开启。旧聚合/榜单来源继续默认关闭。

| 来源 | 官方入口 | 内容与摘要处理 | 当前宿主抓取 |
| --- | --- | --- | --- |
| 超能网 | https://www.expreview.com/rss.php | 硬件评测与选购；description是正文，无独立摘要，使用手动Agent摘要按钮 | 20条fresh |
| 极客公园 | https://www.geekpark.net/rss | AI、消费科技与产业变化；description是正文，使用手动Agent摘要按钮 | 10条fresh |
| Popular Science · 环境与生活 | https://www.popsci.com/category/environment/feed/ | 英文环境与生活科普；直接展示description摘要，content:encoded是正文 | 8条fresh |

另外保留默认关闭的 The Conversation 科技与社会 Atom（https://theconversation.com/uk/technology/articles.atom）：公开样本summary/content、作者和许可提取通过，当前宿主连续请求超时，不能算作宿主联网通过。阅读页保留署名和许可，跟踪像素域名不在图片许可清单内。

## 扩展全文来源所需的修复

- RSS/Atom每次解析一个条目，分开原生64ms回调预算；刷新代数失效停止旧解析，最后一次交付完整结果。
- 原新闻合并通过JSON深复制正文，重复分配耗尽32MiB堆。现在复制新闻对象和引用数组，共享不可变正文字符串，修改合并记录不污染来源缓存。
- 页面每次构建至多40条新闻组件，底部上一页/下一页；查询、分类、导航回到第一页。完整数据继续供Agent检索。
- 手动摘要长正文分段在定时器片间回收临时字符作用域，避免缓存增加后耗尽脚本堆。全文末尾仍进入合成模型请求。
- 来源字段、正文/图片域名和manifest网络申报同步。新增来源不自动下载首页缩略图；正文图片沿用现有权限及大小限制。

## 实际证据

| 检查 | 结果及界限 |
| --- | --- |
| `scripts/test_reading_sources.py` | 130通过、0失败：十一份公开发布方样本字段、正文读取、Atom署名/许可、合并引用独立性、来源选择迁移、手动摘要UI；无宿主错误。模型回复为标注的合成输入，不代表真实LLM语义质量验收 |
| `scripts/test_news_pagination.py` | 原生430×860点击两次下一页、两次上一页；81条合成新闻分为40/40/1页、集合保持81条。人工核对截图第二页从#40开始；无宿主错误 |
| 十源真实联网启动 | `.test-state/live-news-hn-1791613658247345500`：任务10/10完成、busy=false、active=0；9源fresh、NASA返回HTTP429，显示148条真实新闻。三个新增默认源均成功，无脚本错误。原生D3D11记录一次纹理参数错误，未影响新闻完成，不能称为全宿主日志无错误 |
| 缓存重启 | `.test-state/live-news-hn-1791613775463135300`：从上述隔离数据及更早真实抓取的NASA缓存恢复；10源cached、158条、busy=false、无需重复请求、无宿主错误。未改缓存抓取时间，未修改用户数据 |
| 包装检查 | 5项 `test_assembly.py` 通过；ZIP所有bundle文件与磁盘逐字节一致 |

极客公园单源记录：`.test-state/live-news-geekpark-1791613490642441300`，10条fresh、无原生诊断错误。The Conversation失败保留在先前联网记录中，未用公开样本替代失败新闻。

最终未签名开发包：`build/cfaw-news.zip`；组装入口：`bundle/main.splash`；bundle BLAKE3：`f35a5faa4dcd38669c05c863dbafc51cfc404e098adc972400ba8021461308bf`。

本轮只验证以上隔离宿主、公开来源和合成交互，不代表所有文章全文/图片均可读取、真实LLM摘要质量、App Hub准入或上架已验收。
