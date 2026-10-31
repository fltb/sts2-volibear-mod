# STS2 角色动画研究与本项目动作设计

> 历史动画研究（V3）：本文保留当时的观察与来源，下文 references/、diagnostics/ 是研究工作目录，不表示全部历史下载物随包交付。实际精选的 Riot Q/W/E/R 视频、Mega Crit Silent GIF 及联系表位于参考仓库 motion_examples/。当前自产动画、有效分层和检查材料以动画仓库的 animations/README.md、animations/manifest.json、reports/DELIVERY_V5.md 及 reports/animation_revision_v5/ 为准；V3/V4 报告仅作历史对照，不能继续作为当前批准。

研究日期：2026-10-27（本会话客户端日期）。本文把「可下载的网页导出物」「观察到的游戏代码状态图」「模组框架真实接口」「本项目主动增加的动作」分开记录。它们不能互相替代。

本项目交付的是自己绘制并制作的透明逐帧动画。研究参考视频、原版诊断图与自己的运行素材必须放在不同目录。本文不把下载的原版动画视为自己制作的交付资产。

## 1. 可以确定的技术结论

1. STS2 的标准角色动画触发名是 `Idle / Attack / Cast / Hit / Dead / Relaxed`，而素材片段名通常是 `idle_loop / attack / cast / hurt / die / relaxed_loop`。注意大小写与 `Hit→hurt`、`Dead→die` 的区别。RitsuLib 维护者的 `ModAnimStateMachines` 源码直接保留这套映射。[RITSU_STANDARD]
2. 当前检查过的五角色动画图都包含以上六类行为，但亡灵契约师的 `Cast` 指向 `cast_mighty`，其较小的 `cast` 由 `summonTrigger` 触发。不能按目录文件名给所有角色硬套同一张映射表。[GAME_CODE_SNAPSHOT]
3. 没有找到「五角色统一在某个生命百分比自动进入低血动画」的证据。网页目录有铁甲战士 `weak_loop`、亡灵契约师 `nervous_loop`，但此次检查的角色状态图没有注册它们。文件存在不等于其在战斗中自动触发，更不能推定一个百分比阈值。项目的 `weak_loop` 明确归类为扩展动作。
4. 真实原生骨骼与网页导出动画是两类东西。原生代码通过 `MegaSprite` / `SpineSprite` 驱动骨骼；公开图片接口返回的是渲染后的 WebP。此次公开接口检索没有提供可核验的五角色完整 `.skel + .atlas + 贴图页`、骨骼列表、完整 skin 或约束数据。不能声称这些已包含在包中。Spine 官方文档说明这些源数据用于其运行时；其版本必须与运行时匹配，不能根据图片尺寸猜出游戏使用的精确 Spine 版本。[SPINE_GODOT]
5. 使用透明 PNG 序列是可落地的路径。RitsuLib 源码包含 `AnimatedSprite2DBackend`、`GodotAnimationPlayerBackend` 和 `CueAnimationBackend`。前者真实读取 Godot 的 `SpriteFrames`，并报告播放完成。因此当时版本生成的 PNG 序列可以接入，而不必宣称自己已经制作了 Spine 骨骼。[RITSU_SPRITE_BACKEND]

## 2. 五角色原生动作核查

图片目录标签为 **Main v0.107.1**。这是本次 API 返回的快照标签，不代表用户所安装版本，也不代表「当前最新版」。代码依据为公开的游戏代码提取仓库 commit `04cfe6df800156e5339d565e03236302363c829c`。该代码的原始游戏构建版本未独立匹配到图片接口，因此以下结论的范围是「此次可见状态图与素材目录」。它不是 Mega Crit 发布的正式接口规范。

| 角色 | 标准六类的素材 | 额外片段与可核验映射 | 不应作出的推断 |
|---|---|---|---|
| Ironclad | `idle_loop, attack, cast, hurt, die, relaxed_loop` | `heavyAttack→attack_heavy`；目录另有 `weak_loop` | `weak_loop` 未出现在所查 `GenerateAnimator` 中，不能断言自动低血触发 |
| Silent | 同上 | `Shiv→shiv` | `Shiv` 是此角色的专有触发，不是所有角色必须提供 |
| Defect | 从 `CharacterModel` 继承标准图 | 目录另有 `process`；本次图中没有对应分支 | 不能凭名把 `process` 解释成施法、低血或自动循环 |
| Necrobinder | `Idle→idle_loop; Attack→attack; Cast→cast_mighty; Hit→hurt; Dead→die; Relaxed→relaxed_loop` | `summonTrigger→cast`；目录另有 `nervous_loop` | 不应把 `cast` 与 `cast_mighty` 交换；`nervous_loop` 触发未证实 |
| Regent | 标准六类 | `sovereignBladeTrigger→attack_sovereign` | 王剑专有动作不是普遍接口要求 |

