# 沃利贝尔 × 杀戮尖塔 2（v0.107.1）完整 Mod 方案

> 调研任务交付 · 2026-10-30 · 本方案不含实现代码，只给可执行方案与验收口径
>
> 证据文件（同目录）：
> - 平台层：[`sts2-mod-research/platform.md`](sts2-mod-research/platform.md)（官方 Mod 加载器 / 内容 API / 构建链 / 框架兼容；附 `sts2-v0.107.1-api.json` 机读 API 快照）
> - 内容层：[`sts2-mod-research/content.md`](sts2-mod-research/content.md) + [`content-cards.json`](sts2-mod-research/content-cards.json)（89 卡矩阵 / 18 类机制 / 卡表 diff / 55 条边界 / StS2 映射）
> - 表现层：[`sts2-mod-research/assets.md`](sts2-mod-research/assets.md) + [`asset-manifest.json`](sts2-mod-research/asset-manifest.json)（动画 / VFX / 音频 / 卡图 / UI 槽位映射与缺口）

---

## 0. 结论（先看这一节）

**可行。** 内容（89 卡/178 牌面/2 遗物）、美术（26 动作 940 帧 / 40 组 VFX / 47 Ogg / 89×2 卡图 / 14 UI）都已就绪；平台是官方 Mod 系统 + 社区框架，本机游戏 v0.107.1 是 main 分支，RitsuLib 有 0.107.1 专用兼容包，BaseLib 模板声明 `min_game_version 0.107.0`。**不需要升级游戏，不需要第三方加载器。**

真正的工作量在工程化，不在调研：

| 维度 | 状态 | 结论 |
|---|---|---|
| 内容规格 | ✅ 定稿（89 卡 = 87 主卡 + 2 兽形；80/80 血；10 张初始牌；83 张奖励池；2 遗物） | 可直接进实现 |
| 美术资产 | ✅ 格式自洽、卡图尺寸与官方模板逐像素比对一致 | 可接；场景/`.tscn`/`SpriteFrames` 需新建 |
| 平台 API | ✅ 官方 + BaseLib/RitsuLib 均可覆盖 | 3 个机制需原型：雷伤语义、迎战、领域压制 |
| 本地环境 | ❌ 缺 .NET SDK、MegaDot/Godot 4.5.1、`mods/` 目录 | M0 第一件事 |
| 工作量 | 单人全职约 **4–6 个月**（含领域压制 Tier 2：28–40 人日）；可先做 **6–8 周 MVP** 垂直切片 | 见 §8 |

**关键风险只有一个**：迎战（7 张牌）需要在玩家回合内驱动敌人执行意图，属引擎非设计用法。方案里它是**决策门**：原型通过就保留原语义，不通过就用等价降级（§7.2）。

---

## 1. 现状盘点

### 1.1 `card-forge/` 工作区（5.9 GB，本身不是 git 仓库）

| 目录 | 状态 |
|---|---|
| `bear-forge/` | **唯一活跃主线**（模拟器）。ahead 1，工作区 **100 个未提交改动**（docs + 各示例测试结构收敛，−993/+342）；最后提交 `088508a` 2026-10-28。Volibear 内容已完成：89 卡/178 牌面、698 项规则检查、TUI、存档/恢复、A20。 |
| `sts-re/` | **杀戮尖塔 1** 逆向规则书。ahead 107，1 个未提交文件（`EventEffectProbe.java`），最后提交 2026-10-20。对 StS2 Mod 只是方法论参考。 |
| `audit/sts-parity-2026-10-21/` | StS1 复刻差异审计（87 项）+ 修复闭环记录。 |
| `.scratch/` 208 MB、`.npm-cache/` 49 MB | 临时夹具/缓存；`.scratch/repo-split/` 是仓库拆分调研。 |

### 1.2 `fun/sts-mod/` 美术资产（约 3.1 GB，均无有效 git 仓库，完整性靠 `SHA256SUMS`）

| 仓库 | 内容 | 大小 |
|---|---|---|
| `volibear_animation_repo/` | `animations/clean/` 26 序列 / 940 帧（512×512 RGBA、24 fps、8 列图集、`pivot_px=[250,442]`，逐帧 SHA）；`vfx/` 40 组/1070 帧（256×256）；`audio/` 47 Ogg/54 cue（48 kHz 单声道）+ `action_cues.json`；`ui/` 14 PNG；`vfx/icons/` 16 组×4 尺寸 + 16 SVG；`exports/VolibearArt_v5.pck`（126.9 MB，离线 Godot 4.5.1 验证通过）；`integration_sts2_v5/src` 6 个 C# 接入样例（**未编译**，按 RitsuLib 0.6.10 API 写） | 2.5 GB |
| `volibear_cards_repo/` | `cards/masters/` 89 张母版（≈1438×1093 RGB）；`production/sts2/.../card_portraits/` 89×1000×760 + 89×250×190（RGB 无卡框、无文字）；`data/asset_manifest.json`（schema v3、89 reviewed）；`vfx/CARD_BINDINGS.md`（89 卡→219 cue） | 325 MB |
| `volibear_reference_repo/` | 研究/参考（身份图、30 张原作卡面、研究文档、音频许可） | 35 MB |
| `volibear_cards_art_review_v6/` | 评审包：89 当前图 + 29 张用户锁定 + **60 张待重绘、已重绘 0**；`generation_queue.json` 未启动 | 193 MB |

> 动画侧 v6/v7/v8 骨骼重制均被否/未批准（`art_approved=false`）→ **接入继续锁 `animations/clean`（v5）**。卡图 v6 重绘完成后只需替换 PNG 重新 publish，不动代码。

### 1.3 本机 StS2

- 安装：Steam flatpak，`~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2/`
- 版本：**v0.107.1**（commit `59260271`，2026-06-18，branch `v0.107.1`），`main_assembly_hash 1692500715`
- 引擎：Godot **4.5.1**（PCK pack v3，engine 4.5.1）；运行时 .NET **9**（`libcoreclr.so` + `sts2.runtimeconfig.json`）
- 程序集：`data_sts2_linuxbsd_x86_64/sts2.dll`（9.36 MB）、`sts2.xml`（19 636 条文档）、`0Harmony.dll`、`MonoMod.*`
- **缺口**：本机 `dotnet` 只有 runtime 9.0.14（`No SDKs found`）；无 Godot/MegaDot；游戏目录下**没有 `mods/`**。

