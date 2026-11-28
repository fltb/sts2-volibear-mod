# 原生接口报告：0.113.0 → 0.114.0（PBE）

本文件是 0.114.0 迁移（T1）的**先行动作与结果记录**：先给出原生接口差异与结论，再改代码，最后附实机启动证据。
每一条差异都带可复现的取数方法；没有实测到的内容一律标 NOT_RUN。

## 0. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 编译面 | 2 处编译失败（`Creature.LoseHpInternal` 签名/返回类型），已修 |
| 已安装状态 | 隔离副本 0.114.0 启动：`COMPAT_SUMMARY failures=0`、`LOAD_OK`、`COMPAT_SCAN` 完整；状态 **degraded**（1 项已声明不可用） |
| 仍完整工作的锚点 | `WaterfallGiant`（含 private 的 `AboutToBlowMove`/`ExplodeMove`）、`SteamEruptionPower`、`Hook`、`CreatureCmd.Kill`、`AttackCommand`、`CombatManager.Reset`、`MonsterModel.PerformMove` 等，全部存在 |
| 必须改写的锚点 | 6 个模块：攻击伤害调用点、伤害写入点、`HardToKillPower` 保护点、`DamageBlockInternal` 签名、`DampenPower` 降级对、`PainfulStabsPower` 投票覆写 |
| Steam「精确伤害归因」 | **不可保留**，按 capability-yield 契约降级，玩法代价见第 6 节 |

## 1. 证据基线与它的边界

`tools/api_diff.py` 需要两个游戏副本（旧 / 新）才能出全量表面差异，而本机**没有 0.113.0 的程序集**：

- Steam 的 PBE 测试分支只提供最新构建，11-25 自动更新后 0.113 的程序集已被覆盖；`.local/game-pbe` 不存在。
- 仓库内缓存的 `sts2.dll` 副本（`.local/**/bin/**`、`tests/**`、`.local/release-acceptance/**`）经 `release_info.json` 核对全部是 **v0.107.1 / 59260271**（9,364,480 字节），不是 0.113。
- 现装副本为 **v0.114.0 / a7b9a9c0**（`data_sts2_windows_x86_64/sts2.dll`，10,700,288 字节，SHA-256 `DDCEB879…826C5D`）。

因此本报告不伪装成「两份二进制对拼」，而是用三条可复核的证据线：

1. **0.113 侧 = 源码契约**：`src/Volibear` 中所有对原生接口的绑定就是 0.113 的用法（含 `NativeDamage` 的精确签名、`DamageMachine` 的 IL 形状断言）。0.1.3 的发布产物正是由这份源码编译。
2. **0.114 侧 = 现装程序集**：`tools/apidiff` 反射导出完整表面，再对关键方法体做反编译核对。
3. **运行时 = 隔离副本实机启动**：`tools/compat_report.py` 读 `BUILD_GATE` / `CONTENT_OK` / `LOAD_OK` / `COMPAT_SUMMARY` / `COMPAT_SCAN`，每条补丁失败都带模块标签和异常链。

复现命令：

```powershell
# 0.114 表面导出
$env:VOLIBEAR_API_ASSEMBLY="C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.dll"
dotnet run --project tools/apidiff -p:Sts2DataDir="C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64"

# 关键方法体
$env:DOTNET_ROLL_FORWARD="LatestMajor"
.local\dotnet-tools\ilspycmd.exe -t MegaCrit.Sts2.Core.Commands.CreatureCmd "<sts2.dll>"

# 实机启动自检（隔离副本；headless 无窗口、不抢焦点）
python tools/compat_report.py --game-dir .local/game-0.114 --display headless --audio-driver Dummy
```

反编译产物只作核对，不入库：它包含游戏本体代码。

## 2. 差异一：`Creature` 的写入原语

| 成员 | 0.113（源码契约 = 用法） | 0.114.0 | 影响 |
| --- | --- | --- | --- |
| `Creature.LoseHpInternal` | `LoseHpInternal(decimal, ValueProp) → DamageResult`（`Damage.cs:149`、`:152`） | `LoseHpInternal(decimal amount, bool dryRun = false) → HpLossResult` | 编译失败 CS1503、CS0029 |
| `Creature.DamageBlockInternal` | `(decimal, ValueProp) → decimal` | `(decimal, ValueProp, bool dryRun = false) → decimal` | 2 参调用仍合法；多出的 `dryRun` 说明它被用于试算 |
| `HpLossResult` | 不存在 | `record struct { int hpLost; bool killed; int overkillAmount; }` | 只承载「掉多少血/是否致死/溢出多少」，不再携带 `ValueProp` 与格挡信息 |

