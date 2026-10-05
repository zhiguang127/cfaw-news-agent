# Windows 本地开发

业务源码在 `src/`，`scripts/assemble.py` 生成 `bundle/main.splash`。Python 负责组装、测试与打包，Rust 编译宿主和开发工具；应用包不执行 Python 或 Rust。

## 依赖与版本

2026-10-04 再次核对官方 main 后更新。开发依赖放在本项目隔离目录 `.dev/vendor/`，完整提交、配套内核和平台构建记录见 [依赖锁](../dev-dependencies.lock.json)。2026-10-05 已完成 Windows All 构建并启动 SDF Rinx，真实登录页文字与图标可见；当前产物记录在 `windows_build`，之前的 Windows 二进制与结果保留在 `previous_windows_build`。应用的拖动、真实模型及长期白屏回归仍须分别验收。旧的相邻 `../demo-workspace/vendor/` 保留。

| 目录 | 当前提交 |
| --- | --- |
| Rinx | `f18869e4674fb8ffb666b424879ab820d114e432` |
| OctoSense-App-Hub | `e014fa9c596cdbd95de5cf9fb2a6b4fc2b781d17` |
| makepad | `c155f61d0e1600d2ec474209374444a38a09a470` |
| octoscript-makepad | `2cc5ef37d7d6a3d2992673389ce74488f7bb2d87` |
| octoscript | `f67cb843dddb045a75a13b7d166994fc13acd17c` |

后三个目录是最新 App Hub 参考宿主的 sibling 依赖。Rinx 仍按其自己的 Cargo.lock 固定 Makepad `1f3b1de`、bridge `cb66de0`、OctoScript `dbd48cf`、app-peers `98666de` 和 Octos `fe08d8e`。这是两个独立运行时图，不能把参考宿主测试当作 Rinx 验收，也不能单独替换 Rinx 内核为任意最新发行包。

`octoscript-makepad/runtime.json` 要求的 L0 修订为 `5991dfa`；当前 OctoScript main 从该修订起只更新其 Makepad pin，参考图使用最新 sibling 检出。应用的原始代码署名 `application_source` 是历史来源，不是运行时加载依赖。

## 准备和构建

new.2 的应用长按移动还需要 `scripts/patch_gesture_host.py` 的原生 GestureView 补丁。构建脚本会核对固定源 hash，只改本项目 `.dev/vendor/cargo-home`，强制重建 widgets 后记录产物；启动脚本核对记录。未修补宿主仅保留普通点击。2026-10-05 已安装 VS C++ 工具，修复 Rust 1.98.0 MSVC 工具链，并成功构建 Rinx 与补丁；实际拖动产品验收见 [本次 B 交付](b-delivery.md)。

安装 Git、Python 3、Rust、Visual Studio C++ Build Tools、Windows SDK、CMake/Ninja。当前检查使用 Python 3.12.8；宿主要求 Rust 1.98.0。项目没有需要安装的 Python 第三方运行依赖。

在项目根目录执行：

```powershell
rustup toolchain install 1.98.0 --profile minimal
python scripts/prepare_dev_dependencies.py
powershell -ExecutionPolicy Bypass -File scripts/build_windows_tools.ps1
```

准备脚本创建锁中不存在的检出，并应用锁中精确记录的 App Hub Cargo.lock 补丁（三项依赖关系，无版本升级）；已有不同提交或其他修改会停止并保留。构建脚本核对五个提交、加载 Visual Studio 环境，使用私有 Cargo cache 和临时短盘符，依次构建固定 Rinx、打包配套 Octos、构建 hub/card-host 并复制资源。Windows Rinx 构建先应用下述 D3D11 本地补丁，必要时清理该依赖的编译产物，防止 Cargo 复用未修补的 Git 依赖库。日志在 `build/dependency-update/`。可用 `-Mode Rinx` 或 `-Mode Preview` 只构建对应工具。

Rinx 的 `tools/package-octos.py` 同时验证 Cargo.lock 与 packaging/octos.lock.json；配套 `octos.exe --version` 应包含 `fe08d8e`，版本号仍为 `2.0.3-rc.13`。不能仅凭相同版本号复用旧内核。本项目不安装全局 Octos，也不复制模型配置。

2026-10-05 构建排障：Git 的系统级 `core.autocrlf=true` 会改变内置应用的字节；`restore_system_bundle_bytes.py` 仅允许恢复与 HEAD 相比只有 CRLF 转换的 bundle 文件，遇到实际编辑会拒绝覆盖。另一个上游问题是摘要直接使用 Windows 反斜杠路径；`patch_windows_bundle_digest.py` 对私有 Rinx/Hub 两份锁定 contract 源码统一用斜杠排序、计算摘要，并核对原始源码 hash。构建脚本自动执行这两项修复，保留原始 Palpo 清单摘要与完整性校验，不重新盖章内置应用。应将路径摘要问题反馈给上游；更新依赖后须重新核对补丁。旧 Windows Hub 生成的含子目录包需用本项目新 Hub 重新打包后导入。