### 1.4 结论

模拟器已经把"沃利贝尔是什么"定义清楚了（可执行参照），美术把"长什么样"交付了，官方/社区框架把"怎么装进 StS2"铺好了。缺的是一层把三者粘起来的工程：新仓库、构建链、机制子系统、接入场景、测试矩阵。

---

## 2. 目标与范围

### 2.1 v1 目标（Definition of Done）

1. 游戏内 Settings → Mod Settings 能看到 **Volibear** 并启用；新开一局可在选角界面选择沃利贝尔。
2. 初始 80/80 血、10 张初始牌（打击×4、防御×4、霆爪、挺身迎战）、初始遗物「不灭狂雷」、Boss 遗物「万古不灭」、颜色 6。
3. **89 张卡全部可打出**，基础/升级两套牌面、费用、稀有度、目标、消耗正确；奖励池 83 张（基础 4、衍生 2 不入池）。
4. 14 个自定义关键词（雷势/雷伤/雷法/领域/迎战/吸收/兽化/检索回收/减费/咬痕/反雷/蓄势/强化/重演/汲取/留甲/坚甲/净化消耗）在卡面 tooltip 正确显示，中文文案与定稿一致。
5. 三个核心机制按规格工作：领域（附雷 + 时长 + 抽牌净化）、迎战（含吸收）、兽化（手牌变身、继承升级、减费）。
6. 战斗内存档/读档不丢状态；A1–A20 生命值规则生效。
7. 美术：角色战斗动画（idle/attack/cast/hit/die/relaxed + 领域/兽化表现）、89 张卡图、14 张 UI、命中 VFX、音频可用；缺失槽位显式原版回退。
8. 本地化：**中文（zhs）必须**，英文（eng）建议；卡名/牌面/关键词/角色/遗物/能力全量。
9. 单机可完整打通一局（含 Boss 遗物替换、死亡/胜利结算）。

### 2.2 非目标（v1 明确不做）

- **联机同步**（`affects_gameplay=true`，多人下应视为不兼容；v2 再评估）。
- 新敌人/新事件/新先古/新幕（复用原版内容）。
- 自制 FMOD bank（声音走 Godot/Ogg 路线，见 §6.4）。
- 自定义药水（复用原版药水池）；遗物只做 2 件。
- 角色语音、主题曲、商店/篝火独立坐姿（原版回退）。
- 平衡性定稿（先对齐模拟器数值，平衡是 v1.1 的事）。

### 2.3 验收口径

“方案完成”= 上述 9 条在真实游戏 v0.107.1 中逐条演示；“代码完成”= `dotnet publish` 成功 + 游戏内 mod 列表可见 + 89 卡冒烟表全绿；“资料完成”= 本目录四份文档 + 两个机读清单可复现。

---

## 3. 技术选型

### 3.1 分层

```
官方 Mod 加载器（MegaCrit.Sts2.Core.Modding）   ← 必须，负责 dll/pck/manifest/本地化
        └─ 社区内容框架（二选一，不混用注册源）
             ├─ RitsuLib 0.6.10 (Compat 0.107.1)   ← 推荐主选
             └─ BaseLib 3.4.7 + ModTemplate-StS2    ← 备选/对照
                      └─ 本 Mod：角色 / 卡牌 / 能力 / 命令 / Patch / 资产场景
```

### 3.2 推荐：RitsuLib 0.6.10（compat 0.107.1）为主框架

理由（按权重）：

1. **版本对口**：RitsuLib v0.6.10（2026-10-23）官方发布 `STS2.RitsuLib.Compat.0.107.1`、`0.109.0`、`0.110.0` 三个变体包，本机 v0.107.1 直接用对应包。
2. **依赖干净**：`mod_manifest.json` 为 `"dependencies": []`、`has_pck:false`、`affects_gameplay:false`，不依赖 BaseLib，不会引入双框架冲突。
3. **资产适配已按它写**：美术仓 `integration_sts2_v5/src/*.cs`（SpriteFrames / 状态机 / 音频 cue / VFX / UI 槽位）均按 RitsuLib 0.6.10 API 写成（`ModCharacterTemplate.SetupCustomCombatAnimationStateMachine`、`AnimatedSprite2DBackend`、`CharacterAssetProfile`、`GameAudioService`），直接复用/改造成本最低。
4. **覆盖面最全**：内容模板（角色/卡/能力/遗物/药水/池）、关键词注册（`ModKeywordDefinition`）、动态卡面数值、资产 profile、动画状态机（含 `FormSwitchingAnimationBackend`，正好覆盖领域/兽化形态）、持久化（`RunSavedData`）、联机 sidecar。
5. **中文文档**（作者 BAKAOLC），本项目以中文工作流为主。

备选：**BaseLib 3.4.7 + ModTemplate 角色模板**。优势是社区标准、模板/分析器/本地化生成成熟、文档最全（ModTemplate wiki + BaseLib wiki）；劣势是没有现成形态切换/资产 profile，交付的 C# 表现层样例要重写，动画只能走 `CustomAnimation`（按名播放，无条件分支）。

**决策门（M0 第 1 天）**：建两个最小工程（RitsuLib 模板 / ModTemplate+BaseLib），各只注册一个角色 + 一张卡，比较 5 项：能否加载、选角是否出现、卡图/动画是否生效、publish 是否成功、是否与已装 mod 冲突。当天定主选，另一套留作回退。写进 `docs/decisions/ADR-001-framework.md`。

### 3.3 版本 pin（写进新仓库 `versions.json`）

| 组件 | pin 值 |
|---|---|
| 游戏 | v0.107.1，commit `59260271`，`main_assembly_hash 1692500715` |
| Godot | MegaDot 4.5.1（或同版本 Godot .NET 4.5.1）；**pck 版本由它决定，不能更高** |
| .NET | SDK 9.0.x（≥9.0.100） |
| 模板 | `Alchyr.Sts2.Templates`（模板 commit `2c900a04…` 为资产尺寸基准） |
| RitsuLib | 0.6.10（compat 0.107.1 变体） |
| BaseLib（若回退） | 3.4.7 |
| 游戏更新策略 | 只跟 main 分支；每次更新先跑一周回归再升级（见 §10） |

### 3.4 仓库策略

新建独立仓库 `sts2-volibear-mod/`（建议放在 `card-forge/` 同级或 `Projects/` 下，git init）：

