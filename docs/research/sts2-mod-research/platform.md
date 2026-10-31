# 杀戮尖塔 2 v0.107.1 平台层核查（官方 Mod 加载器 / 内容 API / 构建工具链 / 框架兼容）

> 说明：本文件由 Lead 在 `sts2-platform` 研究代理异常退出后，用它留下的机读产物整理完成。原始提取证据保留在同目录：
> - `sts2-v0.107.1-api.json`（261 KB，ECMA-335 元数据读取器直接解析本机 `sts2.dll` 的结果：官方 Modding 命名空间、15 个模型、15 组枚举、20 组命令）
> - `probe_mdread.py` / `probe_dump.py` / `probe_ilstr.py`（可复跑的自研 PE/CLI 元数据读取器与转储脚本）
> - `/tmp/sts2tpl/`（BaseLib、RitsuLib、ModTemplate-StS2 的源码/清单/模板 PNG 抓取）
>
> 核查对象：本机 flatpak 安装的 **Slay the Spire 2 v0.107.1**。凡"已验证"均指本机文件或公开源码可直接核对；未在游戏内跑过的标"未验证"。

## 0. 结论先行

1. **官方 Mod 系统是真实存在且可用的**：`MegaCrit.Sts2.Core.Modding` 提供 `ModManifest`（JSON 清单）、`[ModInitializer]` 入口、`ModManager`（mods 目录 + Steam Workshop 两来源）、`ModHelper.AddModelToPool`（内容池注册）与 Run/Combat 钩子订阅。**不需要**任何第三方加载器。
2. **本机游戏版本 = main 分支 v0.107.1**（commit `59260271`，2026-06-18，Godot 4.5.1 / .NET 9）。当前社区框架都在支持它：ModTemplate 模板清单写 `min_game_version: 0.107.0`；RitsuLib v0.6.10 直接发布 `Compat.0.107.1` 变体包；BaseLib 最新 v3.4.7 发布说明为 "Fix patch for main branch"。
3. **构建链是标准 .NET + Godot**：模板 `CharMod.csproj` 用 `Godot.NET.Sdk/4.5.1`、`net9.0`，从 `$(Sts2DataDir)` 以 `HintPath` 引用 `sts2.dll` / `0Harmony.dll`，`dotnet publish` 时调用 MegaDot/Godot 4.5.1 `--headless --export-pack BasicExport` 生成 mod 的 `.pck`，并把 `dll/jsON/pck` 拷进 `mods/<ModName>/`。
4. **本机当前缺三样**：`.NET SDK`（只有 runtime 9.0.14）、MegaDot/Godot 4.5.1、`mods/` 目录。这三样是 M0 环境任务的唯一硬前置。
5. **两套社区框架都可用且互不依赖**：BaseLib（社区标准，模板/分析器/本地化生成齐全，模板要求 `min_version 3.3.0`，当前 3.4.7）；RitsuLib（v0.6.10，`dependencies: []`，自带内容模板、资产 profile、动画状态机、音频服务、持久化）。**同一份内容只能选一套注册源**，不要混用。
6. **API 面上本项目需要的功能都有官方入口**：卡牌 `OnPlay`、能力 `BeforeApplied/AfterApplied`、193 个 `AbstractModel` 钩子（含 `ModifyDamageAdditive`、`ModifyCardPlayCount`、`ShouldClearBlock`、`ShouldAllowHitting`、`ShouldStopCombatFromEnding`…）、`CreatureCmd.Damage(..., ValueProp, ...)`、`CardCmd.Transform/Afflict/Exhaust`、`CardSelectCmd.FromCombatPile`、`MonsterModel.PerformMove`、`DamageProps` 三档伤害语义。
7. **三个需要实机验证的点**（本文件只能确认符号存在，不能确认行为）：`ValueProp` 与 `DamageProps.*` 的精确加成/格挡语义；玩家回合内驱动 `MonsterModel.PerformMove`（迎战）；`CardCmd.Transform` / `Power` 实例字段在战斗存档里的序列化。