`HpLossResult` 不是「同一方法的搬家」：血量写入被剥离成纯数值原语，`ValueProp` 与格挡结算不再经过它。

## 3. 差异二：`CreatureCmd.Damage` 的「模拟 → 提交」两段式

0.113 的 `Damage` 在一次 `foreach (target)` 里顺着 hook 顺序直接写 HP/格挡：
`BeforeDamageReceived` → `DamageBlockInternal` → `AfterModifyingHpLostBeforeOsty` → `LoseHpInternal`（未格挡重定向）→ `AfterModifyingHpLostAfterOsty` → `LoseHpInternal`（本体）。

0.114 拆成两段：

1. `GetDamageResults(...)`（`private static`，同步）：先用 `LoseHpInternal(amount, dryRun: true)` 与 `DamageBlockInternal(amount, props, dryRun: true)` **试算**，把结果装进 `DamageResult`（`UnblockedDamage` / `BlockedDamage` / `WasTargetKilled` / `OverkillDamage` 此时即已定稿）；
2. `ApplyDamageResults(...)`（`private static async`）：才真正落笔——
   `results.original.Receiver.DamageBlockInternal(results.original.BlockedDamage, results.original.Props)`、
   `results.original.Receiver.LoseHpInternal(results.original.UnblockedDamage)` 等，
   **全部按丢弃返回值的方式调用**。

`CreatureCmd.Damage` 本体（0.114 反编译第 285–459 行）里已经**一个 HP/格挡写入都没有**。

## 4. 差异三：实机启动测得的适配器断裂（6 处）

只修编译错误后第一次启动（隔离副本 0.114.0）得到的真实回执：

| 模块 | 回执（截断） | 0.114 的真实原因 |
| --- | --- | --- |
| `Core.CardResolutionHooks` | `Expected one native … Damage awaited callsite; found 0` | `AttackCommand.Execute` 现在只包 `ExecuteInternal`，伤害循环搬进后者 |
| `Core.DomainSteamEruptionEffects` | `Steam patch failed: attack-machine … native_calls=0, awaiters=0` | 同上 |
| `Core.DomainEnemyEffects` | `MissingMethodException: … HardToKillPower.ModifyDamageCap` | 该能力改成 `ModifyHpLostBeforeOstyLate(Creature, decimal, ValueProp, Creature, CardModel)` |
| `Core.PersistentBlockHooks` | `MissingMethodException: Creature.DamageBlockInternal(decimal,ValueProp)` | 写入原语多了 `bool dryRun`，精确签名查找失败 |
| `Core.DomainDampenTransactions` | `Expected one exact native call: Void Downgrade(CardModel)` | `DampenPower.AfterApplied` 改用 `CardCmd.RemoveAllUpgrades` |
| `Core.DomainAdditionalRevivalEffects` | `You can only patch implemented methods … AbstractModel::ShouldCreatureBeRemovedFromCombatAfterDeath` | `PainfulStabsPower` 不再覆写两个投票，`AccessTools` 解析到抽象基声明 |
| `Presentation.VolibearPresentationBridge` | `Native domain scalar consumption sites drifted … expected [ModifyDamage, ModifyHpLost×4], actual [ModifyDamage]` | HP 损失 hook 全部移出 `CreatureCmd.Damage` |

（表 7 行对应 7 条回执；其中 `Core.DomainSteamEruptionEffects` 的失败是 attack-machine，不是 damage-machine —— damage-machine 已被前置形状探测拦住，见第 5 节。）

### 每一处的处理

