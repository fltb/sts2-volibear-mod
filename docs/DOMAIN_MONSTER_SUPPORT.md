# 锁版全怪物逐机制领域支持调查

## 1. 判定基准与证据边界

- 调查日期：2026-11-02；锁版 **StS2 0.107.1 / 59260271**。本体版本依据 [release_info.json](<../.local/game/release_info.json#L1>)；主程序集 SHA-256：`d13f3f150b1413b24c3a9c5575cdf5398dc74270877d55dec9a556dd8150bd03`。
- **baseline**：本轮调查开始时的实际未提交工作树，HEAD `189389838f065b3efc78c7b89718093095857d4a`。生产快照保存在私有目录 `.local/domain-audit/baseline-src/`；其后修复不回填为“baseline 已实现”。**当前实现回填：2026-11-02，task-5**；第2节“当前实现”、第4节“当前增量”和第7节新增当前列以现行源码为准，原基线结论及121类中文名保留。
- **已实现**指静态实现链已经存在；**未实现**指原生路径会执行且既有领域入口没有覆盖该贡献。保留项明确写“已实现（保留原生）”，不把按规则保留的攻击、力量、格挡、负面效果和清理列成缺陷。混合机制按步骤分别判断。
- 初版调查只反编译、读取、建立引用清单；本次回填只修改本文，读取生产源码、测试源码及既有回执，**没有启动游戏、没有运行 gate、没有重跑测试**。第9节分别记录实现链、已执行窄测试和未执行的游戏验收，不将静态已实现改写为运行通过。
- 原生源码链接指向本机私有反编译缓存；仓库只交付调查文字、类/方法名和必要调用说明，不提交游戏程序集或反编译原文。复现提取命令见第8节。Mod链接指向正常源码，行号以baseline快照为准；后续移动用类/方法名定位。

### 全局调用链

1. `MonsterModel.PerformMove → MoveState.PerformMove → _onPerform(targets) → 怪物具体Move`；[MoveState.PerformMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine/MoveState.cs#L55>)。Power调用则由原生`Hook`逐个调用模型；[Hook.AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Hooks/Hook.cs#L1020>)、[Hook.ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Hooks/Hook.cs#L2361>)。
2. [ModEntry](<../src/Volibear/ModEntry.cs#L19>)实际安装EnemyEffects/Hopper/Summon/Revival/Passive/Card/Dampen/Steam/PlayerStat/PlayerDebuff/EnemyStatus/Special/AdditionalRevival；不是仅测试探针调用。
3. `DomainEnemyEffects.ActiveFor`仅当前活战斗中存活玩家拥有领域时生效，特殊贡献压制全队共享；[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L31>)。附雷与抽牌净化仅持有者本人，[DomainPower](<../src/Volibear/Core/DomainPower.cs#L91>)。
4. Scalar贡献在Hook/Power准确函数边界改中性值；状态新增和被动力量/格挡在真实命令commit前决策；召唤/复活逐事务提交，已提交事实不回滚。普通怪物Move不整体跳过。

## 2. 已确认缺口与关键分步判定

| ID | baseline结论（保留） | 原生链与基线缺口 | 当前实现与依据 |
|---|---|---|---|
| G01a | **未实现：沙坑倒数冻结** | `TheInsatiable.LiquifyMove→SandpitPower.AfterSideTurnStartLate→PowerCmd.Decrement`仍减层，0层仍Remove/detach。当前只拦AfterRemoved payload。 | **已实现：倒计时冻结**。`DomainSandpitEffects.Install/Suppress`在`AfterSideTurnStartLate`入口阻止Decrement；退出后下一敌方回合只扣一次，不追补冻结期间次数。见[S1](#current-sandpit)。 |
| G01b | **未实现：角色/宠物移动抑制、进入恢复** | `AfterPowerAmountChanged / BeforeSideTurnEnd / AfterCreatureAddedToCombat / AfterOstyRevived → UpdateCreaturePositions → TweenProperty(global_position:x)`全部继续。进入领域无沙坑位置恢复入口。 | **已实现：后续玩家/宠物/Osty拉动冻结；已发生位移保留**。所有调用汇入`UpdateCreaturePositions`并在入口被拦。进入领域不把已经发生的位置变化倒带；这不是新增的归位玩法。见[S1](#current-sandpit)。 |
| G01c | **已实现：沙坑处决取消** | `PowerCmd.Remove→DomainEnemySpecialContributions.AfterRemoved`取消吃人动画、隐藏及玩家/Osty `Kill(force:true)`；不取消Remove本身，所以a/b不可算已实现。 | **已实现并保留：处决取消**。既有`DomainEnemySpecialContributions.AfterRemoved`继续拦吃人/隐藏/强制击杀；新倒数冻结使正常回合不再提前耗尽Sandpit。见[S1](#current-sandpit)。 |
| G02 | **未实现：已有Dampen降级进入领域恢复** | 新施加的`ledger.Add+CardCmd.Downgrade`已拦；进入前已执行降级不恢复。原生没有ShouldUpgrade禁止升级；`AfterRemoved`按旧等级升级，新增恢复必须防止双返还。 | **已实现：进入临时返还、退出撤回、原生移除防双返还**。`DomainDampenRestoration`按原账本记录每张牌借回升级量；`DomainPower`进入/退出及死亡刷新，`Dampen.AfterRemoved`前先撤回借回量。领域中新施加保留原降级账本，在每个CommitPair后立即借回升级；不是删除Dampen或清空账本。见[S2](#current-dampen)。 |
| G03 | **未实现：全部自身/无receipt已有debuff** | 六类PlayerDebuff白名单、四类Card白名单、有限stat/Tainted账本均按敌源归因；自身/卡源明确排除，无receipt回退原Amount。KnowledgeDemon四种选择伤害/减抽/限牌/减能量因此漏过。完整47类见第7节。 | **已实现：玩家减益贡献不再依赖敌源receipt**。知识恶魔四惩罚、伤害/格挡/费用/出牌/抽牌/能量、持续伤害/处决及属性补偿已接通；47类逐项见第7节当前列。仅怪物适用的Plow/Shriek仍按其敌方负面效果保留，不宣称玩家挂载适配。见[S3](#current-self)。 |
| G04 | **未实现：Hopper逃脱及其倒数** | `EscapeArtistPower.AfterSideTurnEnd→Decrement`；`ThievingHopper`状态机→`EscapeMove→CreatureCmd.Escape`不在偷牌适配内。 | **未实现**。现行Hopper适配仍只处理偷牌链；`EscapeArtistPower`倒数和`EscapeMove→Escape`没有领域gate。偷牌已实现不改变此结论。 |
| G05 | **未实现：木桩事件超时逃脱压制** | 三个BattleFriend→`BattlewornDummyTimeLimitPower.AfterSideTurnEnd→RanOutOfTime=true / Escape`无领域gate；这是正式事件计时规则，不从全类清单删除。 | **未实现**。三个BattleFriend事件超时倒数、`RanOutOfTime`与Escape没有领域gate，原事件流程继续。 |
| G06 | **未实现：TheForgotten偷敏捷的敌方收益** | `MiasmaMove`玩家-Dex、8Block、敌方+Dex是独立提交；仅玩家-Dex已拦。`DreadDamage`读敌方Dex增加基础伤害。已有及直接力量/格挡例外不等同于允许新+Dex收益。 | **未实现：敌方新获Dexterity收益取消**。玩家负Dex补偿已有，但`MiasmaMove`敌方+Dex和后续`DreadDamage`读取仍执行；直接Block按规则保留。 |
| G07 | **未实现：已有Shrink视觉恢复** | `ShrinkPower.AfterApplied→ScaleTo(0.5)`已经发生；现补丁只中和伤害倍率，没有进入时恢复比例。领域后原缩小/到期恢复与新领域灵体比例需组合而非互相覆盖。 | **已实现：Shrink伤害贡献及进入/退出尺度恢复**。`DomainSelfDebuffEffects.RefreshScales`在领域边界切换1/0.5，领域内新施加由`ShrinkApplied`恢复1；原到期移除保留。与灵体呈现的最终叠加效果尚未进行游戏视觉验收。见[S3](#current-self)。 |
| G08 | **未实现：全机制持续禁用标记/自身debuff悬停** | `PowerPresentationDomain.Suppressed`只接受敌方对象、发实际取消receipt；没有为每个受压制Power持续附加“已被领域禁用”描述的实现。当前动作反馈不等同于玩家自己debuff图标禁用。 | **已实现：玩家减益与已列明贡献的持续标识；未实现：未配置无图标贡献的全面持续标识**。37类enemy Power、8组无图标机制以及玩家减益通过4个原生UI入口显示动态禁用说明、暗化叉线与徽标。未配置的直接贡献仍只有已有取消反馈，不标为全机制持续覆盖。见[S4](#current-presentation)。 |

关键依据：[SandpitPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L58>)；[DomainEnemySpecialContributions](<../src/Volibear/Core/DomainEnemySpecialContributions.cs#L39>)；[DampenPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L29>)；[DomainDampenTransactions](<../src/Volibear/Core/DomainDampenTransactions.cs#L193>)；[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L129>)；[TheForgotten](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L24>)；[ShrinkPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L48>)；[PowerPresentationDomain](<../src/Volibear/Presentation/PowerPresentationDomain.cs#L41>)。

### 进入、持续、退出的 baseline 语义

- 已记录的敌方Weak/Frail/Vulnerable/Constrict/Chains/Shrink、Hex/Tangled/Smoggy/Ringing、属性负债：Power/affliction不删除，仅贡献临时屏蔽；原生到期继续。退出时仍存在的原Power恢复原生贡献。领域中新敌源六类debuff/stat负提交被取消，不排队在退出后补发。
- Dampen领域内首次降级不登记退款账；领域前已降级维持，领域结束也无专门动作。Hex只是虚无贡献静默，原Hexed标记保留，退出恢复虚无；来自其他来源的虚无保留。
- 已取消的复活/召唤/一次性收益不在领域退出补发；已完成出生/生命变动不倒带。沙坑当前反例是倒数消失但处决取消，非“冻结后续跑”。
- 当前无通用“自身debuff进入/退出”生命周期；G03与G08须配套补齐，不能删除全部Power来伪装能力恢复。

## 3. 范围清点：全部121个顶层怪物模型（基线；当前增量见第2、7节）

清点口径为锁版 `MegaCrit.Sts2.Core.Models.Monsters` 命名空间全部121个顶层类，含抽象分节基类、宠物、历史占位和原生测试模型，避免把仅遭遇图鉴表误当全集。原生 `ModelDb.Monsters` 本身仅 `Acts.SelectMany(AllMonsters).Distinct()`，所以本次范围是它的超集。[ModelDb.Monsters](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models/ModelDb.cs#L177>)。
每行的Power条目链接到第4节完整分步结论；原生文件可核对完整Move状态机。第5节补全部非Power出生/偷牌/塞牌/降级等路径。普通攻击和直接力量/格挡统一按第6节保留。下列编号稳定，修复时不可删行。

| 编号 | 游戏中文名 · 类/原生依据 | 全部特殊机制索引（含继承） | 非Power/范围说明 |
|---|---|---|---|
| M001 | 永世沙漏 · [Aeonglass](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L84>)；[StrengthPower](#p-strengthpower) ← [IncreasingIntensityMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L146>)；[WitheringPresencePower](#p-witheringpresencepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L80>) | IncreasingIntensityMove→Wither生成（已实现）。 |
| M002 | 建筑师 · [Architect](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Architect.cs>) | 无Power特殊贡献 | NOTHING隐藏空动作占位。 |
| M003 | 劫掠者刺客 · [AssassinRubyRaider](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/AssassinRubyRaider.cs>) | 无Power特殊贡献 | KillshotMove只是DamageCmd.Attack，普通攻击保留，不是强制处决。 |
| M004 | 劫掠者斧手 · [AxeRubyRaider](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/AxeRubyRaider.cs>) | 无Power特殊贡献 | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M005 | 巨斧机器人 · [Axebot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs>) | [FrailPower](#p-frailpower) ← [HammerUppercutMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L128>)；[StockPower](#p-stockpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L80>)；[StrengthPower](#p-strengthpower) ← [BootUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L108>)；[WeakPower](#p-weakpower) ← [HammerUppercutMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L127>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M006 | 战斗好伙伴V1.0 · [BattleFriendV1](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV1.cs>) | [BattlewornDummyTimeLimitPower](#p-battleworndummytimelimitpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV1.cs#L35>) | 事件木桩，超时倒数/逃脱未实现（G05）。 |
| M007 | 战斗好伙伴V2.0 · [BattleFriendV2](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV2.cs>) | [BattlewornDummyTimeLimitPower](#p-battleworndummytimelimitpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV2.cs#L35>) | 事件木桩，超时倒数/逃脱未实现（G05）。 |
| M008 | 战斗好伙伴V3.0 · [BattleFriendV3](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV3.cs>) | [BattlewornDummyTimeLimitPower](#p-battleworndummytimelimitpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV3.cs#L35>) | 事件木桩，超时倒数/逃脱未实现（G05）。 |
| M009 | 大型假人 · [BigDummy](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BigDummy.cs>) | 无Power特殊贡献 | 原生测试/空动作或固定普通攻击模型，不遗漏也不充当正式遭遇数量。 |
| M010 | 盛碗虫（卵） · [BowlbugEgg](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugEgg.cs>) | 无Power特殊贡献 | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M011 | 盛碗虫（蜜） · [BowlbugNectar](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugNectar.cs>) | [StrengthPower](#p-strengthpower) ← [BuffMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugNectar.cs#L69>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M012 | 盛碗虫（石） · [BowlbugRock](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugRock.cs>) | [ImbalancedPower](#p-imbalancedpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugRock.cs#L66>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M013 | 盛碗虫（丝） · [BowlbugSilk](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugSilk.cs>) | [WeakPower](#p-weakpower) ← [SpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugSilk.cs#L85>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M014 | 劫掠者暴徒 · [BruteRubyRaider](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BruteRubyRaider.cs>) | [StrengthPower](#p-strengthpower) ← [RoarMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BruteRubyRaider.cs#L52>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M015 | 旧日雕像 · [BygoneEffigy](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs>) | [SlowPower](#p-slowpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L37>)；[StrengthPower](#p-strengthpower) ← [WakeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L76>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M016 | 多尼斯异鸟 · [Byrdonis](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Byrdonis.cs>) | [TerritorialPower](#p-territorialpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Byrdonis.cs#L37>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M017 | 异鸟宝宝 · [Byrdpip](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Byrdpip.cs>) | 无Power特殊贡献 | 玩家宠物；不是领域敌方压制目标，保持原生。 |
| M018 | 钙化邪教徒 · [CalcifiedCultist](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CalcifiedCultist.cs>) | [RitualPower](#p-ritualpower) ← [IncantationMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CalcifiedCultist.cs#L83>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M019 | 仪式兽 · [CeremonialBeast](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs>) | [PlowPower](#p-plowpower) ← [StampMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L175>)；[RingingPower](#p-ringingpower) ← [BeastCryMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L229>)；[StrengthPower](#p-strengthpower) ← [PlowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L205>), [CrushMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L259>) | Plow受击次数/眩晕与去力量是敌方不利事实保留；Ringing限牌贡献已实现；Charge/Crush直接力量保留。 |
| M020 | 啃咬机 · [Chomper](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Chomper.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Chomper.cs#L52>) | ScreechMove→Dazed生成（已实现）。 |
| M021 | 噬尸蛞蝓 · [CorpseSlug](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs>) | [FrailPower](#p-frailpower) ← [GoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L132>)；[RavenousPower](#p-ravenouspower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L88>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M022 | 劫掠者弩手 · [CrossbowRubyRaider](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CrossbowRubyRaider.cs>) | 无Power特殊贡献 | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M023 | 碾碎爪 · [Crusher](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs>) | [BackAttackLeftPower](#p-backattackleftpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L117>)；[CrabRagePower](#p-crabragepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L118>)；[FrailPower](#p-frailpower) ← [BugStingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L168>)；[StrengthPower](#p-strengthpower) ← [AdaptMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L175>)；[WeakPower](#p-weakpower) ← [BugStingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L167>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M024 | 立柱构造体 · [CubexConstruct](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L91>)；[StrengthPower](#p-strengthpower) ← [ChargeUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L135>), [RepeaterBlastMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L147>) | IsBurrowed/IsCharging与CurrentHpChanged回调是动画/音频状态，原生不使用BurrowedPower；普通攻击与直接Strength/Block保留，Artifact单独压制。 |
| M025 | 潮湿邪教徒 · [DampCultist](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DampCultist.cs>) | [RitualPower](#p-ritualpower) ← [IncantationMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DampCultist.cs#L83>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M026 | 残杀千足虫 · [DecimillipedeSegment](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs>) | [ReattachPower](#p-reattachpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L143>)；[StrengthPower](#p-strengthpower) ← [BulkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L195>)；[WeakPower](#p-weakpower) ← [ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L204>) | 抽象分节基类，三个具体部件的动作/复活共同定义于此。 |
| M027 | 残杀千足虫（后节） · [DecimillipedeSegmentBack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegmentBack.cs>) | [ReattachPower](#p-reattachpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L143>)；[StrengthPower](#p-strengthpower) ← [BulkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L195>)；[WeakPower](#p-weakpower) ← [ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L204>) | 继承DecimillipedeSegment的全部动作/Power。 |
| M028 | 残杀千足虫（前节） · [DecimillipedeSegmentFront](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegmentFront.cs>) | [ReattachPower](#p-reattachpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L143>)；[StrengthPower](#p-strengthpower) ← [BulkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L195>)；[WeakPower](#p-weakpower) ← [ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L204>) | 继承DecimillipedeSegment的全部动作/Power。 |
| M029 | 残杀千足虫（中节） · [DecimillipedeSegmentMiddle](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegmentMiddle.cs>) | [ReattachPower](#p-reattachpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L143>)；[StrengthPower](#p-strengthpower) ← [BulkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L195>)；[WeakPower](#p-weakpower) ← [ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L204>) | 继承DecimillipedeSegment的全部动作/Power。 |
| M030 | 已弃用怪物 · [DeprecatedMonster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DeprecatedMonster.cs>) | 无Power特殊贡献 | 已删除怪物的历史占位；STUB空动作。 |
| M031 | 虔诚雕刻师 · [DevotedSculptor](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DevotedSculptor.cs>) | [RitualPower](#p-ritualpower) ← [ForbiddenIncantationMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DevotedSculptor.cs#L50>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M032 | 蜂群术士 · [Entomancer](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs>) | [PersonalHivePower](#p-personalhivepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L38>), [SpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L62>)；[StrengthPower](#p-strengthpower) ← [SpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L63>), [SpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L67>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M033 | 外骨骼虫 · [Exoskeleton](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs>) | [HardToKillPower](#p-hardtokillpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs#L49>)；[StrengthPower](#p-strengthpower) ← [EnrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs#L99>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M034 | 利齿之眼 · [EyeWithTeeth](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/EyeWithTeeth.cs>) | [IllusionPower](#p-illusionpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/EyeWithTeeth.cs#L33>) | DistractMove→Dazed生成（已实现）。 |
| M035 | 组装师 · [Fabricator](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs>) | [MinionPower](#p-minionpower) ← [SpawnBot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L116>) | FabricateMove/FabricatingStrikeMove→SpawnBot→CreatureCmd.Add的出生提交已实现；FabricatingStrike普通攻击保留。初始布场和已出生机器人保留。 |
| M036 | 商人？？？ · [FakeMerchantMonster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs>) | [FrailPower](#p-frailpower) ← [ThrowRelicMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs#L102>)；[StrengthPower](#p-strengthpower) ← [EnrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs#L109>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M037 | 胖地精 · [FatGremlin](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FatGremlin.cs>) | [HeistPower](#p-heistpower) | FleeMove入口在ToggleIsInteractable/播放逃跑前被DomainEnemySpecialContributions.Flee取消：已实现。Heist死亡返金保留。 |
| M038 | 连枷骑士 · [FlailKnight](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FlailKnight.cs>) | [StrengthPower](#p-strengthpower) ← [WarChantMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FlailKnight.cs#L63>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M039 | 飞蝇菌子 · [Flyconid](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Flyconid.cs>) | [FrailPower](#p-frailpower) ← [FrailSporesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Flyconid.cs#L74>)；[VulnerablePower](#p-vulnerablepower) ← [VulnerableSporesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Flyconid.cs#L60>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M040 | 雾菇 · [Fogmog](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fogmog.cs>) | [StrengthPower](#p-strengthpower) ← [SwipeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fogmog.cs#L76>) | IllusionMove→Add<EyeWithTeeth>已实现取消；普通攻击/直接力量保留。 |
| M041 | 化石追踪者 · [FossilStalker](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs>) | [FrailPower](#p-frailpower) ← [TackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs#L74>)；[SuckPower](#p-suckpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs#L48>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M042 | 青蛙骑士 · [FrogKnight](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs>) | [FrailPower](#p-frailpower) ← [TongueLashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L110>)；[PlatingPower](#p-platingpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L63>)；[StrengthPower](#p-strengthpower) ← [ForTheQueenMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L93>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M043 | 毛绒伏地虫 · [FuzzyWurmCrawler](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FuzzyWurmCrawler.cs>) | [StrengthPower](#p-strengthpower) ← [Inhale](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FuzzyWurmCrawler.cs#L88>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M044 | 气态炸弹 · [GasBomb](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GasBomb.cs>) | [MinionPower](#p-minionpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GasBomb.cs#L56>) | ExplodeMove是普通DamageCmd.Attack后Kill自己；攻击和自杀清理原生保留，不把普通爆炸攻击误当WaterfallGiant死亡爆炸保护阶段。 |
| M045 | 电球头 · [GlobeHead](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs>) | [FrailPower](#p-frailpower) ← [ShockingSlap](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L78>)；[GalvanicPower](#p-galvanicpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L44>)；[StrengthPower](#p-strengthpower) ← [GalvanicBurstMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L86>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M046 | 地精佣兵 · [GremlinMerc](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs>) | [StrengthPower](#p-strengthpower) ← [HeheMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L122>)；[SurprisePower](#p-surprisepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L49>)；[ThieveryPower](#p-thieverypower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L52>)；[WeakPower](#p-weakpower) ← [DoubleSmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L109>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M047 | 守护机器人 · [Guardbot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Guardbot.cs>) | 无Power特殊贡献 | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M048 | 幽灵船 · [HauntedShip](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HauntedShip.cs>) | [WeakPower](#p-weakpower) ← [HauntMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HauntedShip.cs#L79>) | HauntMove→Dazed生成（已实现）。 |
| M049 | 猎人杀手 · [HunterKiller](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HunterKiller.cs>) | [TenderPower](#p-tenderpower) ← [GoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HunterKiller.cs#L55>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M050 | 感染棱柱 · [InfestedPrism](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs>) | [VitalSparkPower](#p-vitalsparkpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L59>), [PulsateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L114>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M051 | 墨宝 · [Inklet](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Inklet.cs>) | [SlipperyPower](#p-slipperypower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Inklet.cs#L60>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M052 | 同族信徒 · [KinFollower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs>) | [MinionPower](#p-minionpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs#L101>)；[StrengthPower](#p-strengthpower) ← [PowerDanceMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs#L132>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M053 | 同族神官 · [KinPriest](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs>) | [FrailPower](#p-frailpower) ← [OrbOfFrailtyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L136>)；[StrengthPower](#p-strengthpower) ← [RitualMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L173>)；[WeakPower](#p-weakpower) ← [OrbOfWeaknessMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L146>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M054 | 知识恶魔 · [KnowledgeDemon](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs>) | [DisintegrationPower](#p-disintegrationpower)；[MindRotPower](#p-mindrotpower)；[SlothPower](#p-slothpower)；[StrengthPower](#p-strengthpower) ← [PonderMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L218>)；[WasteAwayPower](#p-wasteawaypower) | CurseOfKnowledge→ChooseCurse→OnChosen的Disintegration/MindRot/Sloth/WasteAway四类未实现；选择界面/计次照常。PonderMove普通攻击/直接Strength保留，30×玩家数Heal已实现取消。 |
| M055 | 乐加维林族母 · [LagavulinMatriarch](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs>) | [AsleepPower](#p-asleeppower) ← [Sleep](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L120>)；[DexterityPower](#p-dexteritypower) ← [SoulSiphonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L241>)；[PlatingPower](#p-platingpower) ← [Sleep](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L119>)；[StrengthPower](#p-strengthpower) ← [SoulSiphonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L240>), [SoulSiphonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L242>) | 生命阈值IsShellAwake、WakeUpMove/睡眠状态机保留；SiphonSoul的玩家-Strength/-Dex已实现抵消，敌方直接Strength保留。 |
| M056 | 树叶史莱姆（中） · [LeafSlimeM](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeM.cs>) | 无Power特殊贡献 | StickyShotMove→Slimed生成（已实现）。 |
| M057 | 树叶史莱姆（小） · [LeafSlimeS](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeS.cs>) | 无Power特殊贡献 | GoopMove→Slimed生成（已实现）。 |
| M058 | 活雾 · [LivingFog](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingFog.cs>) | [SmoggyPower](#p-smoggypower) ← [AdvancedGasMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingFog.cs#L82>) | BloatMove→Add<GasBomb>已实现，后续普通攻击继续；Smoggy单独处理。 |
| M059 | 活体盾 · [LivingShield](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs>) | [RampartPower](#p-rampartpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs#L35>)；[StrengthPower](#p-strengthpower) ← [SmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs#L68>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M060 | 虱虫之祖 · [LouseProgenitor](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs>) | [CurlUpPower](#p-curluppower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L70>)；[FrailPower](#p-frailpower) ← [WebMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L99>)；[StrengthPower](#p-strengthpower) ← [CurlAndGrowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L107>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M061 | 魔法骑士 · [MagiKnight](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs>) | [DampenPower](#p-dampenpower) ← [DampenMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs#L86>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M062 | 蛮兽 · [Mawler](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Mawler.cs>) | [VulnerablePower](#p-vulnerablepower) ← [RoarMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Mawler.cs#L57>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M063 | 机甲骑士 · [MechaKnight](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L76>)；[StrengthPower](#p-strengthpower) ← [WindupMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L129>) | FlamethrowerMove→Burn生成（已实现）。 |
| M064 | [MultiAttackMoveMonster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MultiAttackMoveMonster.cs>) | 无Power特殊贡献 | 原生测试/空动作或固定普通攻击模型，不遗漏也不充当正式遭遇数量。 |
| M065 | 神秘骑士 · [MysteriousKnight](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MysteriousKnight.cs>) | [PlatingPower](#p-platingpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MysteriousKnight.cs#L14>)；[StrengthPower](#p-strengthpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MysteriousKnight.cs#L13>), [WarChantMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FlailKnight.cs#L63>) | 继承FlailKnight的全部动作/Power。 |
| M066 | 异螨 · [Myte](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Myte.cs>) | [StrengthPower](#p-strengthpower) ← [SuckMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Myte.cs#L94>) | ToxicMove→Toxic生成（已实现）。 |
| M067 | 小啃兽 · [Nibbit](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Nibbit.cs>) | [StrengthPower](#p-strengthpower) ← [HissMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Nibbit.cs#L114>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M068 | 噪音机器人 · [Noisebot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Noisebot.cs>) | 无Power特殊贡献 | NoiseMove→Dazed生成（已实现）。 |
| M069 | [OneHpMonster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OneHpMonster.cs>) | 无Power特殊贡献 | 原生测试/空动作或固定普通攻击模型，不遗漏也不充当正式遭遇数量。 |
| M070 | 奥斯提 · [Osty](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Osty.cs>) | 无Power特殊贡献 | 玩家宠物；不是领域敌方压制目标，保持原生。 |
| M071 | 直飞产卵虫 · [Ovicopter](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs>) | [MinionPower](#p-minionpower) ← [LayEggsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L91>)；[StrengthPower](#p-strengthpower) ← [NutritionalPasteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L100>)；[VulnerablePower](#p-vulnerablepower) ← [TenderizerMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L117>) | LayEggsMove→CreatureCmd.Add<ToughEgg>及仅新生目标Minion初始化已实现取消；直接Strength/普通攻击保留。 |
| M072 | 猫头鹰法官 · [OwlMagistrate](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs>) | [SoarPower](#p-soarpower) ← [JudicialFlightMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs#L134>)；[VulnerablePower](#p-vulnerablepower) ← [VerdictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs#L145>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M073 | 佩尔的士兵 · [PaelsLegion](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PaelsLegion.cs>) | 无Power特殊贡献 | 玩家宠物；不是领域敌方压制目标，保持原生。 |
| M074 | 寄生惧魔 · [Parafright](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Parafright.cs>) | [IllusionPower](#p-illusionpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Parafright.cs#L38>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M075 | 花园幽灵鳗 · [PhantasmalGardener](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs>) | [SkittishPower](#p-skittishpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L92>)；[StrengthPower](#p-strengthpower) ← [EnlargeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L151>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M076 | 异蛙寄生虫 · [PhrogParasite](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhrogParasite.cs>) | [InfestedPower](#p-infestedpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhrogParasite.cs#L36>) | InfectMove→Infection生成（已实现）。 |
| M077 | 拳击构装体 · [PunchConstruct](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs#L74>)；[FrailPower](#p-frailpower) ← [FastPunchMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs#L118>) | AfterAddedToRoom起始减血SetCurrentHpInternal是布场事实保留；其后Artifact单独压制。 |
| M078 | 女王 · [Queen](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs>) | [ChainsOfBindingPower](#p-chainsofbindingpower) ← [PuppetStringsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L168>)；[FrailPower](#p-frailpower) ← [YoureMineMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L177>)；[StrengthPower](#p-strengthpower) ← [BurnBrightForMeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L190>), [EnrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L218>)；[VulnerablePower](#p-vulnerablepower) ← [YoureMineMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L179>)；[WeakPower](#p-weakpower) ← [YoureMineMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L178>) | ExecutionMove只是DamageCmd.Attack，普通攻击保留，不是force Kill；ChainsOfBinding与99层三debuff分别处理。 |
| M079 | 火箭 · [Rocket](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs>) | [BackAttackRightPower](#p-backattackrightpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L94>)；[CrabRagePower](#p-crabragepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L95>)；[StrengthPower](#p-strengthpower) ← [ChargeUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L157>)；[SurroundedPower](#p-surroundedpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L93>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M080 | 咬人卷轴 · [ScrollOfBiting](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs>) | [PaperCutsPower](#p-papercutspower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs#L76>)；[StrengthPower](#p-strengthpower) ← [MoreTeethMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs#L125>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M081 | 海洋混混 · [Seapunk](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Seapunk.cs>) | [StrengthPower](#p-strengthpower) ← [BubbleBurpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Seapunk.cs#L89>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M082 | 下水道蚌 · [SewerClam](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SewerClam.cs>) | [PlatingPower](#p-platingpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SewerClam.cs#L33>)；[StrengthPower](#p-strengthpower) ← [PressurizeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SewerClam.cs#L51>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M083 | 缩小甲虫 · [ShrinkerBeetle](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ShrinkerBeetle.cs>) | [ShrinkPower](#p-shrinkpower) ← [ShrinkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ShrinkerBeetle.cs#L51>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M084 | [SingleAttackMoveMonster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SingleAttackMoveMonster.cs>) | 无Power特殊贡献 | 原生测试/空动作或固定普通攻击模型，不遗漏也不充当正式遭遇数量。 |
| M085 | 鬼祟珊瑚群 · [SkulkingColony](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs>) | [HardenedShellPower](#p-hardenedshellpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs#L56>)；[StrengthPower](#p-strengthpower) ← [InertiaMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs#L83>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M086 | 史莱姆狂战士 · [SlimedBerserker](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs>) | [StrengthPower](#p-strengthpower) ← [LeechingHugMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L78>)；[WeakPower](#p-weakpower) ← [LeechingHugMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L77>) | LeechingHugMove原生Weak的applier为null；DomainPlayerDebuffContributions.NullSource.BerserkerWeak在确切调用点建立临时上下文归因，故敌源Weak已实现，不是漏过null来源。VomitIchor塞牌分别处理。VomitIchorMove→Slimed生成（已实现）。 |
| M087 | 蛇行扼杀者 · [SlitheringStrangler](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlitheringStrangler.cs>) | [ConstrictPower](#p-constrictpower) ← [ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlitheringStrangler.cs#L61>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M088 | 淤泥旋螺 · [SludgeSpinner](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SludgeSpinner.cs>) | [StrengthPower](#p-strengthpower) ← [RageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SludgeSpinner.cs#L78>)；[WeakPower](#p-weakpower) ← [OilSprayMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SludgeSpinner.cs#L61>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M089 | 熟睡甲虫 · [SlumberingBeetle](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs>) | [PlatingPower](#p-platingpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L76>)；[SlumberPower](#p-slumberpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L77>)；[StrengthPower](#p-strengthpower) ← [RolloutMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L146>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M090 | 闪光贾克斯果 · [SnappingJaxfruit](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SnappingJaxfruit.cs>) | [StrengthPower](#p-strengthpower) ← [EnergyOrb](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SnappingJaxfruit.cs#L66>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M091 | 卑鄙地精 · [SneakyGremlin](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SneakyGremlin.cs>) | 无Power特殊贡献 | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M092 | 灵魂异鱼 · [SoulFysh](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs>) | [IntangiblePower](#p-intangiblepower) ← [FadeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L203>)；[VulnerablePower](#p-vulnerablepower) ← [ScreamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L193>) | BeckonMove→Beckon生成（已实现）；GazeMove→Beckon生成（已实现）。 |
| M093 | 灵魂枢纽 · [SoulNexus](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs>) | [VulnerablePower](#p-vulnerablepower) ← [DrainLifeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L103>)；[WeakPower](#p-weakpower) ← [DrainLifeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L104>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M094 | 幽灵骑士 · [SpectralKnight](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpectralKnight.cs>) | [HexPower](#p-hexpower) ← [HexMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpectralKnight.cs#L67>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M095 | 棘刺蟾蜍 · [SpinyToad](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs>) | [ThornsPower](#p-thornspower) ← [SpikesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs#L82>), [ExplosionMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs#L92>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M096 | 戳刺机器人 · [Stabbot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Stabbot.cs>) | [FrailPower](#p-frailpower) ← [StabMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Stabbot.cs#L54>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M097 | [TenHpMonster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TenHpMonster.cs>) | 无Power特殊贡献 | 原生测试/空动作或固定普通攻击模型，不遗漏也不充当正式遭遇数量。 |
| M098 | 骇鳗 · [TerrorEel](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs>) | [ShriekPower](#p-shriekpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L65>)；[VigorPower](#p-vigorpower) ← [ThrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L102>)；[VulnerablePower](#p-vulnerablepower) ← [TerrorMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L117>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M099 | 实验体 #C{Count} · [TestSubject](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs>) | [AdaptablePower](#p-adaptablepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L177>)；[EnragePower](#p-enragepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L178>)；[IntangiblePower](#p-intangiblepower)；[NemesisPower](#p-nemesispower) ← [RespawnMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L274>)；[PainfulStabsPower](#p-painfulstabspower) ← [RespawnMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L270>)；[StrengthPower](#p-strengthpower) ← [BurningGrowlMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L332>)；[VulnerablePower](#p-vulnerablepower) ← [SkullBashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L296>) | 不是测试占位：Adaptable→TriggerDead→RespawnMove→Revive阶段复活已实现；Burn塞牌、Enrage被动力量、Nemesis无实体、Vulnerable分别处理。BurningGrowlMove→Burn生成（已实现）。 |
| M100 | 对手1型 · [TheAdversaryMkOne](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs#L32>)；[StrengthPower](#p-strengthpower) ← [BarrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs#L73>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M101 | 对手3型 · [TheAdversaryMkThree](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs#L34>)；[StrengthPower](#p-strengthpower) ← [BarrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs#L75>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M102 | 对手2型 · [TheAdversaryMkTwo](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs>) | [ArtifactPower](#p-artifactpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs#L36>)；[StrengthPower](#p-strengthpower) ← [BarrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs#L77>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M103 | 遗忘之物 · [TheForgotten](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs>) | [DexterityPower](#p-dexteritypower) ← [MiasmaMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L57>), [MiasmaMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L59>)；[PossessSpeedPower](#p-possessspeedpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L39>) | MiasmaMove玩家-Dex已实现；8Block保留；敌方+Dex未实现压制，DreadDamage直接读该Dex（G06）。 |
| M104 | 无厌沙虫 · [TheInsatiable](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs>) | [SandpitPower](#p-sandpitpower) ← [LiquifyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L123>)；[StrengthPower](#p-strengthpower) ← [SalivateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L170>) | LiquifyMove生成6张FranticEscape仍原生；这是玩家延长沙坑的可打状态牌（OnPlay→ModifyAmount +1、费用+1），不是未列出的强制处决。自己的领域抽到状态/诅咒时仍按DomainPower.AfterCardDrawnEarly净化。沙坑细分见G01。 |
| M105 | 失落之物 · [TheLost](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs>) | [PossessStrengthPower](#p-possessstrengthpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs#L33>)；[StrengthPower](#p-strengthpower) ← [DebilitatingSmogMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs#L51>), [DebilitatingSmogMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs#L52>) | MiasmaMove玩家-Strength已实现；敌方直接+Strength按冻结边界保留；死亡返还走Possess。 |
| M106 | 胧光怪 · [TheObscura](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheObscura.cs>) | [StrengthPower](#p-strengthpower) ← [WailMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheObscura.cs#L101>) | IllusionMove→Add<Parafright>已实现取消；WailMove直接力量和HardeningStrike直接格挡保留。 |
| M107 | 偷窃草蜢 · [ThievingHopper](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs>) | [EscapeArtistPower](#p-escapeartistpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L155>)；[FlutterPower](#p-flutterpower) ← [FlutterMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L273>)；[SwipePower](#p-swipepower) ← [ThieveryMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L241>) | ThieveryMove的新偷牌已实现；EscapeMove逃脱未实现（G04）。Flutter的减伤已实现，受击扣层/眩晕保留。 |
| M108 | 蟾蜍蝌蚪 · [Toadpole](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Toadpole.cs>) | [ThornsPower](#p-thornspower) ← [SpikeSpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Toadpole.cs#L90>), [SpikenMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Toadpole.cs#L110>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M109 | 火炬头聚合体 · [TorchHeadAmalgam](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs>) | [MinionPower](#p-minionpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs#L43>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M110 | 结实的卵 · [ToughEgg](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ToughEgg.cs>) | [HatchPower](#p-hatchpower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ToughEgg.cs#L134>)；[MinionPower](#p-minionpower) | HatchMove→移除旧Power→Hatch→SetMaxAndCurrentHp：正HP/MaxHP和清除自身debuff已实现压制；孵化外观/状态、HatchPower倒数、后续Nibble攻击仍原生保留，不能写成整段Hatch被跳过。 |
| M111 | 劫掠者追踪手 · [TrackerRubyRaider](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TrackerRubyRaider.cs>) | [FrailPower](#p-frailpower) ← [TrackMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TrackerRubyRaider.cs#L44>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M112 | 地道虫 · [Tunneler](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs>) | [BurrowedPower](#p-burrowedpower) ← [BurrowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs#L99>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M113 | 高塔炮手 · [TurretOperator](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TurretOperator.cs>) | [StrengthPower](#p-strengthpower) ← [ReloadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TurretOperator.cs#L54>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M114 | 树枝史莱姆（中） · [TwigSlimeM](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwigSlimeM.cs>) | 无Power特殊贡献 | StickyShotMove→Slimed生成（已实现）。 |
| M115 | 树枝史莱姆（小） · [TwigSlimeS](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwigSlimeS.cs>) | 无Power特殊贡献 | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |
| M116 | 双尾鼠 · [TwoTailedRat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs>) | [FrailPower](#p-frailpower) ← [ScreechMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L169>) | CallForBackup→Add<TwoTailedRat>已实现取消；HasSummoned/轮次事实保留。 |
| M117 | 墨影幻灵 · [Vantom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs>) | [SlipperyPower](#p-slipperypower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L94>)；[StrengthPower](#p-strengthpower) ← [PrepareMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L195>) | DismemberMove→Wound生成（已实现）。 |
| M118 | 藤蔓蹒跚者 · [VineShambler](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/VineShambler.cs>) | [TangledPower](#p-tangledpower) ← [GraspingVinesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/VineShambler.cs#L67>) | 源码字符串“SwipePower”是动画trigger，不是偷牌Power；只有Tangled与普通攻击。 |
| M119 | 瀑布巨兽 · [WaterfallGiant](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs>) | [SteamEruptionPower](#p-steameruptionpower) ← [PressurizeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L228>), [PressureUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L238>), [StompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L249>), [RamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L259>), [SiphonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L268>), [PressureGunMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L279>)；[WeakPower](#p-weakpower) ← [StompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L248>) | 普通压力攻击和其数值递增保留；SiphonMove活体Heal已实现取消；Steam死亡爆炸保护事务已实现，见Power条目。 |
| M120 | 扭动虫 · [Wriggler](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Wriggler.cs>) | [StrengthPower](#p-strengthpower) ← [WriggleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Wriggler.cs#L100>) | WriggleMove→Infection生成（已实现）。 |
| M121 | 电击机器人 · [Zapbot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Zapbot.cs>) | [HighVoltagePower](#p-highvoltagepower) ← [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Zapbot.cs#L37>) | 其余为普通攻击/直接力量格挡、AI选择和呈现；保留原生。 |

完整性合计：**121/121** 个顶层类；本表机制实际引用 **72** 个Power类（含KnowledgeDemon选择链、FatGremlin金币载体补入），另列Reflect公共防护适配。字符串动画`SwipePower`已排除为伪Power引用，分节/Flail继承已展开。

## 4. 逐Power贡献：触发函数、领域边界与基线明确结论

每项链路：第3节怪物的初始化/Move → `PowerCmd.Apply`（或原生既有Power）→ 下列原生hook → 对应Mod边界。所有生命周期/计数/清理hook列出供交叉核对；“已实现”只针对描述中的有利贡献，不声称整个Power被删除。

<a id="p-adaptablepower"></a>
### AdaptablePower — 已实现

- 原生函数：[DoRevive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AdaptablePower.cs#L27>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AdaptablePower.cs#L32>), [ShouldAllowHitting](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AdaptablePower.cs#L44>), [ShouldStopCombatFromEnding](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AdaptablePower.cs#L53>), [ShouldCreatureBeRemovedFromCombatAfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AdaptablePower.cs#L58>), [ShouldPowerBeRemovedAfterOwnerDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AdaptablePower.cs#L67>)。
- 分步结论：Axebot死亡后的新机器人Add与TestSubject Respawn/Revive的回血、阶段保护和死亡投票精确取消；保留已落地对象及必要清理。
- Mod依据：[DomainAdditionalRevivalEffects.Patches](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs#L33>)。

<a id="p-artifactpower"></a>
### ArtifactPower — 已实现

- 原生函数：[TryModifyPowerAmountReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ArtifactPower.cs#L17>), [AfterModifyingPowerAmountReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ArtifactPower.cs#L38>), [GetScaledAmountForMultiplayer](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ArtifactPower.cs#L43>)。
- 分步结论：TryModifyPowerAmountReceived的敌方负面抵消否决取消，保持实际debuff施加；未宣称直接删除Artifact Amount。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L88>)。

<a id="p-asleeppower"></a>
### AsleepPower — 已实现（保留敌方不利/生命周期）

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AsleepPower.cs#L21>), [BeforeSideTurnEndVeryEarly](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AsleepPower.cs#L38>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/AsleepPower.cs#L46>)。
- 分步结论：睡眠、受到伤害醒来、自然倒数、眩晕与去除Plating按原生保留；有利护甲的GainBlock已单独由Plating路径屏蔽。
- Mod依据：原生不利/清理保留；[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L122>)。

<a id="p-backattackleftpower"></a>
### BackAttackLeftPower — 已实现（保留标记）

- 原生函数：[BackAttackLeftPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BackAttackLeftPower.cs>)（仅身份/标记属性，无行为函数）。
- 分步结论：无独立伤害hook；提供Surrounded左右朝向事实，不应删除整个标记。实际1.5倍率由Surrounded贡献屏蔽。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L157>)。

<a id="p-backattackrightpower"></a>
### BackAttackRightPower — 已实现（保留标记）

- 原生函数：[BackAttackRightPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BackAttackRightPower.cs>)（仅身份/标记属性，无行为函数）。
- 分步结论：无独立伤害hook；提供Surrounded左右朝向事实，不应删除整个标记。实际1.5倍率由Surrounded贡献屏蔽。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L157>)。

<a id="p-battleworndummytimelimitpower"></a>
### BattlewornDummyTimeLimitPower — 未实现（事件倒数及超时逃脱）

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BattlewornDummyTimeLimitPower.cs#L19>)。
- 分步结论：三个BattleFriend相同：AfterSideTurnEnd减量，最后写BattlewornDummyEventEncounter.RanOutOfTime并Escape。事件结算规则明确保留在调查范围，不能当普通野怪偷跑而隐去。
- Mod依据：baseline无此类/方法领域适配。

<a id="p-burrowedpower"></a>
### BurrowedPower — 已实现

- 原生函数：[ShouldClearBlock](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BurrowedPower.cs#L15>), [AfterBlockBroken](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BurrowedPower.cs#L24>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BurrowedPower.cs#L38>)。
- 分步结论：ShouldClearBlock的保留格挡否决解除；已有/本次直接获得格挡不清零。破盾眩晕、移除Power及LoseBlock清理仍原生。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L169>)。

<a id="p-chainsofbindingpower"></a>
### ChainsOfBindingPower — 已实现（敌源）；未实现（任意自身来源）

- **当前增量**：已实现：Bound附着贡献与ShouldPlay否决均按自身减益判定解除；原出牌记录及回合清除保留。[S3](#current-self)。

- 原生函数：[AfterCardDrawn](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L36>), [BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L48>), [ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L67>), [BeforeSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L80>)。
- 分步结论：抽牌Bound附着与ShouldPlay否决分别屏蔽；BeforeCardPlayed事实和回合末ClearAffliction保留；已有敌源限制可恢复出牌。非敌源/无receipt实例不处理。
- Mod依据：[DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L33>)。

<a id="p-constrictpower"></a>
### ConstrictPower — 已实现（敌源）；未实现（任意自身来源）

- **当前增量**：已实现：伤害读取有效量0；新施加保留Power，原计时/施加者死亡清理继续。[S3](#current-self)。

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConstrictPower.cs#L19>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConstrictPower.cs#L27>)。
- 分步结论：新增commit取消；已有敌源AfterSideTurnEnd的Damage只用有效量，原Power与施加者死亡清理不删；非敌源不处理。
- Mod依据：[DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L178>)。

<a id="p-crabragepower"></a>
### CrabRagePower — 已实现

- 原生函数：[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/CrabRagePower.cs#L31>)。
- 分步结论：同伴死亡时Strength和GainBlock两个收益分别取消；一次性Power移除仍执行。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L118>)。

<a id="p-curluppower"></a>
### CurlUpPower — 已实现

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/CurlUpPower.cs#L34>), [AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/CurlUpPower.cs#L56>)。
- 分步结论：只屏蔽被动GainBlock；Plating两条时机都覆盖，原减层/清理保留；CurlUp和Skittish触发登记及回合事实不整段吞掉。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L121>)。

<a id="p-dampenpower"></a>
### DampenPower — 已实现（领域内初次降级）；未实现（进入前已降级恢复）

- **当前增量**：已实现：按原账本临时返还被降级量；退出撤回借回量，原生移除先撤回后返还，避免双升级。[S2](#current-dampen)。

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L29>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L41>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L58>), [AddCaster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L73>)。
- 分步结论：MagiKnight.DampenMove→AddCaster→Apply→AfterApplied→ledger.Add+CardCmd.Downgrade配对拦截。既有降级没有进入恢复；AfterRemoved只在施加者均死亡/原生移除时Upgrade。不是禁止ShouldUpgrade；详见G02。
- Mod依据：[DomainDampenTransactions](<../src/Volibear/Core/DomainDampenTransactions.cs#L193>)。

<a id="p-dexteritypower"></a>
### DexterityPower — 已实现（已记录敌源玩家减值）；保留（直接敌方力量）；未实现（自身负值/敌方偷敏捷收益）

- 原生函数：[ModifyBlockAdditive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DexterityPower.cs#L20>)。
- 分步结论：玩家敌源负提交取消，已有StrengthDebt/DexterityDebt以DomainPower additive贡献补偿，不改原Amount；Tender/Possess返还只结算实际欠账。玩家自己施加负值不补偿。TheForgotten敌方+Dexterity独立提交仍发生，见G06；直接力量、格挡按规则保留。
- Mod依据：[DomainPlayerStatContributions](<../src/Volibear/Core/DomainPlayerStatContributions.cs#L40>)；[DomainPlayerStatContributions.Possess](<../src/Volibear/Core/DomainPlayerStatContributions.Possess.cs#L68>)。

<a id="p-disintegrationpower"></a>
### DisintegrationPower — 未实现

- **当前增量**：已实现：准确Damage调用点按自身减益判定取消，混合回调的计数/递减/移除继续执行。[S3](#current-self)。

- 原生函数：[AfterSideTurnEndLate](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DisintegrationPower.cs#L19>)。
- 分步结论：KnowledgeDemon.ChooseCurse→IChoosable.OnChosen以玩家和所选卡作为来源；分别持续伤害、减抽牌、限出牌、减最大能量；当前敌源白名单与通用领域hooks均不覆盖。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L67>)。

<a id="p-enragepower"></a>
### EnragePower — 已实现

- 原生函数：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/EnragePower.cs#L15>)。
- 分步结论：只包装该Power原生hook里的正Strength提交，在真实PowerCmd commit再检查领域；普通攻击/当前Strength/直接Strength不变。Ravenous吞食眩晕、计数/标志事实与移除保留。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L107>)。

<a id="p-escapeartistpower"></a>
### EscapeArtistPower — 未实现（逃脱倒数及逃脱）

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/EscapeArtistPower.cs#L21>)。
- 分步结论：AfterSideTurnEnd继续Decrement；Hopper的条件分支仍进入EscapeMove→CreatureCmd.Escape；偷牌patch不覆盖这一链。
- Mod依据：[DomainHopperEffects](<../src/Volibear/Core/DomainHopperEffects.cs#L21>)。

<a id="p-flutterpower"></a>
### FlutterPower — 已实现

- 原生函数：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlutterPower.cs#L26>), [AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlutterPower.cs#L39>), [StunnedMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlutterPower.cs#L57>)。
- 分步结论：ModifyDamageMultiplicative的敌方减伤归1；Flutter受击扣层、耗尽眩晕保留；Soar原生移除保留。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L137>)。

<a id="p-frailpower"></a>
### FrailPower — 已实现（敌源）；未实现（任意自身来源）

- **当前增量**：已实现：`BlockMultiplier`将玩家减益格挡倍率置1，原回合到期保留。[S3](#current-self)。

- 原生函数：[ModifyBlockMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FrailPower.cs#L22>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FrailPower.cs#L35>)。
- 分步结论：敌源新增在PowerCmd真实commit前取消；进入前已记录敌源层在伤害/格挡Hook调用点使用retained反事实量；持续时间、敌方自身负面效果和退出后剩余原Amount保留。自身/卡源与无receipt旧实例不压制。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L29>)。

<a id="p-galvanicpower"></a>
### GalvanicPower — 已实现

- 原生函数：[BeforeCombatStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/GalvanicPower.cs#L26>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/GalvanicPower.cs#L42>), [AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/GalvanicPower.cs#L50>)。
- 分步结论：BeforeCombatStart/AfterCardEnteredCombat的Galvanized附着，以及AfterCardPlayed的非攻击电伤分别屏蔽，保留基础攻击。
- Mod依据：[DomainEnemyStatusContributions.PowerEffects](<../src/Volibear/Core/DomainEnemyStatusContributions.PowerEffects.cs#L34>)。

<a id="p-hardtokillpower"></a>
### HardToKillPower — 已实现

- 原生函数：[ModifyDamageCap](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HardToKillPower.cs#L14>), [AfterModifyingDamageAmount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HardToKillPower.cs#L23>)。
- 分步结论：分别解除原生伤害上限/HP损失截断；HardenedShell逐回合窗口只补被压制的额度事实；Slippery受击扣层、Intangible到期、Shell真实伤害记账不吞。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L180>)。

<a id="p-hardenedshellpower"></a>
### HardenedShellPower — 已实现

- 原生函数：[ModifyHpLostBeforeOstyLate](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HardenedShellPower.cs#L32>), [AfterModifyingHpLostBeforeOsty](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HardenedShellPower.cs#L45>), [AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HardenedShellPower.cs#L51>), [BeforeSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HardenedShellPower.cs#L71>)。
- 分步结论：分别解除原生伤害上限/HP损失截断；HardenedShell逐回合窗口只补被压制的额度事实；Slippery受击扣层、Intangible到期、Shell真实伤害记账不吞。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L180>)。

<a id="p-hatchpower"></a>
### HatchPower — 已实现（孵化收益）；保留（计数/阶段事实）

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HatchPower.cs#L18>)。
- 分步结论：HatchPower倒数与ToughEgg.HatchMove的IsHatched/移除来源/变形阶段原生推进；仅取消孵化中正HP/MaxHP增长与去除自身debuff，保留负面HP变化、Buff移除成本和后续普通Nibble；初始已孵化布场不标签化。
- Mod依据：[DomainAdditionalRevivalEffects.Hatch](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Hatch.cs#L45>)。

<a id="p-heistpower"></a>
### HeistPower — 已实现（保留返还）

- 原生函数：[BeforeDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HeistPower.cs#L17>)。
- 分步结论：BeforeDeath给被偷玩家GoldReward并MarkLootReturned是玩家收益及清理，领域不取消；Surprise取消载体时适配同等返还。
- Mod依据：[DomainEnemySpecialContributions.Surprise](<../src/Volibear/Core/DomainEnemySpecialContributions.Surprise.cs#L70>)。

<a id="p-hexpower"></a>
### HexPower — 已实现（敌源虚无）；未实现（任意自身来源）

- **当前增量**：已实现：只撤销Hex贡献的动态Ethereal，Hexed污蚀、其他来源Ethereal和原移除流程保留；退出恢复仍有效的Hex贡献。[S3](#current-self)。

- 原生函数：[TryModifyKeywordsInCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L26>), [AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L39>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L47>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L55>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L63>), [Afflict](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L75>)。
- 分步结论：AfterApplied/AfterCardEnteredCombat仍写Hexed；Hook.ModifyKeywordsInCombat→KeywordsContribution只剔除已记录敌源Hex新增的Ethereal，保留其他来源虚无。退出时原Hex仍有效则重新贡献；原施加者死亡移除与ClearAffliction保留。
- Mod依据：[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L145>)。

<a id="p-highvoltagepower"></a>
### HighVoltagePower — 已实现

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HighVoltagePower.cs#L21>)。
- 分步结论：只包装该Power原生hook里的正Strength提交，在真实PowerCmd commit再检查领域；普通攻击/当前Strength/直接Strength不变。Ravenous吞食眩晕、计数/标志事实与移除保留。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L107>)。

<a id="p-illusionpower"></a>
### IllusionPower — 已实现

- 原生函数：[ShouldPowerBeRemovedOnDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L59>), [AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L68>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L77>), [ShouldAllowHitting](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L95>), [ShouldCreatureBeRemovedFromCombatAfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L108>), [AfterCombatEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L117>), [ReviveMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IllusionPower.cs#L125>)。
- 分步结论：死亡保留/不可击/阻止战斗结束等投票与复活Heal逐提交适配；领域进入可取消尚未提交复活；原节点/模型/Power清理完成，已提交生命事实不倒带。
- Mod依据：[DomainRevivalEffects](<../src/Volibear/Core/DomainRevivalEffects.cs#L80>)。

<a id="p-imbalancedpower"></a>
### ImbalancedPower — 已实现（保留敌方不利）

- **当前增量**：已实现：`DomainSelfDebuffEffects.Penalty`禁用该负面回调，其他计时/移除保留。[S3](#current-self)。

- 原生函数：[AfterDamageGiven](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ImbalancedPower.cs#L17>)。
- 分步结论：敌人受击触发眩晕/去力量/Slow易伤增长是对敌不利，领域保留。不能按Power名称或特殊机制一律禁用。
- Mod依据：原生保留，[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L135>)不安装这些负面hook。

<a id="p-infestedpower"></a>
### InfestedPower — 已实现

- 原生函数：[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/InfestedPower.cs#L19>), [ShouldStopCombatFromEnding](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/InfestedPower.cs#L37>)。
- 分步结论：AfterDeath延迟后的Wriggler Create/Add及阻止战斗结束投票取消，死亡清理继续；已生成的Wriggler不删除。
- Mod依据：[DomainSummonEffects](<../src/Volibear/Core/DomainSummonEffects.cs#L81>)。

<a id="p-intangiblepower"></a>
### IntangiblePower — 已实现

- 原生函数：[ModifyHpLostAfterOsty](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IntangiblePower.cs#L18>), [AfterModifyingHpLostAfterOsty](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IntangiblePower.cs#L35>), [ModifyDamageCap](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IntangiblePower.cs#L46>), [AfterModifyingDamageAmount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IntangiblePower.cs#L59>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/IntangiblePower.cs#L65>)。
- 分步结论：分别解除原生伤害上限/HP损失截断；HardenedShell逐回合窗口只补被压制的额度事实；Slippery受击扣层、Intangible到期、Shell真实伤害记账不吞。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L180>)。

<a id="p-mindrotpower"></a>
### MindRotPower — 未实现

- **当前增量**：已实现：`DrawCount`跳过减抽贡献，返回入参抽牌数。[S3](#current-self)。

- 原生函数：[ModifyHandDraw](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MindRotPower.cs#L14>), [AfterModifyingHandDraw](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MindRotPower.cs#L23>)。
- 分步结论：KnowledgeDemon.ChooseCurse→IChoosable.OnChosen以玩家和所选卡作为来源；分别持续伤害、减抽牌、限出牌、减最大能量；当前敌源白名单与通用领域hooks均不覆盖。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L67>)。

<a id="p-minionpower"></a>
### MinionPower — 已实现（保留身份与清理）

- 原生函数：[ShouldPowerBeRemovedAfterOwnerDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MinionPower.cs#L15>), [ShouldOwnerDeathTriggerFatal](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MinionPower.cs#L20>)。
- 分步结论：OwnerIsSecondaryEnemy及不触发Fatal/死亡保留Power是战斗身份/清理；取消出生由召唤源适配，已存在Minion不删。
- Mod依据：[DomainSummonEffects](<../src/Volibear/Core/DomainSummonEffects.cs#L81>)。

<a id="p-nemesispower"></a>
### NemesisPower — 已实现（有效无实体减伤）；保留（轮换事实）

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NemesisPower.cs#L20>)。
- 分步结论：AfterSideTurnEnd交替Apply/Remove Intangible仍执行；Intangible的HP截断与伤害cap实际贡献被EnemyEffects解除。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L80>)。

<a id="p-painfulstabspower"></a>
### PainfulStabsPower — 已实现

- 原生函数：[ShouldPowerBeRemovedAfterOwnerDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PainfulStabsPower.cs#L24>), [ShouldCreatureBeRemovedFromCombatAfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PainfulStabsPower.cs#L29>), [AfterAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PainfulStabsPower.cs#L34>)。
- 分步结论：分别在AfterDamageReceived/AfterCardPlayed/AfterAttack的确切状态牌生成点取消；已有敌源有害卡payload走状态receipt。PainfulStabs死亡保留投票另交AdditionalRevival适配，不是只拦塞牌。
- Mod依据：[DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>)；[DomainAdditionalRevivalEffects.Patches](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs#L39>)。

<a id="p-papercutspower"></a>
### PaperCutsPower — 已实现

- 原生函数：[AfterDamageGiven](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PaperCutsPower.cs#L16>)。
- 分步结论：AfterDamageGiven中LoseMaxHp贡献取消；实际攻击伤害仍执行。
- Mod依据：[DomainEnemyStatusContributions.PowerEffects](<../src/Volibear/Core/DomainEnemyStatusContributions.PowerEffects.cs#L42>)。

<a id="p-personalhivepower"></a>
### PersonalHivePower — 已实现

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PersonalHivePower.cs#L23>)。
- 分步结论：分别在AfterDamageReceived/AfterCardPlayed/AfterAttack的确切状态牌生成点取消；已有敌源有害卡payload走状态receipt。PainfulStabs死亡保留投票另交AdditionalRevival适配，不是只拦塞牌。
- Mod依据：[DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>)；[DomainAdditionalRevivalEffects.Patches](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs#L39>)。

<a id="p-platingpower"></a>
### PlatingPower — 已实现

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlatingPower.cs#L29>), [BeforeSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlatingPower.cs#L41>), [BeforeSideTurnEndEarly](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlatingPower.cs#L61>), [AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlatingPower.cs#L70>), [GetScaledAmountForMultiplayer](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlatingPower.cs#L85>)。
- 分步结论：只屏蔽被动GainBlock；Plating两条时机都覆盖，原减层/清理保留；CurlUp和Skittish触发登记及回合事实不整段吞掉。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L121>)。

<a id="p-plowpower"></a>
### PlowPower — 已实现（保留敌方不利）

- **当前增量**：已实现（保留敌方负面）；未实现（任意玩家挂载适配）：原生仅敌方用，受击后的移除Strength/Stun未增加玩家贡献gate。不得据其Debuff类型声称玩家效果已禁用。

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlowPower.cs#L28>)。
- 分步结论：敌人受击触发眩晕/去力量/Slow易伤增长是对敌不利，领域保留。不能按Power名称或特殊机制一律禁用。
- Mod依据：原生保留，[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L135>)不安装这些负面hook。

<a id="p-possessspeedpower"></a>
### PossessSpeedPower — 已实现（玩家扣除/返还）；保留（原生记录）

- 原生函数：[AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PossessSpeedPower.cs#L31>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PossessSpeedPower.cs#L57>)。
- 分步结论：Miasma玩家属性负提交被共享stat commit gate取消；已扣数值领域中补偿。AfterDeath精确ReturnStrength/ReturnDexterity归还并退休欠账。敌方正提交是另一条调用，TheForgotten的+Dex缺口见G06。
- Mod依据：[DomainPlayerStatContributions.Possess](<../src/Volibear/Core/DomainPlayerStatContributions.Possess.cs#L68>)。

<a id="p-possessstrengthpower"></a>
### PossessStrengthPower — 已实现（玩家扣除/返还）；保留（原生记录）

- 原生函数：[AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PossessStrengthPower.cs#L31>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PossessStrengthPower.cs#L57>)。
- 分步结论：Miasma玩家属性负提交被共享stat commit gate取消；已扣数值领域中补偿。AfterDeath精确ReturnStrength/ReturnDexterity归还并退休欠账。敌方正提交是另一条调用，TheForgotten的+Dex缺口见G06。
- Mod依据：[DomainPlayerStatContributions.Possess](<../src/Volibear/Core/DomainPlayerStatContributions.Possess.cs#L68>)。

<a id="p-rampartpower"></a>
### RampartPower — 已实现

- 原生函数：[AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RampartPower.cs#L21>)。
- 分步结论：只屏蔽被动GainBlock；Plating两条时机都覆盖，原减层/清理保留；CurlUp和Skittish触发登记及回合事实不整段吞掉。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L121>)。

<a id="p-ravenouspower"></a>
### RavenousPower — 已实现

- 原生函数：[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RavenousPower.cs#L24>), [StunnedMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RavenousPower.cs#L37>)。
- 分步结论：只包装该Power原生hook里的正Strength提交，在真实PowerCmd commit再检查领域；普通攻击/当前Strength/直接Strength不变。Ravenous吞食眩晕、计数/标志事实与移除保留。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L107>)。

<a id="p-reattachpower"></a>
### ReattachPower — 已实现

- 原生函数：[DoReattach](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L40>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L51>), [ShouldAllowHitting](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L76>), [ShouldCreatureBeRemovedFromCombatAfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L89>), [ShouldPowerBeRemovedAfterOwnerDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L98>), [ShouldOwnerDeathTriggerFatal](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L106>), [DoFadeOutOnAllSegments](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L111>), [PlayVfxAndThenRemoveNodes](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L139>), [AreAllOtherSegmentsDead](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReattachPower.cs#L156>)。
- 分步结论：死亡保留/不可击/阻止战斗结束等投票与复活Heal逐提交适配；领域进入可取消尚未提交复活；原节点/模型/Power清理完成，已提交生命事实不倒带。
- Mod依据：[DomainRevivalEffects](<../src/Volibear/Core/DomainRevivalEffects.cs#L80>)。

<a id="p-reflectpower"></a>
### ReflectPower — 已实现

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReflectPower.cs#L19>), [AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ReflectPower.cs#L27>)。
- 分步结论：仅反伤BeforeDamageReceived/AfterDamageReceived的纯伤害payload取消；Reflect到期与普通攻击继续。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L91>)。

<a id="p-ringingpower"></a>
### RingingPower — 已实现（敌源限牌）；未实现（任意自身来源）

- **当前增量**：已实现：`PlayContribution`按玩家减益直接放行；独立的出牌计次/回合重置及污蚀记录保留。[S3](#current-self)。

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L22>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L34>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L42>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L51>), [ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L64>)。
- 分步结论：原生Smog/Ringing附着与计牌事实保留；Hook.ShouldPlay→PlayContribution仅对可追踪敌源返回true；其他否决不变。退出恢复仍有效限制。
- Mod依据：[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L200>)。

<a id="p-ritualpower"></a>
### RitualPower — 已实现

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RitualPower.cs#L36>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RitualPower.cs#L45>)。
- 分步结论：只包装该Power原生hook里的正Strength提交，在真实PowerCmd commit再检查领域；普通攻击/当前Strength/直接Strength不变。Ravenous吞食眩晕、计数/标志事实与移除保留。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L107>)。

<a id="p-sandpitpower"></a>
### SandpitPower — 已实现（处决）；未实现（计数/移动/进入恢复）

- **当前增量**：计数与后续玩家/宠物/Osty移动冻结均已实现，处决拦截保留；进入前已发生的位移保留，退出从剩余层数继续，见[S1](#current-sandpit)。

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L58>), [AfterSideTurnStartLate](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L70>), [AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L78>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L91>), [AfterCreatureAddedToCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L126>), [AfterOstyRevived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L134>), [BeforeSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L139>), [UpdateCreaturePositions](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SandpitPower.cs#L147>)。
- 分步结论：仅PowerCmd.Remove→AfterRemoved的吃人/隐藏/force Kill取消。AfterSideTurnStartLate仍Decrement；所有UpdateCreaturePositions入口仍拉动玩家/宠物；0层detach照常，未冻结或恢复位置。见G01分步骤。
- Mod依据：[DomainEnemySpecialContributions](<../src/Volibear/Core/DomainEnemySpecialContributions.cs#L39>)。

<a id="p-shriekpower"></a>
### ShriekPower — 已实现（保留敌方不利）

- **当前增量**：已实现（保留敌方负面）；未实现（任意玩家挂载适配）：原生回调强转TerrorEel并Stun，无玩家实现；不将本来仅敌方适用的状态列为正常玩家能力。[S3](#current-self)。

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShriekPower.cs#L25>)。
- 分步结论：敌人受击触发眩晕/去力量/Slow易伤增长是对敌不利，领域保留。不能按Power名称或特殊机制一律禁用。
- Mod依据：原生保留，[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L135>)不安装这些负面hook。

<a id="p-shrinkpower"></a>
### ShrinkPower — 已实现（敌源伤害）；未实现（已有缩小视觉/任意自身来源）

- **当前增量**：已实现：伤害倍率中性化；进入/领域内施加恢复尺度1，退出仍有Shrink时回到0.5，原到期保留。[S3](#current-self)。

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L48>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L66>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L79>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L87>), [ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L95>)。
- 分步结论：负数无限Shrink也是敌源新增取消对象；已有敌源0.7伤害倍率恢复1。进入前AfterApplied的ScaleTo(0.5)没有领域进入恢复，不能把倍率修复算视觉已恢复；原死亡/到期移除继续。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L48>)；[DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L29>)。

<a id="p-skittishpower"></a>
### SkittishPower — 已实现

- 原生函数：[AfterAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SkittishPower.cs#L56>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SkittishPower.cs#L71>), [GetScaledAmountForMultiplayer](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SkittishPower.cs#L84>)。
- 分步结论：只屏蔽被动GainBlock；Plating两条时机都覆盖，原减层/清理保留；CurlUp和Skittish触发登记及回合事实不整段吞掉。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L121>)。

<a id="p-slipperypower"></a>
### SlipperyPower — 已实现

- 原生函数：[ModifyHpLostAfterOsty](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlipperyPower.cs#L19>), [AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlipperyPower.cs#L32>), [GetScaledAmountForMultiplayer](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlipperyPower.cs#L41>)。
- 分步结论：分别解除原生伤害上限/HP损失截断；HardenedShell逐回合窗口只补被压制的额度事实；Slippery受击扣层、Intangible到期、Shell真实伤害记账不吞。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L180>)。

<a id="p-slothpower"></a>
### SlothPower — 未实现

- **当前增量**：已实现：`PlayContribution`按玩家减益直接放行；独立的出牌计次/回合重置及污蚀记录保留。[S3](#current-self)。

- 原生函数：[ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs#L22>), [BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs#L31>), [BeforeSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs#L42>)。
- 分步结论：KnowledgeDemon.ChooseCurse→IChoosable.OnChosen以玩家和所选卡作为来源；分别持续伤害、减抽牌、限出牌、减最大能量；当前敌源白名单与通用领域hooks均不覆盖。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L67>)。

<a id="p-slowpower"></a>
### SlowPower — 已实现（保留敌方不利）

- **当前增量**：已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。

- 原生函数：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L26>), [ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L33>), [AfterModifyingDamageAmount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L46>), [AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L52>)。
- 分步结论：敌人受击触发眩晕/去力量/Slow易伤增长是对敌不利，领域保留。不能按Power名称或特殊机制一律禁用。
- Mod依据：原生保留，[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L135>)不安装这些负面hook。

<a id="p-slumberpower"></a>
### SlumberPower — 已实现（保留敌方不利/生命周期）

- 原生函数：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlumberPower.cs#L21>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlumberPower.cs#L34>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlumberPower.cs#L40>)。
- 分步结论：睡眠、受到伤害醒来、自然倒数、眩晕与去除Plating按原生保留；有利护甲的GainBlock已单独由Plating路径屏蔽。
- Mod依据：原生不利/清理保留；[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L122>)。

<a id="p-smoggypower"></a>
### SmoggyPower — 已实现（敌源限牌）；未实现（任意自身来源）

- **当前增量**：已实现：`PlayContribution`按玩家减益直接放行；独立的出牌计次/回合重置及污蚀记录保留。[S3](#current-self)。

- 原生函数：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L22>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L39>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L47>), [ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L64>)。
- 分步结论：原生Smog/Ringing附着与计牌事实保留；Hook.ShouldPlay→PlayContribution仅对可追踪敌源返回true；其他否决不变。退出恢复仍有效限制。
- Mod依据：[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L200>)。

<a id="p-soarpower"></a>
### SoarPower — 已实现

- 原生函数：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SoarPower.cs#L19>)。
- 分步结论：ModifyDamageMultiplicative的敌方减伤归1；Flutter受击扣层、耗尽眩晕保留；Soar原生移除保留。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L137>)。

<a id="p-steameruptionpower"></a>
### SteamEruptionPower — 已实现（死亡爆炸保护事务）；保留（压力事实）

- 原生函数：[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SteamEruptionPower.cs#L15>), [ShouldStopCombatFromEnding](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SteamEruptionPower.cs#L23>), [ShouldCreatureBeRemovedFromCombatAfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SteamEruptionPower.cs#L28>), [ShouldPowerBeRemovedAfterOwnerDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SteamEruptionPower.cs#L37>)。
- 分步结论：WaterfallGiant死亡阶段的投票、AboutToBlow/Explode攻击与HP提交受精确事务适配；Siphon活体回血另外被Heal gate取消。普通压力攻击/PressureGunDamage增加及压力Amount事实不整体回滚。
- Mod依据：[DomainSteamEruptionEffects.Install](<../src/Volibear/Core/DomainSteamEruptionEffects.Install.cs#L35>)。

<a id="p-stockpower"></a>
### StockPower — 已实现

- 原生函数：[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StockPower.cs#L16>), [ShouldStopCombatFromEnding](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StockPower.cs#L28>)。
- 分步结论：Axebot死亡后的新机器人Add与TestSubject Respawn/Revive的回血、阶段保护和死亡投票精确取消；保留已落地对象及必要清理。
- Mod依据：[DomainAdditionalRevivalEffects.Patches](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs#L33>)。

<a id="p-strengthpower"></a>
### StrengthPower — 已实现（已记录敌源玩家减值）；保留（直接敌方力量）；未实现（自身负值/敌方偷敏捷收益）

- 原生函数：[ModifyDamageAdditive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StrengthPower.cs#L15>)。
- 分步结论：玩家敌源负提交取消，已有StrengthDebt/DexterityDebt以DomainPower additive贡献补偿，不改原Amount；Tender/Possess返还只结算实际欠账。玩家自己施加负值不补偿。TheForgotten敌方+Dexterity独立提交仍发生，见G06；直接力量、格挡按规则保留。
- Mod依据：[DomainPlayerStatContributions](<../src/Volibear/Core/DomainPlayerStatContributions.cs#L40>)；[DomainPlayerStatContributions.Possess](<../src/Volibear/Core/DomainPlayerStatContributions.Possess.cs#L68>)。

<a id="p-suckpower"></a>
### SuckPower — 已实现

- 原生函数：[AfterAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SuckPower.cs#L22>)。
- 分步结论：只包装该Power原生hook里的正Strength提交，在真实PowerCmd commit再检查领域；普通攻击/当前Strength/直接Strength不变。Ravenous吞食眩晕、计数/标志事实与移除保留。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L107>)。

<a id="p-surprisepower"></a>
### SurprisePower — 已实现

- 原生函数：[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurprisePower.cs#L17>), [ShouldStopCombatFromEnding](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurprisePower.cs#L40>)。
- 分步结论：死亡分裂的Sneaky/Fat两个Add逐步取消；若Fat未生成则直接保留被偷金币返还奖励与历史；取消后的结束战斗否决解除。
- Mod依据：[DomainEnemySpecialContributions.Surprise](<../src/Volibear/Core/DomainEnemySpecialContributions.Surprise.cs#L38>)。

<a id="p-surroundedpower"></a>
### SurroundedPower — 已实现（背击增伤）；保留（朝向事实）

- **当前增量**：已实现：原有敌方背击增伤屏蔽继续，方向与左右站位事实保留；非敌方攻击不扩大为额外取消范围。

- 原生函数：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L46>), [BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L74>), [BeforePotionUsed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L82>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L90>), [UpdateDirection](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L102>), [FaceDirection](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L121>), [FlipScale](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L147>)。
- 分步结论：玩家身上的背击乘数在敌方攻击时归1；BeforeCardPlayed/BeforePotionUsed转向及BackAttack左右标记原生保留。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L157>)。

<a id="p-swipepower"></a>
### SwipePower — 已实现（新偷牌）；保留（已有偷牌与死亡返还）

- 原生函数：[BeforeDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SwipePower.cs#L50>), [Steal](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SwipePower.cs#L69>)。
- 分步结论：ThievingHopper.ThieveryMove→RemoveFromCombat→Swipe.Steal→RemoveFromDeck双提交分别拦截；已有失窃牌不凭领域即时复制回来；死亡奖励/返还继续。
- Mod依据：[DomainHopperEffects](<../src/Volibear/Core/DomainHopperEffects.cs#L21>)；[DomainHopperEffects.Patches](<../src/Volibear/Core/DomainHopperEffects.Patches.cs#L32>)。

<a id="p-taintedpower"></a>
### TaintedPower — 已实现（有敌源receipt）；未实现（任意自身来源）

- **当前增量**：已实现：`DamageAdditive`跳过玩家Tainted伤害惩罚，不再要求敌源receipt；原到期继续。[S3](#current-self)。

- 原生函数：[ModifyDamageAdditive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TaintedPower.cs#L18>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TaintedPower.cs#L31>)。
- 分步结论：ModifyDamageAdditive只移除敌方VitalSpark记录贡献；不能把未知/卡源已有Amount当作已覆盖。
- Mod依据：[DomainEnemyStatusContributions.PowerEffects](<../src/Volibear/Core/DomainEnemyStatusContributions.PowerEffects.cs#L191>)。

<a id="p-tangledpower"></a>
### TangledPower — 已实现（敌源费用）；未实现（任意自身来源）

- **当前增量**：已实现：`DomainCardContributions.CostContribution`对玩家减益费用贡献返回原费用，计时及其他来源改费保留。[S3](#current-self)。

- 原生函数：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L23>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L32>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L40>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L49>), [TryModifyEnergyCostInCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L59>)。
- 分步结论：Entangled附着保留；Hook.ModifyEnergyCostInCombat→CostContribution只减敌源正增费部分；到期Remove/ClearAffliction保留。
- Mod依据：[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L180>)。

<a id="p-tenderpower"></a>
### TenderPower — 已实现（敌源）

- **当前增量**：已实现：TenderApply按当前领域取消新扣款，已有扣款走属性债务补偿；只归还已支付值，避免未扣却返。[S3](#current-self)。

- 原生函数：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TenderPower.cs#L44>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TenderPower.cs#L55>)。
- 分步结论：每次出牌-Strength/-Dexterity分别取消；已付欠账在领域中补偿；回合结束返还只按真正已付量，避免免费获属性。计牌事实继续。
- Mod依据：[DomainPlayerStatContributions.Tender](<../src/Volibear/Core/DomainPlayerStatContributions.Tender.cs#L46>)。

<a id="p-territorialpower"></a>
### TerritorialPower — 已实现

- 原生函数：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TerritorialPower.cs#L21>)。
- 分步结论：只包装该Power原生hook里的正Strength提交，在真实PowerCmd commit再检查领域；普通攻击/当前Strength/直接Strength不变。Ravenous吞食眩晕、计数/标志事实与移除保留。
- Mod依据：[DomainPassiveEffects](<../src/Volibear/Core/DomainPassiveEffects.cs#L107>)。

<a id="p-thieverypower"></a>
### ThieveryPower — 已实现

- 原生函数：[Steal](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ThieveryPower.cs#L21>)。
- 分步结论：GremlinMerc三个真实move中的Steal→LoseGold被精确包装，普通伤害/直接力量保留；既有失窃金不逆写，死亡返还继续。
- Mod依据：[DomainEnemySpecialContributions](<../src/Volibear/Core/DomainEnemySpecialContributions.cs#L31>)。

<a id="p-thornspower"></a>
### ThornsPower — 已实现

- 原生函数：[BeforeDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ThornsPower.cs#L17>)。
- 分步结论：仅反伤BeforeDamageReceived/AfterDamageReceived的纯伤害payload取消；Reflect到期与普通攻击继续。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L91>)。

<a id="p-vigorpower"></a>
### VigorPower — 已实现

- 原生函数：[BeforeAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VigorPower.cs#L29>), [ModifyDamageAdditive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VigorPower.cs#L57>), [AfterAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VigorPower.cs#L79>)。
- 分步结论：正攻击附加值归零；BeforeAttack登记、AfterAttack消耗照常，负值不吞。
- Mod依据：[DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L146>)。

<a id="p-vitalsparkpower"></a>
### VitalSparkPower — 已实现

- 原生函数：[BeforeCombatStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VitalSparkPower.cs#L25>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VitalSparkPower.cs#L41>), [AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VitalSparkPower.cs#L49>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VitalSparkPower.cs#L58>), [AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VitalSparkPower.cs#L79>)。
- 分步结论：新Tainted附着及AfterCardPlayed的TaintedPower施加分别屏蔽；既有Tainted敌源伤害标量另由EffectiveTaintedAmount处理。
- Mod依据：[DomainEnemyStatusContributions.PowerEffects](<../src/Volibear/Core/DomainEnemyStatusContributions.PowerEffects.cs#L34>)。

<a id="p-vulnerablepower"></a>
### VulnerablePower — 已实现（敌源）；未实现（任意自身来源）

- **当前增量**：已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。

- 原生函数：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VulnerablePower.cs#L27>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VulnerablePower.cs#L59>)。
- 分步结论：敌源新增在PowerCmd真实commit前取消；进入前已记录敌源层在伤害/格挡Hook调用点使用retained反事实量；持续时间、敌方自身负面效果和退出后剩余原Amount保留。自身/卡源与无receipt旧实例不压制。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L29>)。

<a id="p-wasteawaypower"></a>
### WasteAwayPower — 未实现

- **当前增量**：已实现：`MaxEnergy`跳过减最大能量贡献，返回原amount。[S3](#current-self)。

- 原生函数：[ModifyMaxEnergy](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WasteAwayPower.cs#L16>)。
- 分步结论：KnowledgeDemon.ChooseCurse→IChoosable.OnChosen以玩家和所选卡作为来源；分别持续伤害、减抽牌、限出牌、减最大能量；当前敌源白名单与通用领域hooks均不覆盖。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L67>)。

<a id="p-weakpower"></a>
### WeakPower — 已实现（敌源）；未实现（任意自身来源）

- **当前增量**：已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。

- 原生函数：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WeakPower.cs#L24>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WeakPower.cs#L48>)。
- 分步结论：敌源新增在PowerCmd真实commit前取消；进入前已记录敌源层在伤害/格挡Hook调用点使用retained反事实量；持续时间、敌方自身负面效果和退出后剩余原Amount保留。自身/卡源与无receipt旧实例不压制。
- Mod依据：[DomainPlayerDebuffContributions](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs#L34>)；[DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L29>)。

<a id="p-witheringpresencepower"></a>
### WitheringPresencePower — 已实现

- 原生函数：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WitheringPresencePower.cs#L46>)。
- 分步结论：分别在AfterDamageReceived/AfterCardPlayed/AfterAttack的确切状态牌生成点取消；已有敌源有害卡payload走状态receipt。PainfulStabs死亡保留投票另交AdditionalRevival适配，不是只拦塞牌。
- Mod依据：[DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>)；[DomainAdditionalRevivalEffects.Patches](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs#L39>)。

## 5. 非Power与状态牌调用链（基线；知识恶魔当前增量已标注）

| 来源/原生函数 | 精确payload与结论 | Mod依据 |
|---|---|---|
| [MechaKnight.FlamethrowerMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L132>) | 创建/入堆 `Burn`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [TestSubject.BurningGrowlMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L326>) | 创建/入堆 `Burn`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [Aeonglass.IncreasingIntensityMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L128>) | 创建/入堆 `Wither`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [Chomper.ScreechMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Chomper.cs#L76>) | 创建/入堆 `Dazed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [EyeWithTeeth.DistractMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/EyeWithTeeth.cs#L45>) | 创建/入堆 `Dazed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [HauntedShip.HauntMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HauntedShip.cs#L72>) | 创建/入堆 `Dazed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [LeafSlimeS.GoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeS.cs#L50>) | 创建/入堆 `Slimed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [LeafSlimeM.StickyShotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeM.cs#L50>) | 创建/入堆 `Slimed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [TwigSlimeM.StickyShotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwigSlimeM.cs#L55>) | 创建/入堆 `Slimed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [SlimedBerserker.VomitIchorMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L66>) | 创建/入堆 `Slimed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [Myte.ToxicMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Myte.cs#L64>) | 创建/入堆 `Toxic`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [PhrogParasite.InfectMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhrogParasite.cs#L65>) | 创建/入堆 `Infection`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [Wriggler.WriggleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Wriggler.cs#L87>) | 创建/入堆 `Infection`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [Vantom.DismemberMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L170>) | 创建/入堆 `Wound`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [WitheringPresencePower.AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WitheringPresencePower.cs#L46>) | 创建/入堆 `Wither`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [PainfulStabsPower.AfterAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PainfulStabsPower.cs#L34>) | 创建/入堆 `Wound`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [Noisebot.NoiseMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Noisebot.cs#L51>) | 创建/入堆 `Dazed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [SoulFysh.BeckonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L131>) | 创建/入堆 `Beckon`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [SoulFysh.GazeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L156>) | 创建/入堆 `Beckon`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |
| [PersonalHivePower.AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PersonalHivePower.cs#L23>) | 创建/入堆 `Dazed`：**已实现**，只取消该敌源调用；普通攻击与其余效果保留。已有敌源卡的payload按下面说明。 | [DomainEnemyStatusContributions](<../src/Volibear/Core/DomainEnemyStatusContributions.cs#L36>) |

状态牌阶段拆分：

- **新增塞牌已实现**：上表20个准确来源点。`AddToCombatAndPreview`路线在生成前取消；直接CreateCard路线在Add前移除刚注册身份并返回失败结果。不是全局禁止状态牌或只改卡文本。
- **既有卡效果已实现（有限来源）**：Burn/Wither/Toxic/Infection/Beckon的原生有害hook按敌源receipt屏蔽；Wither FakeUpgrade与WitherUpgradeCount另在Aeonglass.IncreasingIntensityMove/MatchWitherToUpgradeCount精确控制。Dazed/Wound/Slimed已有牌仍占牌堆/手牌，并不被全队追溯删除。只有领域持有者实际抽到状态/诅咒才Exhaust并补抽（已实现）。
- **来源之外未实现**：任意来源已经在手的有害状态/诅咒，不由上表有限状态receipt自动屏蔽；与“全自身debuff Power”不同类别。不得把持有者抽牌净化写成全队所有已有牌已被清除。
- **FranticEscape明确保留**：TheInsatiable生成六张可增加Sandpit计数的状态牌，非以上有害生成点。领域持有者抽到仍按净化规则消耗；其OnPlay增加沙坑计数是玩家主动效果，应与敌方倒数分开。[FranticEscape.OnPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Cards/FranticEscape.cs#L37>)。

| 非Power链 | baseline分步结论 | Mod/原生依据 |
|---|---|---|
| Fabricator.FabricateMove / FabricatingStrikeMove → SpawnBot → Add | **已实现**出生门；初始布场、已创建孩子保留，混合攻击继续 | [DomainSummonEffects](<../src/Volibear/Core/DomainSummonEffects.cs#L81>) |
| Ovicopter.LayEggsMove → Add ToughEgg / Minion | **已实现**出生与新孩子后续初始化门；已存在蛋保留 | [DomainSummonEffects](<../src/Volibear/Core/DomainSummonEffects.cs#L82>) |
| LivingFog.BloatMove / TwoTailedRat.CallForBackup / Fogmog.IllusionMove / TheObscura.IllusionMove → Add | **已实现**四处出生取消；状态事实及普通攻击保留 | [DomainSummonEffects.Additional](<../src/Volibear/Core/DomainSummonEffects.Additional.cs#L19>) |
| ToughEgg.HatchMove → Remove各Power → Hatch → SetMaxAndCurrentHp | **已实现**敌方清debuff与正HP两项收益取消；**保留**Buff移除成本/孵化事实/后续普通攻击 | [DomainAdditionalRevivalEffects.Hatch](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Hatch.cs#L56>) |
| TestSubject.TriggerDead / RespawnMove / Revive → HP / 阶段保护 | **已实现**阶段复活收益与保护投票取消，原清理保留 | [DomainAdditionalRevivalEffects.Patches](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs#L33>) |
| 活体CreatureCmd.Heal：KnowledgeDemon.PonderMove、WaterfallGiant.SiphonMove | **已实现**正活体治疗取消；原普通攻击/直接力量保留；死者复活交专用事务 | [DomainEnemyEffects](<../src/Volibear/Core/DomainEnemyEffects.cs#L262>) |
| GremlinMerc三动作 → Thievery.Steal | **已实现**偷金取消；**保留**普通攻击与真实既有金币返还 | [DomainEnemySpecialContributions](<../src/Volibear/Core/DomainEnemySpecialContributions.cs#L105>) |
| ThievingHopper.ThieveryMove → RemoveFromCombat / Swipe.Steal → RemoveFromDeck | **已实现**战斗牌和永久牌两个提交门；**保留**原攻击、既有偷牌和死亡返还 | [DomainHopperEffects](<../src/Volibear/Core/DomainHopperEffects.cs#L21>) |
| FatGremlin.FleeMove → Escape | **已实现**取消整个纯逃跑动作，在隐藏/禁交互前 | [DomainEnemySpecialContributions](<../src/Volibear/Core/DomainEnemySpecialContributions.cs#L54>) |
| ThievingHopper.EscapeMove → Escape | **未实现**；独立于已支持的偷牌 | [ThievingHopper.EscapeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L276>) |
| KnowledgeDemon.ChooseCurse → IChoosable.OnChosen | **baseline未实现；当前已实现**四个选择debuff的抑制；选择和动作计次保留，详见[S3](#current-self) | [KnowledgeDemon.ChooseCurse](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L167>) |
| TheForgotten.MiasmaMove → enemy +Dex → DreadDamage | **未实现**新的敌方敏捷收益取消；玩家负值已支持，直接8Block保留 | [TheForgotten.MiasmaMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L53>) |

## 6. 每怪物Move调用清单：普通/直接收益与特别动作的交叉核对

本节列每类实际声明的动作/战斗hook（排除动画、皮肤、图鉴可见性等纯呈现函数）；每个函数链接为锁版源码定位。上文没有标成压制的`DamageCmd.Attack`均保留；正直接`PowerCmd.Apply<StrengthPower>`及直接`CreatureCmd.GainBlock`均保留。外观缩放/音频/AI状态事实不虚构独立有利机制。TheForgotten+Dex、Sandpit位置与Hopper逃脱等已单列，不受“普通动作”笼统豁免。

| 怪物 | 原生行为函数 |
|---|---|
| Aeonglass | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L74>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L87>)；[EbbMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L112>)；[EyeLasersMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L120>)；[IncreasingIntensityMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L128>)；[AfterCardGeneratedForCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L150>)；[MatchWitherToUpgradeCount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Aeonglass.cs#L160>) |
| Architect | GenerateMoveStateMachine中的空动作/固定状态；无额外行为函数 |
| AssassinRubyRaider | [KillshotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/AssassinRubyRaider.cs#L32>) |
| AxeRubyRaider | [SwingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/AxeRubyRaider.cs#L47>)；[BigSwingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/AxeRubyRaider.cs#L56>) |
| Axebot | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L76>)；[BootUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L102>)；[OneTwoMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L111>)；[HammerUppercutMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Axebot.cs#L121>) |
| BattleFriendV1 | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV1.cs#L33>) |
| BattleFriendV2 | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV2.cs#L33>) |
| BattleFriendV3 | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BattleFriendV3.cs#L33>) |
| BigDummy | [NothingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BigDummy.cs#L30>) |
| BowlbugEgg | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugEgg.cs#L51>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugEgg.cs#L65>) |
| BowlbugNectar | [ThrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugNectar.cs#L58>)；[BuffMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugNectar.cs#L66>) |
| BowlbugRock | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugRock.cs#L63>)；[HeadbuttMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugRock.cs#L84>)；[Stun](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugRock.cs#L96>)；[DizzyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugRock.cs#L103>) |
| BowlbugSilk | [ThrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugSilk.cs#L53>)；[SpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BowlbugSilk.cs#L63>) |
| BruteRubyRaider | [BeatMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BruteRubyRaider.cs#L40>)；[RoarMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BruteRubyRaider.cs#L48>) |
| BygoneEffigy | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L34>)；[InitialSleepMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L58>)；[SleepMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L65>)；[WakeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L70>)；[SlashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/BygoneEffigy.cs#L82>) |
| Byrdonis | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Byrdonis.cs#L34>)；[PeckMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Byrdonis.cs#L52>)；[SwoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Byrdonis.cs#L61>) |
| Byrdpip | GenerateMoveStateMachine中的空动作/固定状态；无额外行为函数 |
| CalcifiedCultist | [IncantationMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CalcifiedCultist.cs#L77>)；[DarkStrikeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CalcifiedCultist.cs#L86>) |
| CeremonialBeast | [StampMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L170>)；[PlowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L178>)；[SetStunned](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L208>)；[StunnedMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L216>)；[BeastCryMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L222>)；[StompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L232>)；[CrushMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CeremonialBeast.cs#L246>) |
| Chomper | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Chomper.cs#L49>)；[ClampMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Chomper.cs#L67>)；[ScreechMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Chomper.cs#L76>) |
| CorpseSlug | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L85>)；[WhipSlapMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L111>)；[GlompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L121>)；[GoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L129>)；[EnsureCorpseSlugsStartWithDifferentMoves](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CorpseSlug.cs#L135>) |
| CrossbowRubyRaider | [FireMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CrossbowRubyRaider.cs#L56>)；[ReloadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CrossbowRubyRaider.cs#L65>) |
| Crusher | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L114>)；[AfterCurrentHpChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L122>)；[BeforeDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L132>)；[ThrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L152>)；[BugStingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L160>)；[AdaptMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L171>)；[EnlargingStrikeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L178>)；[GuardedStrikeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Crusher.cs#L187>) |
| CubexConstruct | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L87>)；[ChargeUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L128>)；[RepeaterBlastMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L138>)；[ExpelBlastMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/CubexConstruct.cs#L151>) |
| DampCultist | [IncantationMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DampCultist.cs#L77>)；[DarkStrikeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DampCultist.cs#L86>) |
| DecimillipedeSegment | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L120>)；[WritheMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L180>)；[BulkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L189>)；[ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L198>)；[DeadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L207>)；[ReattachMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L212>)；[AnimSegmentsAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L222>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L241>)；[ChangePhobiaModeTexture](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegment.cs#L255>) |
| DecimillipedeSegmentBack | [SegmentAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegmentBack.cs#L11>) |
| DecimillipedeSegmentFront | [SegmentAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegmentFront.cs#L11>) |
| DecimillipedeSegmentMiddle | [SegmentAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DecimillipedeSegmentMiddle.cs#L12>) |
| DeprecatedMonster | GenerateMoveStateMachine中的空动作/固定状态；无额外行为函数 |
| DevotedSculptor | [ForbiddenIncantationMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DevotedSculptor.cs#L42>)；[SavageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/DevotedSculptor.cs#L53>) |
| Entomancer | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L35>)；[SpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L55>)；[BeesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L71>)；[SpearMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Entomancer.cs#L81>) |
| Exoskeleton | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs#L46>)；[SkitterMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs#L77>)；[MandiblesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs#L87>)；[EnrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Exoskeleton.cs#L95>) |
| EyeWithTeeth | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/EyeWithTeeth.cs#L30>)；[DistractMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/EyeWithTeeth.cs#L45>) |
| Fabricator | [FabricateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L76>)；[FabricatingStrikeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L83>)；[DisintegrateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L92>)；[SpawnDefensiveBot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L100>)；[SpawnAggroBot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L105>)；[SpawnBot](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fabricator.cs#L110>) |
| FakeMerchantMonster | [SwipeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs#L76>)；[SpewCoinsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs#L85>)；[ThrowRelicMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs#L95>)；[EnrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FakeMerchantMonster.cs#L105>) |
| FatGremlin | [SpawnedMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FatGremlin.cs#L60>)；[FleeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FatGremlin.cs#L66>) |
| FlailKnight | [WarChantMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FlailKnight.cs#L59>)；[FlailMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FlailKnight.cs#L66>)；[RamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FlailKnight.cs#L76>) |
| Flyconid | [VulnerableSporesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Flyconid.cs#L52>)；[FrailSporesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Flyconid.cs#L63>)；[SmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Flyconid.cs#L77>) |
| Fogmog | [IllusionMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fogmog.cs#L60>)；[SwipeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fogmog.cs#L70>)；[HeadbuttMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Fogmog.cs#L79>) |
| FossilStalker | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs#L45>)；[TackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs#L68>)；[LatchMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs#L77>)；[LashAttack](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FossilStalker.cs#L85>) |
| FrogKnight | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L60>)；[ForTheQueenMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L89>)；[StrikeDownEvilMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L96>)；[TongueLashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L104>)；[BeetleChargeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FrogKnight.cs#L113>) |
| FuzzyWurmCrawler | [AcidGoop](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FuzzyWurmCrawler.cs#L62>)；[Inhale](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/FuzzyWurmCrawler.cs#L83>) |
| GasBomb | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GasBomb.cs#L53>)；[ExplodeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GasBomb.cs#L67>) |
| GlobeHead | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L41>)；[ThunderStrike](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L62>)；[ShockingSlap](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L72>)；[GalvanicBurstMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GlobeHead.cs#L81>) |
| GremlinMerc | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L46>)；[GimmeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L73>)；[DoubleSmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L95>)；[HeheMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/GremlinMerc.cs#L112>) |
| Guardbot | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Guardbot.cs#L27>)；[GuardMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Guardbot.cs#L47>) |
| HauntedShip | [SwipeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HauntedShip.cs#L54>)；[StompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HauntedShip.cs#L62>)；[HauntMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HauntedShip.cs#L72>) |
| HunterKiller | [GoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HunterKiller.cs#L51>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HunterKiller.cs#L58>)；[PunctureMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/HunterKiller.cs#L66>) |
| InfestedPrism | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L56>)；[JabMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L80>)；[RadiateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L88>)；[WhirlwindMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L97>)；[PulsateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/InfestedPrism.cs#L107>) |
| Inklet | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Inklet.cs#L57>)；[JabMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Inklet.cs#L86>)；[WhirlwindMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Inklet.cs#L94>)；[PiercingGazeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Inklet.cs#L104>) |
| KinFollower | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs#L98>)；[QuickSlashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs#L120>)；[PowerDanceMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs#L128>)；[BoomerangMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinFollower.cs#L135>) |
| KinPriest | [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L81>)；[OrbOfFrailtyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L129>)；[OrbOfWeaknessMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L139>)；[BeamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L149>)；[RitualMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L164>)；[AllFollowerDeathResponse](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KinPriest.cs#L197>) |
| KnowledgeDemon | [CurseOfKnowledge](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L149>)；[ChooseCurse](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L167>)；[SlapMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L190>)；[KnowledgeOverwhelmingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L198>)；[PonderMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/KnowledgeDemon.cs#L210>) |
| LagavulinMatriarch | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L109>)；[Sleep](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L115>)；[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L130>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L148>)；[SleepMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L184>)；[WakeUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L189>)；[SlashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L201>)；[Slash2Move](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L211>)；[DisembowelMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L222>)；[SoulSiphonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LagavulinMatriarch.cs#L234>) |
| LeafSlimeM | [ClumpShotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeM.cs#L42>)；[StickyShotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeM.cs#L50>) |
| LeafSlimeS | [TackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeS.cs#L42>)；[GoopMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LeafSlimeS.cs#L50>) |
| LivingFog | [AdvancedGasMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingFog.cs#L76>)；[BloatMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingFog.cs#L85>)；[SuperGasBlastMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingFog.cs#L104>) |
| LivingShield | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs#L32>)；[ShieldSlamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs#L54>)；[SmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs#L62>)；[GetAllyCount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LivingShield.cs#L71>) |
| LouseProgenitor | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L67>)；[WebMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L87>)；[CurlAndGrowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L102>)；[PounceMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/LouseProgenitor.cs#L111>) |
| MagiKnight | [DampenMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs#L78>)；[PowerShieldMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs#L98>)；[PrepMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs#L107>)；[MagicBombMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs#L114>)；[SpearMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MagiKnight.cs#L141>) |
| Mawler | [RipAndTearMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Mawler.cs#L46>)；[RoarMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Mawler.cs#L54>)；[ClawMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Mawler.cs#L60>) |
| MechaKnight | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L73>)；[ChargeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L97>)；[HeavyCleaveMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L107>)；[WindupMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L123>)；[FlamethrowerMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MechaKnight.cs#L132>) |
| MultiAttackMoveMonster | [PokeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MultiAttackMoveMonster.cs#L30>) |
| MysteriousKnight | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/MysteriousKnight.cs#L10>) |
| Myte | [ToxicMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Myte.cs#L64>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Myte.cs#L80>)；[SuckMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Myte.cs#L88>) |
| Nibbit | [ButtMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Nibbit.cs#L94>)；[SliceMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Nibbit.cs#L102>)；[HissMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Nibbit.cs#L111>) |
| Noisebot | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Noisebot.cs#L31>)；[NoiseMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Noisebot.cs#L51>) |
| OneHpMonster | [NothingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OneHpMonster.cs#L27>) |
| Osty | [CheckMissingWithAnim](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Osty.cs#L74>) |
| Ovicopter | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L48>)；[LayEggsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L81>)；[NutritionalPasteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L96>)；[SmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L103>)；[TenderizerMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Ovicopter.cs#L111>) |
| OwlMagistrate | [MagistrateScrutinyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs#L110>)；[PeckAssaultMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs#L118>)；[JudicialFlightMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs#L128>)；[VerdictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/OwlMagistrate.cs#L138>) |
| PaelsLegion | GenerateMoveStateMachine中的空动作/固定状态；无额外行为函数 |
| Parafright | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Parafright.cs#L35>)；[SlamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Parafright.cs#L50>) |
| PhantasmalGardener | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L89>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L118>)；[LashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L127>)；[FlailMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L136>)；[EnlargeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhantasmalGardener.cs#L147>) |
| PhrogParasite | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhrogParasite.cs#L33>)；[LashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhrogParasite.cs#L55>)；[InfectMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PhrogParasite.cs#L65>) |
| PunchConstruct | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs#L71>)；[ReadyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs#L95>)；[StrongPunchMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs#L102>)；[FastPunchMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/PunchConstruct.cs#L110>) |
| Queen | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L125>)；[PuppetStringsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L164>)；[YoureMineMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L171>)；[BurnBrightForMeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L182>)；[OffWithYourHeadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L195>)；[ExecutionMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L205>)；[EnrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L214>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Queen.cs#L221>) |
| Rocket | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L90>)；[AfterCurrentHpChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L99>)；[BeforeDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L109>)；[TargetingReticleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L134>)；[PrecisionBeamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L143>)；[ChargeUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L153>)；[LaserMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L160>)；[RechargeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Rocket.cs#L170>) |
| ScrollOfBiting | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs#L73>)；[ChompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs#L103>)；[ChewState](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs#L111>)；[MoreTeethMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ScrollOfBiting.cs#L121>) |
| Seapunk | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Seapunk.cs#L46>)；[SeaKickMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Seapunk.cs#L66>)；[SpinningKickMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Seapunk.cs#L74>)；[BubbleBurpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Seapunk.cs#L84>) |
| SewerClam | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SewerClam.cs#L29>)；[PressurizeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SewerClam.cs#L47>)；[JetMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SewerClam.cs#L54>) |
| ShrinkerBeetle | [ShrinkMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ShrinkerBeetle.cs#L46>)；[ChompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ShrinkerBeetle.cs#L54>)；[StompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ShrinkerBeetle.cs#L62>) |
| SingleAttackMoveMonster | [PokeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SingleAttackMoveMonster.cs#L28>) |
| SkulkingColony | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs#L53>)；[InertiaMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs#L77>)；[PiercingStabsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs#L86>)；[ZoomMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SkulkingColony.cs#L96>) |
| SlimedBerserker | [VomitIchorMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L66>)；[LeechingHugMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L73>)；[FuriousPummelingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L81>)；[SmotherMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlimedBerserker.cs#L90>) |
| SlitheringStrangler | [ConstrictMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlitheringStrangler.cs#L57>)；[ThwackMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlitheringStrangler.cs#L64>)；[LashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlitheringStrangler.cs#L73>) |
| SludgeSpinner | [OilSprayMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SludgeSpinner.cs#L55>)；[SlamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SludgeSpinner.cs#L64>)；[RageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SludgeSpinner.cs#L72>) |
| SlumberingBeetle | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L73>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L89>)；[WakeUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L96>)；[SnoreMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L125>)；[RolloutMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SlumberingBeetle.cs#L130>) |
| SnappingJaxfruit | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SnappingJaxfruit.cs#L33>)；[EnergyOrb](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SnappingJaxfruit.cs#L53>) |
| SneakyGremlin | [SpawnedMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SneakyGremlin.cs#L57>)；[TackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SneakyGremlin.cs#L63>) |
| SoulFysh | [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L81>)；[AfterCardChangedPilesLate](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L91>)；[BeckonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L131>)；[GazeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L156>)；[DeGasMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L177>)；[ScreamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L185>)；[FadeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulFysh.cs#L197>) |
| SoulNexus | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L43>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L49>)；[SoulBurnMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L80>)；[MaelstromMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L88>)；[DrainLifeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SoulNexus.cs#L98>) |
| SpectralKnight | [HexMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpectralKnight.cs#L61>)；[SoulSlashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpectralKnight.cs#L71>)；[SoulFlameMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpectralKnight.cs#L79>) |
| SpinyToad | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs#L71>)；[SpikesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs#L77>)；[ExplosionMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs#L85>)；[LashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/SpinyToad.cs#L96>) |
| Stabbot | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Stabbot.cs#L29>)；[StabMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Stabbot.cs#L49>) |
| TenHpMonster | [NothingMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TenHpMonster.cs#L27>) |
| TerrorEel | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L62>)；[CrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L86>)；[ThrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L94>)；[StunMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L105>)；[TerrorMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TerrorEel.cs#L110>) |
| TestSubject | [TriggerDeadState](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L166>)；[AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L174>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L223>)；[AfterPowerApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L238>)；[AfterPowerRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L246>)；[RespawnMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L254>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L282>)；[SkullBashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L290>)；[MultiClawMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L299>)；[Phase3LacerateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L309>)；[BigPounceMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L318>)；[BurningGrowlMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L326>)；[Revive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TestSubject.cs#L335>) |
| TheAdversaryMkOne | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs#L29>)；[SmashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs#L50>)；[BeamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs#L58>)；[BarrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkOne.cs#L66>) |
| TheAdversaryMkThree | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs#L31>)；[CrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs#L52>)；[FlameBeamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs#L60>)；[BarrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkThree.cs#L68>) |
| TheAdversaryMkTwo | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs#L33>)；[BashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs#L54>)；[FlameBeamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs#L62>)；[BarrageMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheAdversaryMkTwo.cs#L70>) |
| TheForgotten | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L37>)；[MiasmaMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L53>)；[DreadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheForgotten.cs#L62>) |
| TheInsatiable | [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L83>)；[LiquifyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L114>)；[ThrashMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L147>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L157>)；[SalivateMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheInsatiable.cs#L166>) |
| TheLost | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs#L31>)；[DebilitatingSmogMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs#L47>)；[EyeLasersMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheLost.cs#L55>) |
| TheObscura | [IllusionMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheObscura.cs#L78>)；[PiercingGazeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheObscura.cs#L89>)；[WailMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheObscura.cs#L97>)；[HardeningStrikeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TheObscura.cs#L104>) |
| ThievingHopper | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L152>)；[ThieveryMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L184>)；[NabMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L250>)；[HatTrickMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L258>)；[FlutterMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L266>)；[EscapeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ThievingHopper.cs#L276>) |
| Toadpole | [SpikeSpitMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Toadpole.cs#L88>)；[WhirlMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Toadpole.cs#L99>)；[SpikenMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Toadpole.cs#L107>) |
| TorchHeadAmalgam | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs#L40>)；[OnDieToDoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs#L67>)；[TackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs#L81>)；[WeakTackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs#L89>)；[SoulBeamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TorchHeadAmalgam.cs#L97>) |
| ToughEgg | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ToughEgg.cs#L123>)；[HatchMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ToughEgg.cs#L155>)；[Hatch](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ToughEgg.cs#L169>)；[NibbleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/ToughEgg.cs#L176>) |
| TrackerRubyRaider | [TrackMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TrackerRubyRaider.cs#L40>)；[HoundsMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TrackerRubyRaider.cs#L47>) |
| Tunneler | [BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs#L87>)；[BurrowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs#L95>)；[BelowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs#L103>)；[GetStunned](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs#L128>)；[StillDizzyMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Tunneler.cs#L134>) |
| TurretOperator | [ReloadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TurretOperator.cs#L50>)；[UnloadMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TurretOperator.cs#L57>) |
| TwigSlimeM | [ClumpShotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwigSlimeM.cs#L47>)；[StickyShotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwigSlimeM.cs#L55>) |
| TwigSlimeS | [TackleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwigSlimeS.cs#L32>) |
| TwoTailedRat | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L112>)；[ScratchMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L146>)；[DiseaseBiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L155>)；[ScreechMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L164>)；[CallForBackup](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L172>)；[CanSummon](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/TwoTailedRat.cs#L194>) |
| Vantom | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L91>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L97>)；[InkBlotMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L132>)；[InkyLanceMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L150>)；[DismemberMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L170>)；[PrepareMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Vantom.cs#L191>) |
| VineShambler | [GraspingVinesMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/VineShambler.cs#L59>)；[SwipeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/VineShambler.cs#L70>)；[ChompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/VineShambler.cs#L80>) |
| WaterfallGiant | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L159>)；[AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L166>)；[PressurizeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L224>)；[PressureUpMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L232>)；[StompMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L242>)；[RamMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L253>)；[SiphonMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L263>)；[PressureGunMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L272>)；[AboutToBlowMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L283>)；[ExplodeMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L291>)；[TriggerAboutToBlowState](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/WaterfallGiant.cs#L301>) |
| Wriggler | [SpawnedMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Wriggler.cs#L73>)；[BiteMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Wriggler.cs#L78>)；[WriggleMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Wriggler.cs#L87>) |
| Zapbot | [AfterAddedToRoom](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Zapbot.cs#L29>)；[ZapMove](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Monsters/Zapbot.cs#L49>) |

## 7. 玩家已有debuff完整类别核对（47类 + 数值负属性；基线与当前并列）

原生47类直接或条件返回`PowerType.Debuff`，不是按中文名称猜测。基线列的“未实现”指**调查起点的玩家自身/任意来源已有实例**；当前实现单列，不沿用基线缺口为现状；这些基线缺口不否定第4节已存在的敌源细分支持。敌人身上的同名负面Power必须保留。Temporary三类依数值条件是Debuff，不能把返还/到期清理吞掉；Strength/Dexterity/Focus虽Type=Buff也能有负量，另列。

| 原生debuff类/贡献函数 | baseline对玩家已有自身来源 | 基线说明（保留） | 当前实现状态与具体贡献 |
|---|---|---|---|
| [BiasedCognitionPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BiasedCognitionPower.cs>)：[AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BiasedCognitionPower.cs#L21>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DomainSelfDebuffEffects.Penalty`禁用该负面回调，其他计时/移除保留。[S3](#current-self)。 |
| [BorrowedTimePower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BorrowedTimePower.cs>)：[TryModifyEnergyCostInCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BorrowedTimePower.cs#L21>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/BorrowedTimePower.cs#L32>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DomainCardContributions.CostContribution`对玩家减益费用贡献返回原费用，计时及其他来源改费保留。[S3](#current-self)。 |
| [ChainsOfBindingPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs>)：[AfterCardDrawn](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L36>), [BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L48>), [ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L67>), [BeforeSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ChainsOfBindingPower.cs#L80>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源）；未实现（任意自身来源）；详见第4节。 | 已实现：Bound附着贡献与ShouldPlay否决均按自身减益判定解除；原出牌记录及回合清除保留。[S3](#current-self)。 |
| [ConfusedPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConfusedPower.cs>)：[AfterCardDrawn](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConfusedPower.cs#L31>), [NextEnergyCost](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConfusedPower.cs#L47>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DomainConfusedCosts`标记Confused生成的本地费用modifier，读费用时临时跳过；保留随机抽取顺序和其他改费，退出恢复该modifier。[S3](#current-self)。 |
| [ConquerorPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConquerorPower.cs>)：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConquerorPower.cs#L23>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConquerorPower.cs#L40>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [ConstrictPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConstrictPower.cs>)：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConstrictPower.cs#L19>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ConstrictPower.cs#L27>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源）；未实现（任意自身来源）；详见第4节。 | 已实现：伤害读取有效量0；新施加保留Power，原计时/施加者死亡清理继续。[S3](#current-self)。 |
| [DampenPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs>)：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L29>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L41>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L58>), [AddCaster](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DampenPower.cs#L73>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（领域内初次降级）；未实现（进入前已降级恢复）；详见第4节。 | 已实现：按原账本临时返还被降级量；退出撤回借回量，原生移除先撤回后返还，避免双升级。[S2](#current-dampen)。 |
| [DebilitatePower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DebilitatePower.cs>)：[ModifyVulnerableMultiplier](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DebilitatePower.cs#L26>), [ModifyWeakMultiplier](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DebilitatePower.cs#L39>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DebilitatePower.cs#L52>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：其加重倍率只从Weak/Vulnerable调用；外层减益倍率分派直接返回1，因此加重效果也不进入，倒数保留。[S3](#current-self)。 |
| [DemisePower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DemisePower.cs>)：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DemisePower.cs#L19>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：准确Damage调用点按自身减益判定取消，混合回调的计数/递减/移除继续执行。[S3](#current-self)。 |
| [DisintegrationPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DisintegrationPower.cs>)：[AfterSideTurnEndLate](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DisintegrationPower.cs#L19>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：未实现；详见第4节。 | 已实现：准确Damage调用点按自身减益判定取消，混合回调的计数/递减/移除继续执行。[S3](#current-self)。 |
| [DoomPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs>)：[DoomKill](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs#L40>), [IsOwnerDoomed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs#L63>), [BeforeSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs#L68>), [PlayVfx](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs#L80>), [StartDoomAnim](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs#L114>), [WaitForTween](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/DoomPower.cs#L146>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`GetDoomedCreatures`过滤被压制玩家，回合末`IsOwnerDoomed`调用也中性化；退出重新按剩余Doom判断。[S3](#current-self)。 |
| [FlankingPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlankingPower.cs>)：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlankingPower.cs#L28>), [ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlankingPower.cs#L34>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FlankingPower.cs#L51>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [FrailPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FrailPower.cs>)：[ModifyBlockMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FrailPower.cs#L22>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/FrailPower.cs#L35>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源）；未实现（任意自身来源）；详见第4节。 | 已实现：`BlockMultiplier`将玩家减益格挡倍率置1，原回合到期保留。[S3](#current-self)。 |
| [HangPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HangPower.cs>)：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HangPower.cs#L18>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [HexPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs>)：[TryModifyKeywordsInCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L26>), [AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L39>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L47>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L55>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L63>), [Afflict](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/HexPower.cs#L75>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源虚无）；未实现（任意自身来源）；详见第4节。 | 已实现：只撤销Hex贡献的动态Ethereal，Hexed污蚀、其他来源Ethereal和原移除流程保留；退出恢复仍有效的Hex贡献。[S3](#current-self)。 |
| [ImbalancedPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ImbalancedPower.cs>)：[AfterDamageGiven](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ImbalancedPower.cs#L17>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（保留敌方不利）；详见第4节。原生主要面向特定敌方模型，原敌方不利行为保留；不是玩家可用能力的通用适配。 | 已实现：`DomainSelfDebuffEffects.Penalty`禁用该负面回调，其他计时/移除保留。[S3](#current-self)。 |
| [KnockdownPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/KnockdownPower.cs>)：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/KnockdownPower.cs#L28>), [ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/KnockdownPower.cs#L34>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/KnockdownPower.cs#L51>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [MagicBombPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MagicBombPower.cs>)：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MagicBombPower.cs#L21>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MagicBombPower.cs#L32>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：准确Damage调用点按自身减益判定取消，混合回调的计数/递减/移除继续执行。[S3](#current-self)。 |
| [MindRotPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MindRotPower.cs>)：[ModifyHandDraw](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MindRotPower.cs#L14>), [AfterModifyingHandDraw](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/MindRotPower.cs#L23>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：未实现；详见第4节。 | 已实现：`DrawCount`跳过减抽贡献，返回入参抽牌数。[S3](#current-self)。 |
| [NeurosurgePower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NeurosurgePower.cs>)：[AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NeurosurgePower.cs#L21>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DomainSelfDebuffEffects.Penalty`禁用该负面回调，其他计时/移除保留。[S3](#current-self)。 |
| [NoBlockPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoBlockPower.cs>)：[AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoBlockPower.cs#L22>), [ModifyBlockMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoBlockPower.cs#L30>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`BlockMultiplier`将玩家减益格挡倍率置1，原回合到期保留。[S3](#current-self)。 |
| [NoDrawPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoDrawPower.cs>)：[ShouldDraw](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoDrawPower.cs#L19>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoDrawPower.cs#L33>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DrawAllowed`不再让该减益否决抽牌，Power及到期继续。[S3](#current-self)。 |
| [NoEnergyGainPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoEnergyGainPower.cs>)：[ModifyEnergyGain](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoEnergyGainPower.cs#L19>), [AfterModifyingEnergyGain](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoEnergyGainPower.cs#L28>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/NoEnergyGainPower.cs#L34>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`Energy`跳过禁止获得能量贡献，原到期继续。[S3](#current-self)。 |
| [OblivionPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/OblivionPower.cs>)：[BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/OblivionPower.cs#L34>), [AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/OblivionPower.cs#L48>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/OblivionPower.cs#L57>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：仅阻止`AfterCardPlayed`施加Doom的调用，出牌计数与回合清理继续。[S3](#current-self)。 |
| [PlowPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlowPower.cs>)：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PlowPower.cs#L28>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（保留敌方不利）；详见第4节。原生主要面向特定敌方模型，原敌方不利行为保留；不是玩家可用能力的通用适配。 | 已实现（保留敌方负面）；未实现（任意玩家挂载适配）：原生仅敌方用，受击后的移除Strength/Stun未增加玩家贡献gate。不得据其Debuff类型声称玩家效果已禁用。 |
| [PoisonPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PoisonPower.cs>)：[CalculateTotalDamageNextTurn](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PoisonPower.cs#L42>), [AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/PoisonPower.cs#L55>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：准确Damage调用点按自身减益判定取消，混合回调的计数/递减/移除继续执行。[S3](#current-self)。 |
| [RingingPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs>)：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L22>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L34>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L42>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L51>), [ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/RingingPower.cs#L64>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源限牌）；未实现（任意自身来源）；详见第4节。 | 已实现：`PlayContribution`按玩家减益直接放行；独立的出牌计次/回合重置及污蚀记录保留。[S3](#current-self)。 |
| [ShriekPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShriekPower.cs>)：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShriekPower.cs#L25>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（保留敌方不利）；详见第4节。原生主要面向特定敌方模型，原敌方不利行为保留；不是玩家可用能力的通用适配。 | 已实现（保留敌方负面）；未实现（任意玩家挂载适配）：原生回调强转TerrorEel并Stun，无玩家实现；不将本来仅敌方适用的状态列为正常玩家能力。[S3](#current-self)。 |
| [ShrinkPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs>)：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L48>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L66>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L79>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L87>), [ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/ShrinkPower.cs#L95>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源伤害）；未实现（已有缩小视觉/任意自身来源）；详见第4节。 | 已实现：伤害倍率中性化；进入/领域内施加恢复尺度1，退出仍有Shrink时回到0.5，原到期保留。[S3](#current-self)。 |
| [SicEmPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SicEmPower.cs>)：[AfterDamageGiven](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SicEmPower.cs#L23>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SicEmPower.cs#L31>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DomainSelfDebuffEffects.Penalty`禁用该负面回调，其他计时/移除保留。[S3](#current-self)。 |
| [SlothPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs>)：[ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs#L22>), [BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs#L31>), [BeforeSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlothPower.cs#L42>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：未实现；详见第4节。 | 已实现：`PlayContribution`按玩家减益直接放行；独立的出牌计次/回合重置及污蚀记录保留。[S3](#current-self)。 |
| [SlowPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs>)：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L26>), [ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L33>), [AfterModifyingDamageAmount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L46>), [AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SlowPower.cs#L52>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（保留敌方不利）；详见第4节。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [SmoggyPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs>)：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L22>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L39>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L47>), [ShouldPlay](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SmoggyPower.cs#L64>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源限牌）；未实现（任意自身来源）；详见第4节。 | 已实现：`PlayContribution`按玩家减益直接放行；独立的出牌计次/回合重置及污蚀记录保留。[S3](#current-self)。 |
| [StranglePower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StranglePower.cs>)：[BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StranglePower.cs#L36>), [AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StranglePower.cs#L50>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/StranglePower.cs#L59>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：准确Damage调用点按自身减益判定取消，混合回调的计数/递减/移除继续执行。[S3](#current-self)。 |
| [SurroundedPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs>)：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L46>), [BeforeCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L74>), [BeforePotionUsed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L82>), [AfterDeath](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L90>), [UpdateDirection](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L102>), [FaceDirection](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L121>), [FlipScale](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/SurroundedPower.cs#L147>) | 已实现（敌方背击倍率） | 不依赖施加receipt；仅敌方攻击的增伤中性化，原朝向事实保留。 | 已实现：原有敌方背击增伤屏蔽继续，方向与左右站位事实保留；非敌方攻击不扩大为额外取消范围。 |
| [TagTeamPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TagTeamPower.cs>)：[ModifyCardPlayCount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TagTeamPower.cs#L19>), [AfterModifyingCardPlayCount](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TagTeamPower.cs#L41>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`PlayCount`跳过玩家减益重演/出牌次数贡献，返回原count。[S3](#current-self)。 |
| [TaintedPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TaintedPower.cs>)：[ModifyDamageAdditive](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TaintedPower.cs#L18>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TaintedPower.cs#L31>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（有敌源receipt）；未实现（任意自身来源）；详见第4节。 | 已实现：`DamageAdditive`跳过玩家Tainted伤害惩罚，不再要求敌源receipt；原到期继续。[S3](#current-self)。 |
| [TangledPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs>)：[AfterApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L23>), [AfterCardEnteredCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L32>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L40>), [AfterRemoved](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L49>), [TryModifyEnergyCostInCombat](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TangledPower.cs#L59>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源费用）；未实现（任意自身来源）；详见第4节。 | 已实现：`DomainCardContributions.CostContribution`对玩家减益费用贡献返回原费用，计时及其他来源改费保留。[S3](#current-self)。 |
| [TemporaryDexterityPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryDexterityPower.cs>)：[IgnoreNextInstance](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryDexterityPower.cs#L137>), [BeforeApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryDexterityPower.cs#L142>), [AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryDexterityPower.cs#L154>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryDexterityPower.cs#L169>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：有效属性读取补偿当前负量及临时属性债务，原Temporary返还与移除保留。[S3](#current-self)。 |
| [TemporaryFocusPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryFocusPower.cs>)：[IgnoreNextInstance](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryFocusPower.cs#L137>), [BeforeApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryFocusPower.cs#L142>), [AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryFocusPower.cs#L154>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryFocusPower.cs#L169>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：OrbValue补偿临时Focus债务；Focus被归零移除时由首个有效领域的RestoreMissingFocus补偿，退出恢复原贡献。[S3](#current-self)。 |
| [TemporaryStrengthPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs>)：[IgnoreNextInstance](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs#L141>), [BeforeApplied](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs#L146>), [AfterPowerAmountChanged](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs#L158>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs#L173>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：有效属性读取补偿当前负量及临时属性债务，原Temporary返还与移除保留。[S3](#current-self)。 |
| [TenderPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TenderPower.cs>)：[AfterCardPlayed](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TenderPower.cs#L44>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TenderPower.cs#L55>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源）；详见第4节。 | 已实现：TenderApply按当前领域取消新扣款，已有扣款走属性债务补偿；只归还已支付值，避免未扣却返。[S3](#current-self)。 |
| [TheGambitPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TheGambitPower.cs>)：[AfterDamageReceived](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/TheGambitPower.cs#L16>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：受伤回调中的Kill调用被取消，其他战斗伤害事实保留。[S3](#current-self)。 |
| [VulnerablePower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VulnerablePower.cs>)：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VulnerablePower.cs#L27>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/VulnerablePower.cs#L59>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源）；未实现（任意自身来源）；详见第4节。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [WasteAwayPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WasteAwayPower.cs>)：[ModifyMaxEnergy](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WasteAwayPower.cs#L16>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：未实现；详见第4节。 | 已实现：`MaxEnergy`跳过减最大能量贡献，返回原amount。[S3](#current-self)。 |
| [WeakPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WeakPower.cs>)：[ModifyDamageMultiplicative](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WeakPower.cs#L24>), [AfterSideTurnEnd](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WeakPower.cs#L48>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。已有有限支持：已实现（敌源）；未实现（任意自身来源）；详见第4节。 | 已实现：`DamageMultiplier`将玩家减益倍率置1；状态层数、出牌/回合计数及到期仍执行。[S3](#current-self)。 |
| [WraithFormPower](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WraithFormPower.cs>)：[AfterSideTurnStart](<../.local/domain-audit/native/MegaCrit.Sts2.Core.Models.Powers/WraithFormPower.cs#L21>) | 未实现（通用自身已有实例） | 无覆盖所有自身来源的通用领域贡献层。 | 已实现：`DomainSelfDebuffEffects.Penalty`禁用该负面回调，其他计时/移除保留。[S3](#current-self)。 |

负属性补充：`StrengthPower.ModifyDamageAdditive` / `DexterityPower.ModifyBlockAdditive`的敌源欠账已由DomainPlayerStatContributions补偿；**自身来源负Strength/Dexterity以及负Focus没有通用恢复实现**。这不是删除临时属性Power即可正确解决：Temporary到期可能需要返还，必须贡献级区分即时能力与清理。

### 持续展示：基线与当前实现

现 [PowerPresentationDomain.Suppressed](<../src/Volibear/Presentation/PowerPresentationDomain.cs#L41>)只对敌对象发布`domain_suppression_applied`，[MechanicGlossary](<../src/Volibear/Content/MechanicGlossary.cs#L16>)只有领域压制解释。baseline没有逐Power自身禁用图标/持续禁用状态，也无“已被领域禁用”的动态悬停分支。这是基线结论。当前已接通的动态展示范围、仍缺的无图标持续展示和测试层级见G08及[S4](#current-presentation)，不把展示缺口改写成逻辑缺口。

## 8. 复核方法与Lead更新规则

调查私有脚本：[inventory.py](<../.local/domain-audit/inventory.py>)、[methods.py](<../.local/domain-audit/methods.py>)、[powers.py](<../.local/domain-audit/powers.py>)、[debuffs.py](<../.local/domain-audit/debuffs.py>)、[render.py](<../.local/domain-audit/render.py>)。它们只提取静态索引/渲染文档，不运行游戏。脚本中的机制结论是本次逐链阅读形成的显式映射，不以字符串匹配到Power名称就自动判已支持。

```sh
DOTNET_ROLL_FORWARD=Major /home/float/.local/share/volibear-toolchain/tools/ilspycmd -p \
  -o .local/domain-audit/native .local/game/data_sts2_linuxbsd_x86_64/sts2.dll
python .local/domain-audit/inventory.py
python .local/domain-audit/methods.py
python .local/domain-audit/powers.py
python .local/domain-audit/debuffs.py
```

- 本轮实际完成上述静态提取。ilspycmd默认要求.NET8；本机仅.NET9首次报150，设置`DOTNET_ROLL_FORWARD=Major`后成功退出0，未安装新工具。
- 第2节当前列与第7节当前列已按现行源码逐项回填；第3节完整121类清单、第4节基线结论及第7节基线列保留。当前新增链及已执行测试记录见第9节。后续只依据具体修改和独立回执更新，不运行旧render脚本覆盖中文名。
- G01必须分别覆盖计数、全部移动入口、已被拉动后的进入、处决、退出剩余计数、宠物/Osty；G02分别覆盖领域前降级、领域中新降级、重复施法者、退出及原生AfterRemoved防重复退款；G03分别覆盖进入前/领域中、来源、能力恢复、原生命周期、退出；G08展示与逻辑共用同一抑制判定。
- 本文没有“未知状态”作为合格结论：全121类、所有实际Power引用与非Power特殊调用均落在明确已实现/未实现/按规则保留的步骤。实现结论与运行层级分开记录。

## 9. 当前实现增量与测试层级

<a id="current-sandpit"></a>
### S1：沙坑计数、移动与处决

| 步骤 | 当前结论及生产依据 |
|---|---|
| 每敌方回合扣层 | 已实现禁用：[DomainSandpitEffects.Install/Suppress](<../src/Volibear/Core/DomainSandpitEffects.cs#L19>)拦AfterSideTurnStartLate |
| 金额变更、回合末、新生物与Osty复活拉动 | 已实现禁用：全部汇入同文件UpdateCreaturePositions，按IsSuppressed跳过 |
| 进入前已发生位移 | 已实现保留当前位置；不新增回到初始坐标的玩法，领域内后续拉动停止 |
| 吃人、隐藏及强制击杀 | 已实现禁用：[DomainEnemySpecialContributions.AfterRemoved](<../src/Volibear/Core/DomainEnemySpecialContributions.cs#L40>)保留原payload拦截 |
| 退出领域 | 已实现继续剩余计数；下一敌方回合正常扣一层、移动从当前位置继续，不追补冻结回合 |
| 玩家主动加层 | 已实现保留：FranticEscape加层不被回合扣层前缀取消，相应拉动仍由统一入口屏蔽 |

<a id="current-dampen"></a>
### S2：Dampen临时恢复与Hex

- **已有降级进入恢复：已实现。** [DomainDampenRestoration.Refresh](<../src/Volibear/Core/DomainDampenRestoration.cs#L42>)读取原生账本，逐Dampen、逐卡记录实际借回量。[DomainPower.AfterApplied/AfterRemoved/AfterDeath](<../src/Volibear/Core/DomainPower.cs#L75>)刷新全队。
- **领域中新施加：已实现临时中和。** [DomainDampenTransactions.CommitPair](<../src/Volibear/Core/DomainDampenTransactions.cs#L196>)保留原账本与Downgrade，再立即Refresh借回；不沿用基线“账本新增被取消”的结论。
- **退出及原生移除：已实现。** ReturnLoan撤销借回差额，额外正常升级保留；原生AfterRemoved前先撤回借回量，随后原生归还旧账本，防止双加。退出后未到期Dampen重新生效。
- **Hex动态虚无：已实现。** [DomainCardContributions.KeywordsContribution](<../src/Volibear/Core/DomainCardContributions.cs#L162>)保留输入keywords，只禁用Hex新增的Ethereal贡献；Hexed污蚀及其他来源Ethereal保留。退出后仍有效Hex恢复贡献。

<a id="current-self"></a>
### S3：自身减益与47类当前核对

- [DomainSelfDebuffEffects.IsSuppressed/Install](<../src/Volibear/Core/DomainSelfDebuffEffects.cs#L28>)按玩家和领域判定，正常玩家减益不再要求敌源receipt。生产入口为[DomainPlayerDebuffContributions.Install](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L23>)，由[ModEntry](<../src/Volibear/ModEntry.cs>)安装。
- [DomainPlayerDebuffContributions.Patches](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs#L83>)处理伤害/格挡倍率、Chains与Constrict；[DomainCardContributions](<../src/Volibear/Core/DomainCardContributions.cs#L159>)处理关键词、费用与出牌允许；[DomainSelfDebuffEffects](<../src/Volibear/Core/DomainSelfDebuffEffects.cs#L39>)处理能量、抽牌、Orb、出牌次数、加法伤害以及精确负面回调/伤害/处决调用点。知识恶魔四惩罚分别落到伤害、抽牌、出牌和最大能量分派，选择界面与计次保留。
- [DomainPlayerStatContributions.Debt](<../src/Volibear/Core/DomainPlayerStatContributions.cs#L110>)补偿负Strength/Dexterity与Temporary债务；Focus及TemporaryFocus由OrbValue/RestoreMissingFocus补偿，包括Focus归零后原Power不存在的情形。正属性不清空，原Temporary返还继续。
- [DomainConfusedCosts](<../src/Volibear/Core/DomainConfusedCosts.cs#L18>)标记Confused生成的本地费用modifier，领域期间读费用跳过这些身份，退出恢复；随机顺序及其他改费保留。RefreshScales/ShrinkApplied处理已有Shrink进入/退出与领域中新施加，屏幕呈现另作游戏验收。
- 第7节47类当前列均已填写：45类正常玩家减益对应贡献已接通；Plow/Shriek仅怪物适用，敌方负面效果保留，不宣称任意玩家挂载支持。现行IsSuppressed已显式排除这两类，两个玩家挂载负例通过，不再误标禁用。
- **持续与退出：** 新减益Power继续附着，持续时间、计数及必要到期照常推进，领域只禁用负面贡献。退出后尚未到期贡献恢复；不重建已到期状态，不补发取消的持续伤害或一次性事件。

<a id="current-presentation"></a>
### S4：逻辑压制与持续展示分别判定

| 项目 | 当前实现及范围 |
|---|---|
| 自定义关键词 | 已实现：[MechanicHoverTips.ForCard](<../src/Volibear/Content/MechanicHoverTips.cs>)从标题及正文匹配26类词条，保留canonical预览保护 |
| 玩家减益 | 已实现：[PowerPresentationDisabled.PowerTips](<../src/Volibear/Presentation/PowerPresentationDisabled.cs>)调用Core只读判定，附“已被领域禁用”，图标增加暗化叉线，不删除Power |
| 已配置敌方Power | 已实现：37类Power分17类贡献说明；混合Power只说明被压制部分，Strength和敌方负面不笼统禁用 |
| 已配置无图标行动 | 已实现：[MechanicEnemyHoverTips](<../src/Volibear/Content/MechanicEnemyHoverTips.cs>)覆盖8组：召唤、孵化/变形、FatGremlin逃跑、Hopper偷牌、偷金币、有害状态牌、沙坑、知识限制；Hopper逃跑不混入偷牌支持 |
| 未配置的直接瞬时贡献，例如泛化敌方Heal | 逻辑压制已实现；专属持续badge未实现。原取消反馈保留；无专属持续badge不改变Heal压制结论，不宣称全121类自动具有专属徽标 |
| UI生命周期 | 已实现：4个补丁接PowerModel.HoverTips、Creature.HoverTips、NPower._Ready、NCreature._Ready；[PowerPresentationDisabledVisual](<../src/Volibear/Presentation/PowerPresentationDisabledVisual.cs>)订阅CombatStateChanged刷新，TreeExited解绑。引擎屏幕验收未执行 |

**已定位的表现文案错配：** [MechanicGlossary.EnemyEntries](<../src/Volibear/Content/MechanicGlossary.cs#L56>)的KNOWLEDGE绑定KnowledgeDemon，但现行说明写成Dampen/Hex。逻辑上知识恶魔四选择惩罚已实现；该描述的正确对应尚未回填生产，按文本审核顺序由Lead处理。此处仅记录技术缺项，不修改冻结审核稿或生产文本。

### S5：实际执行证据

| 层级 | 结果与证据 |
|---|---|
| Core窄语义与原生引用/Harmony绑定 | 已通过37项自身减益语义（含Plow/Shriek两个负例）、5项沙坑语义、28处绑定，未启动游戏；[test_domain_self_debuff.py](<../tests/test_domain_self_debuff.py#L21>)校验标识，[定向批次日志](<../.local/logs/domain-compat-round1.log#L37>)记录该项OK；整批37项、16.427s、36通过/1跳过，不将跳过计为通过 |
| 悬停原生引用/接线 | 已通过87项检查与4个真实Harmony入口，并执行PowerModel.HoverTips；领域谓词/图标IO使用替身，Godot渲染未运行。[test_native.py](<../tests/domain_disabled_presentation/test_native.py>)、[Program.cs](<../tests/domain_disabled_presentation/Program.cs>)已接[regression.py](<../tools/regression.py>) |
| 关键词/预览 | 已通过5项关键词测试与2项canonical测试：[关键词测试](<../tests/mechanic_hints/Program.cs>)、[canonical测试](<../tests/test_hover_tips_canonical.py>) |
| 三战斗原生探针 | 入口已实现、游戏未执行：[DomainSuppressionAcceptanceProbe](<../src/Volibear/DomainSuppressionAcceptanceProbe.cs>)默认all单进程建立sandpit、knights、self三场新战斗；[headless.py](<../tools/headless.py>)提供domain-suppression场景 |
| 回执独立校验 | 已通过12项工具/畸形回执测试，另2项旧路由与3项报告测试通过；[domain_suppression_evidence.py](<../tools/domain_suppression_evidence.py>)严格校验6+11+12项断言、版本/token/family/布尔/唯一顺序及沙坑baseline/on/off数值；[测试](<../tests/test_domain_suppression_evidence.py>)使用构造回执，不冒充游戏通过 |
| 完整游戏/多人/视觉/release gate | 本轮均未执行；实现与窄测试结果不填为完整原生验收通过 |

### S6：明确剩余范围

1. **未实现：** G04的Hopper逃脱及倒数、G05的三个BattleFriend事件超时逃脱、G06的TheForgotten新获敌方敏捷收益取消。
2. **未实现（表现）：** 未配置直接贡献的专属持续badge；相应逻辑压制及瞬时反馈保持原已实现结论。
3. **明确保留：** 沙坑进入前已发生位移、普通攻击、已有/直接力量格挡、敌方负面状态、原生计数/到期及已提交事实。任意第三方私有写入、超出有限receipt来源的已有有害卡payload仍不属于全来源适配。
4. 实现状态已逐项判定；三战斗实跑、发布与视觉验收尚未执行，作为独立测试层级记录，不作为未知实现占位。
