# 领域压制 · 敌人机制盘点与工作量（StS2 v0.107.1）

> 配套：[`platform.md`](platform.md)（Hook/API 事实）、[`content.md`](content.md) §3.3 / §5.4（机制语义）、[方案正文](../volibear-sts2-mod-plan-2026-10-30.md) §5.4。
> 数据来源：本机 `sts2.dll` 元数据（121 个怪物类、263 个 Power 类、15 种意图、`Hook` 149 个分发方法）+ 从 `SlayTheSpire2.pck` 解出的中英文 `monsters.json`（123 个有招式的怪物 / 356 个 move）、`powers.json`（290 条）、`encounters.json`（93 个遭遇组）。
> 目标：回答"领域到底要压哪些机制、哪些可以放、哪些只能 patch，工作量多少"。

## 0. 结论

1. **不需要自研 AI 循环替换敌人循环。** StS2 的怪物行为是"`MonsterMoveStateMachine`（选招）→ `MoveState.PerformMove(IEnumerable<Creature>)`（执行招式）→ 招式内的意图（15 种 `IntentType`）+ 命令效果"。**压制可以在"意图分类"和"效果执行"两层做**，不必重写选招。
2. **通用禁用覆盖面很大**：`Hook` 是中心分发器（149 个方法，含 `ShouldDie`、`ShouldAllowHitting`、`ShouldAllowTargeting`、`ModifyDamage`、`ModifyPowerAmountGiven`、`ShouldClearBlock`、`ModifyCardBeingAddedToDeck` 等）。在领域 active 时对"来源=敌方的正面 Power/效果"做统一过滤，**一处代码覆盖全部怪物**。
3. **真正需要逐怪例外的只有约 12–22 个**（复活/多阶段/分裂/召唤/偷牌/诅咒/削升级），其中 **8–12 个是重点**；其余可用"禁用一个 move"的数据表处理（0.25–0.5 人日/个），不需要 AI 重写。
4. **工作量**（仅领域压制子系统，不含卡牌/表现）：
   - Tier 1 最小可用：**12–18 人日**
   - Tier 2 推荐 v1：**28–40 人日**
   - Tier 3 全保真：**45–65 人日**
   - Tier 4 自研 AI 循环替换（不推荐）：+50–90 人日，且是最高风险项

## 1. 数据面（本机实测）

| 项 | 数量 | 说明 |
|---|---|---|
| 怪物类 | **121**（123 个有招式） | 含测试/假人；正式遭遇约 100 个 |
| 招式（move） | **356** | 每个 move 有 `StateId`、`Intents`、`PerformMove`、`FollowUpStateId` |
| 遭遇组 | **93** | 普通 41 / 弱 16 / 精英 12 / Boss 12 / 事件 7 / 其他 5 |
| Power 类 | **263** | 本地化条目 290（含 mock/子能力）；描述明确为敌方侧 32 条 |
| 意图类型 | **15** | Attack / Buff / Debuff / DebuffStrong / Defend / Escape / Heal / Hidden / Summon / Sleep / Stun / StatusCard / CardDebuff / DeathBlow / Unknown |
| 死亡/复活相关覆写 | 19 个怪 | `BeforeDeath` / `AfterDeath` / `ShouldDie` / `Revive` |
| 召唤 | 7 个怪 | `Summon` / `CallForBackup` |
| 多阶段/形态 | 3 个怪 | CeremonialBeast、Queen、TestSubject |
| 逃跑 / 偷牌 | 2 / 3 个怪 | ThievingHopper；TheForgotten、TheLost、ThievingHopper |
| 诅咒/卡牌注入 | 2 个怪 | KnowledgeDemon、SpectralKnight |
| 蓄力/计数状态 | 9 个怪 | Axebot、Rocket、CubexConstruct、MechaKnight、FrogKnight 等 |

关键接口（已在本机程序集核实）：

- `MoveState.Intents : IReadOnlyList<AbstractIntent>`、`AbstractIntent.IntentType`
- `MoveState.PerformMove(IEnumerable<Creature>) : Task`
- `MonsterModel.RollMove(IEnumerable<Creature>)` / `PerformMove()`
- `Hook.IterateCombatHookListeners(ICombatState)` + 149 个 Hook 方法；其中带 `IEnumerable<AbstractModel>` / `AbstractModel` 参数的方法可做"模型过滤"

## 2. 敌人机制分类与压制判定

### 2.1 必须压制（对敌有利、影响大）

