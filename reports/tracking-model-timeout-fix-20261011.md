# 检查关注更新：模型等待提前超时修复

## 实际原因

只读诊断用户应用的最近指标：tracking-v2.5 新闻准备3.82秒，session连接0.359秒，总耗时93.88秒，output_bytes=0、timeout。模型最终回调尚未进入，未到格式校验或结果保存。

旧适配器在session.open之前设置90秒总计时器；首次分析与唯一一次自动格式修正共用剩余时间。Rinx真实编译依赖的Octos broker每轮180秒，Rinx服务外层185秒。应用因此先于宿主允许的时限主动中断；历史上还存在首轮19.38秒已返回7757字节、随后修正最终被90秒总期限截断的样本。

## 修复

- 仅tracking_update拆成session70秒、每轮model190秒、总470秒；保留唯一一次修正及总限时。给宿主180/185秒结束与返回回调留出余量。冷启动连接可能包含60秒RPC，避免采用过短的session限时。新闻准备45秒、保存15秒的独立边界保留。
- 阶段计时器核对任务和wait_generation；总、阶段、进度、中断计时器在终止或取消后清理。重复session成功回调不会再启动模型；迟到/重复模型回调不能发布或干扰下一任务。
- 每5秒刷新首次分析/格式修正/连接阶段与已等秒数。真正超时显示实际阶段的原因，宿主Service timed out按timeout归类。指标增加error_phase、repair_count并记录尚未回调轮次的实际等待耗时；不记录私有文本或凭据。
- 模型投影去除重复参考地址、缓存指纹和获取时钟，保留标题、摘要、原文地址、发布时间、正文与引用段落范围。最近已保存快照的隔离原生对照：请求30240 → 28683字节（减少1557字节），5篇证据事实、段落与原本地快照均保持。
- 意图理解和单篇摘要的90秒原期限不变；新闻事实、关注、用户决定与完整历史不改写。

## 验证

- scripts/test_tracking_deadlines.py：115项检查、14个原生固定案例通过；慢响应超过旧总期限仍完成，修正重新获得轮次时间，模型/连接/总期限正确终止，取消后和超时后下一任务可成功，旧/重复回调隔离，宿主超时分类与session重复回调，等待进度持续更新，所有计时器清理。native_errors=[]。
- scripts/test_tracking_evidence_flow.py：39项正文准备、引用校验、结果保存与交互检查通过；3次固定模型响应，含一次修正。无真实模型请求。
- scripts/test_intent_format.py：22项通过；原理解期限、单次修正、草稿保护及确认保存保持。
- scripts/test_tracking_publication.py：125项检查、12个保存场景通过；成功、写入失败、丢失回调、取消与恢复均结束等待，重试不再请求模型。
- 请求投影对照：.test-state/context-sizing/report.json。只读复制已有快照到隔离目录，未传给模型，用户目录未写入。
- 源码组装一致性、5项组装单元测试、git diff --check、ZIP内8文件CRC与逐文件字节核对通过。更新bundle digest为43d18709dd9d5ab829085aa7976bbf9a952f54161ff773beb45ac0ec61f26330。

相关代码：src/agent/runtime/tracking.splash、src/app/config.splash、src/app/tracking.splash、src/app/insights.splash、src/app/controller.splash。

本轮未调用真实MiniMax，修复与验证针对已确认的应用提前中断和生命周期问题；远端模型服务自身未返回时仍会明确结束并允许重试，不能把固定响应测试当作远端服务可用性证明。宿主终端事件满通道的理论风险未发现本次运行证据，不作为这次超时原因。重新生成unsigned bundle后需重新Review / Run再检查关注。
