# 沃利贝尔战斗动作与特效扩充

日期：2026-11-18。目标环境：StS2 PBE **0.113.0 / 16ac0fe3**、BaseLib **3.4.8**、Godot **4.5.1 stable Mono**、.NET SDK **9.0.320**。

## 交付范围

本轮围绕战斗中的动作身份、逐段命中、目标适配和机制联动实施，覆盖全部 **89 张卡牌**的显式表现配置。新增 **14 组骨骼动作、358 帧**，与原有 26 组 / 940 帧合计 **40 组 / 1298 帧**；另新增 **29 类原生 Godot 几何／粒子表现**，与既有 atlas 特效共同使用。

89 张牌各有配置，并不代表 89 组互不复用的身体动作。轻击、连击、重击、雷法、防御、能力部署和兽化分别使用适合的动作，再以命中轨迹、节奏、目标和实际机制回执区分。原版参考证据与版本边界见 [参考审查](COMBAT_PRESENTATION_REFERENCE_2026-11-18.md)。

角色绘制部件沿用既有 `skeletal_v9`。新增图集来自真实肩、肘、腕、头、躯干和腿部 IK 关键帧，不是把同一普通攻击复制并改名。制作和资源校验见 [动作资源说明](../assets/animation/animations/combat/README.md)。本轮没有调整伤害、费用、攻击次数、选敌、联动规则或 U21 裁决；现有音频选择与播放包继续沿用。

## 修复导致“总是普通打击”的接入问题

### 原生通用触发覆盖专属动作

卡牌开始时选择的专属动作，可能被后续原生 `Attack` 通过 BaseLib 再次切回普通攻击。本轮在 `NCreature.SetAnimationTrigger` 的表现边界，仅为正在执行本角色卡牌的通用 `Attack` / `Cast` 保留当前专属动作。前缀排在 BaseLib 之前；恢复方法拒绝接管时仍走原生路径。原有 `CreatureCmd.TriggerAnim` 的 Task、等待和战斗结算继续执行，受伤、死亡、其他角色与其他 trigger 继续由原生处理。

每个真实 `CardPlay` 拥有独立视觉序列 ID，普通攻击与主动雷还区分序列分支，避免混合牌的两种第 0 段互相抑制。嵌套牌完成后可恢复外层；重演有独立段号和短余像，不重新执行完整付费出牌的长起手。第四、第五等超过图集接触帧数量的真实攻击，只在新的原生段触发到来时复用短起手；重复或旧段号不能倒播。

### 命中特效从“整组结束”移到真实逐段完成

旧的 `CreatureAttacked` 历史事件可能到全部多段攻击结束才到达。现在直接观察已有普通攻击管线的单段 native damage 完成点，先显示真实结果，再让领域与普通段联动继续原来的顺序。所有结果保持实际接收者，按 `DamageResult` 对象身份与历史兜底去重，群体攻击每个接收者各有落点，同一段保留一次接触声音。

这里不根据 `Unpowered` 等标记猜测普通攻击，也不按卡面文字自行定时生成段数。异常、取消和结算顺序都由原来的原生 Task 决定，表现观察者异常不会改变结算。

### 主动雷与机制追雷分开

雷批次携带只用于表现的来源：卡牌、领域、导雷、雷池、反击或其他被动。同一源卡附带的领域雷不会消耗该牌的主动施法段号，也不会抢身体的主动作。纯雷可能不发送原生 `Cast`；这类卡牌由真实完成的主动雷批次恢复对应短施法，保护首批已有进度，并保留当前受伤反应。新完成回执与旧雷订阅按真实 batch ID 去重。

最后一击可能先令战斗进入 `IsEnding`，才返回伤害结果。现有房间允许已经完成的命中显示有限期尾效；终战暂停只停止持续领域／循环音轨，保留一次性尾效自然结束。死亡、战斗正式停止和离开房间仍清理全部资源，不会重开循环或再次播放旧结果。

## 新动作与可辨认的用途

