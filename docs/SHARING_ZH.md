# 分享给别人：该发哪个包、怎么发

## 1. 先选对包：公开分享只用 open 音频版

| 包 | 能不能公开分享 | 说明 |
| --- | --- | --- |
| `Volibear-0.1.0-StS2-0.107.1-share-open.zip` | ✅ 可以 | 完整开放音频（CC0 录音 + 本项目原创音效），`PACKAGE.json` 里 `private_audio: false` |
| `Volibear-0.1.0-StS2-0.107.1-riot_en-private.zip` | ❌ 不要分发 | 含 Riot 官方角色录音，版权归 Riot，仓库未获得转授权；只适合本机自用 |

两个包的代码、卡牌、美术、UI 完全一致，只是音频来源不同。分享前用
`PACKAGE.json` 核对 `audio_profile`/`private_audio`，别把私有包发出去了。

## 1b. 私发 riot 版给好友（仅限私下，不公开上传）

- 文件：`.local/release/Volibear-0.1.0-StS2-0.107.1-riot_en-private.zip`
  （173,213,873 字节，SHA-256 `e18f57ff448853977fcb66accd94ac24b2ffa51d73c47acd745cb6217db78235`）。
- 只发给认识的好友本人，不要上传 Steam Workshop、网盘公开链接、Discord 公共频道或任何公开仓库：
  包内 Riot 官方录音的再分发权仍在 Riot，仓库只保留本机自用位置。
- 好友的安装与 open 包完全相同：解压 `mods/Volibear` 与 `mods/BaseLib` 到游戏目录，
  游戏版本 0.107.1/59260271，BaseLib 3.4.7 已随包附带；双方联机需要同版本。
- 对外的公开页面/公告请用 open 版并保留 `PACKAGE.json` 里的 `private_audio: false` 标识。

## 2. 接收方需要满足

- 《Slay the Spire 2》**0.107.1 / 构建 59260271**（版本不符会在打补丁前拒绝）。
- **BaseLib 3.4.7**：open ZIP 内已随附在 `mods/BaseLib/`；如果只发 `mods/Volibear`，
  要提醒对方另装同版本 BaseLib（Steam Workshop 订阅 `3737335127`）。
- 不需要源码、SDK、Godot 或任何测试启动参数。

## 3. 三种发布方式

### A. 直接发 ZIP（最快，适合小范围）
把 open ZIP 发过去，对方退出游戏后解压合并到游戏目录：

```
<游戏目录>/
  mods/
    Volibear/  (Volibear.dll / .pck / .json)
    BaseLib/   (BaseLib.dll / .pck / .json)
```

解压后保留 `PACKAGE.json`；包的 `INSTALL_ZH.md` 里有逐文件 SHA-256 核对方法，
以及 Windows / Linux 的 Steam 游戏目录定位步骤。多人游玩要求双方装同一版本。

### B. Steam Workshop（公开分发，自动更新）
用官方上传器 [megacrit/sts2-mod-uploader](https://github.com/megacrit/sts2-mod-uploader)
上传 `mods/Volibear` 整目录。Workshop 页面需要写清：依赖 BaseLib 3.4.7、
适用游戏 0.107.1/59260271、本 Mod 为非官方同人作品、许可见仓库 `LICENSING.md`。
上传前先确认 Steam 账号与 Workshop 条款允许你发布这类同人内容。

### C. GitHub Release / 网盘
仓库已含完整源码与许可；可在 Release 里附上 open ZIP 作为安装包。
版本更新时 bump `Volibear.json` 版本号、重新构建并重新上传。

## 4. 重新出包（改过任何代码或资产之后）

```sh
python3 -B tools/local_delivery.py --game-dir "<游戏目录>" --godot "<Godot 4.5.1 mono>" \
  --dotnet "<.NET 9 SDK>" --audio-profile open
```

产物在 `.local/release/`；公开分发请用带 `share-open` 的这一份，不要用 `-riot_en-private`。
构建/验收细节见 [LOCAL_WORKFLOW.md](LOCAL_WORKFLOW.md)。

## 5. 不要打包或分享的东西

游戏程序集与本体文件、`.local/`（工具链、日志、存档、私钥）、测试报告与产物、
Riot 官方音频源文件、以及任何本机路径/配置。open ZIP 已按这些规则打好了。

## 6. 授权与署名（发给别人时保留）

- 代码：GPL-3.0-only（`LICENSE`）。
- 本项目原创美术/音效/文档：CC-BY-SA-4.0（`LICENSE-ASSETS`），署名需注明
  fltb / sts2-volibear-mod、仓库链接、是否修改，并按相同许可分享衍生作品。
- BaseLib 3.4.7：MIT，随包附许可文本。
- 沃利贝尔角色、Slay the Spire 及相关第三方素材的权利归各自权利人；本项目为非官方项目，
  无 Riot Games / Mega Crit 背书，本仓库的 GPL/CC 声明不覆盖第三方角色衍生权。
- 本次只在 Linux + 游戏 0.107.1 实测；Mod DLL 为 .NET 程序集，理论跨平台但未在
  Windows / macOS 实机验收。
