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

## 启动与验证边界

从本项目根目录执行：

```powershell
python .\scripts\package.py
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

默认启动 `card-host`，自动获取真实新闻，可操作收藏与来源/主题/关键词追踪。它未实现 Octos 服务，“更多 → 连接诊断 → 测试连接”应显示真实服务不可用错误。`-Mode Rinx` 打开正式宿主，Matrix 登录、bundle 导入和模型配置见 [开发说明](development.md#3-导入并运行)。用户自己在宿主中输入凭据。

数据逻辑检查运行 `python scripts/test_runtime.py`，组装检查运行 `python scripts/assemble.py --check`。原生测试在独立 `.test-state/runtime-*/` 中执行实际 OctoScript 模块，不读写 `.local-state/`。公开来源复测需要允许宿主访问 manifest 声明的 HTTPS 域名。Windows 固定宿主拥有 `User-Agent`，应用不能自行覆盖；请求头中的值必须为字符串数组。

脚本默认将 Rinx 数据和缓存放在本项目 `.local-state/rinx/`；该目录已被 Git 忽略。可通过 `RINX_DATA_DIR` 指定其他绝对路径，脚本也沿用旧版 `ROBRIX_DATA_DIR` 配置。2026-10-01 迁移时保留了原宿主登录数据和缓存。直接双击 `rinx.exe` 会回到 Windows 默认应用数据目录，应通过脚本启动以使用项目中的数据。

启动脚本只使用已编译、已复制资源的工具，缺少资源时显示对应错误。Windows Git 的 CRLF 转换可能改变 bundle 摘要。启动脚本通过 `package.py` 调用固定 `hub.exe` 刷新未签名包，生成 `build/cfaw-news.zip`。仅摘要不同不表示业务代码改变；签名包不能用这个开发流程重写。

当前检查结果见 [验收记录](acceptance.md)。参考宿主的交互验证、Rinx 启动、实际 Matrix/Octos 联调和 App Hub 发布验收分别报告，不能互相替代。
