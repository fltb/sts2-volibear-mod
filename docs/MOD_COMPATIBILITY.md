# 与其他 Mod 的兼容性评估

范围：当前 `codex/mode7-completion` 源码（PBE 0.111.0 / 41cef1ea 通道）与其他 StS2 Mod
同时加载时的冲突面。结论分「已确认（读代码可得）」与「推断（需实机组合验证）」两类。

## 1. 结论摘要

| 对方 Mod 类型 | 例子 | 判断 | 依据 |
| --- | --- | --- | --- |
| 框架：BaseLib 3.4.7 | 依赖项 | 必须共存，无冲突 | `Volibear.json` 声明 `dependencies: BaseLib >= 3.4.7`，模型注册全走 BaseLib `Custom*Model`/`CustomID` |
| 框架：RitsuLib | STS2-RitsuLib | 可并存，需实测 | 官方表述为「与 BaseLib 并列而非取代」；但两者都 patch 核心战斗，需组合回归 |
| 其他角色/卡牌/遗物 Mod | The Watcher、The Alchemist 等 | 低风险 | 内容 ID 与资产根目录互不影响（本 Mod 资产全在 `res://VolibearArt/`） |
| QoL/信息类 | Quick Restart 2、Intent Graph、Minty Spire 2 | 中低，需实测 | 本 Mod 对 `CombatManager.Reset` 有 18 处引用、对 `Hook.*` 有 27 处引用；重开类 Mod 常在同一点挂钩 |
| 大改战斗数值的 Mod | Ascender's Sandbox 等 | **高风险** | 本 Mod transpile 了 `Creature.Block` setter、`DamageBlockInternal`、`Hook.ModifyBlock/ModifyDamage`，语义叠加难保证 |
| 本地化/翻译 Mod | 中文包 | 中风险 | 本 Mod 用 `LocManager.GetTable` postfix 注入词条；若对方整体替换表引用而非合并，会互相覆盖 |
| 存档/进度类 | — | 低风险 | 不自定义存档格式，走原生 `SaveManager`；`affects_gameplay=true` |
| 多人 | 任意 gameplay Mod | 需全员同版本同装 | 原生大厅按 `affects_gameplay` 校验 |

**最现实的阻碍不是代码冲突，而是版本通道**：社区主流 Mod 目前按稳定版 0.107.1 构建，
本仓库在 `0315aa1` 之后只保留 PBE 通道代码（`BranchingPlayerChoiceContext`、
`AttackCommand.BridgeFromCard`、`PlayerChoiceContext.OwnerId` 均为 0.111.0 接口）。
因此与本机 0.107.1 生态内的 Mod 事实上无法同版本共存，除非回补稳定通道或对方跟进 PBE。

## 2. 本 Mod 的侵入面（读代码统计，非估算）

生产构建（beta 通道、不含 probe）共 128 个源文件、约 **30 个独立 Harmony ID**：

- transpiler 51 处、prefix 53 处、postfix 33 处。
- 被改写最多的原生成员：

| 原生成员 | 引用数 | 用途 |
| --- | --- | --- |
| `CombatManager.Reset` | 18 | 每场战斗清理本 Mod 的账本/订阅 |
| `PowerCmd.Apply` | 13 | 领域/雷势的状态施加旁路 |
| `CreatureCmd.Damage` | 9 | 领域压制与直接伤害归因 |
| `Hook.ShouldPlay` / `ShouldStopCombatFromEnding` / `ShouldAllowHitting` / `ShouldCreatureBeRemovedFromCombatAfterDeath` | 各 3–6 | 改写原生 Hook 派发（`DomainAdditionalRevivalEffects.Votes.cs`） |
| `Creature.DamageBlockInternal` / `Creature.Block` setter | 4 | 留甲（Standing）与铁壁（ImmovableBody）的格挡保持 |
| `CardModel.OnPlayWrapper`、`AttackCommand.Execute`、`CardPileCmd.Draw` 的 async 状态机 `MoveNext` | — | 出牌/攻击/抽牌的结算钩子 |
| `MonsterModel.PerformMove`、`WaterfallGiant`、`Fabricator`、`DoomPower`、`ReattachPower` 等 | 各 3–8 | 领域禁用敌方特殊机制 |

