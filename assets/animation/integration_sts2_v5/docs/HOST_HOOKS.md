# 宿主接入边界与事件契约

状态：`integration_source_uncompiled`。以下是接入样例的使用契约；只有项目本地类的方法才写成调用示例，未知游戏版本的钩子不伪装成已经存在的 API。

## 实例创建与图层

在真正的 `NCreatureVisuals` 场景中配置框架要求的视觉根、交互 Bounds、意图和中心位置。将一个 `AnimatedSprite2D` 放在角色视觉节点下，将独立 `Node2D` 用作该角色特效 holder。`VolibearPresentationController.Configure(sprite, effectHolder, currentGameVolume)` 只调用一次，返回 RitsuLib `ModAnimStateMachine`，供框架的角色动画入口使用。角色图集使用 `centered=false` 与 `offset=(-250,-442)`，其余位置/缩放由真实战场布局决定。

固定版本 RitsuLib 的实际重写入口位于 `src/Scaffolding/Characters/ModCharacterTemplate.cs`：`protected virtual ModAnimStateMachine? SetupCustomCombatAnimationStateMachine(Node visualsRoot, CharacterModel character)`。在自己继承的角色模板类中重写它，创建/获取该 `visualsRoot` 的 controller 并返回其 `Configure(...)` 结果；旧名 `SetupCustomNonSpineAnimationStateMachine` 已标记 obsolete。不要把这里的 `ModAnimStateMachine` 塞给 BaseLib 的 Spine `SetupCustomAnimationStates(MegaSprite)`，后者返回的是 `CreatureAnimator`，是另一条路径。[固定版本源码](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/ModCharacterTemplate.cs#L761-L774)

holder 的负 `ZIndex` 是相对其局部排序上下文；`owner_ground` 要传脚底源坐标，`owner_chest` 要传胸口源坐标，`owner_hand` 要传出招手位置，`target_*` 要传真实目标的对应锚点。跨 CanvasLayer 时不能把 UI 全局坐标直接当世界坐标；先转换到目标特效层，再调用。两点效果按各自 `segment_anchors_px.source / target` 做二维基变换；连锁雷为 `[30,128]→[224,128]`，吸血为 `[216,142]→[40,142]`，不能假设所有素材同向。吸血的源端应为被吸取者、目标为受益者；地环脚底采用各自 `pivot_px`，不强制画布中心。

两点判断以 `segment_anchors_px` 字段存在为准，覆盖 `counter_release / lightning_chain / lifesteal`，不能只匹配字符串 `source_to_target`。`resolved_enemy_group` 的目标位置由已结算敌群确定，逐个还是组中心由卡牌映射决定。`owner_energy` 的源坐标是能量UI，`owner_mouth_to_targets` 是角色口部。

`roar_wave` 的第一条波前在素材局部 `x=55`，pivot为 `x=128`。朝右且1倍比例时，传入的演出锚应为嘴部位置加 `(73,0)`，这样波前从嘴边发出；缩放/转向时把此局部偏移一并变换。不要只把画布pivot压在嘴上，让发波边落进脸部。

卡牌各锚点已显式列入接入类：净化/兽化/消耗/重放绑定该次事件选择的真实卡；抽牌和取回绑定手牌接收点；弃牌绑定被弃卡节点的演出点；减费绑定该牌的费用位置。抽、取、弃的贴图是抽象运动提示，不代替真实卡节点移动。`feral_transfer` 自带局部卡轮廓，保持比例，以其 `target_anchor_px` 放到实际所选牌的插画区域；`source_anchor_px` 只表示局部到达路径，未声明与远处owner精确相连。它不套用整图两点拉伸，以免把目标卡拉成长斜面，更不能挂在角色本体上。需要全程世界连接线时，宿主应另建连线/粒子节点，再播放牌面局部污染。

完整身体图集的内部遮挡已经烘焙；holder 只负责独立特效。不要重新装配身体或用全图 ZIndex 修复辫子/手臂关系。

## 角色动作与已提交事件

框架常用触发包括 `Idle / Attack / Cast / Hit / Dead / Relaxed / Revive`。本项目增加 `Block / HeavyAttack / Bite / Counter / DomainEnter / DomainExit / FeralEnter / Roar / StormLeap` 等触发；宿主必须在对应规则动作已经提交时显式调用。`Revive` 使用待机回退，本包未制作独立复活动画。

本地样例：

```csharp
// These are this delivery's own types, not claims about a vanilla game hook.
var cues = new [] {
    new PresentationCue(0.25, "sfx.lightning_strike", "lightning_strike",
        casterHandGlobal, committedTargetCenterGlobal)
};
presentation.Present("Cast", nextCommittedSequence, cues);
```

`nextCommittedSequence` 是**该角色范围内单调递增的已提交动作序号**；网络重发和重复回调保持同序号。每个表现事件也只能由一个宿主路径发出，避免同时从卡牌处理、模型动画入口和每帧更新播放三次。动画时间点只影响效果何时可见，不负责伤害结算，也不决定命中目标。暂停身体时未来时间点不推进；动画完成后只补齐本动作尚未发出的末帧 cue，中断丢弃旧时间线。

`audio/action_cues.json` 与 `vfx/card_vfx_bindings.json` 是可移植数据契约。宿主可将已选择的行转为 `PresentationCue`，并以真实动作变体的时长检查时间点。状态切换依赖持久领域/低血量标记，不应让 `attack` 的完成处理无条件回到普通待机。

## 领域、兽化、受伤与死亡

领域效果由规则层先提交，再设置 `presentation.Flags.Domain`。进入后按项目选定时点启动 `Audio.PlayCue("sfx.domain_loop")` 和 `Effects.Spawn("domain_loop", footGlobal, footGlobal)`；两者已有同 ID 循环去重。退出时更新标记并触发退出动作；controller 在 `domain_exit` 开始时停止对应循环。若跳过退出动作直接清除领域，也需显式调用 `Audio.StopLoop("sfx.domain_loop")`、`Effects.StopLoop("domain_loop")`。循环存在于实例生命周期，不能靠下一张牌或动画结束“顺便”停止。清洁图集中的 `skin` 字段是状态提示；它没有暗藏第二套领域染色。

低血量由宿主血量变更事件调用 `UpdateLowHealth` 并在静止状态刷新待机。默认 30%/35% 是可改的表现防抖参数。受伤音效由已提交受击事件发出；不使用不存在的 `CustomHurtSfx` 字段。controller 在死亡动作开始时停止本实例旧声音/效果，再允许新的死亡 cue；战斗结束必须调用 `EndCombat()`。

兽化是本项目手牌机制：源端为角色施放位置，终点为被转化的手牌；手牌刷新由模型层完成。`FeralEnter` 只是一段施放动作，完成回到实际领域/低血量/普通状态。可选 `PlayTemporaryFeralPose` 最长 0.5 秒，token 防止旧计时器取消新姿态，不构成永久角色 Buff。

## 音量、并发与清理

`VolibearCueAudio` 使用原生 Godot `AudioStreamPlayer`，没有假设存在 FMOD bank。宿主必须提供 `currentGameVolume(bus)`，返回尚未被当前 Godot Master 总线施加的音量增益（0–1，静音为0）；游戏音量变化时调用 `RefreshGameVolume()`。若游戏/框架已经同步 Master 总线主音量，回调只返回其余 SFX/Voice 增益，避免主音量乘两次。BaseLib 自有音频服务会利用游戏配置和 Godot SFX 总线；本例没有调用它的混音管理，不能只看逻辑 bus 字符串就假设所有 FMOD 开关已自动继承。

**避免占位角色声音混入或重复播放：**RitsuLib `ModCharacterTemplate.PlaceholderCharacterId` 默认是 `ironclad`，其回退 profile 包含原版攻击/施放/死亡声。`null` 或空字符串不会自动表示“静音”。本交付提供可选 `VolibearNativeAudioAssets.CharacterSlots()`，用实际 `res://` Ogg 路径覆盖5个角色音效入口；BaseLib 的 `PlayResourcePatch` 会将 `NAudioManager.PlayOneShot` 的合法资源路径转入 `ModAudio`。采用这条原生入口路线时，从自定义动作 cue 时间线中移除已由它负责的同一角色声音，保持每事件一个所有者。若需要全部精确到自定义时间点，则由目标版本的宿主专门接管这些角色事件，并验证已停止原版占位声音，不能编造一个不存在的 FMOD 静音事件。

上述依据：[回退 profile 与默认 ironclad](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfiles.cs#L15-L68) · [BaseLib 资源音频桥](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/Patches/Audio/PlayResourcePatch.cs) · [BaseLib 音量路由](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/Audio/ModAudio.cs)

同 cue 有最大并发数与冷却；loop 同 ID 不重复创建。一个新短动作取消旧时间线的**未来** cue；已经开始的非循环尾音可自然结束。如某种动作必须硬中断旧效果，请按 effect token 停止其拥有的节点，不能全局清空其他生物音效。

离场、死亡退出、读档重建、战斗结束均需停止循环并清空实例持有的播放器。`_ExitTree` 已执行最后清理；宿主仍应在 `EndCombat()` 时提前处理，避免等待场景销毁。返回的新场景使用恢复后的规则标记重建表现，不序列化一个正在播放的粒子或声音来充当游戏状态。

## 联机与游戏验证

新角色/卡牌/能力属于改变游戏规则的 Mod，不能标成纯美术。各客户端只消费相同已提交动作、目标与状态，不从本地随机粒子、声音时长或帧率推导伤害。RitsuLib Sidecar 能提供自定义消息，但消息注册不等于自动实现规则同步；本样例不发送网络消息。

需要在用户目标游戏版本完成：角色注册/选角、单人与多人、所有触发、重复同名攻击、死亡与显式复活、领域退出、低血量阈值切换、手牌兽化、读档、切场景、静音/调音量、加速/暂停及所有循环清理。当前独立 Godot 报告只能证明交付资产能被该引擎读取与组织，不能替代以上游戏测试。

