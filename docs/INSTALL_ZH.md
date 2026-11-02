# 沃利贝尔 Mod：安装、多人游玩与卸载

版本 **0.1.0**。包含沃利贝尔角色、89 张卡牌及其升级牌面、两件专属遗物，以及迎战、领域、
雷伤、兽化和配套图像、动画与音频。角色接入游戏的正常单人和原生多人流程。

本说明用于含 `PACKAGE.json` 和 `mods/` 的完整安装 ZIP。若拿到的是源码覆盖包，先按
[LOCAL_WORKFLOW.md](https://github.com/fltb/sts2-volibear-mod/blob/codex/mode7-completion/docs/LOCAL_WORKFLOW.md) 执行 `tools/local_delivery.py --verify-release`，
从当前源码构建并验收完整包。完整发布验收覆盖卡牌、领域与终局剧情、表现、存读档和双客户端。
本轮更新包含向下挥爪的打击卡图、重绘状态图标、蓝色灵体与立体雷电领域、领域禁用反馈、
清晰区分空满的能量外观、纯色中心的卡牌费用底图及整理后的全部文案。
最终剧情中，沃利贝尔进入领域后进入胜利结算。

仅面向《Slay the Spire 2》**0.107.1 / 构建 59260271**。固定依赖为 **BaseLib 3.4.7**，
完整包随附该依赖；不要混用其他 BaseLib 版本或另一套注册框架。游戏版本不符时先停止安装，
运行时也会在安装 Volibear 补丁前检查目标版本。

安装后正常启动游戏，在单人新局或原生多人大厅中选择沃利贝尔。玩家不需要源码、SDK、
Godot 编辑器或测试启动参数。

## 包内内容

- `mods/Volibear/`：`Volibear.dll`、完整 `Volibear.pck`、`Volibear.json`。
- `mods/BaseLib/`：固定官方发行包中的 `BaseLib.dll`、`BaseLib.pck`、`BaseLib.json`。
- `licenses/BaseLib-LICENSE.txt`：BaseLib 原始 MIT 许可。
- `LICENSE`、`LICENSE-ASSETS`、`LICENSING.md`：模组代码、原创资产及第三方例外的许可。
- `licenses/audio/`：默认开放音频的作者、来源 URL、录音摘要及 Kenney 原始许可。
- `PACKAGE.json`：构建标识、锁定版本、官方依赖来源及每个包内文件的 SHA-256，不含本机安装目录。

模组源码与构建说明：[fltb/sts2-volibear-mod](https://github.com/fltb/sts2-volibear-mod)。
官方依赖来源：[BaseLib 3.4.7](https://github.com/Alchyr/BaseLib-StS2/releases/tag/v3.4.7)。

本包不含游戏程序集、日志、存档、开发配置或自动安装程序。不要从研发工作目录另外复制
零散文件，也不要给正常游戏添加隔离验收参数。

## 安装

1. 退出游戏。通过 Steam 的“管理 → 浏览本地文件”定位游戏目录，核对游戏版本与构建号。
2. 解压到新的空目录，保留原压缩包与 `PACKAGE.json`。对照清单核对文件 SHA-256；不一致则停止。
   Windows 可用 `Get-FileHash .\mods\Volibear\Volibear.dll -Algorithm SHA256`，其余文件同理。
3. 检查游戏目录下的 `mods/Volibear`。已有同名目录、文件、符号链接或目录联接而无法证明归属时，
   不覆盖或合并。旧版自有安装也先使用**当时的旧包清单和旧哈希**卸载，不用新包清单认领旧文件。
4. 检查 `mods/BaseLib`。若不存在，复制本包整个 `mods/BaseLib` 目录。若已存在，只有三个文件
   均与本包清单哈希一致、版本确为 3.4.7 且没有重定向时才能原样复用；不替换或删除不一致的
   既有 BaseLib，因为其他 Mod 也可能依赖它。
5. 在 `mods/Volibear` 不存在时，复制本包该目录到游戏的 `mods` 下。不要把完整包根目录、
   `PACKAGE.json` 或说明文档复制进 `mods`，避免被游戏误识别为 Mod 清单。保留其他 Mod 目录。
6. 正常启动游戏，按游戏自身提示确认 Mod 加载。加载或版本检查失败时保留现有存档，根据日志
   定位；不要为排错删除或重置存档。

文件管理器不会替你验证归属。出现意外的“替换同名文件”提示时取消，先核对来源和清单。

## 多人版本一致与保存恢复

参加同一局的所有玩家都需要：

- 相同的游戏版本 **0.107.1 / 59260271**。
- 同一候选构建的 Volibear，建议使用同一完整安装包，并用 `PACKAGE.json` 核对文件一致。
- 相同的 **BaseLib 3.4.7** 及所需依赖；其他影响玩法的 Mod 也保持相同版本和配置。

通过游戏原生多人大厅建立新局；每个玩家仍从自己的正常角色选择入口操作。不要只给主机安装
这个影响玩法的 Mod。既有角色/卡牌、实际付款、原生玩家选择、永久牌组和存档沿用游戏的
同步流程。对其他 Mod 的支持边界见 [RELEASE_PLAN.md](https://github.com/fltb/sts2-volibear-mod/blob/codex/mode7-completion/docs/RELEASE_PLAN.md)，不把版本相同
等同于任意第三方私有玩法都已验证兼容。

**断线恢复沿用原生房间检查点。** 主机回到菜单，重新打开已有多人存档的原生大厅，原成员
重新加入后加载该存档。恢复从游戏保存的房间 checkpoint 重建；已在该房间打出的临时动作
可能需要重做，不是回到任意暂停的战斗瞬间。锁版游戏的正式运行入口尚未实现任意中战斗热重连，
本 Mod 没有添加另一套中途快照或网络协议来改变这个边界。

发布流程中的多人验收已实现两端原生 ENet、真实付费、状态一致、断线和 checkpoint 恢复检查，
详情见 [MULTIPLAYER_ACCEPTANCE.md](https://github.com/fltb/sts2-volibear-mod/blob/codex/mode7-completion/docs/MULTIPLAYER_ACCEPTANCE.md)。统一发布门禁包含两端有序退出及检查点恢复。
Steam 传输、跨公网及人工操作体验需要在对应环境另行验证。

## 卸载

1. 退出游戏，使用当时安装的原包清单，确认目标仍是游戏目录下真实的 `mods/Volibear`，不是链接或目录联接。
2. 逐一核对 `Volibear.dll`、`Volibear.pck`、`Volibear.json` 与原 `PACKAGE.json` 中相同相对路径的 SHA-256。
3. 仅删除确认来自该包且哈希未变的这三个文件。缺失文件可跳过；已有文件哈希不符或来源不明时停止，保留它。
4. 仅在 `mods/Volibear` 完全为空时删除空目录，不递归删除含其他内容的目录。

卸载 Volibear 不删除或修改 BaseLib、其他 Mod、游戏原文件、设置、存档和云端数据。已有 Volibear 存档
继续需要对应 Mod 模型；卸载不把它转换成无 Mod 存档，也不承诺任意旧版本的存档迁移。
不要借卸载操作清理存档。

## 音频方案切换

完整安装包默认使用 `open`：47 个开放声音覆盖 54 个声音事件。可选 `riot_en` 的英文原声来源、
自动获取和构建命令见 [音频说明](https://github.com/fltb/sts2-volibear-mod/blob/codex/mode7-completion/assets/animation/audio/profiles/README.md)；公开源码不包含
Riot 录音。两套方案都按事件保留开放音频回退。

若包名含 `riot_en-private` 且附有 `AUDIO_PROFILE.txt`，该完整包已经内置 Riot 音频，直接按上文
安装即可，无需另行下载、转码或替换 PCK。本次配置为 11 条固定来源覆盖（9 条英文语音和
2 条官方 Q 开发示例声音），其余 43 个声音事件使用 open 回退；并非完整当前客户端技能音效集。

资源替换包只替换 `mods/Volibear/Volibear.pck`。退出游戏、保留原 PCK 后，使用与当前 DLL
同一版源码构建的目标 PCK 替换；切回 `open` 时恢复对应默认 PCK。资源替换包没有 DLL 和
BaseLib，不能单独安装成完整 Mod。使用替换包后，卸载时按该包实际 PCK 摘要核对这个文件，
其余两个 Volibear 文件仍按原完整安装包清单核对。多人约局前共同确认使用的候选与资源方案。