- `card-forge` 保持"模拟器 + 逆向 + 调研"职责，**不当 mod 仓库**。
- 模拟器是**行为 oracle**（不是运行时依赖）：卡效、边界、数值以 `bear-forge/examples/sts/src/content/characters/volibear` 与 `docs/volibear/*` 为准。
- 美术三个仓库是**只读素材源**：用同步脚本按 SHA 拉取，不把 2.5 GB 原始素材塞进 mod 仓库（只提交运行时需要的子集）。

---

## 4. 工程骨架

### 4.1 目录结构（基于角色模板 + RitsuLib 约定）

```
sts2-volibear-mod/
├─ VolibearMod.sln
├─ Directory.Build.props          # GodotPath / Sts2Path（flatpak 路径必须显式写）
├─ versions.json                  # §3.3 pin + 游戏/框架哈希
├─ docs/
│  ├─ decisions/ADR-001-framework.md
│  ├─ plan.md                     # 里程碑勾选
│  ├─ test-matrix.md              # §9 验收表
│  └─ research/                   # 本方案三份调研（软链/复制）
├─ tools/
│  ├─ gen_cards.py                # content-cards.json → C# 卡牌骨架 + 本地化 key
│  ├─ sync_assets.py              # 从 fun/sts-mod 按清单 SHA 同步运行时资产
│  ├─ verify_content.py           # 卡表/资产一致性（89/83/178、肖像存在、关键词覆盖）
│  └─ compare_oracle.py           # 与模拟器 TS 卡表/测试数值对拍
├─ src/VolibearMod/
│  ├─ VolibearMod.csproj
│  ├─ VolibearMod.json            # manifest（§4.2）
│  ├─ ModEntry.cs                 # [ModInitializer(nameof(Initialize))]
│  ├─ Character/
│  │  ├─ Volibear.cs              # 角色：80/80、颜色 6、初始牌组/遗物、卡池
│  │  ├─ VolibearCardPool.cs      # 83 奖励池 + 4 基础 + 2 衍生
│  │  ├─ VolibearRelicPool.cs
│  │  └─ VolibearPotionPool.cs
│  ├─ Cards/
│  │  ├─ VolibearCard.cs          # 卡牌基类（本地化/肖像/关键词模板）
│  │  ├─ Basic.cs / Common.cs / Uncommon.cs / Rare.cs / Tokens.cs
│  │  └─ (89 个 partial 类，生成骨架 + 手写 OnPlay)
│  ├─ Powers/                     # 自定义能力（§5.3）
│  ├─ Commands/                   # LightningCmd / EngageCmd / BeastifyCmd / SearchCmd
│  ├─ Patches/                    # 领域压制 / 迎战回合 / 卡牌转换等 Harmony
│  ├─ Relics/HuntersHeart.cs, ImmortalHeart.cs
│  ├─ Keywords/VolibearKeywords.cs
│  ├─ Visuals/                    # 角色场景、SpriteFrames 构建、动画状态机
│  ├─ Audio/                      # cue 播放器 / 原生槽映射
│  ├─ Vfx/                        # VFX 图集播放 / .tscn 包装
│  └─ Volibear/                   # res:// 资产根（pck 内容）
│     ├─ images/card_portraits/{,big}/<key>.png   # 89×2
│     ├─ images/charui/*.png                      # 14
│     ├─ animations/...                           # 26 图集 + JSON
│     ├─ vfx/...                                  # 40 图集 + JSON + .tscn
│     ├─ audio/ogg/*.ogg                          # 47
│     ├─ scenes/creature_visuals/volibear.tscn
│     ├─ materials/volibear_transition_mat.tres
│     └─ localization/{zhs,eng}/*.json
└─ tests/
   ├─ VolibearMod.Tests/          # 纯逻辑单测（伤害/计数/关键词/费用）
   └─ smoke/                      # 游戏内冒烟脚本（§9）
```

### 4.2 manifest（初版）

```json
{
  "id": "VolibearMod",
  "name": "Volibear",
  "author": "<作者>",
  "description": "League of Legends' Volibear as a Slay the Spire 2 character: 89 cards, thunder momentum, domain and engage mechanics.",
  "version": "v0.1.0",
  "min_game_version": "0.107.0",
  "has_pck": true,
  "has_dll": true,
  "dependencies": [
    {"id": "STS2-RitsuLib", "min_version": "0.6.10"}
  ],
  "affects_gameplay": true
}
```

> `dependencies` 按 M0 决策门结果填写：RitsuLib 主选；回退 BaseLib 时写 `{"id":"BaseLib","min_version":"3.4.7"}`。`affects_gameplay` 必须 `true`（新角色/卡牌属于玩法）。

### 4.3 构建与调试循环

```bash
# 一次性
dotnet tool install --global dotnet-sdk 9 # 或 dotnet-install.sh 装到 ~/.dotnet
dotnet new install Alchyr.Sts2.Templates
# RitsuLib: 下载 STS2.RitsuLib.Compat.0.107.1.0.6.10.github.zip 解到
#   <游戏目录>/mods/STS2-RitsuLib/
# BaseLib（若用）: <游戏目录>/mods/BaseLib/（BaseLib.3.4.7.zip 或 Workshop）
# MegaDot: 解压后 Directory.Build.props 写 <GodotPath>...</GodotPath>
#         flatpak 游戏必须写 <Sts2Path>/home/.../Slay the Spire 2</Sts2Path>

# 日常
dotnet build          # 只改 .cs：编译 dll + 拷 json 到 mods/VolibearMod/
dotnet publish        # 改了文本/图片/场景：重导 pck（Godot 4.5.1 headless export-pack）
# 启动游戏（flatpak）
flatpak run com.valvesoftware.Steam -applaunch 2868840   # 或桌面图标
# 游戏内 Settings → Mod Settings 启用 VolibearMod；-nomods 回归
```

本地已验证：模板 csproj 用 `Godot.NET.Sdk/4.5.1`、`net9.0`，HintPath 引用 `$(Sts2DataDir)/sts2.dll` 与 `0Harmony.dll`，Publish 后自动 `--export-pack "BasicExport"` 并把三件套拷进 `mods/<Name>/`（详见 [`platform.md`](sts2-mod-research/platform.md) §7）。

---

## 5. 内容实现方案

### 5.1 数据源与代码生成（把 89 卡变成 89 个类）