## 1. 本机安装与程序集

| 项 | 值 | 证据 |
|---|---|---|
| 安装方式 | Steam flatpak | `~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2/` |
| 版本 | `v0.107.1`，commit `59260271`，2026-06-18，branch `v0.107.1`，`main_assembly_hash 1692500715` | 游戏目录 `release_info.json`；`sts2-v0.107.1-api.json.source.release_info` |
| 引擎 | Godot 4.5.1（PCK header `GDPC` pack v3，engine 4.5.1） | 本机 `SlayTheSpire2.pck` 头解析（见 Lead 的 pck 解析；文件表在 pck 尾部，12327 条） |
| 运行时 | .NET 9（`libcoreclr.so`、`libhostfxr.so`、`sts2.runtimeconfig.json`） | `data_sts2_linuxbsd_x86_64/` |
| 主程序集 | `data_sts2_linuxbsd_x86_64/sts2.dll`（9.36 MB）+ `sts2.xml`（5.3 MB，19 636 条 XML 文档注释） | 同目录 |
| 补丁/反射依赖 | `0Harmony.dll`、`MonoMod.*`、`GodotSharp.dll` 同目录 | 同目录 |
| Mod 目录 | **本机尚不存在** `mods/`（首次安装 BaseLib/本地 mod 时创建） | `ls` 游戏根目录无 `mods` |
| 保存/配置 | `user://` 下按平台+账号分 profile（`user://saves/...` 迁移逻辑见 sts2.xml #94224 一带） | `sts2.xml` |

## 2. 官方 Mod 加载器

### 2.1 清单文件 `ModName.json`（JSON key 为 snake_case；C# 侧字段为 camelCase）

本机 `ModManifest` 字段（`sts2-v0.107.1-api.json.official_modding.ModManifest.fields`）：
`id:string`、`name:string`、`author:string`、`description:string`、`version:string`、`hasPck:bool`、`hasDll:bool`、`dependencies:List<ModDependency>`、`affectsGameplay:bool`、`minGameVersion:string`。
`ModDependency`：`id:string`、`minVersion:string`。
模板实测清单（`Alchyr/ModTemplate-StS2@master content/CharacterModTemplate/CharMod.json`）：

```json
{
  "id": "CharMod",
  "name": "CharMod",
  "author": "...",
  "description": "...",
  "version": "v0.0.0",
  "min_game_version": "0.107.0",
  "has_pck": true,
  "has_dll": true,
  "dependencies": [{"id": "BaseLib", "min_version": "3.3.0"}],
  "affects_gameplay": true
}
```

- 文件名必须与 `id` 一致（游戏按 id 找 `ModName.json/.dll/.pck`）。
- `affects_gameplay: false` 的纯表现 mod 不参与联机一致性检查；新角色/新卡属于 gameplay，必须 `true`。
- 清单由 `ModManifest.ReadFromStream(Stream, ref List<LocString>)` 读取；`min_game_version`/依赖 `min_version` 是 0.105 之后加入的能力（wiki：Modding-Basics）。
- `ModSource`：`ModsDirectory`(1) / `SteamWorkshop`(2)；`ModLoadState`：Loaded/Failed/Disabled/DisabledDuplicate/AddedAtRuntime。

### 2.2 入口

`[ModInitializer(nameof(Initialize))]` 标注一个 `partial class ... : Node`，静态 `Initialize()` 里做 `Harmony.PatchAll(assembly)`、注册内容、初始化资源。
本机 `ModInitializerAttribute` 构造参数为 `string initializerMethod`（`sts2-v0.107.1-api.json.official_modding.ModInitializerAttribute`）。
官方 `ModManager` 公开成员：`State`、`Mods`、`PlayerAgreedToModLoading`、`Initialize(IModManagerFileIo, ModSettings, SemanticVersion)`、`ReadModsInDirRecursive`、`EvaluateBranchSupport`、`GetModdedLocTables(string, string)`、`GetGameplayRelevantModNameList()` 等（同 JSON `official_modding.ModManager`）。
模板入口实测（`CharModCode/MainFile.cs`）：

