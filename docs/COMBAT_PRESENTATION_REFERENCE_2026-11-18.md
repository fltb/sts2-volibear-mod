# 战斗动作与特效：原版参考和接入审查

日期：2026-11-18。调查基线：`bb06bb1329d664fc4da69ccc6302a0196eafa461`。

本轮目标是让沃利贝尔在真实战斗中呈现不同攻击、雷法、防御、迎战、领域和兽化的动作身份，并使卡牌联动和不同目标上的命中效果可辨认。本文记录参考证据、调查基线的缺口和验证边界；不是实现完成证明，也不以资源文件数代替游戏内表现验收。

## 1. 参考证据与适用范围

| 来源 | 能证明什么 | 不能据此声称什么 |
| --- | --- | --- |
| [Mega Crit：July 2026 Neowsletter](https://www.megacrit.com/news/2026-7-17-neowsletter-issue-24/) | 动画师以 Aeonglass 说明：攻击轮廓、运动方向和 VFX 共同表达招式；环的持续旋转与主体状态使用独立时间线；引擎 Shader 补充动画软件中的占位层 | 不能推导所有原版角色的动作数量，也不是沃利贝尔资源的视觉批准 |
| [Mega Crit 官方 Steam 公告页](https://steamcommunity.com/app/2868840?l=english)，2026-11-16 的 Major Update #3 v0.111.1 | 官方列出了低血量待机、角色形态 VFX、Defect Orb 被动触发、卡牌消耗/移除、Ironclad 施法、Necrobinder 斩击等更新 | 公告页会继续更新；不把它当作 PBE 0.113.0 的完整资产清单 |
| [BaseLib v3.4.8：CustomAnimationPatch](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/Patches/UI/CustomAnimationPatch.cs) 与 [CustomAnimation](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/Utils/CustomAnimation.cs) | 作者锁版本源码，明确原生动画 trigger 怎样转交给 Godot 的自定义动画节点 | 未替代本地 BaseLibCompatibilityHelper 与当前游戏程序集的实际加载验证 |
| [Alchyr：Creating a Character](https://github.com/Alchyr/ModTemplate-StS2/wiki/Creating-a-Character) 与 [Replacing Base Game Text & Images](https://github.com/Alchyr/ModTemplate-StS2/wiki/Replacing-Base-Game-Text-&-Images) | 角色接入、原生攻击命中特效与 Spine/自定义视觉方案的作者文档 | 文档可能随版本变化，具体 ABI 仍以锁版程序集为准 |
| [旧版原生代码快照](https://github.com/zhiyue/sts2-rl-agent/tree/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled) | 直接观察该快照的角色状态和攻击调度顺序，是排查线索 | 第三方保存的反编译快照，不是最新 PBE 官方源码或当前实机证据；不复制游戏实现或资产进本仓库 |

### 原版角色的动作身份

下面只列旧快照中查到的核心状态。各角色另外都有待机、受伤、死亡、放松等状态；不在这里宣称最新版本的总数。

| 角色 | 查到的核心差异 | 对沃利贝尔的启发 |
| --- | --- | --- |
| [Ironclad](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Characters/Ironclad.cs) | `attack`、`attack_heavy`、`cast` | 轻爪、重砸和施法应有不同重心与轮廓 |
| [Silent](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Characters/Silent.cs) | `attack`、`shiv`、`cast` | 高频连击需要自己的节奏，不能一律重播完整重击 |
| [Defect](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Characters/Defect.cs) | `attack`、`cast`、`process` | 能力部署/成长应与直接攻击区别；被动层应可独立触发 |
| [Necrobinder](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Characters/Necrobinder.cs) | `attack`、`cast`、`cast_mighty` | 普通法术和大范围风暴需要不同施法姿态 |
| [Regent](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Characters/Regent.cs) | `attack`、`attack_sovereign`、`cast` | 标志性机制应有专属动作身份 |

[Whirlwind 的旧快照](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Cards/Whirlwind.cs)组合了水平速度线、暗角、巨型横斩命中特效和多段攻击；[SwordBoomerang](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Models.Cards/SwordBoomerang.cs)仍可复用基础攻击/斩击。对标标准是动作语义、节奏、轨迹、目标适配和机制反馈的组合，不要求每张牌拥有全新全身动画。

## 2. 基线中定位到的实际问题

### 2.1 专属主动作会与原生通用 Attack 竞争

`VolibearPresentationBridge.Motion.cs` 在 `CardPlayStartedEntry` 选择卡牌主动作；随后 `DirectEffects.Attack`、`Basic.cs`、`HistoryEffects.Attack`、兽化攻击等调用原生攻击命令。`tools/build_assets.py` 又将原生 `Attack` alias 固定映射为 `attack`。

[旧版 AttackCommand](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Commands.Builders/AttackCommand.cs)的 `FromCard` 默认选择 `Attack`，并默认逐段触发攻击动画。BaseLib v3.4.8 会把这个 trigger 直接交给 `AnimatedSprite2D.Play`。因此已选的重击、撕咬等动作可能立即被通用打击覆盖；这是必须优先验证的调用链根因。

这里的结论来自源码链路，并未声称已在 PBE 0.113.0 录制到复现。新增资源后仍须验证真正播放的动画名和帧进度。

### 2.2 多段物理特效在整组历史结束后集中发出

基线 `RouteHistory` 在 `CreatureAttackedEntry` 中遍历全部 `DamageResults`。旧版原生 `AttackCommand` 在整次多段循环结束之后才发布这条历史。因此这条入口不适合作为逐段命中特效的主时钟。

本项目已有更精确的边界：`CardResolutionHooks.OrdinaryAttackPipelineV1` 每段只调用一次原生 `nativeDamage`，取得真实结果之后才进入领域附雷及普通段响应。只读表现收据应在原生伤害成功完成之后、领域/被动联动之前发出，使画面顺序对应真实事件顺序。

不能把所有沃利贝尔造成的 `DamageReceivedEntry` 都视为普通攻击，也不能通过 `Unpowered` 判断雷伤。雷伤、反伤及其他伤害同样经过伤害入口；普通攻击本身也可能带有 `Unpowered`。

### 2.3 表现分类过窄

| 基线位置 | 观察到的限制 | 改进方向 |
| --- | --- | --- |
| `ReadContactEffect` | 只接受爪击、重击、撕咬、反扑四种接触样式 | 增加横扫、交叉连爪、砸地/踏地等可辨认形状 |
| `OwnerScope.Lightning` | 雷伤归为 `lightning_all` 或 `lightning_strike` | 按真实来源区分法术、领域附雷、普通段追雷、雷池和反雷 |
| `OwnerScope.Incoming` | 格挡命中与失血受伤的表现较单一 | 区分实际格挡、破防、连续命中；死亡优先 |
| `effects.gd` | 主要依靠中心/地面/状态锚点，目标尺寸适配不足 | 使用实际可见目标的锚点与边界，限制缩放，避免盖住意图和血条 |
| `LightningBatch` | 被动来源经常 `Card == null`；领域附雷沿用攻击牌来源 | 增加只读表现来源，禁止改写伤害、计数、目标或战斗 RNG |

### 致死最后一击的结尾阶段

旧版 [CombatManager](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Combat/CombatManager.cs) 的 `IsEnding` 是实时 getter：没有存活的主敌人时就可能返回 `true`，并非等到 `CombatEnded` 才置位。相同快照的 `CreatureCmd.Damage` 先扣生命，再记录受伤历史，最后等待死亡处理和短暂停顿后返回；受伤历史自身也会排除 `IsEnding`。

因此，普通段和雷伤的完成回执若沿用“只在未结束战斗中播放”的身体动作门，可能漏掉击杀最后敌人的接触特效。当前 PBE 尚未实机核对这一顺序，但旧版原生代码明确支持此风险。安全处理应区分“同房间、节点仍有效、已经结算完成的接触尾迹”和“发起新动作、领域循环、玩法回应”：前者可以短暂显示，后者保持原来的结束守卫。不能为保留最终雷光而放开 `LightningBatches.CanUse` 或玩法 `Notify` 的结束条件。

## 3. BaseLib v3.4.8 的最小动画仲裁点

已核对 tag `v3.4.8`：

- 原生目标是 `NCreature.SetAnimationTrigger(string trigger)`；旧版原生声明返回 `void`。
- BaseLib 前缀签名为 `static bool SendTriggerToOtherAnimators(NCreature __instance, string trigger)`。
- 该类和该方法没有声明 Harmony 优先级或前后顺序。
- [BaseLibMain](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/BaseLibMain.cs)将 Harmony owner 设为 `BaseLib`。
- [Harmony 官方优先级说明](https://harmony.pardeike.net/articles/priorities.html)规定未指定时为 `Priority.Normal`，数值 400。

建议在同一个同步、只影响表现的方法上安装窄前缀，显式 `Priority.First` 和 `before = ["BaseLib"]`。只在下列条件同时满足时接管通用 `Attack`/`Cast`：

1. 该节点确实属于沃利贝尔，且当前仍绑定原来的活动战斗/房间。
2. 角色存活、视觉节点有效，存在本次实际出牌已选中的专属动作。
3. 当前 trigger 确实是要仲裁的通用入口；既有自定义 trigger 不受影响。
4. 接管成功或已确认专属动作仍在播放；资源/状态失配时应让原生路径继续。

此时返回 `false` 可防止后续 BaseLib 前缀再播放通用动作。[Harmony 官方 Prefix 文档](https://harmony.pardeike.net/articles/patching-prefix.html)说明：返回 `false` 会跳过后续有副作用的前缀及原方法，仍会执行无返回值且无 `ref` 参数的观察前缀，以及 postfix/finalizer。BaseLib 这个前缀返回 `bool`，会被跳过。

不要为此改写 `CreatureCmd.TriggerAnim` 的返回 Task、等待时长或取消语义。旧版 [CreatureCmd](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Commands/CreatureCmd.cs)在调用 `SetAnimationTrigger` 后仍执行原生缩放等待，因此在同步视觉入口仲裁能保留该调度。

接入审查必须额外检查：

- 不泛拦 `Hit`、`Dead`、`Revive`、`Idle`，不阻止死亡和恢复。
- 不能仅凭“最近一张牌”选动作，必须绑定当前 owner 和出牌身份，避免嵌套出牌/重演串动作。
- 重演不一定重新收到主动作登记；它的通用 Attack 也不能把原专属动作改回默认打击。
- 被动追雷/格挡/成长使用叠加层，不反复抢占主动作。
- 单次主动作结束后，多段攻击继续时应采用明确分段策略，不能永久吞掉后续可见动作。
- 恢复专属动作必须检查实际返回值；演员脚本拒绝恢复时，不应继续吞掉原生 trigger。
- 每个原生 `CardPlay` 需要独立动作序列身份；其中普通攻击与本卡雷段还需分开记录，避免双方从 0 开始的索引互相抑制。恢复和接触必须传递相同类别的序列；嵌套结束能恢复外层序列，重演即使仍在播放同一 clip 也必须绑定新的序列。
- 使用 `Harmony.GetPatchInfo` 验证安装 owner 和实际前缀顺序；源码排序建议不等于实机已按序运行。

## 4. 逐段收据与联动来源的接口选择

`IOrdinarySegmentResponder` 是真实能力实例的玩法接口，由 `Owner.Powers` 枚举且在领域之后执行。为视觉增加假能力会改变模型，时机也不对，因此不使用这条路径承载普通命中特效。

现有 `GameplayPresentationReceipts` 适合复用反雷、雷甲、咬痕、吸血、领域压制、兽化、强化和牌堆移动等已经提交的事实。但它不携带原生 `DamageResult` 身份和整段分组，难以可靠完成逐段命中、格挡细分与历史 fallback 去重。

若新增普通段收据，应保持最小范围：

- 携带实际 Card、Owner、原 Combat 引用、原出牌标识及只读原生结果。
- 在 `await nativeDamage()` 成功之后发布；失败/取消不制造完成事件。
- 发布前检查原 scope 未关闭，呈现时再检查同房间/同战斗世代，阻止旧 continuation 穿越 reset。
- 订阅者同步、逐个隔离异常、不等待动画、不改变或替换结果。
- 物理命中收据先于领域及被动雷；历史汇总只为没有逐段收据的原生攻击补足，并按结果身份去重。
- AOE 的一个普通段允许多个真实接收者；随机多段用每段已产生的接收者，不自行选敌。

雷伤来源可增加纯表现标签，例如领域附雷、逐段追雷、雷池、反雷。不要从 `Card == null`、伤害数值或“最后一次动作”倒推来源；也不要让表现标签参与次数统计、玩法目标或存档逻辑。

本卡雷段的身体索引只由本卡雷回执推进。领域附雷等被动即使携带同一张来源牌，也不能消耗本卡雷段的索引。完成回执还应保留出牌身份：晚到的外层回执、已完成出牌和无卡来源仍可显示真实目标上的接触，但不能推进当前另一张牌的身体动作。

## 5. 本轮表现矩阵

以下是适合本项目的制作与验收分组，属于设计建议。卡牌效果和数值以当前生产代码及用户裁决为准。

| 分组 | 卡牌例子 | 身体动作 | 接触/联动表现 |
| --- | --- | --- | --- |
| 快速爪击 | B01、C01、C20、U20 | 短前探、左右变化、小幅回收 | 窄爪痕，连打可见方向变化 |
| 连爪 | C02、C05、C06、U06、T01 | 左右连抓，按实际段数推进 | 每段独立命中；随机攻击跟随真实新目标 |
| 重击/砸地 | C03、U05、U07、C22、U31 | 蓄肩、双臂砸下、连续踏击不同重心 | 冲击环、地裂；多段不能集中堆在最后 |
| 横扫 | C09 | 大幅横摆/转肩 | 横弧贯穿敌方构图，各目标真实受击处短闪 |
| 撕裂/撕咬 | C08、U08、U24 | 撕开与咬合分别表现 | 已有咬痕的第二口才出现联动强化；吸血沿真实目标回流 |
| 雷法 | C24、U37、U40、R17、R23 | 指向释放、举臂引雷、双臂聚雷 | 天降、连弧、多次裂雷、地面风暴有不同构图 |
| 防御 | B02、C12、U03、R02、R05 | 低伏架挡、皮毛绷紧、扎根防御 | 格挡/留甲/坚甲可辨认；完全挡住不播失血姿态 |
| 迎战 | B04、C04、C10、C11、U28、U35、R09 | 邀战/架挡、承受真实动作、反扑 | 挑战目标、吸收聚集、反击释放；全体迎战按实际敌人处理 |
| 领域 | C18、R01、R25、R31 | 展开、领域内动作、退出 | 灵体/地面层独立持续；压制和附雷有真实来源 |
| 兽化 | U41–U43、R27–R30、T01/T02 | 转化、爪形与躯形区别 | 原牌消耗到生成牌；批量转化一次主动作、逐牌反馈 |
| 整备/增益 | C17/C19、U10–U17、R06/R12 | 振臂、调息、抬爪整备 | 肩爪力量、背刺雷势、牌上强化/保留分别可读 |
| 被动联动 | U02/U04/U19/U21/U25/U26/U34、R16/R18/R28/R30 | 优先使用叠加层 | 攻击追雷、雷伤叠甲/回能、迎战成长、兽化收益可追溯 |

### 目标与敌人适配

按目标实际可见锚点、尺寸和结算结果适配，保留敌人自己的原生招式：小敌不被特效完全覆盖，大敌命中不缩成一点；悬浮目标的身体接触与地面波分离；格挡/破盾只按真实结果表现；群攻的大构图播放一次，各真实接收者有独立接触。死亡、替换、召唤后不得把旧目标特效错误绑定到新实体。

## 6. 验收要求与当前边界

| 检查 | 需要的证据 |
| --- | --- |
| 主动作路由 | 记录真实原生 trigger、最终 clip 和帧进度，确认专属动作不被通用 Attack 覆盖 |
| 逐段接触 | C02/C05/C06/U07/U08 的真实段数、结果身份、VFX 时间；包含换敌、提前击杀、咬痕第二口 |
| 联动顺序 | 领域 + U02 + U21 + U34 下，攻击、附雷、追雷、雷甲/回能各自来源与时间 |
| 目标适配 | 小体型、大体型、悬浮、有格挡/无格挡对比；血条、意图、手牌保持可读 |
| 生命周期 | 快模式、重演、嵌套出牌、死亡、退出房间和 reset 无残留/串场 |
| 多人 | 本地和远端按各自 owner/原生对象显示；不要求虚构远端手牌锚点 |
| 玩法不变 | 数值、费用、次数、目标、战斗 RNG、原始等待与原 Task 语义保持一致 |

本次参考调查尚未运行锁定的 StS2 PBE 0.113.0 / 16ac0fe3 本体。当前共享环境调查未找到游戏程序集和对应 BaseLib DLL。资源预览、离线分类检查、Godot 脚本运行和源码审查分别有价值，但都不能替代真实游戏加载、出牌、多人及最终人工视觉验收。实际验证结果应由本轮独立验证记录提供，不能从本文推定通过。