单一事实来源：`audit/sts2-mod-research/content-cards.json`（89 条，字段含 id/名称/类型/费用/稀有度/目标/消耗/文本/关键词/雷法/实现要点）+ `bear-forge/docs/volibear/cards_s2.json`（牌面文案双方一致）。

`tools/gen_cards.py` 一次生成：

1. 卡牌类骨架：类名（`Volibear_B03_ThunderClaw`）、构造参数（费用、`CardType`、`CardRarity`、`TargetType`）、关键词、`PortraitPath`（`<key>.png`，严格小写去前缀）、本地化 key；
2. 本地化占位：`localization/zhs/cards.json` 填定稿牌面（动态数值用占位符），`card_keywords.json` 填 14 个关键词；
3. 实现待办清单：每个类一个 `// TODO OnPlay` 和指向该卡"实现要点"的注释；
4. 一致性校验：89 = 4 基础 + 24 普通 + 36 罕见 + 23 稀有 + 2 衍生；奖励池 83；178 牌面。

骨架生成只做**静态数据**；效果必须手写（89 张卡 + 25 张能力/衍生效果，量约 2000–3000 行 C#），从模拟器 TS 卡模块逐张翻译（对照 `content.md` §2.3 的实现要点与 §6 边界清单）。

### 5.2 卡牌实现范式（官方 API 形态，模板 cookbook 实测语法）

```csharp
public sealed class Volibear_B03_ThunderClaw : VolibearCard
{
    public Volibear_B03_ThunderClaw() : base(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy) {}

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [ new DamageVar(8, ValueProp.Move), new DamageVar("Lightning", 3, ValueProp.Unpowered) ];

    protected override async Task OnPlay(PlayerChoiceContext ctx, CardPlay play)
    {
        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .FromCard(this).Targeting(play.Target)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(ctx);
        await LightningCmd.DealAllEnemies(ctx, DynamicVars["Lightning"].BaseValue, this); // 自研
    }
}
```

约定：

- 牌面数值全部进 `CanonicalVars`/`DynamicVars`，升级在 `OnUpgrade` 里改基础值（不手改 UI 文本）；
- 效果只调 `DamageCmd / CreatureCmd / CardPileCmd / CardSelectCmd / PowerCmd / CardCmd / PlayerCmd`，不直接改数据结构；
- 触发型效果一律放 `PowerModel` 的钩子（`AfterCardPlayed`、`AfterDamageReceived`、`AfterSideTurnStart` 等），卡牌本体保持"一次命令序列"；
- 每张卡一个 partial 类文件，按稀有度分目录；生成器可重跑不覆盖已手写的 `OnPlay`（文件头标记 `// generated:fields` / `// hand-written`）。

### 5.3 机制子系统映射（14 类，决定 80% 的实现风险）

| # | 机制 | 承载 | 关键 API/钩子 | 风险 | 备注 |
|---|---|---|---|---|---|
| 1 | 雷势 | 自定义 `PowerModel`（Amount=层数，本战） | 只作数值容器，**不注册** `ModifyDamageAdditive` | 低 | 6 个来源：C25/U29/U26/U04/R28/R17 |
| 2 | 雷伤 | 自研 `LightningCmd` → `CreatureCmd.Damage(..., ValueProp.Unpowered, card)` | `AfterDamageReceived` 计数 | **中：语义待实测** | 不吃力量/易伤/虚弱、可格挡、按"批次"计 1 次 |
| 3 | 雷伤计数（strikes） | `DomainPower`/全局 power 字段，回合切换逻辑归零 | 自定义事件/`AfterDamageReceived` | 低 | 驱动 U21/U27/U34/U38/U40 |
| 4 | 领域 N | `DomainPower`：`UntilTurn?`、`DrawnTurn`、`LastPlayId` | `AfterCardPlayed`（附雷）、`AfterHandDraw`（扣时）、`AfterCardDrawn`（净化） | 中 | 1 覆盖"本回合+敌方阶段+下次起手抽牌后" |
| 5 | 领域·附雷 | 同上 | `AfterCardPlayed` + 判断首个普通攻击段 | 中 | 每张实际出牌 1 次，重演共用；金额 4+雷势+U12 |
| 6 | 领域·压制 | Patch + `Modify*/Should*` 钩子 | 见 §5.4 分档 | **高：需用户裁决范围** | 字面"全压制"≈关敌人 AI |
| 7 | 迎战 | 自研 `EngageCmd`：`MonsterModel.PerformMove` + 隐藏"本轮已行动"标记 | `MonsterModel.MoveStateMachine`、`CombatManager`、`AfterDamageReceived`（吸收） | **最高：POC 门** | 7 张牌；降级方案见 §7.2 |
| 8 | 吸收 | 自研 `EngageWindowPower` + 伤害结果累计 | `AfterDamageReceived` | 中 | 完全格挡也计；多目标累加 |
| 9 | 兽化 | 生成 T01/T02 副本（`CardCmd.Transform` 或克隆入战斗） | `CardCmd.Transform`、`CardPileCmd.AddGeneratedCardToCombat`、`TemporaryCardCost` | 高 | 继承升级/临时减费；形态牌消耗；战后原牌不变 |
| 10 | 蓄势/强化 | 卡牌级战斗状态（`AfflictionModel` 或 power 内字典） | `CardCmd.Afflict`、`ModifyDamageAdditive`（条件限定本卡） | 中 | 蓄势=下次打完清除；强化=本战持续 |
| 11 | 重演 | 优先验证 `ModifyCardPlayCount` 语义 | `ModifyCardPlayCount`/`GeneratePlayCount` | 中 | 若语义是"重打"则改为卡内二次执行序列 |
| 12 | 咬痕/反雷/汲取 | 敌人身上的 `PowerModel` / 受击响应 / `CreatureCmd.Heal` | `PowerCmd.Apply`、`AfterDamageReceived` | 低 | 咬痕随敌人实体存本战 |
| 13 | 留甲/坚甲 | `ShouldClearBlock` 钩子 / 格挡消耗 Patch | `ShouldClearBlock`、格挡消耗需 publicizer | 中 | 留甲=回合开始 block−min(N,block) |
| 14 | 减费/检索/X 费/临时力量 | 原生 `TemporaryCardCost`、`CardSelectCmd`、`HasEnergyCostX`、`TemporaryStrengthPower` | `TryModifyEnergyCostInCombat` 等 | 低-中 | 4 套减费不可混用 |