| 动作 | 轮廓与节奏 | 代表卡牌 |
| --- | --- | --- |
| `backhand` | 收肘、反手横掠 | B03、C08、U27 |
| `double_claw` | 近爪与远爪两次独立挥击 | C02、T01 |
| `claw_flurry` | 三段交替挥爪，连续段短回弹 | C05、C06、U06、R08 |
| `sweep` | 压低重心的大弧横扫 | C09 |
| `uppercut` | 屈膝蓄势后向上挑击 | C04、U41 |
| `lunge` | 低身前踏，肩爪向前送出 | B04、C01、C07、U20、U38 |
| `ground_slam` | 双臂举起砸下，身体承重下沉 | C03、C22、U05 |
| `stomp_chain` | 左右提膝落踏，适配更多实际段 | U07、U31 |
| `bite_rend` | 张口前探，接第二次向后撕扯 | U08、U24 |
| `thunder_call` | 单臂举起唤雷 | C24、U12、U29、U32、U35、U39、R23 |
| `chain_channel` | 两掌交替导引雷弧 | C25、U02、U11、U21、U36、U40、R17、R24 |
| `storm_channel` | 双臂展开，风暴释放时咆哮下压 | U19、U37、R01、R07、R18、R25 |
| `iron_guard` | 交臂护胸，沉重心支撑 | C11、C12、U03、R02、R05、T02 等 |
| `primal_charge` | 收爪蓄势后展开胸部 | C17、C19、U10、U13、R06 等 |

原有普通攻击、格挡、迎战反击、咆哮、兽化、跃击、领域、低血量、受伤和死亡动作继续参与配置。领域下的新动作配合独立地环和雷效，不再被通用“进入领域”动作覆盖掉卡牌身份。

## 特效和联动

| 场景 | 实际表现依据 | 新的可视区别 |
| --- | --- | --- |
| 双爪／连爪 | 每个已完成普通攻击段 | 交叉爪痕、交替方向、独立接触位置 |
| 踏地／重砸 | 每个实际接收者与段号 | 地面碎片、落点环、下砸冲击，与横向斩击区分 |
| U08 撕咬 | 同一真实 play 的第 1、2 个普通段 | 首口为咬合，后续段为撕裂；重演从首口重新计数 |
| 雷矛／导雷／风暴 | 卡牌自己的已完成雷批次 | 定向雷矛、曲折导雷、范围风暴、垂直爆雷 |
| 领域附雷 | `Domain` 来源批次 | 目标脚下的领域余波，独立于主攻击动作 |
| U02 狂雷渐起 | `Conduction` 来源批次 | 追雷链条，主攻击完成后另有轨迹 |
| R18 雷池 | `Pool` 来源批次 | 贴地雷效，与头顶落雷区分 |
| 反击雷 | `Counter` 来源批次 | 反击轨迹；保留现有声音，避免双份完整命中效果 |
| 雷甲／实际格挡 | 正的格挡回执及雷甲回执 | 胸前护甲、受击屏障；快速连续触发复用短效，避免遮头 |
| 兽化 | 实际转换批次完成 | 兽化轮廓与既有卡牌转换连线 |
| 吸血／迎战吸收 | 实际恢复／正吸收结果 | 回流粒子与吸收脉冲，不为零收益伪造反馈 |
| 重演／净化 | 真实重演开始／可见净化卡牌回执 | 短余像、净化火花，沿真实卡牌或角色锚点显示 |

29 类新样式：`claw`、`cross_claw`、`rake`、`sweep`、`uppercut`、`lunge`、`slam`、`stomp`、`bite`、`bite_tear`、`feral_claw`、`bolt`、`chain`、`spear`、`storm`、`ground_thunder`、`fork`、`eruption`、`guard`、`armor`、`retaliation`、`domain_echo`、`storm_charge`、`thunder_armor`、`replay_echo`、`lifesteal`、`beast`、`absorb`、`purify`。

### 不同敌人的适配

效果读取实际目标视觉节点的 `Bounds` 和 `CenterPos`，区分小型、大型、浮空、镜像、非均匀缩放和移动目标。群体攻击跟随各自实际命中目标；格挡结果改变冲击反馈；目标被释放时结束依附。没有给原版敌人替换动作资源，也没有按敌人名称推测结算机制。

每个角色自己的特效控制器保持独立。新旧视觉共用 64 个实例上限；被动护甲、余波等密集触发会刷新短效，真实物理和雷击接触仍各段独立。颜色变化和路径扰动不读取游戏 RNG，不加入玩法等待。

## 验证状态

**已完成：**