| 位置 | 处理 | 依据 |
| --- | --- | --- |
| 攻击调用点（两个模块） | 新增 `NativeAttackAnchor`：优先 `ExecuteInternal`，回退 `Execute` | 0.114 的 `Execute` 只剩动画状态与死后清理，伤害循环在 `ExecuteInternal` |
| `HardToKillPower` | 新方法存在时改挂 `ModifyHpLostBeforeOstyLate` + `NeutralHpLoss`，否则保留 `ModifyDamageCap` + `NeutralCap` | 新方法体就是 `Math.Min(amount, Amount)`，与旧 cap 同义；`NeutralHpLoss` 正是「把被压低的值还原成输入值」 |
| `DamageBlockInternal` | 3 参优先、2 参回退；替换点仍在原生 `if (!dryRun)` 分支内 | 试算路径不经过 `set_Block`，不会把试算记成真实格挡变化 |
| `DampenPower` 降级对 | 先探测原生实际调用的是 `RemoveAllUpgrades` 还是 `Downgrade`，`CommitPair` 回放同一个调用 | 只镜像调用，不改效果；探测结果存入 `_nativeRemoveAllUpgrades` |
| 复活投票覆写 | 覆写不存在时打印 `REVIVAL_VOTE_SITE_ABSENT` 并跳过，不碰抽象基声明 | 没有覆写就没有可拦截的投票；方法整体改名仍会硬失败 |
| 领域标量回执 | 0.114 的 `CreatureCmd.Damage` 只钉 `ModifyDamage ×1`；HP 损失回执不再钉 | 4 个 `ModifyHpLost` 已移入 `GetDamageResults`，见第 6 节降级 |

## 5. `NativeWriteShape`：先测形状，再决定装不装

`DomainSteamEruptionEffects.DamageMachine` 把 `CreatureCmd.Damage` 的每个写入点换成 `BlockCommit` / `HpCommit`，安装时断言 IL 形状 `1/3/1/1/2/1`。

新增 `Core/NativeWriteShape.cs`：在安装前直接读原生状态机的 IL，数出
`DamageBlockInternal` / `LoseHpInternal` / 4 个伤害 hook 的调用点，只有**明确测到「没有任何内联写入」**时才让位；其它任何异常形状仍然走原来的硬断言（宁可启动失败，也不静默降级）。

0.114 实测（启动日志）：

```text
[Volibear] NATIVE_DAMAGE_SHAPE 0/0/1/0/0/1 relocated=true
[Volibear] NATIVE_DAMAGE_WRITE_CAPABILITY unavailable; the inline HP/block write points this adapter gates are not in CreatureCmd.Damage.
```

分类含义：`blocks/hp/beforeDamage/beforeOsty/afterOsty/afterHp`。与 0.113 契约 `1/3/1/1/2/1` 相比，写入点 0、两个 osty hook 归零，而 `BeforeDamageReceived` 与 `AfterCurrentHpChanged` 仍在。

### 为什么不能搬到 `ApplyDamageResults`

那里确实还有写入点（3× `LoseHpInternal` + 2× `DamageBlockInternal`），但那时 `DamageResult` 已定稿、提交调用的返回值被丢弃：

- 门控返回 0 或缩小值，生物身上确实少掉血/少掉格挡，但 `DamageResult.UnblockedDamage/BlockedDamage/WasTargetKilled` 仍是原值；
- 伤害数字、`History.DamageReceived`、`AfterDamageReceived`/`AfterDamageGiven`、`DamagedTaken` 统计、屏幕震动都会与实际不符；
- 这些字段中 `UnblockedDamage` / `OverkillDamage` / `WasTargetKilled` 是 `init`，事后无法改写。

所以这不是签名搬家，是结算模型变更：**写入返回值即结果的归因链消失了**。

## 6. 降级决定与玩法代价（capability-yield）

`steam_explosion_damage_attribution` 在 0.114 上标记为 **unavailable**（`COMPAT_SCAN` 里可见完整 reason/impact）。保留的能力：

- 爆发命令开跑前的取消（`ExplodeAttack` 在 `Allow(episode)` 为假时根本不执行 `AttackCommand`）；
- 阶段门（`TriggerAboutToBlowState`）与 move 门（`AboutToBlowMove` / `ExplodeMove`）；
- 死亡旁路（`KillWithoutCheckingWinCondition`、公开 `Kill`、`SteamEruptionPower.AfterDeath`、`ShouldStopCombatFromEnding`）；
- 普通段（ordinary segment）的领域闪电与响应者不受影响。

失去的能力与**玩法代价**：

