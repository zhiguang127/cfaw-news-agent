# Rinx Review 摘要修复（2026-10-09）

用户 Review 目录为本项目 `bundle/`，当前进程是 `Rinx-main/target/release/rinx-reader.exe`。其计算的完整摘要为：

`b55c92514239f8d1350e97331726175c7d8ed32a0597700a8aee8ef84a0e0579`

此前清单记录 `c70cf398ac52b40b2867220b1e7a5d8de9dc9d5865ff60386cbfa2203111d3dc`，由 `octosense-ws/OctoSense-App-Hub/target/release/hub.exe` 生成。该旧工具在 Windows 使用不一致的目录路径计算方式；其自身 check 通过不代表当前 Rinx 可接纳。

## 修复

- 使用已有兼容 Hub 重新 stamp 清单并生成 ZIP，未修改应用正文、权限或宿主，没有关闭摘要校验。
- package.py 在组装与 stamp 应用前，先用两个固定文件（含一个子目录）核对可移植路径摘要。预期值来自当前 Rinx 编译的 contract 库，两份已编译库计算一致。旧 Hub 被拒绝且不会修改应用。
- 支持 `--hub`，成功选择在 build/package-tool.json 缓存；下次没有本项目默认 Hub 时复用，仍重新验证算法。

## 验证

- 当前 Rinx 编译库的 digest_dir 和 admit_digest 对修复后的清单通过；完整摘要与用户界面的 b55c925 前缀一致。
- 旧 Hub 回归：被兼容性校验拒绝，bundle 所有文件 SHA-256 前后不变。
- 缓存工具默认打包通过；ZIP 中 manifest/main.splash 与目录字节一致。
- 组装一致性检查通过。

编译诊断工具和记录位于 build/digest-diagnostic/。兼容 Hub 的 `check` 另有 Windows 路径校验问题（将本机反斜杠视为非可移植路径），本次使用当前 Rinx 的编译 contract 库验证实际摘要与 admit_digest，不把该 Hub 的完整 admission 流程记为通过。

先前 reports/life-scenarios-20261009.md 中的打包摘要已被本次修复替代；功能回归结果不变。用户需要再次点击 Review bundle，再按宿主权限审查点击 Run；没有代替用户操作实际 Review/Run 界面。
