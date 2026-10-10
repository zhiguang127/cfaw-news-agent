# 初赛反馈修改记录（2026-10-09）

1. 阅读页在外部原文链接旁显示 Windows / Linux 宿主差异，指出 Windows 需 open_url 补丁，并提供复制原文地址的替代说明。无摘要场景也明确提示复制地址。应用内既有图文阅读保留；本次选择官方建议的界面说明方案，没有新增完整 WebReader 或修改用户安装的宿主。
2. 五份运行时提示词提取到 `src/agent/prompts/*.txt`，通过 `catalog.json` 统一登记模板及版本，组装器在调用前生成常量。提取保留原字符串和换行，版本号未变。基准打包脚本改为使用同一加载入口。源文件为维护入口，bundle/main.splash 仍为宿主所需的生成单文件。

验证：

- 组装一致性检查通过。
- Windows Rinx-main 隔离阅读页测试（430×860）通过：正文、配图、平台说明、无摘要提示和取消后的图片状态；截图位于 `.test-state/reader-430x860/`。
- Agent 确定性验证：76 项通过，0 项失败。修复了容量测试依赖 2026-10-05 过期日程的问题，改为相对当前时间的日程。报告：`.test-state/runtime-178d28808b2e/combined-report.json`。
- `scripts/package.py` 生成 `build/cfaw-news.zip`，刷新完整性摘要；`hub check bundle --allow-unsigned` 通过。使用本机现有 Hub 工具 `octosense-ws/OctoSense-App-Hub/target/release/hub.exe`，此验证不表示正式发布或当前 App Hub 接纳。

本次没有调用真实模型或打开外部原站浏览器。默认未补丁宿主的浏览器打开限制仍存在，现由界面和文档明确说明。交付包为未签名本地导入包。