- `tests.test_assets`、`tests.test_asset_pack_cache`、`tests.test_combat_motion_assets`、`tests.test_combat_vfx_behavior`、`tests.test_combat_presentation`、`tests.test_lightning_responses`、`tests.test_presentation_bridge_behavior`：**73 个测试通过**（57.659 秒）。
- 其中新 C# 行为组 **16 项**、原有表现回归 **11 项**；旧 fixture 已按当前本地化注册／语言资源修复失修接口，保留低血量、重演、多人与 mutation 回归断言。
- 新 C# 行为组直接编译 production catalog、combat bridge 和精确投影的已有普通段管线方法；覆盖 89 卡集合、逐段／历史去重、U08 重演、AOE、源快照、被动来源、Attack/Cast 接管与拒绝、嵌套／旧 play、终战尾效、原异常／取消语义。原生场景对象为明确的测试替身，不是游戏 ABI 或实机通过证明。
- Godot 4.5.1 真实 VFX：29 类样式，初轮 **94 个行为检查**、含真实像素渲染版本 **166 个检查**。涵盖坐标、追踪、格挡、释放、实例上限、双主人隔离、被动短效合并与终战循环清理。最终 PCK 加入退出清理断言后，**98 项检查连续两次通过**，无退出资源错误。
- 最终检查还补上原生 `hurt` / `Hurt` / `hit` / `Hit` / `domain_hurt` 全部已有别名的受伤优先级；16 个新 SDK 场景再次通过。预览工具以弱引用确认停止音轨确已释放，避免 headless 过快退出早于 AudioServer 回收，超时与错误仍判失败。
- Godot 真实动作播放：14 组 / 358 帧资源，接触推进、受伤恢复、死亡优先级、第四／第五段、嵌套序列和重复抑制；固定 1440×1080 预览的 32 帧标题与 14 个标签区域逐帧保持完整。
- 6 场角色＋特效资源组合预览：60 帧、38 次演示效果。画面明确标注为资源回放；演示事件顺序不充当原生结算时序证明。
- 最终资源 PCK 的 staging、导入、导出、pack compatibility、资源加载、既有特效及音频 profile 检查全部通过；open 音频包 251,481,244 字节，冷构建 121.330 秒。这是资源包验证，不是生产 DLL 编译或可安装版验收。

最终检查的生产 `actor.gd` SHA256 为 `55ff894b90b59364a457f76de41f23cfb28f173c445997ff74e84a321a81eb4c`，与最终打包 staging 完全一致。最终 PCK SHA256 为 `9e6f5e4d2ef81b49e1ef3312918281ad607ea64cb12ba6bf2b0c071320ee5d4d`。PCK 为本地构建产物，不提交到源码仓库。

**全仓库回归边界：**上面的 73 项是与本轮相关的指定套件，不是全仓库全绿。额外检查旧 `test_persistent_cards.py` 时，卡面解析仍期待已迁移掉的内联 `CardLoc`，出现 36 个子用例错误；在未修改的 `bb06bb1329d664fc4da69ccc6302a0196eafa461` 精确快照上重跑，同样为 10 项／36 个错误。本轮没有改动这些无关卡面断言，也没有将其记作通过。

### 合入 #4 后的本地集成

本地动画分支已接入 #4 的普通攻击完成回调。每段在原生或其他模组包装的伤害任务成功返回后显示命中，再结算领域与其他响应。战斗身份在调用伤害前捕获，等待期间换场会丢弃旧战斗的显示请求。

草稿包含 2 张 PNG 与全部 14 组关键帧和元数据。本地使用草稿的绘制脚本重建其余 12 张图集。重建后的姿态、锚点、接触帧、帧数与逐帧边界均与草稿记录一致，像素散列随本次渲染重新记录。

使用 StS2 PBE 0.113.1（d09d48e5）和 BaseLib 3.4.8 编译生产 DLL 成功。79 项动作、特效、雷电、资源打包和伤害回调兼容性相关测试通过。Godot 播放了 14 组新动作；本地 Riot PCK 通过资源与音频检查，并从包中渲染了 6 个动作与特效组合，共 60 帧、38 次效果。游戏内打牌时序、真实联机和存读档后的表现仍待实机验收。

### 可重跑的独立验证