亡灵目录还列出 `_ignore-animation`、`_ignore-attack_w_settle`、`_ignore-extra_assets_pose`、`_ignore-sleeve_rigging_pose`。这些不进入本项目制作清单，也不当成正式动作需求。

### 触发与收尾

游戏代码快照里的 `CreatureCmd.TriggerAnim(Creature, string triggerName, float waitTime)` 最终调用角色节点的 `SetAnimationTrigger`。攻击、施法由相应卡牌或战斗命令显式选择；提供一个名叫 `cast.png` 的文件不会自动注册施法行为。其 `waitTime` 是结算节奏的一部分，应与本项目动作接触时刻对齐。

伤害处理里检查到：当该分支的 `damage > 0`，受伤者不是伤害来源，并且没有 `ValueProp.SkipHurtAnim` 时，加入 `Hit` 动画请求。这足以说明存在显式条件，不足以把它简化为「每一次扣血都一定播放」或「格挡时必播」。

`NCreature.StartDeathAnim` 请求 `Dead`，并取得动画时长参与后续处理。原生图与 RitsuLib 标准图的死亡状态不设置自动返回 idle。**死亡片段不能播放完就站起来，也不能循环倒地。** RitsuLib 对非 Spine 死亡、等待和复活另有适配补丁；接入仍需要在目标游戏构建验证。

## 3. 下载和实看得到的重要限制

### 官方可用的早期动画参考

