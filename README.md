# CFAW News Agent

面向美股与全球科技的中文新闻研究 MVP。应用入口是 **`bundle/main.splash`**，由 Rinx 内的 Makepad 渲染；没有 React、Tauri、独立 Rust 服务或宿主专属补丁。

已在 Linux 官方参考宿主 `card-host` 中运行、联网并完成原生 UI 测试。**Rinx 登录后的导入/运行与真实模型回答尚待手动验收**；参考宿主不能提供 Octos，应用会显示实际错误，不生成替代答案。见 [验收记录](tests/acceptance.md)。

## 现在可以做什么

- 从 Apple Newsroom、NVIDIA 官方博客加载 RSS，每个来源最多 10 条，按来源分组；支持刷新、加载、空结果、失败与重试。
- 查看标题、来源、摘要、原文 URL、发布时间、来源更新时间和抓取时间。原始新闻保留原语言；URL 输入框可全选复制到浏览器。
- 点击“分析影响 / 重试”，通过公开的 `octos.turn.start` 发送所选新闻；要求输出事实/来源、公司行业、条件性影响、不确定性与后续问题。支持取消，退出由 Rinx 撤销会话。
- 保存、查看、移除最多 30 条本地关注，按原文 URL 去重，保存已有分析；关注中的分析完成后会更新保存记录。
- 主动点击“演示数据”查看两条明确标注的虚构事件。演示不会覆盖最近一次联网状态；来源首页不是演示事件的证据。

关注只是本地记录，**没有后台监控或通知**。不做交易、持仓、天气、日程或多 Agent 辩论。

## 本机直接开始

在当前仓库运行（默认复用相邻 `demo-workspace/vendor/`，不更新它）：

```bash
cd /home/juvenile/Development/Hackathon/cfaw-news-agent
python3 scripts/doctor.py
bash scripts/check-bundle.sh
bash scripts/check-target-policy.sh
python3 scripts/test-reference.py
python3 scripts/package.py
```

最后一个命令生成 `build/cfaw-news-agent-0.1.0.zip`。**Rinx 导入的是文件夹，不是 ZIP**；当前机器直接使用：

```text
/home/juvenile/Development/Hackathon/cfaw-news-agent/bundle
```

在 Rinx 中：

1. 登录 Matrix → 左侧 **Mini apps → Import an app**。也可从 **App Hub → Developer** 进入，但本应用不依赖目标仓库已有的 Hub 可见性修改。
2. 输入上面的完整 `bundle` 路径，Room 留空；应用没有 Matrix 读取或发送权限。
3. 点击 **Review bundle**，核对四项权限及两个网络域名，然后 **Run**。
4. 新闻 → 点击标题 → 复制来源链接核对 → **分析影响 / 重试** → **保存关注** → **关注清单**。
5. 用 Rinx 的 **Back** 关闭应用，再按上述路径重新 Review / Run，检查关注记录仍存在。

每次编辑包后先重新检查，再在 Rinx 重新 Review。宿主运行校验后的快照，不会直接热更新源文件。首次导入无需签名、远程仓库或 Hub 上架。

## 模型在哪里配置

凭据只填在 **Rinx 宿主自己的开发导入表单**，绝不写入本应用。

- Standalone Rinx 的 **Mini apps → Import an app**：填写 provider、Model、可选 Base URL 和 API key，点击 **Use this device**。需要该 Rinx 构建包含本地 Octos 功能与可用内核。
- 已有远程 Octos 时：在宿主表单填写 Octos server URL、profile、access token，然后 **Connect Octos**。需要构建包含远程功能。
- 被 OctoSense 托管的 Rinx：使用外层宿主的 **AI providers** 配置。
- 如果 Rinx 运行包时已判定服务不可用，配置后返回并重新 Review / Run。

`card-host` 没有 Octos 服务，配置模型密钥也不会让这个参考宿主提供服务。真实模型成功回答和实际服务中断须在 Rinx 验收；测试中“测试桩回答”只存在于 `build/ui-tests/`，不进入应用包。

## 固定版本与开发环境

完整 SHA、来源、工作区状态与实际二进制校验值见 [dev-dependencies.lock.json](dev-dependencies.lock.json)。这是本项目的版本记录，不是 Hub 自动识别的锁文件。