### 5.4 领域压制：禁用 + 小 patch + 例外（已细化，详见专项文档）

模拟器实现是"只压制对敌人有利的效果，保留普通攻击/直接力量/直接格挡/战斗事实与全部负面效果"。对 StS2 v0.107.1 的实际盘点（121 个怪物类 / 123 个有招式 / 356 个 move / 263 个 Power 类 / 93 个遭遇组 / 15 种 `IntentType`）后，结论是**不需要自研敌人 AI 循环**，四层实现即可：

| 层 | 做法 | 覆盖 | 成本 |
|---|---|---|---|
| L1 意图级跳过 | 领域 active 时读 `MoveState.Intents`：纯 Buff/Debuff/Heal/Summon/StatusCard/CardDebuff 招跳过执行，状态机正常流转；含 Attack/Defend 的混合招正常执行 | 纯特殊招 | 3–5 人日 |
| L2 Hook 模型过滤 | 在 `Hook`（149 个分发方法）的 `ShouldDie`/`ShouldAllowHitting`/`ShouldAllowTargeting`/`ModifyDamage`/`ModifyHpLost`/`ModifyPowerAmountGiven`/`ShouldClearBlock`/`ModifyCardBeingAddedToDeck` 等 12–15 个方法里过滤"敌方正面 Power 模型" | 复活/限伤/无敌/不可选/被动增益/塞牌/削升级的大部分 | 6–9 人日 + 分类表 3–5 人日 |
| L3 命令级 gate | 敌方招式上下文中拦截 `PowerCmd.Apply`（非白名单）、`CreatureCmd.Heal/GainMaxHp`（敌）、`CreatureCmd.Add`（召唤）、`CardPileCmd.AddGeneratedCardToCombat/AddCurseToDeck`、`CardCmd.Upgrade/Downgrade/Transform`（削升级） | 招式内一次性效果 | 5–8 人日 |
| L4 逐怪例外 | `domain_exceptions.json`（怪物 → `skip_move`/`patch_hook`/`allow`）+ 小 patch；重点 12 个（TestSubject、CeremonialBeast、Queen、Decimillipede、KnowledgeDemon、ThievingHopper、TheForgotten、TheLost、Aeonglass、Fabricator、TheObscura、TwoTailedRat） | 多阶段/偷牌/诅咒/分段 | 8–20 人日 |

**推荐 v1 = Tier 2**：L1 + L2（12–15 Hook）+ L3 + 8 个重点例外 + 93 遭遇冒烟 ≈ **28–40 人日**（≈90% 遭遇语义正确；剩余为显式例外）。对比：89 张卡全量约 30–45 人日——领域压制与全部卡牌同量级，必须分档做。

明确放行（写进 mod 文档）：敌人已有力量/格挡、敌方自身负面、Escape/Sleep/Stun、纯视觉形态；v1.1 再补偷牌归还与剩余例外。完整盘点、具体 Hook 清单、POC 与分档工作量见 [`sts2-mod-research/domain-suppression-workload.md`](sts2-mod-research/domain-suppression-workload.md)。

### 5.5 角色 / 卡池 / 遗物

- 角色：`StartingHp=80`、`MaxEnergy=3`、`CardPool/RelicPool/PotionPool`、`StartingDeck`（B01×4、B02×4、B03、B04）、`StartingRelics`=[HuntersHeart]、颜色 6；A20 生命规则沿用游戏原生（模拟器口径：最大 75/初始 68；StS2 的难度体系不同，`content.md` §1 的 A20 规则需在 StS2 侧按自身 Ascension 实现，M1 校准）。
- 初始遗物「不灭狂雷」：每战每回合首次**完成**迎战时抽 1；Boss 遗物「万古不灭」：替换后抽 2（`RelicCmd.Replace`）。
- 卡池：`AllCards` 83 张奖励池；基础 4 张（不入奖励池）与 T01/T02 衍生（`CardRarity.Token`，不入池）。
- 药水：复用原版药水池（`VolibearPotionPool` 空池 + 原版池映射，M1 决定）。

### 5.6 本地化

- 语言：`zhs` 必做、`eng` 建议（中文文案直接取自 `cards_s2.json`；英文需要一轮翻译 + 校对）。
- 范围：89 卡 × 2 牌面、14 关键词、角色名/描述/选角文本、2 遗物、约 25 个能力、UI 提示（`static_hover_tips.json`）。
- 动态数值统一用 `DynamicVars` 占位符（`{Damage}`, `{Block}`, `{Cards}`），避免升级后文本与数值不一致；模板分析器（`Alchyr.Sts2.ModAnalyzers`）负责查缺。

---

## 6. 表现层接入

### 6.1 卡图（最低成本，先做）

- 来源：`volibear_cards_repo/production/sts2/Volibear/images/card_portraits/{,big}/<key>.png`（89+89，1000×760 / 250×190，RGB 不透明），与官方模板逐像素尺寸一致，**命名 = 卡类 ID 去前缀小写**（`B01`→`b01.png`），填 `CardModel.PortraitPath`。
- 接入：`tools/sync_assets.py` 按 `asset-manifest.json` 的 SHA 复制到 `src/VolibearMod/Volibear/images/card_portraits/`；改图后 `dotnet publish` 即可。
- 风险：命名不一致会静默回退 `card.png`（89 张全变默认图）→ 用 `verify_content.py` 校验。

### 6.2 角色动画与战斗场景

- 战斗根场景 `NCreatureVisuals`（**必须新建**）：`Visuals`(Node2D)、`Bounds`(Control)、`IntentPos`(Marker2D)、`CenterPos`(Marker2D，VFX 生成位)。图集锚点 `pivot_px=[250,442]` → `AnimatedSprite2D` 建议 `centered=false`、`offset=(-250,-442)`；`Bounds` 固定不随帧变。
- SpriteFrames：运行时从 `animations/clean/manifest.json` + 26 个 PNG/JSON 构建（复用 `integration_sts2_v5/src/VolibearSpriteFrames.cs`），或离线烘焙 `.tres`。帧时长为**相对值**：`SpriteFrames` 秒 = `duration_ms*fps/1000`，24 fps/41.6667 ms 写 **1.0**。
- 状态机（RitsuLib 路线）：26 序列 → 游戏动作集映射（Idle/Attack/Cast/Hit/Dead/Relaxed + 项目扩展 HeavyAttack/Bite/Counter/DomainEnter/Exit/Feral/Roar/StormLeap）；领域与兽化用状态机条件（`Func<bool>`）切换，**不要在卡牌代码里直接 `Play()`**。
- 未验证：RitsuLib 状态机与 BaseLib 同时安装的冲突；朝左镜像（`flip_h` 会翻转 pivot 语义）。