构建时 `MAKEPAD_PACKAGE_DIR=.` 使资源从可执行文件旁加载。`stage_windows_resources.ps1` 在短盘符仍存在时读取构建的 `.path` 并复制字体、主题和 Rinx 资源。构建结束取消映射，运行不需要该盘符。资源缺失时启动脚本报具体路径。

## 启动与临时白屏修复

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

Windows Rinx 模式默认将同一固定宿主 App 重新链接到 `build/windows-rinx-sdf/`，在 Startup 中将共享字体栅格化模式切换为 SDF。入口使用相同宿主服务和配套内核；第一次需要编译好的 `librinx` 和 Rust 工具链，后续复用构建缓存。可执行文件名包含构建摘要，启动脚本读取 `build-info.json` 选择它，避免改写正在运行的 Windows 程序。每次确保资源及内核副本完整。

[D3D11 本地补丁](../scripts/patches/makepad-d3d11-buffer-accounting.patch) 修正普通缓冲区复用时重复记账、GPU 完成状态未持续刷新导致旧额度滞留，以及额度不足时静默跳过可见绘制的问题。每次重绘按真实 GPU query 更新完成状态，再以有限扫描回收旧 lease；没有伪造 GPU 完成或提高生产额度。它只应用到本项目私有 Cargo cache 内固定 `1f3b1de` 的 Makepad，不切换依赖版本，不修改 App Hub 的独立参考图。构建脚本核对源文件摘要，并在编译库中验证补丁标记后记录 `cfaw-render-patch.json`；启动和 SDF 链接拒绝不匹配的库。启动日志应包含 `CFAW D3D11 buffer accounting v3`。默认字体选项也使用这份修补后的宿主库。

该补丁不是正式上游发行版。移除条件是固定宿主的上游实现通过相同缓冲区压力复现；真实驱动分配或映射失败仍由宿主记录错误，脚本堆、存储和请求额度保持原值。问题与验证范围见调查报告第 7 节。

这是本机 MSDF 白屏触发的临时保护。SDF 可能改变字形边缘；新依赖上的实际显示与长期稳定性仍须验收。移除条件是上游默认模式通过真实标题/原始 My Notes 复现和新闻连续刷新。原因和对照见 [白屏调查](../reports/FAILURE_ANALYSIS.md)。

比较默认字体模式或采集本机日志时使用（仍含 D3D11 修补）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx -RinxTextRasterizer Default -Diagnostic
```

`-Diagnostic` 将 stdout、stderr **重定向到文件**，宿主自己的控制台可以没有输出。日志与 session.json 位于 `.local-state/diagnostics/`，启动脚本打印文件位置和实时查看命令，并启用仅 loopback 的原生诊断 API。日志可能含宿主账户信息，不随 issue 或应用包分发。没有错误日志也不能排除渲染失败：本次发现的旧 D3D11 额度拒绝路径没有打印错误。

在 Rinx 的 **Mini apps → Import an app** 选本项目 `bundle/`，执行 **Review bundle → Run**。分析模型由用户在 Rinx 配置，新闻浏览不需要模型。完整导入、模型与 Linux 说明见 [开发说明](development.md)。

不传 `-Mode` 时启动 card-host，窗口 430×860。它没有 Rinx 的 Octos 服务，连接检查应报告真实服务不可用。启动脚本通过固定 hub 刷新未签名摘要和 `build/cfaw-news.zip`；签名包不能使用该流程改写。

## 数据与验证边界

Rinx 默认沿用项目 `.local-state/rinx/`，此目录不入 Git。设置 `RINX_DATA_DIR` 或旧 `ROBRIX_DATA_DIR` 可覆盖。更新依赖不迁移或清理用户记录。直接双击原始 rinx.exe 会使用宿主默认数据目录，建议通过项目脚本启动。

```powershell
python scripts/test_runtime.py
python scripts/test_runtime.py --agent-only
python scripts/test_runtime.py --suites feed --inspect-ui
python scripts/test_runtime.py --suites feed --rinx-render-probe --navigation-rounds 1000
python -m unittest discover -s tests/unit -p "test_*.py"
python scripts/assemble.py --check
python scripts/package.py
```

原生固定输入测试使用独立 `.test-state/`，不调用真实模型。最新结果、未覆盖的重启/模型业务闭环和 App Hub 发布见 [验收记录](acceptance.md)。包完整性、参考宿主行为、Rinx 行为和实际发布分别验收。

`--rinx-render-probe` 使用固定 Rinx 的真实 App/Modal 和 SDF，直接挂载合成新闻 fixture，不登录或读取账户。它在测试实例中将绘制计账额度收紧到 64 MiB，连续排队 4,000 次切页并检查 PNG 中的品牌、四页标题、额度峰值与拒绝数。GPU 完成状态的测试探针只读取计数，不代替宿主刷新。此检查不包含真实 bundle 导入审查或 Octos 服务租约。

原生宿主修补需要完整退出旧 Rinx，再通过项目脚本启动新程序；仅重跑 bundle 不会加载新的 D3D11 代码。