```csharp
[ModInitializer(nameof(Initialize))]
public partial class MainFile : Node
{
    public const string ModId = "CharMod";
    public const string ResPath = $"res://{ModId}";
    public static void Initialize() {
        var asm = Assembly.GetExecutingAssembly();
        new Harmony(ModId).PatchAll(asm);
    }
}
```

### 2.3 加载位置与启用

- 本地 mod：`<游戏安装目录>/mods/`（Windows/Linux；macOS 在 `SlayTheSpire2.app/Contents/MacOS`）。每个 mod 放一个同名子目录，含 `dll/json/pck` 三件套（可缺省其一，由 `has_dll/has_pck` 声明）。
- Workshop mod：`Steam/steamapps/workshop/content/2868840/<workshopId>/`。
- 启用/顺序：游戏内 Settings → Mod Settings；禁用全部即回到无 mod；`-nomods` 启动参数可整体禁用。加载顺序可手工调整（`SettingsSaveMod`）。
- 本地化：mod 的 pck 内 `localization/<lang>/*.json`，由 `ModManager.GetModdedLocTables` 合并；模板用 `Alchyr.Sts2.ModAnalyzers` 分析器从 `AdditionalFiles Include="<Mod>/localization/**/*.json"` 校验并生成缺失项。

## 3. 内容模型 API（本机程序集核实）

以下成员来自 `sts2-v0.107.1-api.json.models`（公共字段/属性/方法；完整列表见该 JSON）。

| 模型 | 关键公共成员 | 用途 |
|---|---|---|
| `AbstractModel` | 193 个生命周期钩子：`BeforeCardPlayed/AfterCardPlayed(Late)`、`BeforeSideTurnStart/AfterSideTurnStart`、`BeforeDamageReceived/AfterDamageReceived(Late)`、`ModifyDamageAdditive/Multiplicative`、`ModifyDamageCap`、`ModifyBlockAdditive`、`ModifyCardPlayCount`、`TryModifyEnergyCostInCombat`、`ModifyXValue`、`ShouldClearBlock`、`ShouldDie/ShouldAllowHitting/ShouldAllowTargeting`、`ShouldStopCombatFromEnding`、`AfterCardDrawn`、`AfterShuffle`、`ModifyHandDraw`… | 所有状态/效果钩子的基类 |
| `CharacterModel` | `StartingHp`、`StartingGold`、`MaxEnergy`、`StartingDeck`、`StartingRelics`、`CardPool/RelicPool/PotionPool`、`Title/NameColor`、`CreateVisuals`、`GenerateAnimator`、`TrailPath` | 自定义角色 |
| `CardModel` | 受保护构造 `(int cost, CardType, CardRarity, TargetType, bool)`、`OnPlay(PlayerChoiceContext, CardPlay)`、`OnUpgrade`、`CanPlay`、`TryManualPlay`、`PortraitPath/BetaPortraitPath/FramePath/PortraitPngPath`、`TitleLocString/Description`、`GetKeywordsWithSources`、`AddKeyword/RemoveKeyword`、`SetToFreeThisTurn/Combat`、`ResolveEnergyXValue`、`UpgradeInternal` | 卡牌 |
| `PowerModel` | `Title/Description`、`IconPath/BigIconPath`、`Type`、`InstanceType`、`Amount`、`AmountOnTurnStart`、`BeforeApplied/AfterApplied/AfterRemoved`、`ApplyInternal/RemoveInternal` | 能力/状态 |
| `RelicModel` | `Title/Flavor/Description/DynamicDescription`、`IconPath/BigIconPath`、`Rarity`、`Pool`、`AfterObtained/AfterRemoved`、`IncrementStackCount` | 遗物 |
| `PotionModel` | `Title/Description/ImagePath/OutlinePath`、`Rarity/Usage/TargetType`、`OnUseWrapper` | 药水 |
| `CardPoolModel` | `AllCards`、`AllCardIds`、`EnergyColorName`、`EnergyIconPath`、`CardFrameMaterialPath`、`GetUnlockedCards` | 卡池 |
| `RelicPoolModel` / `PotionPoolModel` | `AllRelics` / `AllPotions`、`EnergyColorName` | 池 |
| `MonsterModel` | `PerformMove`、`SetMoveImmediate`、`RollMove`、`IsPerformingMove`、`ResetStateMachine`、`OnSideSwitch`、`VisualsPath`、`AttackSfx/CastSfx/HurtSfx/DeathSfx` | 敌人；迎战原型的关键入口 |
| `EncounterModel` / `EventModel` / `AncientEventModel` / `ActModel` | 遭遇/事件/先古/幕的完整接口 | 本 Mod v1 不新增 |