- 一旦取消在**某次攻击已经开始之后**才成立，这次攻击后续的伤害不再被压制：水流巨人的蒸汽喷发会按原生伤害结算到玩家身上。
- Steam 写入回执（`SteamWriteReceipt` / `Decision.Writes`）不再产生，依赖回执的两条旁路不再触发：① `HasProtectedCommit` 保护的「无 Power 的受保护阶段被外部真实死亡消费」；② 致命写入观察（`ObserveLethalWrite`）与边界观察者（`Boundary`）。两者都是死亡保护/证据路径，正常路径（Power 仍在）不受影响。

其它已声明退化（非玩法）：

- **领域标量 HP 损失回执**：0.114 不再钉 `Hook.ModifyHpLost` 的 4 个点，只保留伤害标量。影响限于「被领域压制的数值」的图标/音效回执，不改动伤害本身。启动日志打印 `NATIVE_DAMAGE_WRITE_CAPABILITY` 与形状行，`COMPAT_SCAN` 里有对应记录。
- **`PainfulStabsPower` 两个投票**：0.114 不再覆写，模块打印 `REVIVAL_VOTE_SITE_ABSENT` 并跳过；该 Power 现在改在 `AfterAttack` 工作。

## 7. 实机启动证据（0.114.0，隔离副本）

```text
[Volibear] BUILD_GATE build=unverified-compatible found=v0.114.0/a7b9a9c0 target=unpinned
[Volibear] CONTENT_OK cards=89 character=VolibearCharacter framework=BaseLib-3.4.8.0
[Volibear] NATIVE_DAMAGE_SHAPE 0/0/1/0/0/1 relocated=true
[Volibear] NATIVE_DAMAGE_WRITE_CAPABILITY unavailable; …
[Volibear] REVIVAL_VOTE_SITE_ABSENT PainfulStabsPower.ShouldCreatureBeRemovedFromCombatAfterDeath; …
[Volibear] REVIVAL_VOTE_SITE_ABSENT PainfulStabsPower.ShouldPowerBeRemovedAfterOwnerDeath; …
[Volibear] COMPAT_SUMMARY failures=0
[Volibear] LOAD_OK version=0.1.3 target=unpinned build=unverified-compatible found=v0.114.0/a7b9a9c0
```

`tools/compat_report.py` 判定：`failure_count=0`、`missing_evidence=[]`、`support_status=degraded`（因一项 capability 声明为 unavailable；这是设计内的降级，不是补丁失败）。

### 复现这套启动证据（Windows）

游戏在「用户尚未确认 mod 警告」时会跳过所有 mod（日志：
`Skipping loading mod … user has not yet seen the mods warning`）。因此在隔离 profile 里先写入一次性同意，
再启动；全程不碰操作者的真实 `%APPDATA%`：

```powershell
$iso = "$PWD\.local\tmp\compat-appdata"
New-Item -ItemType Directory -Force "$iso\Roaming\SlayTheSpire2\default\1" | Out-Null
# settings.save 至少要含 {"mod_settings":{"mods_enabled":true},"schema_version":8,...}
$env:APPDATA="$iso\Roaming"; $env:LOCALAPPDATA="$iso\Local"; $env:TEMP="$iso\Temp"
python tools/compat_report.py --game-dir .local/game-0.114 --display headless --audio-driver Dummy
```

`.local/game-0.114` 是 Steam 安装目录的整份副本（`release_info.json` = v0.114.0 / a7b9a9c0），
`mods/` 只放 BaseLib 3.4.8 五文件与本仓库构建的 `Volibear.dll` + `Volibear.pck` + `Volibear.pbe.json`（改名 `Volibear.json`）。

## 8. 未验证（NOT_RUN）

- **stable（v0.111.1）编译与启动**：需要一份 0.111.1 游戏副本，本机没有；`GameChannel=stable` 尚未在 0.111.1 上编译过（本轮只完成 beta=0.114.0）。
- **玩法矩阵**：`tools/pbe_verify.py` 一个场景都没在 0.114 上跑过；本报告不声称任何玩法结果。
- **领域标量回执退化**与 `PainfulStabsPower` 投票缺位：只做了启动验证，玩法未验证。
- **静态回归**：`tools/regression.py` 在本轮之前即已失败（`src/Volibear/Content/InlineModelLocalization.cs` 不在 HEAD 中，多个测试工程引用它；另有 Linux 专属窗口守卫用例），与本次改动无关，未计入 T1 结论。