### 6.3 VFX

- 40 组图集（256×256，8 列）不能直接传给 `WithHitFx`：`vfx` 参数是**场景路径**（`res://vfx/*.tscn`）→ 为每张用到的特效建 `.tscn`（`Node2D` + `AnimatedSprite2D`），或走 `VfxCmd.PlayOnCreatureCenter` + 自有 holder。
- 绑定：`card_vfx_bindings.json`（89 卡 / 219 cue / 10 全局规则）是项目语义契约，需在卡牌 `OnPlay`/伤害事件里真实发出对应事件；4 个特效（`domain_exit/feral_body/lightning_all/lightning_chain`）无绑定行，需补。
- v1 可先接最常用的 10–15 个特效，其余留空（原版命中特效回退），不阻塞卡牌功能。

### 6.4 音频

- 47 Ogg/54 cue 齐全，但**没有 FMOD bank** → 原生 `event:/sfx/characters/...` 不可用。三条路线：
  1. **自有 Godot 播放器**（推荐 v1）：`VolibearCueAudio` 用 `AudioStreamPlayer` 播 `res://` Ogg，按 `action_cues.json` 时间线触发，自带 cooldown/loop/stop/实例清理；不依赖 FMOD。
  2. BaseLib `PlayResourcePatch`：把角色 3–5 个原生音效槽指向 `res://` Ogg（源码存在，未实测）。
  3. 自制 FMOD bank（工作量大，v2 再说）。
- 去重：若用路线 2，原生槽接管的声音必须从自有时间线移除，否则双播；受伤音无原生槽，只能走时间线。

### 6.5 UI

- 直接可接（`Texture2D` 槽）：角色图标、描边、选角图/锁定图、地图标记、大/小能量图标，共 11 张。
- 需新建：`EnergyCounterPath`（PackedScene，只有贴图）、`CharacterSelectTransitionPath`（Material，只有 PNG）、`NCreatureVisuals` 场景；`character_select_background.png` 可走 RitsuLib 的 Texture2D 回退（换框架版本可能失效）。
- 原版回退：卡框/费用/稀有度/描述由游戏 UI 绘制；商店/篝火复用 `relaxed_loop`；复活无独立动画（回待机）。
- 16 组机制图标覆盖 17 关键词中的 13 个：缺 雷伤/雷法、迎战、吸收、检索回收 → 补 4 个图标或显式声明复用（建议补）。

---

## 7. 必须先做的三个技术原型（POC 门）

> 顺序即优先级；POC 不通过不进入全量实现，避免 5 周后返工。

### 7.1 POC-1：雷伤语义（0.5–1 天）
一张测试卡对敌造成 5「雷伤」。验证矩阵：力量 3 / 易伤 2 / 虚弱 2 / 目标格挡 10 / 无格挡。期望：伤害恒为 5（不吃力量/易伤/虚弱），被格挡吸收。若 `ValueProp.Unpowered` 不满足，试 `DamageProps.cardUnpowered` 组合或自研 `CreatureCmd.Damage` 前后补偿；结论写 ADR。

### 7.2 POC-2：迎战（2–4 天，最高风险）
最小场景：玩家回合打出一张"迎战"卡 → 目标执行当前意图（攻击 move）→ 玩家格挡结算 → 正常敌方阶段跳过该敌。
验证点：`MonsterModel.MoveStateMachine` 当前 move 读取、`PerformMove` 调用时机、动画/阵营/VFX 归属、玩家死亡中断、敌人已行动标记、存档序列化。
失败时的降级（按推荐顺序，需用户裁决）：
1. **按意图拆解为等价命令**（Attack→`CreatureCmd.Damage`；Buff→`PowerCmd.Apply`；Defend→`GainBlock`；Heal/Status/Summon 同理），再标记本轮已行动 —— 可控、可测，覆盖全部意图类型；
2. **眩晕+提前行动**：先执行，再给目标下回合跳过；
3. **规则改写**："本回合结束时敌人行动一次，其下回合跳过"（经济性近似，时序不同）；
4. 不建议：删掉吸收/改成"按意图攻击力直接造成伤害"（破坏设计）。

### 7.3 POC-3：领域压制通用性（2–4 天，决定 L2 方案是否成立）
用 3 个场景验证"中心 Hook 过滤"可行：RITUAL/HIGH_VOLTAGE 被动加力量（领域内应停止）、ADAPTABLE/ILLUSION 复活（领域内应死透）、HARDENED_SHELL/GUARDED 限伤（领域内应正常掉血）。同时验证 `MoveState.Intents` 在 `PerformMove` 前可读、纯 Buff 招能跳过且状态机不卡。结论写 ADR；不成立则退回"命令级 gate + 逐怪例外"（工作量上浮 30–50%，见专项文档 §3）。

---

## 8. 里程碑、工作量与排期

假设：1 名熟悉 C#/Godot 的开发者全职；美术/音频由现有流水线并行提供（v5 可用）；模拟器作为 oracle 随时查。

| 里程碑 | 内容 | 出口验收 | 人日 |
|---|---|---|---|
| **M0 环境与决策** | SDK 9 + MegaDot + 模板 + RitsuLib/BaseLib 安装；两套最小工程；ADR 定框架；新仓库骨架 + versions.json；`dotnet publish` 成功；mod 在游戏内可见 | 游戏内 Mod Settings 出现测试角色；构建链可重复 | 2–3 |
| **M1 垂直切片** | 角色可选；80/80、初始 10 牌、初始遗物；B01–B04 + C01/C05；POC-1 雷伤；选角/战斗/卡面/基础动画 | 可开一局、打出 6 张牌、雷伤语义确定 | 5–8 |
| **M2 机制内核** | 雷势、领域（附雷/时长/净化）、雷伤计数、U02/U34/U21、14 关键词 + tooltip、本地化框架（zhs） | 用 15 张机制牌覆盖领域/雷势全路径 | 8–12 |
| **M3 迎战 POC + 吸收** | POC-2 + 7 张迎战牌 + 吸收；降级方案决策 | 迎战在游戏内可用或降级方案获用户确认 | 5–8 |
| **M4 89 卡全量** | 生成器 + 89 卡 OnPlay + 卡池/稀有度/升级面 + 178 牌面文案 + eng 本地化 | 89 张逐张冒烟表全绿；奖励池 83 | 15–22 |
| **M5 高级机制** | 兽化、蓄势/强化、重演、咬痕、反雷、汲取、留甲、坚甲、2 遗物（领域压制另列 M5b） | 对应机制回归用例全绿 | 8–12 |
| **M5b 领域压制（Tier 2）** | L1 意图跳过 + L2 Hook 过滤（12–15 个）+ 263 Power 分类表 + L3 命令 gate + 8 个重点例外 + 93 遭遇冒烟 | 90% 遭遇语义正确、例外清单与放行项成文 | 28–40 |
| **M6 表现层** | `NCreatureVisuals` 场景、SpriteFrames/状态机、89×2 卡图、40→15 VFX `.tscn`、音频时间线、14 UI、4 个缺失图标 | 表现层逐项验收（§9.4） | 10–15 |
| **M7 打磨发布** | 存读档、A1–A20、长局、性能、与模拟器数值对拍、文档、Workshop 包 | §2.1 九条全过 | 8–12 |

