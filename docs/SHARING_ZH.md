# 分享给别人：该发哪个包、怎么发

> 2026-11-28 重写。此前版本仍写游戏 0.107.1 / BaseLib 3.4.7，与当前双通道清单（两者都要求
> BaseLib 3.4.8）矛盾，按当前事实整体替换。

## 1. 目标版本与依赖（两个通道）

| 通道 | 游戏版本 | Volibear 清单 | BaseLib |
| --- | --- | --- | --- |
| 正式版（public） | **0.111.1 / cc1f9462** | `Volibear.stable.json`（min_game_version 0.111.1） | **3.4.8**（含 CompatibilityHelper 五文件） |
| 公测（public-beta） | **0.114.0 / a7b9a9c0** | `Volibear.pbe.json`（min_game_version 0.114.0） | 同上 |

游戏加载器会同时强制 `min_game_version` 与依赖 `min_version`：BaseLib 版本过低或游戏版本不符时
Volibear 会拒绝初始化，这是预期行为，不要绕过。两个通道共用同一份 BaseLib 3.4.8；
`tools/dependencies.py` 固定拉取该版本并校验 SHA-256。

## 2. 音频两个变体

- `riot-sound`：Riot 英文语音。仓库的保守默认是**不公开分发**（Riot 录音再分发权在 Riot）。
  **2026-11-28 用户明示覆盖**：本仓库所有者将 riot 变体直接发布到自己的创意工坊条目
  （“自己玩、无人订阅”），风险自担；此决定仅适用于所有者本人的创意工坊条目。
- `opensound`：开放音频（CC0 + 自制音效），公开渠道的保守选择。

## 3. 创意工坊更新（当前流程）

1. 构建对应通道的 `mods/Volibear`（DLL/PCK/JSON，用 `tools/build_pbe_release.py --channel stable|pbe`）。
2. 用官方 [sts2-mod-uploader](https://github.com/megacrit/sts2-mod-uploader)（v0.2.0，本地
   `.local/moduploader/`）更新条目：workspace 的 `content/` 放 `Volibear` 三件套，
   `workshop.json` 填 `changeNote`（更新说明会显示为 changelog），`mod_id.txt` 保存条目 ID。
3. `ModUploader.exe upload -w <workspace>`（走本机 Steam 客户端会话）。当前条目 ID
   `3840408533`（"Volibear - The Relentless Storm (沃利贝尔 · 不灭狂雷)"），已随 0.1.4
   更新于 2026-11-28；提交末尾可能报 `k_EResultTimeout`，以 `time_updated`/`file_size`
   （Steam Web API `GetPublishedFileDetails`）确认实际生效。
4. 条目分支范围用 `minBranch`/`maxBranch` 标注（public-beta 条目记得 scope 到 public-beta）。

## 4. 私发 ZIP（小范围）

用 `tools/build_pbe_release.py --channel <stable|pbe>` 出包；文件命名含通道与游戏版本。
接收方解压合并到游戏目录即可；版本不符会在启动时被拒绝并列出缺失面。
多人游玩要求双方同通道同版本。

## 5. 不打包不分享的东西

游戏程序集与本体文件、`.local/`、测试报告与产物、本机配置、存档。Riot 音频源文件只留在忽略目录，
只进 riot 私有包与所有者自己的工坊条目。
