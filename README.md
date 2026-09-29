# CFAW News

使用官方 OctoSense News 的 Makepad / Splash 页面，在 Rinx 中运行。唯一入口是 `bundle/main.splash`。保留来源标签、搜索、新闻卡片、摘要阅读和本地收藏，界面沿用官方英文文案。

当前没有 Octos 分析或后台采集服务；阅读页展示 feed 摘要，不代表已读取全文。

## 运行准备

需要 Python 3、已安装且可以登录的 Rinx，以及用于生成包摘要的 `hub` 可执行文件。不需要单独启动 OctoSense，不需要配置模型或 API key。

本项目验证过的版本：

| 组件 | 提交 |
| --- | --- |
| Rinx 目标宿主 | `68afcf796d303aaf646eeb832d65c450a56c92b5` |
| OctoSense-App-Hub 打包工具 | `a72989ff2e4d51562693d05210b68e11f3bf3fcd` |

完整来源、工具校验值与宿主差异见 [dev-dependencies.lock.json](dev-dependencies.lock.json)。此前界面验证使用的本机 Rinx 有既存 UI 修改，不代表纯净官方构建已完成验收。

打包脚本默认从版本记录的 `relative_checkout` 查找 `target/release/hub`。如果工具放在其他位置，先设置真实的可执行文件路径：

```bash
export OCTO_HUB=/path/to/OctoSense-App-Hub/target/release/hub
```

这是路径示例，需要替换为本机路径。打包脚本不会下载工具、编译宿主或安装依赖。

## 打包并导入 Rinx

在仓库根目录执行：

```bash
python3 scripts/package.py
realpath bundle
```

第一条命令执行官方 `hub stamp`，更新 `bundle/manifest.json` 中的摘要，并生成 `build/cfaw-news.zip`。第二条命令输出待导入文件夹的绝对路径。

1. 打开 Rinx 并登录 Matrix。
2. 进入 **Mini apps → Import an app**，输入刚才输出的 `bundle` 路径；Room 留空。
3. 点击 **Review bundle**，核对应用名 `CFAW News` 和应用 ID `dev.cfaw.news`。
4. 核对 `net`、`images`、`storage` 权限，然后点击 **Run**。

网络域名为 `hn.algolia.com`、`www.techmeme.com`、`news.google.com`；图片通过宿主加载公开 HTTPS 缩略图，本地存储额度为 8 MiB。应用不请求 Matrix 读写或模型权限。

**Rinx 导入文件夹，不直接导入 ZIP。** 分享 ZIP 时，接收方解压后选择其中的 `bundle/`。需要将打包产物放到其他位置时：

```bash
python3 scripts/package.py --output /tmp/cfaw-news.zip
```

## 页面操作

- **Today / HN / TechMeme / Google**：切换聚合列表或单个新闻来源。
- **Search stories**：筛选当前列表；清空输入恢复列表。
- **Refresh**：重新请求新闻。应用打开期间也会每 15 分钟刷新；关闭后不会继续采集。
- 点击新闻卡片查看摘要；复制阅读页的来源 URL 到浏览器查看原文。点击 **‹ News** 返回列表。
- 点击 **Save** 收藏，在 **Saved** 标签查看；再次点击阅读页的 **Saved** 按钮取消收藏。
- 使用 Rinx 的 **Back** 退出。再次导入同一应用 ID 时，同一宿主账号下的收藏仍使用原有应用存储。

缓存与收藏由 Rinx 存储在应用沙箱中，不写入仓库；当前沿用官方页面适配版的 `dev.cfaw.news` ID，不迁移已删除旧 MVP 的关注记录。

## 修改后重新运行

直接编辑 `bundle/main.splash`，再执行 `python3 scripts/package.py`。随后在 Rinx 退出应用，重新 **Review bundle → Run**。宿主运行的是已审核的快照，修改源文件不会自动热更新已打开页面。

| 遇到的情况 | 处理方法 |
| --- | --- |
| `Hub tool not found` | 将 `OCTO_HUB` 指向已有且可执行的固定版本 `hub` 文件 |
| 导入提示摘要不符 | 重新运行打包命令，并重新 Review 当前 `bundle/` |
| 找不到应用入口 | 确认选择的文件夹直接包含 `main.splash` 和 `manifest.json` |
| 来源失败或无新闻 | 检查网络后点击 Refresh；每源请求有 18 秒超时，失败可能保留旧缓存，不能当作最新新闻 |
| `Refusing to restamp a signed bundle` | 当前脚本只处理未签名开发包，不用于修改已签名发布包 |

本包只用于本地开发导入，已移除商店 listing、图标和截图，不满足 Hub 正式上架材料要求。`hub stamp` 只生成摘要，不代表 UI 或联网验收通过；本次精简后的包已通过目标 AppPolicy 校验，尚未重新完成真实 Rinx UI 回归。

## 文件与来源

```text
bundle/
  main.splash                 页面与新闻逻辑
  manifest.json               应用身份和权限
scripts/package.py            本地开发包打包
dev-dependencies.lock.json    工具、宿主及上游版本记录
LICENSE / NOTICE              上游许可与修改归属
```

页面源自 [OctoSense apps/news](https://github.com/OctoSense-org/OctoSense/tree/d1596d739e187c689ada4b59093ca8086c23bbbe/apps/news)，保留官方 Makepad 布局，适配了 Rinx 的回调请求、超时、空结果渲染与摘要阅读。上游许可和修改归属保存在 LICENSE、NOTICE 及脚本文件头。
