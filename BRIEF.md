# CFAW News Agent MVP
新闻页：Apple / NVIDIA 官方 RSS，自动加载、刷新、失败保留错误、空结果、主动切换演示。
详情页：原始标题、来源、摘要、发布时间与抓取时间，原文 URL 可选择复制。
分析页：通过 Rinx octos.turn.start 请求中文的事实/来源、公司行业、条件性影响、不确定性与后续问题；可取消；配置缺失直接报错。
关注页：按来源链接去重、保存完整记录与已有分析、移除、重开恢复。没有后台监控。
权限：net 仅请求 www.apple.com / blogs.nvidia.com；storage 保存关注；octos.turn.start 与 octos.turn.interrupt 分析及取消。不申请 Matrix 权限，不存密钥。
首版无后端。使用官方模板结构和公开 API，目标 Rinx；参考 card-host 单独验收。