表现层另有全局 UI 补丁：`NPowerContainer.UpdatePositions/_EnterTree`、`NPower._Ready/Model/
RefreshAmount/OnHovered/OnUnhovered`、`NCreature.ShowHoverTips`，并直接读写私有字段
`NPowerContainer._powerNodes`（`Presentation/PowerStackVisual.cs`）。这会与任何「改状态图标/悬浮提示」
的 Mod 在同一组节点上竞争。

## 3. 冲突机理

1. **精确锚点 + fail-fast**：转译器普遍以 `Require(count == 1, ...)` 校验 IL 锚点
   （例：`DomainAdditionalRevivalEffects.Votes.cs:77`、`Core/PersistentBlockHooks`）。
    Harmony 的 transpiler 按安装顺序链式执行，前一环改了调用序列就会让后一环计数不符。
2. **默认不降级**：`ModEntry.Initialize` 里的 `Step()` 默认 `throw`（`ModEntry.cs`），
   任何一个模块锚点漂移都会让整个 Mod 在初始化阶段抛异常；只有
   `VOLIBEAR_COMPAT_DIAG=1` 时才改为记录 `COMPAT_FAIL` 并继续加载其余模块。
3. **语义叠加**：`Creature.Block` setter 被整体替换为 `SetClearedBlock/SetDamagedBlock`；
   另一个同样实现「保留格挡」的 Mod 再改写同一指令时，两者会按安装顺序互相覆盖。
4. **全局派发改写**：`Hook.ShouldStopCombatFromEnding` 等被转译后追加了本 Mod 的裁决调用，
   任何依赖这些 Hook 的第三方 Power 仍会被调用（调用点保留），但顺序与返回值组合会变化。

## 4. 现状下的可操作结论

- 与 **BaseLib 生态**的普通内容 Mod：可以一起开，前提是同一游戏版本。
- 与 **RitsuLib** 双框架：允许，但要专门跑一次组合启动（两者都装、开一局、看
  `[Volibear] BUILD_GATE`/`COMPAT_FAIL` 与 RitsuLib 诊断）。
- 与 **改战斗数值的 Mod**：默认按不兼容处理，先做组合回归再谈。
- 出问题时先设 `VOLIBEAR_COMPAT_DIAG=1` 启动：它会把「哪个模块锚点不匹配」逐条打印，
  而不是只抛第一个异常。

## 5. 待实机验证的清单

| 组合 | 观察点 |
| --- | --- |
| Volibear + BaseLib 3.4.7（单独） | `CONTENT_OK cards=89`、`BUILD_GATE build=verified channel=pbe` |
| Volibear + RitsuLib | 双方初始化日志、模型 ID 冲突告警、一局战斗 |
| Volibear + Quick Restart 2 | 重开后本 Mod 是否仍能正确清理（`CombatManager.Reset` 竞争） |
| Volibear + 中文翻译 Mod | 卡名/关键词是否被覆盖（`LocManager.GetTable` 竞争） |
| Volibear + 大改战斗 Mod | `VOLIBEAR_COMPAT_DIAG=1` 下的 `COMPAT_FAIL` 列表 |

## 6. 若要主动提高兼容性（建议，未实施）

1. 组合回归脚本：把「本 Mod + 另一个 gameplay Mod」做成一次性启动检查，输出双方的
   `COMPAT_FAIL`/异常，而不是靠人工开游戏。
2. 锚点语义从「必须恰好 1 处」放宽为「已满足则跳过、缺失则报告」——但这会削弱机制正确性，
   须与玩法权威裁决一起决定，不能单方面降级。
3. `PowerStackVisual` 的容器改写限定到持有本 Mod Power 的 `NPowerContainer`，
   减少对纯原版容器的重排。
4. 为 `VOLIBEAR_COMPAT_DIAG` 提供正式设置项，并在 `docs/INSTALL_ZH.md` 写明排查步骤。
