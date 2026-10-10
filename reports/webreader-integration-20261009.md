# 应用内 WebReader 接入与 Windows 宿主限制

本文件记录首次接入时的结果。后续 WebView2 宿主修复与真实 Ars Technica 验证见 `reports/windows-webreader-fix-20261009.md`；请以后续报告为准。

## 已修改

- 新闻详情的“打开图文原文”改为应用内 `WebReader.open(source_url)`，删除 LinkLabel 的系统浏览器跳转。
- 删除用户指定的全部平台说明文案；无摘要时的引导也改为应用内阅读。
- 原文页提供文章标题、重新打开与错误反馈。进入时隐藏悬浮按钮；返回时关闭 native reader，恢复新闻详情和原阅读位置；再次返回新闻列表。
- 通过 generation 检查丢弃页面关闭或重开后尚未执行的打开回调；切换详情时关闭旧网页。
- README 改为描述 WebReader 行为，不再声称详情页显示平台说明。

## 验证结果与尚未完成的部分

430×860 隔离原生测试通过原有图文正文、图片比例与顺序、段落排版、返回及无摘要状态检查。WebReader 点击、组件 open/close、文章状态保留与返回流程也已执行，但完整原站展示测试 **失败**。

当前 Rinx-main 编译所用的 Makepad Windows 后端，在 `platform/src/os/windows/windows.rs` 的 `handle_platform_ops` 中未处理 `SpawnSystemBrowser`、`UpdateSystemBrowser`、`CloseSystemBrowser`。实测日志直接报告 `Not implemented on this platform: CxOsOp::SpawnSystemBrowser`，截图为没有网页内容的 reader。WebReader 的 `open()` 返回 true 只表示操作已排队，不能当成网页已呈现。该宿主也没有将这个缺失转换为 WebReader 的 on_error。

应用源码接入已完成；**Windows 原站网页浏览问题尚未解决**。在这个宿主中，仅替换应用组件不能补齐原生内嵌浏览器。需要宿主实现 Windows 的系统浏览器操作（例如 WebView2）并重新构建，才可验收真实网页展示。此次没有伪造成功、绕回系统浏览器或删除用户数据。