池注册（`sts2-v0.107.1-api.json.official_modding.ModHelper`）：
`AddModelToPool(Type poolType, Type modelType)`、`ConcatModelsFromMods<T>(IPoolModel, IEnumerable<T>)`、`SubscribeForRunStateHooks(string, RunHookSubscriptionDelegate)`、`SubscribeForCombatStateHooks(...)`、`IterateAllRunStateSubscribers(RunState)`、`IterateAllCombatStateSubscribers(CombatState)`。

## 4. 枚举（直接决定卡牌声明写法）

| 枚举 | 值 |
|---|---|
| `CardType` | None 0, Attack 1, Skill 2, Power 3, Status 4, Curse 5, Quest 6 |
| `CardRarity` | None 0, Basic 1, Common 2, Uncommon 3, Rare 4, Ancient 5, Event 6, Token 7, Status 8, Curse 9, Quest 10 |
| `TargetType` | None 0, Self 1, AnyEnemy 2, AllEnemies 3, RandomEnemy 4, AnyPlayer 5, AnyAlly 6, AllAllies 7, TargetedNoCreature 8, Osty 9 |
| `CardKeyword` | None 0, Exhaust 1, Ethereal 2, Innate 3, Unplayable 4, Retain 5, Sly 6, Eternal 7 |
| `CardTag` | None 0, Strike 1, Defend 2, Minion 3, OstyAttack 4, Shiv 5 |
| `PileType` | None 0, Draw 1, Hand 2, Discard 3, Exhaust 4, Play 5, Deck 6 |
| `ValueProp` | Unblockable 2（不可格挡 HP loss）、Unpowered 4、Move 8（攻击）、SkipHurtAnim 16 |
| `PowerType` / `PowerStackType` / `PowerInstanceType` | Buff/Debuff；Counter/Single；Instanced/InstancedPerApplier |
| `RelicRarity` / `PotionRarity` / `PotionUsage` | Starter 1…Ancient 7；Common 1…Token 5；CombatOnly/AnyTime/Automatic |
| `CharacterGender` | Neutral/Feminine/Masculine |
| 多人约束 | `CardMultiplayerConstraint`: None/MultiplayerOnly/SingleplayerOnly |

`DamageProps` 组合常量另见 `DamageCmd`/`CreatureCmd` 重载（`card`/`cardUnpowered`/`cardHpLoss`/`monsterMove`/`nonCardUnpowered`/`nonCardHpLoss`），`ValueProp` 是位掩码。

## 5. 命令（效果实现只走命令）

`sts2-v0.107.1-api.json.commands` 已列全 20 个命令类，下列为与 Volibear 直接相关的签名（省略 `PlayerChoiceContext` 等前缀细节，完整见 JSON）：

