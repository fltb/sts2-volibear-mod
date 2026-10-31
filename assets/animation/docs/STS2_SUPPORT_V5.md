# 《杀戮尖塔 2》角色、美术、音频与特效接入核查

核查日期：2026-10-27（UTC）。本报告针对 **Slay the Spire 2 / C# / Godot**。STS1 的 Java、ModTheSpire、libGDX、AbstractGameEffect 接口不适用于这里。Mega Crit 官方 FAQ 明确说明两代引擎和架构不同，STS1 Mod 不能直接平移。[官方 FAQ](https://www.megacrit.com/faq/)

## 结论与本项目选择

角色不需要录制一套人声台词才能运行。已核实的角色接口提供选择、转场、攻击、施放、死亡音效入口；BaseLib 自定义战斗音效默认值是 `null`，空值继续走基础实现，而不是因没有配音拒绝注册。也没有名为“每张卡必须配一句台词”的要求。为表现力补齐攻击呼气、受伤、低血量、咆哮、死亡、雷击及机制音效有价值，但这是本项目的演出决策。受伤声不属于该角色音效集合内的单独字段，应从本项目受击事件触发，不能捏造 `CustomHurtSfx`。[BaseLib 角色源码](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/Abstracts/CustomCharacterModel.cs#L107-L109) · [RitsuLib 角色音频字段](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfile.cs#L163-L192)

本轮建议使用透明 PNG 图集 + `SpriteFrames` + `AnimatedSprite2D` 播放已有动作；新增战斗特效作为独立透明图集。这里的 `rig.json` 是本项目绘制器的装配数据，不是 Spine skeleton。不要将它改扩展名冒充 Spine，也不要把带旧特效的预览图集再叠上整套新特效。集成优先使用 `animations/clean/manifest.json`。[作者动画文档](https://sts2-ritsulib.ritsukage.com/guide/creature-visuals-and-animation) · [实际 AnimatedSprite2D 后端源码](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Visuals/StateMachine/Backends/AnimatedSprite2DBackend.cs)

“音效可以为空”不等于“空值会静音”。RitsuLib 模板的默认占位角色是 `ironclad`，回退素材集合含其攻击、施放、死亡音效。若全部声音由项目时间线控制，宿主要明确接管原版音效入口；不能让原版声音和新兽吼双播。另一条已有源码支持的路线，是把角色音效槽设为有效 `res://` Ogg 路径，由 BaseLib 对 `NAudioManager.PlayOneShot` 的补丁转入 `ModAudio`，并从自定义时间线移除重复的角色声音。本包两种接入方式的职责写在 `integration_sts2_v5/docs/HOST_HOOKS.md`，不虚构 FMOD bank 或“静音事件”。[占位回退实现](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfiles.cs#L15-L68) · [资源音频桥源码](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/Patches/Audio/PlayResourcePatch.cs)

## 本次固定的源码版本

| 来源 | 实际读取版本 | 本次用途 |
| --- | --- | --- |
| Alchyr/BaseLib-StS2 | `c070755d11ec062f6c97c4dda1a205d975ed066a` | 角色属性、非 Spine 动画、原生 Godot 音频 |
| BAKAOLC/STS2-RitsuLib | `772f280964f2efc7c7e2f29fc59844e68616dd57`，2026-10-24 的 v0.6.10 合并 | 动画状态机、形态切换、音频生命周期、卡牌素材、联机边界 |
| Alchyr/ModTemplate-StS2 | `2c900a04dd2073872f677f4fb78ee2ad1e871009` | 实际角色模板文件与示例 PNG 尺寸 |

这些是社区框架作者的实现，不能称为 Mega Crit 承诺长期兼容的稳定 API。当前源码依赖 `GodotSharp / Godot.NET.Sdk 4.5.1`、`.NET 9`。作者安装指南优先使用 Mega Crit 的 MegaDot，备选才是与其版本完全一致的 Godot .NET；离线美术演示可以使用标准 Godot 4.5.1。抢先体验的游戏更新可能使 Mod 需要适配。[BaseLib 工程依赖](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/BaseLib.csproj) · [RitsuLib 依赖](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/Directory.Build.targets) · [作者安装指南](https://github.com/Alchyr/ModTemplate-StS2/wiki/Setup)

## 能力矩阵

“支持”表示查到接口或实现，不表示本项目的游戏 DLL 已编译或已经在游戏中测试。

| 需求 | 已核实接入层 | 符号 / 入口 | 本项目处理及界限 |
| --- | --- | --- | --- |
| 角色逐帧动画 | Godot 原生 + 两个社区框架适配 | `SpriteFrames`、`AnimatedSprite2D`；RitsuLib `AnimatedSprite2DBackend`；BaseLib `CustomAnimation.PlayCustomAnimation` | 读取透明图集区域、帧速率和循环标志；不需要 Spine |
| Spine 动画 | 游戏 MegaSpine + 框架适配 | `MegaSprite`、`SetupCustomAnimationStates`、`SpineAnimationBackend` | 可选路线；本项目没有交付 Spine 工程，不能直接使用这条路线 |
| 常规动作触发 | 游戏触发 + 社区桥接 | `Idle / Attack / Cast / Hit / Dead / Relaxed / Revive` | `Revive` 映射待机是本项目显式回退；不宣称已有独立复活动画 |
| 低血量 | 自定义表现状态 | 本项目健康比例监听 → 状态机 | 30% 进入、35% 退出是项目防抖参数，不是游戏官方要求 |
| 兽化、领域形态 | 自定义状态 / 社区后端 | `FormSwitchingAnimationBackend.SwitchForm` 或自定义状态机 | 已有通用换形能力；“兽化手牌”“领域压制”的规则仍由卡牌/能力模型实现，图集不会自动实现机制 |
| 卡牌命中特效 | 游戏命令或自定义 Godot 节点 | `DamageCmd.Attack(...).WithHitFx(...)`；自有 VFX holder | 已有原版命中效果入口；本项目图集通过自有节点播放，不能假设把任意 PNG 路径传入 `WithHitFx` 就能工作 |
| 雷电、连锁、全体命中 | 自定义特效 | `Node2D`、`AnimatedSprite2D`、可选 `GPUParticles2D` | 传入实际源/目标位置。多目标每次已结算命中各触发一次，不由美术预览决定目标或伤害 |
| 地面领域与环境反馈 | Godot 节点 / shader | `CanvasItem.ZIndex`、`ShaderMaterial` | 地面层和前景粒子分开；限定在战场，不能遮住卡牌文字、数值和敌人意图 |
| 卡牌边框、覆盖层、拖尾 | 社区素材 profile | `CardAssetProfile.OverlayScenePath`、材质字段；`CharacterVfxAssetSet.TrailPath` | 机制反馈可以用 overlay / scene；完整卡牌拖尾要求场景结构，单张图不会自动变成拖尾 |
| 普通音效 | Godot 或社区音频服务 | BaseLib `ModSound / AutoModAudio`；RitsuLib `GameAudioService` | Ogg/WAV 可用；本轮 source 样例用原生 Godot 播放交付的音效，拥有明确 loop 停止与音量桥接 |
| FMOD bank 与事件 | RitsuLib 扩展 | `FmodStudioDeferredBankRegistration.RegisterBank`、GUID 映射 | 可支持，但本轮未制作 `.bank`；不能把音效文件名当作不存在的 FMOD 事件 |
| 音频重复与清理 | 社区服务或自有节点 | `CooldownMs`、`AudioScopeToken`、`TryStop`；Godot owned players | 同动作事件去重、同循环不重复创建、离场/死亡/中断清理；不能全局停止其他角色声音 |
| 保存与恢复 | 社区数据机制 | Run saved data / typed slots | 恢复领域与低血量状态后重建表现；不能从一个未播放完的特效推断游戏规则 |
| 联机 | 游戏模型同步 + 社区自定义消息 | `affects_gameplay`；RitsuLib Sidecar endpoints | 新角色/新机制属于 gameplay；特效本地消费已提交事件，可丢帧但不可改变结算；本包没有完成联机实测 |
| 打包与分发 | 游戏加载器 / Godot 资源包 / 官方上传器 | `.dll + .pck + manifest.json`、`res://`、官方 Mod Uploader | repo ZIP 是可编辑交付，不能当作已经可装的游戏 Mod；发布操作未执行 |

矩阵依据：[BaseLib 实际动画分派](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/Utils/CustomAnimation.cs) · [形态后端](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Visuals/StateMachine/Backends/FormSwitchingAnimationBackend.cs) · [命令范例](https://github.com/Alchyr/ModTemplate-StS2/wiki/Common-Commands-Cookbook) · [Godot 粒子](https://docs.godotengine.org/en/4.5/classes/class_gpuparticles2d.html) · [卡牌素材 profile](https://sts2-ritsulib.ritsukage.com/guide/asset-profiles-and-fallbacks) · [音频服务](https://sts2-ritsulib.ritsukage.com/guide/fmod-and-audio) · [Sidecar 注册实现](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Networking/Sidecar/Endpoints/Api/RitsuLibSidecarEndpoints.cs) · [Mod manifest 与联机](https://github.com/Alchyr/ModTemplate-StS2/wiki/Modding-Basics) · [官方上传器](https://github.com/megacrit/sts2-mod-uploader)

## 角色场景结构与容易遗漏的资源

`NCreatureVisuals` 是游戏生物视觉根节点。直接自定义时应按框架要求设置 `Visuals`、`Bounds`、`IntentPos`、`CenterPos` 等位置；通过 NodeFactory 转换时部分节点可自动补充。`Bounds` 是交互/布局框，不能由每帧透明像素包围盒改变，否则角色动作会让命中区域跳动。胸前辫子与前景右臂应在图集生成阶段就按正确深度合成；运行时不能把一整张已合成图的 ZIndex 当成内部遮挡修复。[BaseLib 生物场景文档](https://alchyr.github.io/BaseLib-Wiki/docs/scenes/creature-visuals.html) · [Godot 层序规则](https://docs.godotengine.org/en/4.5/classes/class_canvasitem.html)

除战斗角色和卡图，角色选择、锁定头像、顶部头像与描边、地图标记、能量计数器、商店、篝火、卡牌拖尾、状态图标、特殊遗物/药水视觉以及多人手势都有对应接入点。它们不都要求原创美术；允许基础回退的字段，应在交付目录明确写“原版回退”，不能把缺失资源标成已经制作。[角色素材集合源码](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfile.cs) · [完整清单](ART_ASSET_COMPLETENESS_CHECKLIST.md)

当前 RitsuLib 的选角背景工厂明确支持先查 `PackedScene`、再将 `Texture2D` 包装成 `TextureRect`。这使本轮选角背景 PNG 有直接纹理回退路径；它不意味着所有资源槽都能直接填 PNG。`CharacterSelectTransitionPath` 按 `Material` 校验，`EnergyCounterPath` 按 `PackedScene` 校验。大/小能量图标则在作者模板卡池、遗物池、药水池的 `BigEnergyIconPath / TextEnergyIconPath` 中有实际 override。交付的转场 PNG 和空能量图只是相应场景/材质的输入素材。[背景工厂](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/Patches/CharacterSelectBackgroundRuntimeFactoryPatch.cs#L132-L158) · [资源槽类型验证](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/Patches/CharacterAssetOverridePatches.cs#L112-L155) · [模板能量图标入口](https://github.com/Alchyr/ModTemplate-StS2/blob/2c900a04dd2073872f677f4fb78ee2ad1e871009/content/CharacterModTemplate/CharModCode/Character/CharModCardPool.cs)

## 官方沃利贝尔语音的获取与使用状态

**V5.1 更新：** 用户已明确要求为个人资产包收录官方录音。已从独立 Wiki 媒体 CDN 实际取得 150 个默认英文语音与 1 个选择音效，并取得腾讯官方元数据指向的 2 个国服录音，放在 `audio/official/`。来源、原字节 SHA、实际解码与范围说明见其目录。当前运行 cue 和 PCK 继续使用 V5 原声音。

以下两段保留 V5 当时的调查记录，不能代替上述 V5.1 下载结果。

公开目录能找到选择语音候选 `.../champion-choose-vo/106.ogg`，但是本轮对 CommunityDragon 的普通下载请求返回 HTTP 403；没有成功取得该音频字节，也没有绕过拦截。英雄联盟 Wiki 的音频页面在检索中可见，直接访问被 robots 规则阻止，因此没有继续从该站提取音频。`VOLIBEAR_AUDIO_SOURCE_STATUS.json` 保存具体候选和失败状态，不能将它当作已下载语音包。

可下载与可在另一个游戏中分发是两件事。Riot 的公开粉丝内容政策第 3 条明确限制把其 IP 放入未经授权的游戏或应用；公开网页没有授予本项目跨游戏使用官方配音的明确许可。本轮实际声音资产采用有明确许可的素材加工及原创声音设计，附各来源和许可。不把它们称作“官方沃利贝尔配音”，也不声称角色形象因此自动获得商业授权。[Riot 官方政策](https://www.riotgames.com/en/legal)

## 交付验证边界

美术文件完整、图集可解码、原生 Godot 能播放、事件时序正确和“最终 Mod 已经通过游戏实测”是不同验收项。离线 Godot 报告仅覆盖真实引擎的资源读取、帧区/时长、音频解码和节点生命周期；C# 样例保留 `integration_source_uncompiled` 标记。最终游戏接入还需要用户目标分支的游戏程序集、对应框架版本，以及单人/联机、读档、加速、暂停、死亡、切场景的真实测试。