| 类别 | 具体机制（实例） | 当前实现载体 | 压制方式 |
|---|---|---|---|
| 复活/续命 | ADAPTABLE（复活更强）、ILLUSION（下回合满血复活）、INFESTED（死后召唤）、TestSubject 的 `Revive` | Power + `ShouldDie`/`BeforeDeath` 覆写 | Hook 过滤 + `ShouldDie` 覆盖 + 1 个怪例外 |
| 保护性阶段 | BURROWED（格挡不清且被打光后才眩晕）、二阶段转换（CeremonialBeast）、三层形态（TestSubject） | Power + 状态机 | Hook 过滤 + 2–3 个怪例外 |
| 限伤/减伤 | HARDENED_SHELL（每回合最多掉 20）、GUARDED（半伤）、SLIPPERY（下次只掉 1） | Power + `ModifyDamage`/`HpLost` | Hook `ModifyDamage`/`ModifyHpLost` 过滤 |
| 无敌/不可选 | INTANGIBLE、无敌/不可选中阶段、`ShouldAllowHitting`/`ShouldAllowTargeting` | Power/覆写 | Hook `ShouldAllowHitting`/`ShouldAllowTargeting` |
| 永久增益 | HIGH_VOLTAGE / TERRITORIAL（每回合 +力量）、RITUAL、ENRAGE（出技能 +力量）、CRAB_RAGE（同伴死亡 +5 力量 99 格挡）、被动格挡（CURL_UP/SKITTISH） | Power 钩子（回合开始/受伤触发） | Hook 过滤敌方 Power + 命令级 `PowerCmd.Apply` gate |
| 召唤/分裂 | Queen、TheObscura、Fabricator、TwoTailedRat、FatGremlin/SneakyGremlin(WakeUp)、Decimillipede 分段 | 招式内 `CreatureCmd.Add` / `SummonIntent` | 意图层 + 命令 gate |
| 治疗/回血 | `HealIntent`、SIPHON 类 | `CreatureCmd.Heal` | 意图层 + 命令 gate |
| 给玩家塞牌 | PERSONAL_HIVE（每次被攻击塞 Dazed）、状态牌注入 | `CardPileCmd.AddGeneratedCardToCombat` / `AddCurseToDeck` | 命令 gate |
| 卡牌改写/削升级 | Aeonglass 的 Wither（`_witherUpgradeCount`、`MatchWitherToUpgradeCount`）、降级/转化玩家牌 | `CardCmd.Downgrade/Transform`、`ModifyCardBeingAddedToDeck` | 命令 gate + Hook |
| 限牌/禁打 | 限制每回合出牌数 / 禁某类牌 | Power + `ModifyCardPlayCount` | Hook 过滤 |
| 玩家负面 | Debuff / DebuffStrong 意图：Weak、Vulnerable、Frail、Poison、Doom、Burn、Dazed、Entangle 类 | 招式内 `PowerCmd.Apply` / 状态牌 | 意图层 + 命令 gate |
| 偷窃/逃跑 | ThievingHopper 偷牌后逃跑；TheForgotten/TheLost 偷牌 | 招式内自定义逻辑 | 逐怪例外（3 个） |
| 诅咒/选牌干扰 | KnowledgeDemon 的 Curse of Knowledge | 自定义选择界面 | 逐怪例外（1–2 个） |

### 2.2 可以放行（领域内保持原样，不影响设计）

| 放行项 | 理由 |
|---|---|
| 普通攻击 / 多段攻击 / DeathBlow（Attack/MultiAttack 意图） | 领域保留"普通攻击" |
| `Defend` 意图（直接格挡） | 领域保留"直接格挡" |
| 敌方 **自身** 的负面效果：DEMISE（每回合掉血）、STRANGLE、SLOW、UNSTABLE、INKED、HANG、KNOCKDOWN、MONARCHS_GAZE、SHRINK | 对敌不利，属"敌人自身的不利效果继续生效" |
| Escape / Sleep / Stun 意图 | 逃跑=敌人离场（对玩家有利）；睡眠/眩晕=敌人自控 |
| 战斗事实与清理：死亡、离场、状态到期、Doom 结算 | 必须保留，否则战斗卡死 |
| 敌人已有的力量/格挡（领域开启前获得的） | 领域保留"当前/直接力量、当前/直接格挡" |

### 2.3 需要用户裁决的边界（表现上"必须压制"但成本高）