- **伤害**：`CreatureCmd.Damage(ctx, Creature target, decimal amount, ValueProp props, CardModel? card)`；`CreatureCmd.Damage(ctx, Creature[], ...)` 批量；`DamageCmd.Attack(decimal).From(...)...` builder 链（`.WithHitFx` 等扩展在 `DamageCmd` builder 内，模板 cookbook 有示例）。
- **格挡/生命**：`CreatureCmd.GainBlock(Creature, BlockVar|decimal, CardPlay?, bool)`、`LoseBlock`、`Heal`、`SetCurrentHp`、`GainMaxHp`、`Kill`、`Stun`。
- **能力**：`PowerCmd.Apply(ctx, PowerModel|Type, Creature, decimal, Creature? applier, CardModel? card, bool silent)`、`Remove`、`ModifyAmount`、`Decrement`、`TickDownDuration`。
- **牌堆/牌**：`CardPileCmd.Draw(ctx, Player)`、`Draw(ctx, decimal, Player, bool)`、`AddGeneratedCardToCombat(CardModel, PileType, Player, CardPilePosition)`、`Add(...)`、`Shuffle`；`CardCmd.Exhaust/Discard/Transform/TransformTo/Upgrade/Enchant/Afflict/ApplyKeyword/RemoveKeyword/SetToFreeThisTurn...`。
- **选牌**：`CardSelectCmd.FromCombatPile(ctx, CardPile, Player, CardSelectorPrefs)`、`FromSimpleGrid`、`FromHand`、`FromDeckGeneric` 等（检索/回收/手牌选择用）。
- **能量/金币/回合**：`PlayerCmd.GainEnergy/LoseEnergy/SetEnergy/GainStars/EndTurn`。
- **表现**：`VfxCmd.PlayOnCreatureCenter/PlayOnCreatures/PlayVfx(Vector2, string, Control)`、`SfxCmd.Play/PlayLoop/StopLoop`、`TalkCmd`、`ThinkCmd`。
- **其他**：`OrbCmd`、`OstyCmd`、`ForgeCmd`、`RewardsCmd`、`RelicCmd`、`PotionCmd`、`MapCmd`、`Cmd.Wait`。

结论：雷伤→`ValueProp` 组合；迎战→`MonsterModel.PerformMove`；兽化→`CardCmd.Transform` 或 `CardPileCmd.AddGeneratedCardToCombat`；重演→`ModifyCardPlayCount`（语义待验证）；领域压制→对应 `Modify*/Should*` 钩子 + Harmony；关键词→RitsuLib `ModKeywordDefinition` 或 BaseLib。

## 6. 资源 / UI / 音频

- **卡图**：`CardModel.PortraitPath`/`BetaPortraitPath`/`FramePath`/`PortraitPngPath`；模板实测尺寸 `card_portraits/card.png 250×190`、`big/card.png 1000×760`（RGB 不透明），命名 = 卡类 ID 去前缀小写（`B01`→`b01.png`）。与美术仓 `volibear_cards_repo/production/sts2/` 完全一致。
- **角色**：`CharacterModel.CreateVisuals`/`GenerateAnimator`；战斗视觉根节点 `NCreatureVisuals` 需要 `Visuals`(Node2D)、`Bounds`(Control)、`IntentPos`(Marker2D)、`CenterPos`(Marker2D，VFX 生成位)，可选 `OrbPos/TalkPos/PhobiaModeVisuals`。模板 `CharMod/images/charui/*` 给出选角/地图/能量图标尺寸（实测 132×195、128×128、74×74、24×24 等）。
- **动画**：官方走 Spine（`MegaSprite`/`SpineAnimationBackend`）；非 Spine 路线由社区框架提供：BaseLib `CustomAnimation`（按名 `Play`，支持 `AnimatedSprite2D`）或 RitsuLib `ModAnimStateMachine` + `AnimatedSprite2DBackend`/`FormSwitchingAnimationBackend`（支持状态、形态切换）。
- **音频**：官方 `SfxCmd.Play(string eventPath, ...)` 指向 FMOD 事件；`SfxCmd.Play(string bankPath, string eventPath, ...)` 一类重载可带 bank。BaseLib 有 `PlayResourcePatch` 把 `res://` Ogg 接到 `NAudioManager.PlayOneShot`。游戏本体 bank 只有 Master/Music/ambience/act*，**没有角色专属 bank** → 直接 `event:/sfx/...` 不可用，必须走 Ogg 桥或自制 bank。
- **本地化**：`localization/<lang>/cards.json`、`powers.json`、`relics.json`、`characters.json`、`card_keywords.json`、`static_hover_tips.json`、`ancients.json`（模板目录即完整清单）；分析器 `Alchyr.Sts2.ModAnalyzers` 从代码里的 `LocString` 反查缺失 key。