```sh
VOLIBEAR_DOTNET=/path/to/dotnet VOLIBEAR_GODOT=/path/to/godot \
  python -m unittest tests.test_assets tests.test_asset_pack_cache \
  tests.test_combat_motion_assets tests.test_combat_vfx_behavior \
  tests.test_combat_presentation tests.test_lightning_responses \
  tests.test_presentation_bridge_behavior -v

python tools/build_assets.py --godot /path/to/Godot-4.5.1-mono
python tools/preview_combat_vfx.py --godot /path/to/Godot-4.5.1-mono \
  --pack .local/packs/Volibear.pck --headless --output .local/combat-vfx-packed
python tools/preview_combat_motions.py --godot /path/to/Godot-4.5.1-mono \
  --dotnet /path/to/dotnet --display :93 --output .local/combat-motion-godot
DISPLAY=:93 python tools/preview_combat_combos.py --godot /path/to/Godot-4.5.1-mono \
  --pack .local/packs/Volibear.pck --output .local/combat-combo-packed
```

真实渲染需有效的 X11 显示（Windows 可按脚本说明使用本机 Godot）；headless 只验证行为，不提供像素验收。

### 安装游戏环境后必须补的验收

先按 [PBE 通道说明](PBE_CHANNEL.md) 的同版程序集编译生产与开发探针，隔离部署当前 DLL、PCK、依赖与清单。`tools/build_pbe_release.py` 是当前玩家包构建入口；只构建 PCK 不能成为可安装更新包。

现有启动／API／内容入口：

```sh
VOLIBEAR_GAME_VERSION=v0.113.0 VOLIBEAR_GAME_COMMIT=16ac0fe3 \
  python tools/pbe_verify.py --only baseline --only api --only content
```

旧验收矩阵不自动代表本轮所有新动作已实际观看。还需要用当前游戏录像检查以下具体组合：

| 实机组合 | 必须观察到 |
| --- | --- |
| C02 与 C05/C06 | 双爪与快速交替爪不同，效果逐段到达，不在末尾同时爆出 |
| U07 升级／额外攻击段 | 第四、第五个实际段仍有短踏，无定时器产生多余命中 |
| U08 首次、已咬痕、重演 | 首口／撕裂分明；重演回到第 0 段；一次回执不重复 |
| C03、C09、C04 | 下砸、横扫、上挑方向明显不同 |
| C24、U37、U40、R17、R07 | 唤雷、风暴、导雷、雷矛、群体爆雷有可见区别 |
| C05 + 领域 + U02 + 雷甲 | 主爪、领域余波、追雷、胸前雷甲并存，身体主动作不中断 |
| 迎战过程中受伤，再由外层牌攻击 | 先保留真实受伤反应，下一真实攻击段恢复外层动作 |
| 嵌套出牌、普通攻击重演、雷法重演 | 序列归属正确，通用 Attack/Cast 不覆盖成普通打击 |
| 小／大／浮空敌人，镜像和群体目标 | 落点贴各自视觉边界，非固定屏幕坐标 |
| 最后一击击杀、敌人复活、离开房间 | 接触尾效可见；持续环停止；不重放旧结果、不残留循环 |
| 两名沃利贝尔 | 命中、卡牌锚点和循环归属各自角色 |

## 全部 89 张卡牌配置

下表从 `CombatPresentationCatalog.cs` 的实际条目整理；卡名／类别来自既有 `cards_s2.json`。`普通命中`、`主动雷` 是该来源真实产生对应回执时使用的样式，**不是给无伤害技能添加攻击**。联动列仅在实际能力部署、格挡等相应事件发生时使用；其他特定机制由上面的语义回执决定。领域变体为空表示保留该专属身体动作，领域气氛由独立层显示。