| 组件 | 本次采用提交 |
| --- | --- |
| 目标 Rinx-CFAW / 官方 Rinx | `68afcf796d303aaf646eeb832d65c450a56c92b5` |
| OctoScript-App-Design-Flow | `ec0fa223f29800fdf02ee54311c4e309b9ca913d` |
| App Hub（参考工具） | `a72989ff2e4d51562693d05210b68e11f3bf3fcd` |
| Makepad（参考宿主） | `975c5630e01b0f3f3ae16cafd2e0fce3c9a5f7d9` |
| Octoscript | `68f6a9df55692b5d8ef8873a12721e279a3f40d6` |
| Octoscript-Makepad（参考宿主） | `65d30a091eee284ed45afe5b8502835563fb56f7` |

Rinx 自己固定 App Hub `e8601b80`、Makepad `6cf03859`、Octoscript-Makepad `6881fb6c`，与参考宿主不同；不能把参考宿主测试视为 Rinx 已兼容。应用只使用核实过的共同接口，没有 `agent`、`model.complete` 或 `sys.*` 依赖。[兼容性说明](docs/development.md) 记录了核验依据。

另一台机器将上述官方仓库按固定 SHA 检出成兄弟目录后，指定环境变量：

```bash
export ECO_ROOT=/your/workspace/vendor
export RINX_REPO=/your/workspace/Rinx
# 第一次缺少工具时，从 Hub 根目录构建；不要更新共享源码或 Cargo.lock。
(cd "$ECO_ROOT/OctoSense-App-Hub" && cargo build --locked --release -p octosense-app-hub -p octosense-card-host)
python3 scripts/doctor.py
```

可通过 `OCTO_HUB`、`OCTO_CARD_HOST` 指向自定义二进制。不要自动运行依赖更新命令；版本不符时使用独立检出目录。`doctor.py` 只读核验。Linux 测试需要 Python 3.9+、Xvfb；截图另需 ffmpeg。构建工具还需要 Rust 和官方 Makepad 的系统开发依赖。

参考宿主手动运行：

```bash
bash scripts/run-reference.sh --port 8193 --detach
# 在打开的原生窗口操作；结束测试实例：
curl -s http://127.0.0.1:8193/quit
```

可加 `--hidden` 使用隐藏模式；本次 Linux 版本的 `/g` 截图会超时。自动测试脚本使用独立 Xvfb，不占用桌面。真实截图通过 `scripts/capture.py PORT output.png` 从该虚拟显示的实际窗口区域取得，没有生成或拼接。

## 目录

```text
bundle/                    Rinx 可直接导入的完整包
  main.splash              唯一业务源代码入口
  manifest.json            最小权限、资源限制与官方摘要
  listing.json             明确标注未发布的开发版资料
  assets/icon.svg          本项目矢量图标
  screenshots/             真实参考宿主截图
scripts/                   版本检查、运行、UI 驱动、截图、测试与打包
tests/                    原生 UI 回归、测试样本、目标政策验证器和验收记录
docs/                     兼容性、数据来源/隐私、扫描回答
build/                    可再生 ZIP、日志、临时测试包（忽略）
.local-state/             参考宿主测试状态（忽略）
```

## 数据与恢复

关注文件位于宿主批准的应用存储沙箱。参考宿主默认是 `.local-state/cfaw-news-agent/watch-a.json` 和 `watch-b.json`；Rinx 按 Matrix 账号与应用 ID 隔离。每次保存交替写入副本、读回校验；启动选取序号最高的有效副本。单副本损坏可恢复另一份；可能回退最近一次修改。两个副本都坏时停止写入并显示提示，不自动覆盖。

恢复前先退出应用，备份两个文件。在宿主数据目录找到此应用的沙箱，只针对这两个文件恢复备份；若决定清空，将它们移出沙箱再重新打开。移除关注并不承诺安全擦除旧副本或宿主备份。新闻列表本身不缓存，只有明确保存的关注可离线读取。

[数据来源与权限](docs/data-sources.md) 说明网络请求、模型发送和存储范围。`listing.json` 的隐私 URL 是明确标注的 `example.invalid` 保留域名占位，本地包未发布；正式上架必须由发布者提供真实支持信息和 HTTPS 隐私页面。本次不签名、不提交审核、不发布服务。

`tests/policy-check/` 是独立的只读 Rust 开发验证器，使用 Rinx 固定的 AppPolicy；不随 bundle 运行，不是后端服务。其 Cargo.lock 已固定，首次运行会构建少量校验依赖。
