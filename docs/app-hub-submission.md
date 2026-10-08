# CFAW News：App Hub 提交指南

依据本地 `D:\Hackathon_agenticapp\OctoSense-App-Hub` 的发布规范整理。日期：2026-10-06。

## 1. 提交方式

作品放在自己的公开 GitHub 仓库，最终代码提交并打版本标签后，在 [OctoSense App Hub Issues](https://github.com/OctoSense-org/OctoSense-App-Hub/issues) 提交审核申请。

维护者按指定 commit 检出作品，重新校验、审核并发布。不要修改官方 `catalog.json`、`index/` 或 `artifacts/`，也不要向这些目录提交发布 PR。

首次提交允许未签名（unsigned）。采用发布者签名后，后续版本需要维持相同发布者密钥。提交 Issue 不等于已经上架。

## 2. 发布包需要哪些文件

```text
bundle/
  manifest.json
  listing.json
  main.splash
  assets/
    icon.svg
  screenshots/
    01-home.png
    02-intent.png
    03-analysis.png
    04-schedule.png
```

- `manifest.json`：应用身份、版本、权限和资源限制。
- `listing.json`：商店介绍、分类、关键词、发布者、支持地址、隐私地址、图标、截图和平台。
- `main.splash`：真正运行的程序，由项目源码组装。
- 图标：本作品独立的正方形 SVG 或 PNG；PNG 不超过 1024×1024，图标文件不超过 1 MiB。
- 截图：至少 1 张、最多 8 张真实 PNG，任一边不超过 4096 像素。

只把运行内容与商店素材放进 bundle，不放开发脚本、测试输入、日志、审核报告或密钥。bundle 总大小不超过 8 MiB。

## 3. 推荐准备 4 张截图

| 文件名 | 内容 |
| --- | --- |
| `01-home.png` | 刷新后的真实新闻首页，露出搜索、分类、AI 球和导航 |
| `02-intent.png` | 真实需求的助手理解预览及确认按钮 |
| `03-analysis.png` | 真实成功的分析，包含变化、建议和来源证据 |
| `04-schedule.png` | 有效日程及允许 Agent 提议改期选项 |

可以额外增加收藏或图文阅读页。保持原始比例，不用设计稿、模拟结果或虚构新闻代替实际运行截图，避开密钥、账户及私人日程。

按你的要求，正式截图使用你后续提供的文件；本机参考截图不能自动作为最终上架素材。

## 4. 商店信息需要你确认

需要公开作品仓库 URL 和发布者/团队名称。支持地址可以使用该仓库的 Issues，隐私说明放在仓库根目录 `PRIVACY.md`，商店填写其公开 HTTPS 地址。

商店分类建议 `news`；平台只声明实际验收的平台，目前优先 Windows。隐私说明需要解释本地记录、新闻及图片请求、城市天气请求，以及关注、日程和证据会通过宿主交给用户配置的模型。

以下仅为字段示例，不能把占位值作为真实资料提交：

```json
{
  "schema": 1,
  "subtitle": "让 AI 新消息，与你的下一步有关",
  "description": "以自然语言表达关注，阅读真实新闻、核对变化分析与证据，并自主决定是否调整应用内安排。",
  "category": "news",
  "keywords": ["AI", "news", "agent", "关注", "日程"],
  "screenshots": ["screenshots/01-home.png", "screenshots/02-intent.png", "screenshots/03-analysis.png", "screenshots/04-schedule.png"],
  "icon": "assets/icon.svg",
  "platforms": ["windows"],
  "publisher": {
    "name": "实际团队名称",
    "support": "https://github.com/实际账号/实际仓库/issues",
    "privacy_policy_url": "https://github.com/实际账号/实际仓库/blob/main/PRIVACY.md"
  },
  "release_notes": "首个提交版本：新闻、关注分析、应用内日程、收藏与天气。",
  "age_rating": "12+",
  "license": "Apache-2.0"
}
```

年龄标识需由团队与维护者确认；新闻包含第三方内容，不应声称应用对每条报道完成了年龄筛选。

## 5. 打包、检查与审核材料

准备当前版本的 Hub 工具后，在作品根目录执行。`$taskHub` 需替换为实际可用的可执行文件路径。

```powershell
$taskHub = '实际路径\hub.exe'
$env:OCTO_HUB = $taskHub
python scripts/package.py
python scripts/assemble.py --check
& $taskHub check bundle --allow-unsigned
& $taskHub scan bundle --packet build/review.json
```

`package.py` 生成 `build/cfaw-news.zip` 并通过 stamp 更新摘要。任何截图、图标或代码变化后都需重新打包。不要手工填写摘要。检查必须无 refusal；首次 unsigned 的签名警告可以保留。

`hub scan --packet` 只生成审核问题包，不代表官方审核通过。回答时说明作品是否符合介绍、权限和域名为何需要、界面是否误导、源码中的助手提示词属于什么业务、是否存在不当内容。AI 能力依赖真实 Rinx/Octos 执行器，不能用参考 card-host 截图证明真实模型成功。

Windows 本地工具曾涉及路径摘要及目录分隔符兼容问题。应使用兼容的工具，并让维护者在官方环境对最终 commit 重新检查；本地通过不能代替官方发布。

## 6. 上传 GitHub、打标签

把 new.3 的内容作为作品仓库根目录，不上传整个工作区。保留源码、bundle、依赖锁、许可、文档和测试；排除 `.dev/`、`.local-state/`、`.test-state/`、`build/`、账户数据及密钥。

在作品 Git 仓库核对并暂存需要发布的文件，完成提交和推送，再打 `v1.0.0` 标签。标签必须指向通过检查的同一份最终字节。已有仓库不要重新初始化，已有发布版本不要复用。

```powershell
git status --short
git diff --cached --stat
# 确认暂存文件后提交
git commit -m 'Prepare CFAW News for App Hub review'
git tag v1.0.0
git push origin HEAD
git push origin v1.0.0
git rev-parse 'v1.0.0^{commit}'
```

注意 Git 换行处理会改变 bundle 字节；保持 `.gitattributes` 的 LF 与二进制图片规则。提交后再修改文件时，重新打包、检查并更新最终 commit。

## 7. Issue 正文

标题示例：`Submit dev.cfaw.news 1.0.0`，最终以 manifest 的实际 id 和 version 为准。

正文包括：

1. 公开仓库 URL。
2. tag 和完整 commit SHA。
3. bundle 路径：`bundle/`。
4. 发布者信息；首次未签名写明 `unsigned first submission`。
5. 完整的 `hub check` 输出。
6. 对 `hub scan` 问题的回答。
7. 目标宿主与已知限制：正文依来源而异、AI 依赖宿主服务、仅前台跟踪、日程在应用内部、变更由用户确认。

提交前确认浏览器能公开访问指定 tag、bundle 和隐私说明。维护者审核并写入签名目录后，应用才会进入商店。
