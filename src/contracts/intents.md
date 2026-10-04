# 意图空间契约

入口为悬浮小球或原菜单。目标/新闻输入通过 `parse_intent` 整理为关注；日程输入通过 `parse_schedule_intent` 整理为日程预览。两者使用同一应用 Agent、宿主 session/turn 和关联/取消边界；任务类型是应用上下文，不是新宿主服务或参数。

## 日程理解

输入包含 original_input、supplement、previous_question、timezone、reference_now（UTC RFC3339）、reference_date（所选时区日期）和 prompt_revision。相对日期只能按这些参考值解析。默认美国东部，可选北京时间；用户明确指定另一支持时区时，预览显示最终时区。

结果 `{schema_version:1,status,question,understanding}`。status 为 ready 或 needs_clarification。ready 的 question 为空，understanding 必须包含 title、content、location、start、end、timezone；content/location 可空。needs_clarification 的 understanding 为 null，只问一个关键问题。缺日期、开始或结束/时长不能虚构安排。

start/end 为带正确本地偏移、秒为 00 的 RFC3339；支持 Asia/Shanghai 和 America/New_York，结束晚于开始。验证器复用日期/时区规则，拒绝不存在日期、错误 DST 偏移和歧义时段。结构通过不证明理解准确，因此预览需要用户确认。

## 草稿与保存

topics_v2.json 继续使用 schema_version 2。草稿新增可选 intent_kind（goal/news/schedule）、schedule_timezone、schedule_understanding、schedule_prompt_revision。没有 intent_kind 的旧草稿按 news 读取，原有 understanding 与关注字段保持原契约。schedule 的 ready 草稿需要完整 schedule_understanding；切换模式、时区或修改输入使旧理解失效。关闭保留草稿，丢弃只清理当前草稿。

确认日程后调用日程存储 owner，刷新磁盘记录、验证时间和冲突再写入；不开启改期、不修改已有日程。schedules_v1.json 的 schema 1 新增可选 origin_intent_id，旧记录缺字段仍有效。该字段由应用草稿 ID 生成，不取自模型，用于确认重试的幂等检查；同 ID 的内容不一致则拒绝重试。

日程写入后再清理草稿。清理失败会明确说明日程已保存，再次确认返回同一日程，不重复创建。写入失败或冲突保留草稿供调整；解析和模型完成回调均不授权保存。

## 动画与上下文

进入/退出为 420 ms 的圆形扩散/收回，仅动画阶段安排帧回调。新过渡使旧 generation 失效；空闲不持续刷新。关闭返回原页面并保留新闻浏览位置，记录改变后刷新原详情。动画覆盖应用视口，不替代 Rinx 的窗口管理。
