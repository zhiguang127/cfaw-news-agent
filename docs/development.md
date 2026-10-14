# CFAW News 运行与构建

本文件说明最终作品的导入和维护入口。产品介绍与运行说明见 [README](../README.md)，实际运行需要兼容的 Rinx 宿主。

## 在本机启动

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_news_host.ps1 -Visible
```

脚本默认查找项目根目录相对路径 `../../Rinx-main/target/release/rinx-news.exe`，沿用宿主用户数据。宿主位于其他位置时，使用 `-HostRoot` 指定已准备的 Rinx 仓库根目录：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_news_host.ps1 -HostRoot 'D:\path\to\Rinx' -Visible
```

运行目录必须包含配套 `octos.exe`、`makepad_widgets/resources` 和 `rinx/resources`。Windows 原文页需要 WebView2 Runtime。完整新闻宿主同时包含正文排版、WebReader 与新闻内存回收适配。

退出旧宿主后，在新宿主中重新 **Review bundle → Run** 本项目 `bundle/`。导入页使用审核后的快照，修改源文件不会自动替换已运行的应用。

## 导入与助手配置

1. 按 Rinx 的要求完成账号登录。
2. 打开 **Mini apps → Import an app**，在 **OctoSense bundle folder** 填入本项目 `bundle/` 的绝对路径。Room 可留空。
3. 核对应用名称 `CFAW News`、ID `dev.cfaw.news`，以及存储、联网、图片、网页和 Octos 会话权限。
4. 配置宿主助手，再点击 **Review bundle → Run**。

分享 `build/cfaw-news.zip` 时，接收方先解压，再导入其中的 `bundle/` 文件夹。

团队使用的助手配置：

| 字段 | 值 |
| --- | --- |
| Provider | `minimax` |
| Model | `MiniMax-M3` |
| Base URL | `https://api.minimax.cn/v1` |
| API key | 使用自己的密钥，只在 Rinx 中填写 |

点击 **Use this device**，由 Rinx 管理本机 Octos。模型可以通过云端 API 推理；应用不另建模型客户端，也不要求填写 Octos 服务地址。

在应用 **我的 → 新闻来源 → 连接诊断 → 测试连接** 检查真实回复。当前锁定宿主重新保存助手配置时需重新填写密钥，空密钥再次保存可能覆盖已有配置；日常启动无需重复保存。

## 组装与打包应用

需要实际可执行的 Python 3，以及兼容的 Hub 工具。源码维护在 `src/`；`scripts/assemble.py` 的 `ORDER` 定义加载顺序，并编译提示词目录。不要直接修改生成的 `bundle/main.splash`。

仅核对源码与生成入口：

```powershell
python scripts/assemble.py --check
```

修改业务源码后，执行完整打包：

```powershell
python scripts/package.py --hub 'D:\path\to\hub.exe'
python scripts/assemble.py --check
& 'D:\path\to\hub.exe' check bundle --allow-unsigned
```

也可以通过环境变量 `OCTO_HUB` 指定工具。脚本验证工具的跨平台路径摘要算法，组装源码、核对网络域名、执行 `stamp` 并生成 `build/cfaw-news.zip`。不要手改 manifest 中的摘要；脚本拒绝重写已签名包。当前 ZIP 是未签名本地导入包，完整性检查不等于正式发布审核。

仅更新 README 和 `docs/images/` 不改变运行 bundle，无需重新盖章。应用 `bundle/` 内的任意文件变化均需通过打包流程更新完整性元数据。

## 准备宿主构建环境

依赖版本以 [dev-dependencies.lock.json](../dev-dependencies.lock.json) 为准。Windows 构建需要 Git、Python 3、Rust `1.98.0`、Visual Studio C++ Build Tools、Windows SDK、CMake 和 Ninja。将真正的 Python 放入 PATH，避免使用不可执行的 Windows 应用商店别名。

```powershell
rustup toolchain install 1.98.0 --profile minimal
python scripts/prepare_dev_dependencies.py
powershell -ExecutionPolicy Bypass -File scripts/build_windows_tools.ps1 -Mode All
```

默认依赖目录为 `.dev/vendor/`；工具构建脚本按锁定记录准备配套 Octos 与宿主资源。现有仓库版本或修改不符合记录时，依赖准备脚本会退出并保留现场。

完整新闻宿主还需同时应用本项目的阅读、WebReader 和内存适配。以下示例使用刚准备好的私有依赖目录：

```powershell
$taskPython = (Get-Command python).Source
$taskCargo = (Resolve-Path '.dev/vendor/cargo-home').Path
powershell -ExecutionPolicy Bypass -File scripts/build_news_refresh_host.ps1 -HostRoot '.dev/vendor/Rinx' -CargoHome $taskCargo -Python $taskPython
powershell -ExecutionPolicy Bypass -File scripts/start_news_host.ps1 -HostRoot '.dev/vendor/Rinx' -Visible
```

构建适配针对锁定 Makepad `1f3b1de…`，遇到不一致的上游内容会停止。WebReader 的 Rust 源码在 [native/windows-webreader](../native/windows-webreader/README.md)，必须编译到宿主中，单独导入脚本包无法安装原生后端。

保留的 `run_windows.ps1` 支持锁定环境的 Rinx / Preview 启动与 Windows 渲染适配；完整新闻展示使用上面的 `start_news_host.ps1`。Preview 参考宿主适合查看界面，不提供 Rinx 的 Octos 助手。

`run_linux.py --build` 保留 Linux 源码构建入口，需要图形环境及系统原生依赖；当前决赛交付与截图以 Windows 为准，Linux 入口不代表本次已完成完整跨平台验证。

## 常见问题

| 现象 | 检查方式 |
| --- | --- |
| `bundle digest does not match the manifest` | 使用兼容 Hub 重新打包，退出旧应用后重新 Review / Run。 |
| `The assistant is off` | 在 Rinx 中配置助手并选择 Use this device，然后重新打开应用。 |
| `no packaged assistant runtime` | 核对实际宿主运行目录中的配套 Octos，而非另一个宿主目录。 |
| 模型鉴权或连接失败 | 根据连接诊断核对密钥、模型 ID、Base URL 与网络。 |
| 新闻来源超时 | 在来源页核对具体状态，保留可用缓存，稍后刷新或选择其他来源。 |
| 正文受限或网站要求验证 | 在应用内原文页阅读或完成网站验证；网站 Cookie 不会自动交给 HTTP 抓取器。 |
| 关注尚无结论 | 区分检查中、未找到候选、正文待补、无相关新依据与失败，按界面原因处理。 |

关注、日程、收藏和判断记录保存在宿主应用存储中。重新 Review / Run 不需要删除用户记录。清除数据前应使用宿主能力核对并备份需要保留的内容。