## 7. 构建工具链（模板实测）

### 7.1 前置

1. **.NET SDK 9.0+**（本机只有 runtime 9.0.14，`dotnet --info` 显示 `No SDKs were found`）——用官方 `dotnet-install.sh` 装到 `~/.dotnet` 或发行版包。
2. **MegaDot**（Mega Crit 的 Godot 4.5.1 定制版，`https://megadot.megacrit.com/`）或其版本完全一致的 Godot .NET 4.5.1；`Directory.Build.props` 里 `GodotPath` 指向可执行文件。**游戏不会加载用更新 Godot 版本打的 pck**（模板注释原文）。
3. **BaseLib**：Workshop 订阅（`steamapps/workshop/content/2868840/3737335127/BaseLib`）或 GitHub Release zip 解到 `mods/BaseLib/`。
4. **模板**：`dotnet new install Alchyr.Sts2.Templates`，然后 `dotnet new alchyrsts2charmod -o VolibearMod`（或 Rider 里选 "Slay the Spire 2 Character"）。

### 7.2 工程与 csproj（模板原文要点）

`Godot.NET.Sdk/4.5.1` + `net9.0` + `ImplicitUsings` + `Publicize`（Krafs.Publicizer 2.3.0，用于访问 private 的游戏成员）+ `AllowUnsafeBlocks`；从 `$(Sts2DataDir)` HintPath 引用 `0Harmony.dll`、`sts2.dll`（`Private=false`）；NuGet `Alchyr.Sts2.BaseLib`、`Alchyr.Sts2.ModAnalyzers`；`AdditionalFiles` 挂 `localization/**/*.json`。
构建目标：`CopyToModsFolderOnBuild` 把 `dll/json/pdb` 拷到 `$(ModsPath)<ProjectName>/`；`GodotPublish` 在 Publish 后执行
`"$(GodotPath)" --headless --export-pack "BasicExport" "$(ModsPath)<Name>/<Name>.pck"`。
`Directory.Build.props`：`<GodotPath>...</GodotPath>`，可选 `<Sts2Path>`（flatpak 本机必须显式指到 `.../Slay the Spire 2`，否则 `Sts2PathDiscovery.props` 找不到）。
`Sts2PathDiscovery.props` 自动探测 `?/steamapps/common/Slay the Spire 2/data_sts2_<platform>_x86_64`。

### 7.3 调试循环

- 只改 `.cs`：`dotnet build`（拷 dll/json 到 mods，不用 Godot）。
- 改文本/图片/场景：必须 `dotnet publish`（重新导 pck）；模板注释强调“忘记 publish 是最常见错误”。
- 游戏内 Settings → Mod Settings 启用；`-nomods` 回归无 mod；有 mod/无 mod 存档分离。

### 7.4 发布

`mods/<Name>/` 整目录即分发物（json+dll+pck）；Steam Workshop 用官方上传器 `https://github.com/megacrit/sts2-mod-uploader`。

## 8. 框架版本兼容矩阵

