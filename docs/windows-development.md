# Windows 本地开发

宿主入口是自动生成的 `bundle/main.splash`，业务源码放在 `src/`。Python 工具负责源码组装、原生测试启动和打包，Rust 编译宿主与开发工具。无需 npm 或应用级 Python 虚拟环境。2026-10-01 已在 Windows x86_64 上使用 Python 3.12.8、Rust 1.98.0、Visual Studio 2026 Build Tools / Windows SDK 和 Visual Studio 自带的 CMake、Ninja 完成构建。

## 固定依赖与位置

开发工具放在本项目相邻的 `../demo-workspace/vendor/`，与依赖记录一致。源码、二进制、Octos 配套运行时和 Cargo cache 都保存在该目录，不依赖 Codex 工作树。不要切换已有的共享或有修改的检出。

| `../demo-workspace/vendor/` 子目录 | 官方仓库 | 提交 |
| --- | --- | --- |
| `Rinx` | `https://github.com/hagency-org/Rinx.git` | `68afcf796d303aaf646eeb832d65c450a56c92b5` |
| `OctoSense-App-Hub` | `https://github.com/OctoSense-org/OctoSense-App-Hub.git` | `a72989ff2e4d51562693d05210b68e11f3bf3fcd` |
| `makepad` | `https://github.com/OctoSense-org/makepad.git` | `975c5630e01b0f3f3ae16cafd2e0fce3c9a5f7d9` |
| `octoscript-makepad` | `https://github.com/OctoSense-org/Octoscript-Makepad.git` | `65d30a091eee284ed45afe5b8502835563fb56f7` |
| `octoscript` | `https://github.com/OctoSense-org/Octoscript.git` | `68f6a9df55692b5d8ef8873a12721e279a3f40d6` |

后三个检出是固定 App Hub 工作区的 sibling path 依赖，版本来自其 Cargo.toml 和对应 Octoscript-Makepad 工作区。Rinx 自己的 Makepad、bridge 和 Octos 由其 Cargo.lock 下载，不能把两组运行时依赖混用。新机器可将表中的仓库克隆到对应目录，再 `git checkout --detach <提交>`。

## 构建环境

先安装 Git、Python 3、Rust 和 Visual Studio 的 C++ Build Tools、Windows SDK、CMake/Ninja 组件。安装宿主工具链：

```powershell
rustup toolchain install 1.98.0 --profile minimal
```

在本项目根目录的 **Developer PowerShell for VS** 中执行：

```powershell
$taskVendor = (Resolve-Path '../demo-workspace/vendor').Path
$env:RUSTUP_TOOLCHAIN = '1.98.0'
$env:CARGO_HOME = Join-Path $taskVendor 'cargo-home'
$env:CARGO_NET_OFFLINE = 'false'
$env:CARGO_NET_GIT_FETCH_WITH_CLI = 'true'
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'core.longpaths'
$env:GIT_CONFIG_VALUE_0 = 'true'
$env:CMAKE_GENERATOR = 'Ninja'
$env:MAKEPAD_PACKAGE_DIR = '.'
```

确保该终端的 `cmake` 和 `ninja` 命令可用；若未加入 PATH，从当前 Visual Studio 安装目录的 `Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin` 与 `Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja` 加入。使用 Developer PowerShell 与 Ninja 避免固定依赖中的旧 cmake crate 无法识别 Visual Studio 2026 generator。

`MAKEPAD_PACKAGE_DIR` 在编译时生效，让宿主从可执行文件旁加载资源。`.path` 文件是资源打包输入，修改它们不能替换二进制内部的编译路径。迁移开发目录后，按下述方式重新构建并复制资源；运行不需要短盘符映射。

构建正式宿主和配套内核：

```powershell
Push-Location ../demo-workspace/vendor/Rinx
try {
    cargo build --locked --release --features agent_chat
    if ($LASTEXITCODE -ne 0) { throw 'Rinx build failed' }
    python tools/package-octos.py desktop --app-binary target/release/rinx.exe
    if ($LASTEXITCODE -ne 0) { throw 'Octos packaging failed' }
    ./target/release/octos.exe --version
} finally { Pop-Location }
powershell -ExecutionPolicy Bypass -File scripts/stage_windows_resources.ps1 -Mode Rinx
```

Octos 应报告 `2.0.3-rc.13` 和提交前缀 `a6ea850`，打包 metadata 的完整 revision 应与宿主 `packaging/octos.lock.json` 相同。该版本的官方发行包报告 `4231669`，不能仅凭相同版本号替代本宿主锁定的内核。本项目使用宿主脚本构建的配套文件，不安装个人 Octos、不复制模型配置。

构建参考宿主和打包工具：

```powershell
$env:CARGO_HOME = Join-Path $taskVendor 'hub-cargo-home'
Push-Location ../demo-workspace/vendor/OctoSense-App-Hub
try {
    cargo build --locked --release -p octosense-app-hub --bin hub -p octosense-card-host --bin card-host
    if ($LASTEXITCODE -ne 0) { throw 'App Hub tools build failed' }
} finally { Pop-Location }
powershell -ExecutionPolicy Bypass -File scripts/stage_windows_resources.ps1
```

两个构建共用 cache 时会等待 Cargo 文件锁；本机参考宿主使用 `../demo-workspace/vendor/hub-cargo-home/`，Rinx 使用 `../demo-workspace/vendor/cargo-home/`。资源脚本将构建输出的 `.path` 文件所指向的 `resources/` 按 crate 名复制到二进制旁，供已编译的 `MAKEPAD_PACKAGE_DIR=.` 布局加载。

## 启动与验证边界

从本项目根目录执行：

```powershell
python .\scripts\package.py
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_windows.ps1 -Mode Rinx
```

默认启动 `card-host`，自动获取真实新闻，可操作收藏与来源/主题/关键词追踪。它未实现 Octos 服务，来源页底部的 Test Octos 应显示真实服务不可用错误。`-Mode Rinx` 打开正式宿主，Matrix 登录、bundle 导入和模型配置见 [README](../README.md#3-导入并运行)。用户自己在宿主中输入凭据。

数据逻辑检查运行 `python scripts/test_runtime.py`，组装检查运行 `python scripts/assemble.py --check`。原生测试在独立 `.test-state/runtime-*/` 中执行实际 OctoScript 模块，不读写 `.local-state/`。公开来源复测需要允许宿主访问 manifest 声明的 HTTPS 域名。Windows 固定宿主拥有 `User-Agent`，应用不能自行覆盖；请求头中的值必须为字符串数组。

脚本默认将 Rinx 数据和缓存放在本项目 `.local-state/rinx/`；该目录已被 Git 忽略。可通过 `RINX_DATA_DIR` 指定其他绝对路径，脚本也沿用旧版 `ROBRIX_DATA_DIR` 配置。2026-10-01 迁移时保留了原宿主登录数据和缓存。直接双击 `rinx.exe` 会回到 Windows 默认应用数据目录，应通过脚本启动以使用项目中的数据。

启动脚本只使用已编译、已复制资源的工具，缺少资源时显示对应错误。Windows Git 的 CRLF 转换可能改变 bundle 摘要。启动脚本通过 `package.py` 调用固定 `hub.exe` 刷新未签名包，生成 `build/cfaw-news.zip`。仅摘要不同不表示业务代码改变；签名包不能用这个开发流程重写。

本次检查结果见 README 的 Windows 运行段落。参考宿主的交互验证、Rinx 启动、实际 Matrix/Octos 联调和 App Hub 发布验收分别报告，不能互相替代。
