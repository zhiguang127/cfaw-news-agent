# Windows WebReader 与人机验证阅读修复

## 已交付

应用检测到 AWS / Cloudflare 验证响应时，保留摘要和真实正文获取状态，并自动进入应用内原文页。使用者可以在原站页面完成验证后继续阅读；未抓取的正文不会成为 Agent 的全文证据。删除了旧的“在浏览器阅读”文案，未恢复平台说明。

`native/windows-webreader` 为 Rinx/Makepad 补齐 Windows WebView2 创建、布局、隐藏、销毁、历史和失败反馈。网页执行其自己的脚本，没有通往应用或模型工具的 JS 桥；链接保留在应用内，网页会话 Cookie 保存到单独的宿主目录。关闭页面会销毁 controller，丢弃过期创建回调与事件。

当前机器已生成 `D:/Hackathon_agenticapp/Rinx-main/target/release/rinx-webreader.exe`。真实用户的旧宿主进程和账户数据未被关闭或清除。用户需退出旧宿主，运行新 exe，再从更新后的 `bundle` 进行 Review / Run。仅更新 OctoScript bundle 不能给旧 Windows 宿主增加原生网页能力。

维护文件：`scripts/patch_webreader_host.py`、`scripts/build_webreader_host.ps1`、`scripts/start_webreader_host.ps1`。依赖固定为 WebView2 COM 0.39.1 / windows 0.62.2。此次开发宿主的 Rinx crate 使用 opt-level 1，Makepad 保持 release 优化；临时构建配置已还原。源代码、Cargo.lock、补丁与 exe 的 SHA256 位于 `build/webreader-host-patches/final-fingerprint.json`。

## 实测

- `native/windows-webreader` 导航权限测试通过：公共 HTTPS、无 web grant 时保留原站 origin、拒绝文件/脚本/私有目标。
- 隔离 native WebView2 测试直接加载真实 Ars Technica 文章，截图包含标题、图片和正文段落：`.test-state/webview-native-probe/captures/1.png`。
- 新 Rinx 430×860 应用测试通过：AWS/Cloudflare 响应识别、合成验证响应自动路由、真实 Ars Technica 页面成功导航与 PNG 渲染、返回详情保留文章、重新打开与返回列表；未调用系统浏览器，宿主日志无 `[E]`。
- 综合验证报告：`.test-state/webreader-1791557562199060000/report.json`。首轮真实网页等待 60 秒超时；复测约 30 秒完成，说明网页加载时延仍取决于网络和原站资源。
- 结构化图文阅读回归通过：`.test-state/reader-430x860/report.json`，覆盖正文、图片比例与顺序、排版、返回和空摘要状态。
- 新闻数据回归 69 项通过、0 项失败：`.test-state/runtime-ec28195cab75/combined-report.json`。宿主编译期间的两次执行曾触发 64 ms 时间预算，构建完成后的同一套件通过；此结果不代表任意 CPU 负载下的性能保证。
- 更新后的包摘要由已编译的 Rinx contract 校验通过；最终 bundle digest：`2d1a85c98ac3a162d9b3b9747da991bf37c20ddde4d322de3595acdaf8504fc5`。

合成响应用于确定性验证路由，真正展示的页面来自 Ars Technica。测试没有代替真人完成验证码；不能由一篇成功网页推断所有站点都可访问，也不能承诺绕过登录、订阅或网站限制。WebView2 网页中的可读正文不会自动被回填给普通 HTTP 抓取器或 Agent。