1. **敌人已有被动增益是否在领域内失效**（例如开领域前已叠了 10 层 RITUAL 力量）：模拟器语义是"当前力量保留、被动生成压制"，建议保留已有数值、只拦后续生成。
2. **"保护性阶段"是否连视觉/形态一起压**：建议只压机制（不减伤、不复活、不转阶段），形态动画照常。
3. **偷牌/诅咒这类"非数值型"干扰**：建议 v1 做例外表（压制或跳过对应 move），不追求战斗内归还动画。

## 3. 实现手法（成本从低到高）

### L1：意图级跳过（最便宜，覆盖"纯特殊招"）
- 在 `MoveState.PerformMove` 前读 `Intents`；领域 active 时：
  - 若招式**不含** Attack/Defend/DeathBlow 意图（即纯 Buff/Debuff/Heal/Summon/StatusCard/CardDebuff 等）→ **跳过执行**（播被压制的表现或直接过），状态机正常流转；
  - 若混合（攻击+增益）→ 正常执行，用 L2/L3 过滤非攻击效果。
- 覆盖：纯 buff 招、纯召唤招、纯治疗招、纯 debuff 招。**无需逐怪数据**，意图是运行时读的。
- 成本：3–5 人日（含状态机跳过与表现、跳过后的存档一致性）。

### L2：Hook 模型过滤（覆盖面最大，一处管多类）
- 领域 active 时，在 `Hook` 的取值/判定方法里过滤掉"敌方正面 Power 模型"：
  `ShouldDie`、`ShouldAllowHitting`、`ShouldAllowTargeting`、`ModifyDamage`、`ModifyHpLost`、`ModifyPowerAmountGiven`、`ModifyPowerAmountReceived`、`ShouldClearBlock`、`ModifyCardBeingAddedToDeck`、`ShouldAddToDeck`、`ModifyCardPlayCount`、`ModifyBlock` 等约 12–15 个方法。
- 需要一张 **Power 分类表**（263 个类 → 压制/保留/中性），可先用描述自动分类，再人工复核 32 条敌方侧 + 20 条边界。
- 覆盖：被动增益、限伤、无敌、不可选、复活、塞牌、削升级的**大部分**。
- 成本：6–9 人日 + 数据表 3–5 人日。

### L3：命令级 gate（处理"招式内一次性效果"）
- 敌方招式执行期间（`PerformMove` 前置 flag / 上下文栈）拦截：
  - `PowerCmd.Apply`：目标是敌方且 Power 属"正面" → 取消；目标是玩家且属 debuff → 取消；白名单：直接 `StrengthPower`/`DexterityPower`（保留直接力量/敏捷）。
  - `CreatureCmd.Heal`（敌方）/ `CreatureCmd.GainMaxHp`（敌方）→ 取消。
  - `CreatureCmd.Add`（召唤）/ `CardPileCmd.AddGeneratedCardToCombat` / `AddCurseToDeck` → 取消。
  - `CardCmd.Upgrade/Downgrade/Transform`（对玩家牌、来源=敌人）→ 取消。
- 成本：5–8 人日（每个 gate + 边界 + 测试）。

### L4：逐怪例外（数据表 + 小 patch）
- 只处理"效果不在上述通用路径里"的怪：多阶段状态机、偷牌、诅咒选择、分段重组。
- 形式：`domain_exceptions.json`（怪物 ID → 压制策略：`skip_move` / `patch_hook` / `allow`）+ 每怪一个 `DomainException_<Monster>.cs`（0.25–1.5 人日/个）。
- 优先名单（12 个重点）：TestSubject、CeremonialBeast、Queen、Decimillipede、KnowledgeDemon、ThievingHopper、TheForgotten、TheLost、Aeonglass、Fabricator、TheObscura、TwoTailedRat。
- 次级名单（约 8 个）：Axebot、Rocket、CubexConstruct、MechaKnight、FrogKnight、WaterfallGiant、SlumberingBeetle、LivingFog（多数可被通用 gate 覆盖，只需冒烟确认）。
- 成本：重点 12 个 × 0.5–1.5 人日 + 次级 8 个 × 0.25 人日 ≈ **8–20 人日**。

### L5：自研 AI 循环替换（评估：不需要）
- 只有"必须阻止敌人选择/进入某类 move"才需要。我们可以用 L1 + L4 的 `skip_move` 数据替代：拦截该 move 的 `OnPerform` 或把状态机当前状态强制改为下一条，成本约 0.5 人日/招，不需要重写选招。
- 真要做"整套敌人 AI 替换"（选招逻辑、分支、计数器全部重写）：**+50–90 人日**，还要重测 93 遭遇，不推荐。

