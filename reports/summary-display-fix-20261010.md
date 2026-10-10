# 摘要完成后文字不显示

已复现并修复“显示 Agent 摘要标签，但没有摘要内容”的问题。摘要已在 `reader_summary.text` 中保存；阅读页从running切换为ready时，匿名控件序号复用将取消按钮的位置用于摘要段落，宿主没有建立正确的Label控件。

`src/frontend/pages/detail.splash` 为来源摘要、Agent摘要文字、进度、取消按钮和错误提示分别设置稳定控件ID。`reader_agent_summary_text` 不再与按钮共用动态位置。

之前的测试只检查生成后内存中有摘要，漏掉了结果文字实际显示的检查。本次修改测试：点击按钮后暂停后续场景，捕获完成状态的真实widget树和PNG；要求摘要Label包含完整回复且宽高非零，随后继续原有流程检查。

验证结果：修复前新增界面检查明确失败，截图只有摘要标签；修复后66项运行时检查通过，界面检查通过，截图可见摘要文字。结果Label的逻辑位置为 `[40, 643, 350, 78]`，运行日志无脚本错误。模型回包为明确标注的合成回复，此检查验证显示流程，不代表真实LLM质量验收。

证据：`.test-state/reading-sources/summary-after.json`、`.test-state/reading-sources/summary-after.png`、`.test-state/reading-sources/report.json`。

最终应用包通过 `scripts/package.py` 重新组装和stamp。需要退出旧应用后重新Review/Run `bundle/` 或导入 `build/cfaw-news.zip`；不需要清空关注、收藏或日程。
