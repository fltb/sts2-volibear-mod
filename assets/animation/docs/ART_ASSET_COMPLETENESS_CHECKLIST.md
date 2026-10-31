# 角色美术完整性交付清单

本表列出接入槽位，避免把“动画和卡图齐了”误写成“所有游戏界面及规则都已实现”。TR1 为主体成品，TR2 为角色界面/机制补充，TR3 为可选原版回退。TR 是本项目交付范围分级，不是游戏官方标准，也不是技术验证成熟度；三类都放在完整 repo 包中，不拆成分卷。

| 级别 | 槽位 / API | 文件格式与实证 | 验收内容 |
| --- | --- | --- | --- |
| TR1 | 战斗 `VisualsPath` / `CreateCustomVisuals` | `.tscn` 或 NodeFactory；本项目 PNG RGBA 图集 | 原图体型、完整肩/肘/髋/腿、前后遮挡；固定脚底原点 |
| TR1 | 待机/攻击/施放/受击/死亡 | `AnimatedSprite2D` + `SpriteFrames` 或 Spine | 循环闭合、终止动作停末帧；攻击中断不复用旧事件 |
| TR1 | 专属机制表现 | 自定义触发；非原生固定名称 | 兽化明确作用于卡牌/手牌；侵染指向外物；雷击清楚指向结算对象 |
| TR1 | 战斗命中与防御 | VFX 图集/场景/粒子 | 自身受击不画到敌人身上；格挡获得、格挡命中、破盾三个事件分开 |
| TR1 | 声音反馈 | Ogg / WAV；本项目交付主文件与编辑源 | 一次事件一次播放、声效限流、循环退出、主音量/音效音量桥接 |
| TR1 | 卡牌 portrait | 作者模板：250×190，big 1000×760 | 卡牌可读；完整卡图不包含引擎生成的费用/描述/卡框文本 |
| TR1 | 卡牌机制绑定 | 项目 JSON / 代码 | 每个卡牌 ID 有明确表现族或“只使用基础反馈”，不能由词名随机猜机制 |
| TR2 | 选角 / 锁定 portrait | 作者模板：132×195 PNG | 裁切不丢头/肩；锁定状态仍可识别轮廓 |
| TR2 | `IconTexturePath` / `IconOutlineTexturePath` | 作者模板头像128×128 PNG；描边槽位存在 | 顶栏、历史、多人地图的对比度 |
| TR2 | `MapMarkerPath` | 作者模板128×128 PNG | 小尺寸清晰，与顶栏头像区别用途 |
| TR2 | `CharacterSelectBgPath` / transition | 场景或当前 RitsuLib 背景纹理回退 / 转场材质 | 背景与转场纹理已交付；转场贴图仍需正确材质包装，不把 PNG 当材质路径 |
| TR2 | `EnergyCounterPath` | Godot场景；模板 big_energy74×74、text_energy24×24 | 大能量和文本内小能量图标都有对应素材 |
| TR2 | `MerchantAnimPath` / `RestSiteAnimPath` | Godot场景，可复用 relaxed cue；当前RitsuLib另支持静态纹理回退 | 商店/篝火姿势比例正确；读档路径不缺图 |
| TR2 | `CharacterVfxAssetSet.TrailPath` | Godot场景，须满足框架拖尾节点结构 | 不能仅填一张 PNG 期望变成 NCardTrailVfx |
| TR2 | `PowerAssetProfile` | 模板64×64与big256×256 PNG | 领域、伤口、雷等状态可读；数值由UI层绘制 |
| TR2 | `RelicAssetProfile` | 模板94×94+同尺寸outline，big256×256 | 仅对卡表/设计已规定的专属遗物制作；没有设计不要擅造玩法 |
| TR2 | `PotionAssetProfile` | 模板256×256与outline | 专属药水若没有设计，明确使用原版 |
| TR3 | `ArmPointingTexturePath` | PNG；本次未核定统一强制尺寸 | 多人指向手势；可注明回退 |
| TR3 | `ArmRock/Paper/ScissorsTexturePath` | 三张PNG；本次未核定统一强制尺寸 | 多人石头剪刀布，不得拿同一只手谎称三个姿势 |
| TR3 | `CustomYummyCookie` / vanilla relic override | 原版专属遗物视觉替换槽位 | 可以原版回退；若未制作不能记为自定义完成 |
| TR3 | `PhobiaModeVisuals` | 可选节点 | 本项目若不涉及恐惧模式对象，可声明不适用 |
| TR3 | 台词、商店对白配音、主题音乐 | 可选音频；没有“必须录满台词”要求 | 不覆盖原版音乐系统；来源与实际配音身份明确 |
| TR3 | 独立复活 / 胜利动画 | 可选新动作 | 若复用待机/放松，必须写明回退，不冒充独立绘制 |

以上 PNG 尺寸是读取作者模板图片实际得到的示例尺寸，不是 Godot 对所有 Mod 的硬性限制。模板固定于 commit `2c900a04dd2073872f677f4fb78ee2ad1e871009`，路径 `content/CharacterModTemplate/CharMod/images/`。[模板来源](https://github.com/Alchyr/ModTemplate-StS2/tree/2c900a04dd2073872f677f4fb78ee2ad1e871009/content/CharacterModTemplate/CharMod/images)

槽位依据：[角色 profile 源码](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfile.cs) · [素材回退文档](https://sts2-ritsulib.ritsukage.com/guide/asset-profiles-and-fallbacks) · [生物节点要求](https://alchyr.github.io/BaseLib-Wiki/docs/scenes/creature-visuals.html)

发布前将每个适用项映射到交付路径、明确原版回退，或标注尚未实现；用实际资产清单核查。不能以模板有 fallback 为由声称已经画好一套原创资源。