| 卡牌 | 类别 | 身体动作 | 普通命中 | 主动雷 | 部署／格挡联动 | 领域身体变体 |
| --- | --- | --- | --- | --- | --- | --- |
| B01 打击 | 攻击 | `attack` | `claw` | `bolt` | — | `domain_attack` |
| B02 防御 | 技能 | `block` | `claw` | `bolt` | `guard` | `domain_block` |
| B03 霆爪 | 攻击 | `backhand` | `cross_claw` | `fork` | — | — |
| B04 挺身迎战 | 攻击 | `lunge` | `lunge` | `bolt` | `guard` | — |
| C01 逼近 | 攻击 | `lunge` | `lunge` | `bolt` | — | — |
| C02 双爪 | 攻击 | `double_claw` | `cross_claw` | `bolt` | — | — |
| C03 轰雷重击 | 攻击 | `ground_slam` | `slam` | `ground_thunder` | — | — |
| C04 擂首一击 | 攻击 | `uppercut` | `uppercut` | `bolt` | — | — |
| C05 雷霆爪击 | 攻击 | `claw_flurry` | `cross_claw` | `fork` | — | — |
| C06 狂乱挥击 | 攻击 | `claw_flurry` | `rake` | `bolt` | — | — |
| C07 追嗅 | 攻击 | `lunge` | `lunge` | `bolt` | — | — |
| C08 撕开伤口 | 攻击 | `backhand` | `rake` | `bolt` | — | — |
| C09 雷霆横扫 | 攻击 | `sweep` | `sweep` | `fork` | — | — |
| C10 以牙还牙 | 攻击 | `counter` | `uppercut` | `bolt` | `guard` | — |
| C11 正面迎敌 | 技能 | `iron_guard` | `claw` | `bolt` | `guard` | — |
| C12 厚重皮毛 | 技能 | `iron_guard` | `claw` | `bolt` | `armor` | — |
| C13 呼吸 | 技能 | `relaxed_loop` | `claw` | `bolt` | — | — |
| C14 雷霆护身 | 技能 | `iron_guard` | `claw` | `chain` | `thunder_armor` | — |
| C15 重整爪牙 | 技能 | `cast` | `claw` | `bolt` | — | `domain_cast` |
| C17 蓄力 | 技能 | `primal_charge` | `claw` | `bolt` | `storm_charge` | — |
| C18 显圣 | 技能 | `roar` | `claw` | `storm` | — | `domain_roar` |
| C19 追猎准备 | 技能 | `primal_charge` | `claw` | `bolt` | — | — |
| C20 乘势追击 | 攻击 | `backhand` | `claw` | `bolt` | — | — |
| C21 稳住阵脚 | 技能 | `iron_guard` | `claw` | `bolt` | `guard` | — |
| C22 雷震 | 攻击 | `ground_slam` | `slam` | `ground_thunder` | — | — |
| C24 霹雳 | 技能 | `thunder_call` | `claw` | `fork` | — | — |
| C25 雷引 | 技能 | `chain_channel` | `claw` | `chain` | `storm_charge` | — |
| C26 接地 | 技能 | `primal_charge` | `claw` | `ground_thunder` | — | — |
| U02 狂雷渐起 | 能力 | `chain_channel` | `claw` | `chain` | `storm_charge` | — |
| U03 屹立 | 能力 | `iron_guard` | `claw` | `bolt` | `armor` | — |
| U04 战痕 | 能力 | `iron_guard` | `claw` | `bolt` | `armor` | — |
| U05 挟山 | 攻击 | `ground_slam` | `slam` | `bolt` | — | — |
| U06 三重撕裂 | 攻击 | `claw_flurry` | `rake` | `bolt` | — | — |
| U07 崩山 | 攻击 | `stomp_chain` | `stomp` | `ground_thunder` | — | — |
| U08 暴怒撕咬 | 攻击 | `bite_rend` | `bite` | `bolt` | — | — |
| U10 磨砺爪牙 | 技能 | `primal_charge` | `claw` | `bolt` | — | — |
| U11 暴风再临 | 技能 | `chain_channel` | `claw` | `chain` | `replay_echo` | — |
| U12 原始力量 | 技能 | `thunder_call` | `claw` | `fork` | `storm_charge` | — |
| U13 力量归身 | 技能 | `primal_charge` | `claw` | `bolt` | `storm_charge` | — |
| U14 迎战准备 | 技能 | `iron_guard` | `claw` | `bolt` | `guard` | — |
| U15 暴风换气 | 技能 | `relaxed_loop` | `claw` | `bolt` | — | — |
| U17 古老直觉 | 技能 | `relaxed_loop` | `claw` | `bolt` | — | — |
| U19 风暴不散 | 能力 | `storm_channel` | `claw` | `storm` | `domain_echo` | — |
| U20 势不可挡 | 攻击 | `lunge` | `lunge` | `bolt` | — | — |
| U21 雷霆余威 | 能力 | `chain_channel` | `claw` | `chain` | `storm_charge` | — |
| U23 迎风咆哮 | 技能 | `roar` | `claw` | `storm` | — | `domain_roar` |
| U24 饮血而战 | 攻击 | `bite_rend` | `bite_tear` | `spear` | — | — |
| U25 猎物未倒 | 能力 | `primal_charge` | `claw` | `bolt` | — | — |
| U26 愈战愈烈 | 能力 | `primal_charge` | `claw` | `bolt` | `storm_charge` | — |
| U27 淬躯爪击 | 攻击 | `backhand` | `cross_claw` | `bolt` | — | — |
| U28 雷霆反扑 | 技能 | `counter` | `uppercut` | `chain` | `guard` | — |
| U29 雷霆渐盛 | 能力 | `thunder_call` | `claw` | `fork` | `storm_charge` | — |
| U31 万钧连踏 | 攻击 | `stomp_chain` | `stomp` | `ground_thunder` | — | — |
| U32 迎雷 | 能力 | `thunder_call` | `claw` | `fork` | `domain_echo` | — |
| U34 雷甲 | 能力 | `iron_guard` | `claw` | `bolt` | `thunder_armor` | — |
| U35 霹天雳地 | 技能 | `thunder_call` | `claw` | `fork` | — | — |
| U36 奔雷 | 技能 | `chain_channel` | `claw` | `chain` | — | — |
| U37 风暴汇聚 | 技能 | `storm_channel` | `claw` | `storm` | — | — |
| U38 雷势奔袭 | 攻击 | `lunge` | `lunge` | `chain` | — | — |
| U39 雷暴先兆 | 技能 | `thunder_call` | `claw` | `fork` | `guard` | — |
| U40 雷路贯通 | 技能 | `chain_channel` | `claw` | `chain` | — | — |
| U41 破皮见骨 | 攻击 | `uppercut` | `feral_claw` | `bolt` | — | — |
| U42 蛮荒护体 | 技能 | `iron_guard` | `claw` | `bolt` | `armor` | — |
| U43 循着本能 | 技能 | `feral_enter` | `feral_claw` | `bolt` | — | — |
| R01 风暴形态 | 能力 | `storm_channel` | `claw` | `storm` | `domain_echo` | — |
| R02 不动神躯 | 能力 | `iron_guard` | `claw` | `bolt` | `armor` | — |
| R05 全身之力 | 技能 | `iron_guard` | `claw` | `bolt` | `armor` | — |
| R06 天人合一 | 技能 | `primal_charge` | `claw` | `bolt` | `storm_charge` | — |
| R07 天崩地裂 | 技能 | `storm_channel` | `claw` | `eruption` | — | — |
| R08 雷霆万钧 | 攻击 | `claw_flurry` | `cross_claw` | `fork` | — | — |
| R09 众敌皆来 | 技能 | `counter` | `uppercut` | `storm` | `guard` | — |
| R10 这场战斗尚未结束 | 技能 | `cast` | `claw` | `bolt` | — | `domain_cast` |
| R12 解放本能 | 技能 | `feral_enter` | `feral_claw` | `bolt` | — | — |
| R13 重返蛮荒 | 技能 | `primal_charge` | `claw` | `storm` | — | — |
| R14 不休之猎 | 能力 | `primal_charge` | `claw` | `bolt` | — | — |
| R16 愈战神躯 | 能力 | `primal_charge` | `claw` | `bolt` | `storm_charge` | — |
| R17 天雷决 | 技能 | `chain_channel` | `claw` | `spear` | — | — |
| R18 雷池 | 能力 | `storm_channel` | `claw` | `ground_thunder` | `domain_echo` | — |
| R21 雷霆化身 | 技能 | `iron_guard` | `claw` | `bolt` | `thunder_armor` | — |
| R23 裂天 | 技能 | `thunder_call` | `claw` | `eruption` | — | — |
| R24 雷涌 | 技能 | `chain_channel` | `claw` | `chain` | — | — |
| R25 风暴重临 | 技能 | `storm_channel` | `claw` | `storm` | `domain_echo` | — |
| R27 旧日重临 | 技能 | `feral_enter` | `feral_claw` | `bolt` | — | — |
| R28 熊灵侵染 | 能力 | `feral_enter` | `feral_claw` | `bolt` | — | — |
| R29 不再为人 | 技能 | `feral_enter` | `feral_claw` | `bolt` | — | — |
| R30 我即荒野 | 能力 | `feral_enter` | `feral_claw` | `bolt` | — | — |
| R31 天声震落 | 攻击 | `storm_leap` | `slam` | `eruption` | — | `domain_storm_leap` |
| T01 裂骨之爪 | 攻击 | `double_claw` | `feral_claw` | `bolt` | — | — |
| T02 风暴之躯 | 技能 | `iron_guard` | `claw` | `ground_thunder` | `thunder_armor` | — |

U08 的第二及后续实际普通段使用 `bite_tear`；重演拥有新段号。上表只描述表现，不改变基础／升级牌面的任何数值。