| 框架 | 最新版本（核查日） | 与 v0.107.1 的关系 | 依赖 | 备注 |
|---|---|---|---|---|
| Mega Crit 官方 Mod API | 随游戏 v0.107.1 | 本机 dll 直接核实 | — | 早测期 API 会变；每次游戏更新需回归 |
| `Alchyr/ModTemplate-StS2` | master（模板 commit `2c900a04…`，2026-10 抓取） | 模板清单 `min_game_version 0.107.0` | BaseLib ≥3.3.0 | 文档最全的“标准路径”（wiki: Setup / Modding-Basics / Decompiling / Common-Commands-Cookbook） |
| `Alchyr/BaseLib-StS2` | **v3.4.7**（2026-09-11，"Fix patch for main branch"） | main 分支可用 | 无 | 社区事实标准；提供 `CustomCharacterModel/CustomCardModel/CustomAnimation/PlayResourcePatch` |
| `BAKAOLC/STS2-RitsuLib` | **v0.6.10**（2026-10-23） | 官方发布 `Compat.0.107.1` / `0.109.0` / `0.110.0` 三个变体包 | `dependencies: []`（不依赖 BaseLib） | 内容模板、资产 profile、动画状态机（含形态切换）、音频服务、持久化、联机 sidecar、中文文档 |
| `Alchyr/Sts2ModAnalyzers` | NuGet `*` | 随模板 | — | 本地化/loc key 分析器 |

**本方案的选型建议（详见方案文档 §3）**：以 RitsuLib 0.6.10（compat 0.107.1）作为内容/表现框架（它无 BaseLib 依赖、有 0.107.1 专用包、且美术仓的 C# 接入样例就是按它的 API 写的），ModTemplate+BaseLib 作为 M0 对照与回退；同一内容只注册一次。

## 9. 未验证项（必须在 M0/M1 实测）

1. 本机 flatpak 路径下 `Sts2PathDiscovery.props` 能否自动找到游戏；若不能，`<Sts2Path>` 指向 flatpak 目录是否被接受。
2. `ValueProp.Unpowered`/`DamageProps.cardUnpowered` 的确切语义：是否可格挡、是否吃力量/易伤/虚弱、是否触发 `AfterDamageReceived`。
3. `MonsterModel.PerformMove` 在玩家回合内驱动的可行性（迎战原型）与敌方阶段跳过方式。
4. `CardCmd.Transform`/`ApplyGeneratedCardToCombat` 的升级/临时费用继承与战斗存档序列化。
5. `ModifyCardPlayCount` 是“效果结算 N 次”还是“重新完整打出 N 次”（决定重演实现）。
6. RitsuLib 状态机与 BaseLib 同时安装是否冲突（两者都 patch 角色视觉/资产 profile）。
7. Steam flatpak 下 Workshop 目录与本地 `mods/` 的识别（本机 Steam 为 flatpak，路径在 `~/.var/app/...`）。

## 10. 参考

- 本机：`~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2/`（`release_info.json`、`data_sts2_linuxbsd_x86_64/sts2.dll`、`sts2.xml`、`SlayTheSpire2.pck`）
- 机读 API：`audit/sts2-mod-research/sts2-v0.107.1-api.json`（本目录）
- 官方/社区文档：<https://github.com/Alchyr/ModTemplate-StS2/wiki>（Modding-Basics / Setup / Decompiling / Testing-and-Debugging）、<https://alchyr.github.io/BaseLib-Wiki/>、<https://sts2-ritsulib.ritsukage.com/>
- 框架源码：Alchyr/BaseLib-StS2、Alchyr/ModTemplate-StS2、BAKAOLC/STS2-RitsuLib（均已按上述 commit/release 抓取，缓存见 `/tmp/sts2tpl/`）
- 美术侧既有核查：`fun/sts-mod/volibear_reference_repo/research/STS2_SUPPORT_AND_ASSET_REQUIREMENTS_2026-10-27.md`、`STS2_SUPPORT_V5.md`
