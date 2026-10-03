# Windows 本地开发

业务源码在 `src/`，`scripts/assemble.py` 生成 `bundle/main.splash`。Python 负责组装、测试与打包，Rust 编译宿主和开发工具；应用包不执行 Python 或 Rust。

## 依赖与版本

2026-10-03 核对官方 main 后更新。开发依赖放在本项目隔离目录 `.dev/vendor/`，完整提交、配套内核和实际二进制摘要见 [依赖锁](../dev-dependencies.lock.json)。旧的相邻 `../demo-workspace/vendor/` 保留，启动默认路径已切换。

| 目录 | 当前提交 |
| --- | --- |
| Rinx | `3bedeadfd5a6e42cd149b89ea0b8845ee6fe48f9` |
| OctoSense-App-Hub | `2bcb8985bc1d2c8856f2a61e65baa7ed443ae817` |
| makepad | `c155f61d0e1600d2ec474209374444a38a09a470` |
| octoscript-makepad | `2cc5ef37d7d6a3d2992673389ce74488f7bb2d87` |
| octoscript | `f67cb843dddb045a75a13b7d166994fc13acd17c` |

后三个目录是最新 App Hub 参考宿主的 sibling 依赖。Rinx 仍按其自己的 Cargo.lock 固定 Makepad `1f3b1de`、bridge `cb66de0`、OctoScript `dbd48cf`、app-peers `98666de` 和 Octos `fe08d8e`。这是两个独立运行时图，不能把参考宿主测试当作 Rinx 验收，也不能单独替换 Rinx 内核为任意最新发行包。

`octoscript-makepad/runtime.json` 要求的 L0 修订为 `5991dfa`；当前 OctoScript main 从该修订起只更新其 Makepad pin，参考图使用最新 sibling 检出。应用的原始代码署名 `application_source` 是历史来源，不是运行时加载依赖。

## 准备和构建

安装 Git、Python 3、Rust、Visual Studio C++ Build Tools、Windows SDK、CMake/Ninja。当前检查使用 Python 3.12.8；宿主要求 Rust 1.98.0。项目没有需要安装的 Python 第三方运行依赖。

在项目根目录执行：

```powershell
rustup toolchain install 1.98.0 --profile minimal
python scripts/prepare_dev_dependencies.py
powershell -ExecutionPolicy Bypass -File scripts/build_windows_tools.ps1
```

准备脚本只创建锁中不存在的检出，遇到已有不同提交或修改会停止并保留它。构建脚本核对五个提交、加载 Visual Studio 环境，使用私有 Cargo cache 和临时短盘符，依次构建固定 Rinx、打包配套 Octos、构建 hub/card-host 并复制资源。日志在 `build/dependency-update/`。可用 `-Mode Rinx` 或 `-Mode Preview` 只构建对应工具。

Rinx 的 `tools/package-octos.py` 同时验证 Cargo.lock 与 packaging/octos.lock.json；配套 `octos.exe --version` 应包含 `fe08d8e`，版本号仍为 `2.0.3-rc.13`。不能仅凭相同版本号复用旧内核。本项目不安装全局 Octos，也不复制模型配置。

构建时 `MAKEPAD_PACKAGE_DIR=.` 使资源从可执行文件旁加载。`stage_windows_resources.ps1` 在短盘符仍存在时读取构建的 `.path` 并复制字体、主题和 Rinx 资源。构建结束取消映射，运行不需要该盘符。资源缺失时启动脚本报具体路径。

## 启动与临时白屏修复

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

Windows Rinx 模式默认将同一固定宿主 App 重新链接为 `build/windows-rinx-sdf/rinx-sdf.exe`，在 Startup 中将共享字体栅格化模式切换为 SDF。它使用相同宿主服务和配套内核，不修改上游源码；第一次需要编译好的 `librinx` 和 Rust 工具链，后续复用构建缓存。每次确保资源及内核副本完整。

这是本机 MSDF 白屏触发的临时保护。SDF 可能改变字形边缘；新依赖上的实际显示与长期稳定性仍须验收。移除条件是上游默认模式通过真实标题/原始 My Notes 复现和新闻连续刷新。原因和对照见 [白屏调查](../reports/FAILURE_ANALYSIS.md)。

比较原始宿主或采集本机日志时使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx -RinxTextRasterizer Default -Diagnostic
```

`-Diagnostic` 记录 stdout、stderr 和 session.json 到 `.local-state/diagnostics/`，启用仅 loopback 的原生诊断 API。日志可能含宿主账户信息，不随 issue 或应用包分发。

在 Rinx 的 **Mini apps → Import an app** 选本项目 `bundle/`，执行 **Review bundle → Run**。分析模型由用户在 Rinx 配置，新闻浏览不需要模型。完整导入、模型与 Linux 说明见 [开发说明](development.md)。

不传 `-Mode` 时启动 card-host，窗口 430×860。它没有 Rinx 的 Octos 服务，连接检查应报告真实服务不可用。启动脚本通过固定 hub 刷新未签名摘要和 `build/cfaw-news.zip`；签名包不能使用该流程改写。

## 数据与验证边界

Rinx 默认沿用项目 `.local-state/rinx/`，此目录不入 Git。设置 `RINX_DATA_DIR` 或旧 `ROBRIX_DATA_DIR` 可覆盖。更新依赖不迁移或清理用户记录。直接双击原始 rinx.exe 会使用宿主默认数据目录，建议通过项目脚本启动。

```powershell
python scripts/test_runtime.py
python scripts/test_runtime.py --agent-only
python scripts/test_runtime.py --suites feed --inspect-ui
python -m unittest discover -s tests/unit -p "test_*.py"
python scripts/assemble.py --check
python scripts/package.py
```

原生固定输入测试使用独立 `.test-state/`，不调用真实模型。最新结果、未覆盖的重启/模型业务闭环和 App Hub 发布见 [验收记录](acceptance.md)。包完整性、参考宿主行为、Rinx 行为和实际发布分别验收。