## 4. 建议的 v1 压制范围（推荐 Tier 2）

**v1 做**
- L1 意图级跳过（纯特殊招）
- L2 Hook 过滤（12–15 个关键 Hook + 263 Power 分类表）
- L3 命令 gate（Power/Heal/Summon/塞牌/削升级）
- L4 重点例外 6–8 个（TestSubject、CeremonialBeast、Queen、Decimillipede、KnowledgeDemon、ThievingHopper、Aeonglass、Fabricator）
- 测试：93 遭遇冒烟 + 20 个定向场景

**v1 明确放行（写入 mod 文档）**
- 敌人已有力量/格挡、敌方自身负面、Escape/Sleep/Stun、纯视觉形态变化
- TheForgotten/TheLost 的偷牌（低频事件怪，v1.1 再补）

**v2 补**
- 剩余次级例外、偷牌归还动画、Doom 等特殊结算的领域交互、联机同步

## 5. 工作量分档

| 档 | 内容 | 人日 | 覆盖 |
|---|---|---|---|
| **Tier 1 最小可用** | POC + L1 意图跳过 + L3 的 Power/Heal/Summon gate + 3 个 Boss 例外 + 冒烟 | **12–18** | 纯特殊招 + 大部分增益/召唤；限伤/无敌/复活部分靠后续 |
| **Tier 2 推荐 v1** | Tier 1 + L2 Hook 过滤（12–15 个）+ Power 分类表 + 8 个重点例外 + 93 遭遇冒烟 | **28–40** | ~90% 遭遇语义正确，剩余为显式例外 |
| **Tier 3 全保真** | Tier 2 + 全部 Hook 覆盖 + 20+ 例外 + 偷牌/诅咒/分段完整处理 + 全遭遇回归 | **45–65** | 接近模拟器语义 |
| Tier 4 自研 AI | 选招/状态机整体替换 | +50–90（不推荐） | 无必要 |

> 对照：89 张卡全量实现约 30–45 人日。领域压制 Tier 2 ≈ 与全部卡牌同量级，所以**必须分档做、不能默认全保真**。

## 6. POC 清单（先验证再排期，2–4 人日）

1. `Hook.IterateCombatHookListeners` 能否安全过滤模型（拿 1 个敌方 RITUAL/HIGH_VOLTAGE 测试：领域内是否停止加力量）。
2. `Hook.ModifyDamage` 能否在领域内忽略 HARDENED_SHELL/GUARDED（打一次验证伤害）。
3. `ShouldDie` 能否阻止 ADAPTABLE/ILLUSION 复活。
4. `MoveState.Intents` 是否在 `PerformMove` 前可读且可靠（纯 Buff 招能否跳过且状态机不卡）。
5. `PowerCmd.Apply` 在敌方 move 上下文内的来源判定（`CardModel`/applier 参数是否足够区分"直接力量/格挡"与"被动增益"）。

## 7. 风险

| 风险 | 说明 | 对策 |
|---|---|---|
| Hook 过滤影响面过大 | 过滤敌方模型可能误伤"敌方自身负面"或战斗清理 | 分类表 + 白名单 + 每个 Hook 定向测试 |
| 跳过 move 卡状态机 | 某些 move 必须在状态机里推进 | 用 `SetCurrentState`/`OnMovePerformed` 正常推进；异常怪走 L4 |
| `IntentType` 与真实效果不一致 | Hidden/Unknown 意图的 move 可能仍有效果 | 这类 move 不跳过，走 L2/L3 |
| 领域与迎战叠加 | 迎战让敌人在玩家回合行动，压制上下文需覆盖"提前执行"路径 | 统一用同一个"敌方行动上下文" flag；POC 同时验证 |
| 存档一致性 | 被压制的 move/状态要可序列化 | 只用 Power 实例字段/combat 数据；跳过不写临时状态 |

## 附录：数据出处

- 本机 `sts2.dll` 元数据：`audit/sts2-mod-research/probe_mdread.py`（可用 `python3 probe_mdread.py` 重跑）
- 本地化：从 `SlayTheSpire2.pck` 解出的 `localization/eng/{powers,monsters,intents,encounters}.json`（本次提取到 `/tmp/sts2loc/`，可复现）
- Hook/模型/意图成员：`audit/sts2-mod-research/platform.md` §3–§5 与 `sts2-v0.107.1-api.json`
- 机制语义：[`content.md`](content.md) §3.3（领域）与 §5.4（分档建议）