**合计 ≈ 89–132 人日（单人 4–6 个月）；两人并行（卡牌/表现 vs 领域压制）约 3–4 个月。**

**MVP 建议（先可玩，再全量）**：M0 + M1 + M2 + M3 的迎战子集（约 20 张牌）≈ **20–31 人日（4–7 周）**，产出"能选角、能打、核心机制成立"的演示版；之后再决定是否全量 89 卡。

**并行建议**：M4 卡牌翻译可与 M6 表现层并行（不同人/不同目录，互不冲突）；M3 迎战与 M2 机制内核可并行（不同文件域）。

---

## 9. 验证与回归

### 9.1 数据一致性（每次生成后自动跑）

`tools/verify_content.py`：89 卡 = 4+24+36+23+2；奖励池 83；178 牌面；每卡 `PortraitPath` 对应 PNG 存在且尺寸 250×190/1000×760；关键词 14 个在本地化表齐全；资产清单 SHA 与 `asset-manifest.json` 一致。

### 9.2 逻辑回归（不依赖游戏）

- 从模拟器 `tests/volibear-content.test.ts` 的 89 个逐牌用例与 `volibear-flow.test.ts` 提取输入/期望，移植为 C# 单测（纯计算：伤害、计数、费用、关键词状态）。
- oracle 对拍：`compare_oracle.py` 用同一组场景对比 TS 模拟器与 C# 纯逻辑结果（数值/事件顺序）。

### 9.3 游戏内冒烟（每里程碑）

| 类别 | 用例 |
|---|---|
| 启动 | 无 mod/有 mod 各启动一次；Mod Settings 启用/禁用；`-nomods` |
| 选角 | 新档可见/可选；角色图标/描边/选角图/背景/转场（回退） |
| 战斗 | 初始牌组；每张卡实际打出（89 张）；升级版；目标选择；消耗/保留；多段/X 费/重演 |
| 机制 | 领域开启/延长/到期/净化；雷势 6 个来源；迎战 7 张 + 吸收；兽化手牌/批量/继承升级；咬痕/反雷/蓄势/强化/留甲/坚甲 |
| 状态 | 战斗内存档→读档；跨战斗遗物/牌组不变；Boss 遗物替换；死亡/胜利结算 |
| 长局 | A0/A20 各打通一局（或至少到第三幕）；幕间转换；商店/篝火 |
| 表现 | 动画 26 动作触发；命中 VFX；音频 cue；UI 槽位 |
| 性能 | 89 卡 tooltip 打开流畅；战斗帧率无明显下降 |

### 9.4 明确不验证（v1 边界）

联机同步、Steam Workshop 上传审核、macOS/Windows 打包（Linux 构建产物 MSIL，理论跨平台，未实测）。

---

## 10. 风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| 迎战无法在玩家回合驱动敌人 | 高 | POC-2 前置；3 个降级方案；用户裁决 |
| 雷伤 `ValueProp` 语义不符 | 中 | POC-1 当天出结论；备选组合/补偿 |
| 领域全压制范围过大 | 高 | v1 A+B 分档 + 逐敌白名单；C 档不做（需用户同意） |
| 兽化转换与存档序列化 | 中 | M5 先做 1 张兽化牌 + 存读档验证 |
| `ModifyCardPlayCount` 语义不明 | 中 | POC 验证；否则卡内二次执行 |
| 框架版本漂移（早测期） | 中 | pin 版本 + vendor DLL；跟 main 分支，更新前跑一周回归 |
| 游戏更新破坏 mod | 中 | `versions.json` 记录哈希；升级窗口与框架作者同步（BaseLib/RitsuLib 通常 1–2 天跟进） |
| 卡图 v6 未重绘 | 低 | v5 可接；重绘后只换 PNG 重新 publish |
| 无 FMOD bank | 低-中 | 自有 Godot 音频播放器；原生槽走 Ogg 桥（未验证）或留空回退 |
| 本机无 SDK/Godot | 低 | M0 一次性安装（dotnet-install + MegaDot zip） |
| **IP/分发**：沃利贝尔是 Riot IP | 中 | 自用/免费非商业分发；不使用官方语音；标注同人性质。研究已确认 Riot 政策限制跨游戏使用其 IP，公开上架前需用户决定 |
| 工作量被低估（89 卡 × 边界） | 中 | 先 MVP；每张卡有模拟器 oracle 与 55 条边界清单，降低返工 |

---

## 11. 需要你裁决的问题（按优先级）

1. **领域压制范围：已确认（2026-10-31）**。采用"禁用 + 小 patch + 例外"四层方案，v1 = **Tier 2**（28–40 人日，覆盖 ~90% 遭遇）；明确放行"敌人已有力量/格挡、敌方自身负面、Escape/Sleep/Stun、偷牌类（TheForgotten/TheLost）"；全保真 Tier 3 留 v2；不采用自研 AI 循环替换。
2. **迎战降级预案**：若 POC-2 失败，接受"按意图拆解为等价命令"（推荐）还是"眩晕+提前行动"/"回合末行动+下回合跳过"？还是必须原语义（接受更高风险）？
3. **雷伤是否可格挡**：模拟器语义是"可格挡的非攻击伤害"；确认沿用？
4. **U03 留甲 6/3**（升级后保留更少=更强）确认不是笔误？卡面怎么写？
5. **2026-10-28 四处修订**（U02 逐段、U21 每 2 次、C26/U40 不限次、U15 消耗为牌效）确认全部替代你 10-27 卡表的旧规则？
6. **多人范围**：v1 只做单人？（建议是）
7. **语言范围**：zhs 必做；eng 是否 v1 就要？
8. **音频策略**：接受"自有 Godot 播放器 + 原生槽可选 Ogg 桥"、不做 FMOD bank？
9. **美术锁版本**：动画继续锁 `animations/clean`（v5），卡图用 v5（v6 重绘完成后替换）——确认？
10. **分发范围**：仅自用/小范围，还是计划 Steam Workshop 公开发布？（影响 IP 处理与文档工作）