Mega Crit 在 [2024-10-02 开发日志](https://www.megacrit.com/news/2024-10-02-neowsletter-issue-3/) 直接展示 [Silent 动画 GIF](https://www.megacrit.com/images/silent_anim.gif)。本次已下载并实看 16 格抽帧联系表：600×495、121 帧、2.42 秒。保存在 `references/megacrit_silent_2024_preview.gif` 与 `references/megacrit_silent_2024_contact.jpg`。

画面清楚展示受击回撤、待机、前伸攻击和恢复。躯干带动动作，披风展开成大而清楚的形，辫子与布料随后跟进；头部骷髅轮廓一直可辨。重心通过腿部支撑和身体倾斜改变，主体没有拆散成漂浮部件。这是可用的动作语言参考，尤其适合检查「身体先行、衣物后随、短促动作后恢复稳定姿态」。它带有场景与伤害数字，不是透明运行素材。

**该 GIF 是 2024 年早期官方展示，不能冒充当前版本的完整动作、精确节奏或五角色动画规范。** 本包用它补足可靠的实际动作观察，用维护者框架源码核查接入接口，两者职责不同。

### 网页导出物的诊断

Spire Codex 维护者文档说明，它的渲染器把 Spine 动画转换为 WebP、GIF 或 APNG。[SPIRE_CODEX] 此次下载了 10 个小样并逐帧检查，元数据在 `diagnostics/sts2_export_diagnostics.json`。

| 导出小样 | 实际帧数 | 此导出文件总时长 | 实看判断 |
|---|---:|---:|---|
| ironclad_attack | 10 | 1.25 s | 部分帧出现手臂独立漂到躯干外，不能作完整动作范本 |
| ironclad_attack_heavy | 8 | 1.60 s | 同类异常；不复制这种肢体关系 |
| ironclad_cast | 12 | 1.65 s | 躯干接近静止、局部能量变化；不据此推导原生骨骼动作 |
| ironclad_die | 7 | 2.40 s | 部件消失、分离的异常导出；不能作死亡动作范本 |
| silent_shiv | 6 | 0.80 s | 披风、部件分离的异常导出；不能作掷匕首运动范本 |
| necrobinder_cast_mighty | 35 | 1.75 s | 能看到镰刀蓝色能量层变化，未验证完整骨骼运动 |
| ironclad_idle_loop / hurt / weak_loop | 各 1 | 无动态时长 | 单帧静图，不构成可播放动作 |
| beta ironclad_demon_form | 1 | 无动态时长 | 形态静态参考，不是变身动画 |

这些时长描述的是收到的网页文件，不是原生动作时长规格。异常原因仅标记为「导出或渲染问题疑似」，没有证据定位到哪一级工具；不把它描述为游戏里的正常表现。最终包只需要保留诊断 JSON 与小联系表，不要把异常 WebP 放进生产参考白名单。

实看文件包括 `diagnostics/ironclad_attack_strip.jpg`、`ironclad_attack_heavy_strip.jpg`、`ironclad_cast_strip.jpg`、`ironclad_die_strip.jpg`、`silent_shiv_strip.jpg`、`necrobinder_cast_mighty_strip.jpg`。每张由该 WebP 的实际帧抽取，未重绘内容。

## 4. 形态、卡面动画、领域表现是三层不同资源

API 的 `animations/cards` 目录列出 36 项，即 18 张卡的基础/升级展示：`apotheosis, apparition, biased_cognition, break, brightest_flame, corruption, forbidden_grimoire, maul, meteor_shower, neows_fury, protector, quadcast, relax, suppress, the_sealed_throne, whistle, wish, wraith_form`。它们是动态卡面渲染，不代表角色出这张卡时就有一段同名全身动画。

Beta v0.110.0 的 `characters-forms` 目录列出五种形态静图：`defect_echo_form`、`ironclad_demon_form`、`necrobinder_reaper_form`、`regent_void_form`、`silent_serpent_form`。本次只下载并检验了铁甲恶魔形态，实际是一帧。不能把五张目录项描述为已获得的五套形态动画，更不能推断全部骨骼/皮肤数据。

本项目领域效果建议分为三层，这是项目设计，不是「STS2 强制规范」：

- **身体层**：正常和领域素材使用同一画布、地面基准、朝向和识别特征。领域动作改变毛色、轮廓光与能量，但保持角色身份。
- **场景效果层**：地面领域环、电弧、落雷、冲击波各自播放。不要把覆盖整个战场的特效烘焙进 512×512 身体帧，否则会污染身体的包围盒、遮挡 UI，并使同一效果难以对应不同敌人位置。
- **状态与结算层**：领域进入、保持、退出由本项目状态机驱动。PNG、GIF、atlas JSON 都不会自行施加领域效果、护盾或伤害。

当前 BaseLib 的视觉节点工厂明确包含 `FormVfx` 控件，RitsuLib 则提供 `FormSwitchingAnimationBackend`。它们说明引擎集成有可用扩展点；本包默认选择单个 `AnimatedSprite2D` 播放对应 clip 的实现，避免把可选框架能力误写成已经完成的源骨骼换肤。[BASELIB_FACTORY / RITSU_BUILDER]

## 5. Riot 官方 Volibear 动作参考

只使用 PC《英雄联盟》官方角色页及其嵌入的视频。没有混入 2011 年旧版沃利贝尔，也没有混入《英雄联盟手游》动作。四个 MP4 全部下载成功；保留原视频、16 格等间隔抽帧联系表、来源和 SHA-256，见 `references/manifest.json`。[RIOT_VOLIBEAR]

| 官方视频 | 官方描述对应的动作含义（意译） | 实际抽帧观察 | 本项目可提炼的动作原则 |
|---|---|---|---|
| Q / Thundering Smash | 朝敌人加速，首次攻击造成伤害并眩晕 | 先降低重心、四足式冲近，再立起前身进行下砸；结束后回到稳定站姿 | 重量先向前压，攻击前有蓄势，接触点明确，身体不要只整块平移 |
| W / Frenzied Maul | 对目标施加标记，再次对同一目标使用会增强伤害并治疗 | 近身的前肢/上身扑击；第二次靠近动作伴随头部明显前探；标记保留在目标上 | 抓击与咬击应有可读差别；咬击用头颈前探和下颌闭合，不只画一个发光嘴巴 |
| E / Sky Splitter | 在指定位置召雷，伤害和减速；处于范围内可获得护盾 | 角色先抬前肢，地面圈出现，延迟后垂直闪电落下，随后角色有护盾轮廓 | 将施法姿态、目标范围、雷击接触、护盾维持拆开，延迟要在时间线上可核对 |
| R / Stormbringer | 跃向指定地点，落点伤害/减速并获得生命增益；附近塔暂时失效 | 起跳离地、落下强冲击，随后较大的暗色风暴形态保持；后续仍能攻击 | 起跳准备→离地→落点→余震四段明确；领域形态需要保持状态，而非仅闪一次 |

本项目不照搬 MOBA 的视角、移动距离、塔交互或完整时间长度。把动作的重心、接触次序与体态语言转换成 STS2 固定战场里的侧向角色表演。官方视频中完整场景包含敌人、地形和光效，不能直接裁成可复用透明角色素材。

以上观察基于四张实际查看的联系表：`references/riot_volibear_Q_contact.jpg`、`...W_contact.jpg`、`...E_contact.jpg`、`...R_contact.jpg`。原视频分别为 5.60 s、9.967 s、6.867 s、11.567 s，均 1056×720、30 fps。这些是参考视频参数，不是本项目制作规范。

## 6. 本项目 24 种动作、26 段实际序列的定位

制作包使用 24 fps、512×512 透明 PNG 帧；`manifest.json` 的 `clips` 包含 24 种动作，`variants` 包含 `domain_roar / domain_storm_leap` 两个领域变体，共 26 段实际序列。清单记录真实帧路径、时长、循环、图集和事件。以下是设计与接入要求，动画成品通过实际导出与复查后才标记通过。

| clip | 归属 | 设计重点 | 收尾 |
|---|---|---|---|
| idle_loop | 标准行为 | 呼吸与重心微动；足底不漂，不能全身像纸片一起缩放 | 循环 |
| relaxed_loop | 标准行为 | 肩颈和前肢放松，保持角色重量 | 循环；收到 Idle 恢复战斗站姿 |
| weak_loop | 项目扩展 | 上身略压低、呼吸变沉，仍能识别正在存活 | 循环；项目默认 30% 进入 / 35% 退出，可配置，非原版事实 |
| attack | 标准行为 | 肩、肘、爪有先后，快速接触后恢复重心 | 回当前形态待机 |
| attack_heavy | 项目扩展；原版铁甲有同类专有动作 | 更清楚的蓄势、前肢下砸与后随 | 回当前形态待机 |
| bite | 项目扩展 | 头颈前探，嘴部与目标接触，避免仅摇整张脸 | 回当前形态待机 |
| cast | 标准行为 | 抬爪或引导姿态；身体与外部落雷分层 | 回当前形态待机 |
| hurt | 标准行为 | 短促受力回撤，不能倒向错误侧；不改变朝向 | 回当前形态待机 |
| block | 项目扩展 | 稳定支撑、前肢防御和短促受力 | 回当前形态待机 |
| counter | 项目扩展 | 完整片段先吸收再反弹；C10/U28/R09 已完成迎战时仅播普通第 14–31 帧 | 回当前形态待机；领域回退完整 domain_attack |
| domain_enter | 项目扩展 | 清楚的领域启动体态与能量扩展 | 领域标志已生效后进入 domain_idle |
| domain_idle | 项目扩展 | 同一角色持续风暴形态；能量不遮脸与爪 | 循环 |
| domain_exit | 项目扩展 | 能量收束或消退，主体保持可见 | 清除领域标志后回相应待机 |
| feral_enter | 项目扩展的短动作 | 重心降低、前爪展开，体态可读；卡表兽化只转换手牌，不建立角色永久 buff | 默认一次结束即回实际领域/低血/普通待机 |
| feral_idle | 可选短时展示 | 低伏、紧绷、有限呼吸；只在非领域且非低血时短暂使用 | 必须带 TTL 或显式结束；helper 默认及上限均为 0.5 s（最多 12 帧） |
| die | 标准行为 | 重心确实失去支撑、倒下；不能只是透明度降低 | 非循环、保持终帧 |
| domain_attack | 项目扩展，接标准 Attack | 身份与动作同正常版，领域外形持续 | 回 domain_idle |
| domain_cast | 项目扩展，接标准 Cast | 强调施法姿态与电光，主体仍清楚 | 回 domain_idle |
| domain_hurt | 项目扩展，接标准 Hit | 领域中的受击不能闪回正常皮肤 | 回 domain_idle |
| domain_block | 项目扩展，接自定义 Block | 领域中的防御姿态，不能与施法完全相同 | 回 domain_idle |
| domain_weak_loop | 项目扩展 | 低血体态保持领域皮肤与识别特征，避免切回普通形态 | 循环；低血恢复后回 domain_idle |
| domain_die | 项目扩展，接标准 Dead | 领域形态死亡不闪回正常皮肤；保持死亡终帧 | 非循环、保持终帧 |
| roar | 项目扩展，接 Roar | 站稳、开胸、抬头张口，读得出咆哮；对应本项目 U23 | 一次后回实际待机 |
| storm_leap | 项目扩展，接 StormLeap | 下蹲蓄力、离地、落地冲击，跳起阶段释放足底固定；对应本项目 R31 | 一次后回实际待机 |

另有 `domain_roar` 和 `domain_storm_leap`，分别是上述两动作的领域皮肤序列，不再计作两种新动作。C18 和 R31 的玩法先赋予领域，再分别直接选择 `domain_roar`、`domain_storm_leap`；进入感由短 `domain_on` VFX 辅助，不在主体动作前面重复插入一整段 `domain_enter`。U23 根据真实领域状态选择普通/领域咆哮。

当时版本没有名为 `domain_bite / domain_heavy / domain_counter` 的独立片段。示例适配器在领域开启时将这三种攻击触发映射到 `domain_attack`，避免角色中途闪回普通皮肤。这是明确的复用选择；后续需要三种不同领域攻击时应新增素材并更新清单，不能用不存在的路径凑齐。

领域只在实际状态从 false→true 时播放进入动作；续时仅表现为领域光效短促增强，不重播整段进入动作。手牌兽化动作的临时凶猛体态不改变角色领域或低血真值。低血展示在普通形态中优先于临时凶猛体态，避免把濒危状态藏在姿势循环后面。

## 7. 动作验收应检查什么

每个动作至少检查起始、蓄势、接触、回收和结束帧；对循环还要检查最后一帧接回第一帧。检查真实透明底 PNG，不只检查 GIF 预览。固定画布保留统一地面基准；按透明内容裁边再居中会引入漂移。

重点检查手掌与前臂的连接、颈部与躯干的遮挡、脚底接触、爪尖和耳朵是否在边缘被裁掉。角色用分层插值动画时，关节周围要有足够遮挡，避免出现研究样本里的漂浮部件。多张姿态图必须保持同一头部比例、肩背轮廓、爪数与皮毛分区。

时间验收以 `manifest.json` 的帧时长和事件为准。接触、咬合、雷击、领域切换的事件需要与画面动作同时出现。GIF 的调色板和时间精度用于预览，不取代 RGBA PNG 的颜色与时间依据。`die` 与 `domain_die` 末帧保持，不触发自动待机。

本包集成源码的状态标签为 **`integration_source_uncompiled`**：已核对真实框架方法与素材清单接口，但当前研究环境没有用目标游戏 DLL 编译，也没有在游戏中完成运行验收。此标签只说明接入代码的验证层级；自己产出的动画素材由它们各自的导出和图像验收记录决定完成状态。

## 来源索引

完整 URL、快照、哈希与证据类型在 `sources_animation.json`。主要入口：

- [RitsuLib 角色模板](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/ModCharacterTemplate.cs)
- [RitsuLib 标准状态图](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Visuals/StateMachine/ModAnimStateMachines.cs)
- [RitsuLib AnimatedSprite2D 后端](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Visuals/StateMachine/Backends/AnimatedSprite2DBackend.cs)
- [BaseLib 非 Spine 动画支持](https://github.com/Alchyr/BaseLib-StS2/blob/c070755d11ec062f6c97c4dda1a205d975ed066a/Utils/CustomAnimation.cs)
- [公开提取的游戏代码快照（非官方 API 文档）](https://github.com/Zamiell/slay-the-spire-2-emulator/tree/04cfe6df800156e5339d565e03236302363c829c/decompiled)
- [Spire Codex 渲染与 API 文档](https://github.com/ptrlrd/spire-codex)
- [Mega Crit 2024-10-02 开发日志及官方 Silent 动画](https://www.megacrit.com/news/2024-10-02-neowsletter-issue-3/)
- [Godot SpriteFrames 官方文档](https://docs.godotengine.org/en/stable/classes/class_spriteframes.html)
- [Godot AnimatedSprite2D 官方文档](https://docs.godotengine.org/en/stable/classes/class_animatedsprite2d.html)
- [Spine 官方 Godot 运行时文档](https://en.esotericsoftware.com/spine-godot)
- [Riot 官方 Volibear 角色页](https://www.leagueoflegends.com/en-us/champions/volibear/)