---

## 12. 立即可执行的第一步（本周 checklist）

1. **装环境**：.NET SDK 9（`dotnet-install.sh --channel 9.0`）→ MegaDot 4.5.1 解压 → `dotnet new install Alchyr.Sts2.Templates`；创建游戏目录 `mods/`。
2. **建空工程**：`dotnet new alchyrsts2charmod -o VolibearMod`；`Directory.Build.props` 写 flatpak 的 `Sts2Path` 与 `GodotPath`；`dotnet publish`；启动游戏确认 Mod Settings 出现角色（M0 验收）。
3. **装框架**：RitsuLib 0.6.10 compat 0.107.1 解到 `mods/STS2-RitsuLib/`；跑 ADR-001 对比 BaseLib 模板，当天定主选。
4. **建仓库**：`git init sts2-volibear-mod`；提交骨架 + `versions.json`（游戏 commit `59260271`、RitsuLib 0.6.10、BaseLib 3.4.7、模板 `2c900a04…`）。
5. **搬资料**：把 `audit/sts2-mod-research/` 四份文档 + 两个 JSON 复制进仓库 `docs/research/`。
6. **跑 POC-1（雷伤）**：一张测试卡，按 §7.1 矩阵记录结果。
7. **跑 POC-2（迎战）**：按 §7.2 最小场景记录结果；这两份结论直接决定 §11 的 1、2 两条。
8. **接一张卡图 + 一段动画**：`sync_assets.py` 拉 B03 卡图与大图、`idle_loop` 图集；在游戏里看到"这张卡有图、角色会动"即证明表现层链路通。

---

## 附录 A：关键 API 速查

- 入口：`[ModInitializer("Initialize")]` + `Harmony.PatchAll`；`ModHelper.AddModelToPool(poolType, modelType)`。
- 卡牌：`CardModel(int cost, CardType, CardRarity, TargetType, bool)` / `OnPlay(PlayerChoiceContext, CardPlay)` / `OnUpgrade` / `CanPlay` / `TryManualPlay` / `PortraitPath`。
- 能力：`PowerModel.Type`、`StackType`、`Amount`、`BeforeApplied/AfterApplied/AfterRemoved`。
- 命令：`DamageCmd.Attack(x).FromCard(this).Targeting(play.Target).WithHitFx(...).Execute(ctx)`；`CreatureCmd.GainBlock(...)`；`PowerCmd.Apply<T>(...)`；`CardPileCmd.Draw(...)`；`CardSelectCmd.FromHand/FromCombatPile(...)`；`CardCmd.Transform/Exhaust/Afflict`；`PlayerCmd.GainEnergy`。
- 伤害语义：`ValueProp.Move`（攻击）/ `Unpowered`（非攻击可格挡）/ `Unblockable`（HP loss）；`DamageProps.*` 组合常量。
- 钩子：`AbstractModel` 193 个，常用 `AfterCardPlayed`、`AfterDamageReceived`、`AfterHandDraw`/`AfterCardDrawn`、`BeforeSideTurnStart`、`ShouldClearBlock`、`ModifyDamageAdditive`、`ModifyCardPlayCount`、`TryModifyEnergyCostInCombat`、`ShouldDie`、`ShouldAllowHitting`。
- 敌人：`MonsterModel.PerformMove` / `SetMoveImmediate` / `RollMove` / `MoveStateMachine`。
- 资源：`res://` + `NCreatureVisuals`（`Visuals/Bounds/IntentPos/CenterPos`）；卡图路径即 `CardModel.PortraitPath`。
- 本地化：`localization/<lang>/cards.json|powers.json|relics.json|characters.json|card_keywords.json|static_hover_tips.json|ancients.json`。

## 附录 B：调研产出索引

| 文件 | 内容 |
|---|---|
| [`sts2-mod-research/platform.md`](sts2-mod-research/platform.md) | 官方加载器/manifest/入口/API/命令/资源/构建链/框架兼容/未验证项 |
| [`sts2-mod-research/sts2-v0.107.1-api.json`](sts2-mod-research/sts2-v0.107.1-api.json) | 本机 `sts2.dll` 机读 API 快照（模型/枚举/命令/Modding 命名空间） |
| [`sts2-mod-research/content.md`](sts2-mod-research/content.md) | 89 卡矩阵、18 类机制规格、卡表 diff、StS2 映射、55 条边界、8 个待裁决 |
| [`sts2-mod-research/content-cards.json`](sts2-mod-research/content-cards.json) | 89 卡机器矩阵（生成器输入） |
| [`sts2-mod-research/assets.md`](sts2-mod-research/assets.md) | 资产清单、卡图管线、动画/VFX/音频/UI 槽位、接入清单、缺口、v6 进度 |
| [`sts2-mod-research/asset-manifest.json`](sts2-mod-research/asset-manifest.json) | 26 序列/40 特效/54 cue/89 卡逐项路径·尺寸·SHA |

## 附录 C：术语

- **雷势（thunder momentum）**：本战累加的角色独立数值，每点使每段雷伤 +1；不吃力量加成链。
- **雷伤**：非攻击、可格挡、不吃力量/易伤/虚弱、按批次计 1 次的卡牌伤害。
- **领域**：战斗内状态，提供攻击附雷、对敌有利效果压制、抽牌净化；按"下一次起手抽牌后"扣轮。
- **迎战**：令目标立即执行本轮尚余意图；每敌每轮一次机会。
- **兽化**：把手牌攻击→裂骨之爪、其他→风暴之躯，继承升级/临时减费，形态牌消耗，战后原牌不变。
- **POC 门**：原型验证点，不通过则按预案降级，不进入全量实现。
