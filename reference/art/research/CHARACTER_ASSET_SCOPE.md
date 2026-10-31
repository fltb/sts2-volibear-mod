> 历史范围快照（V3）：下文“当时版本”及未制作项描述历史交付，不是 V5 当前范围。V5 已交付头像、选择图、地图、能量等14张UI，以及47个独立声音成品。当前范围以 [ASSET_SCOPE_TR.md](ASSET_SCOPE_TR.md) 为准；资源槽类型以 [UI_PROFILE_MAP.md](UI_PROFILE_MAP.md) 和 [STS2_SUPPORT_V5.md](STS2_SUPPORT_V5.md) 为准。历史文中将 CharacterSelectBgPath 绝对视为场景路径、以及只列 FMOD 音效入口的表述，不适用于 V5 已核实的纹理回退与 OGG 资源音频路线。

# 角色整体美术范围：战斗、静态立绘、头像与界面

研究日期：2026-10-27（本会话客户端日期）。

角色美术除了卡面和战斗动画，还会出现在选择界面、顶部头像、地图、营火和商店。**这些资源槽确实存在，但不能据此推断每一槽都必须重新绘制。** RitsuLib 的 `CharacterAssetProfile` 将这些覆盖项定义为可选；`CharacterAssetProfiles.Resolve` 可以用原版角色资源填充未指定字段。当前源码默认占位角色为 `ironclad`。[维护者资源配置源码](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfiles.cs)

V3 已制作角色的普通/领域战斗形象和可用作静态战斗立绘的透明 hero 图。当前身份依据为批准原图，头部与躯干采用当前连续分层；旧版独立头像切片已退出交付。存在这些源图不表示已经完成所有游戏 UI 替换。

## 1. 必需性与当前交付边界

| 场景或资源 | 真实资源槽 / 技术形式 | 对这个项目的要求 | 当时版本范围 |
|---|---|---|---|
| 战斗角色主体 | `Scenes.VisualsPath` / `CustomVisualsPath`，`NCreatureVisuals` 场景 | 核心：自己的身份、朝向、脚底基准和动作 | 自己的透明帧、图集、静态 hero 已纳入动画素材；场景/模组接入源代码另行标记未编译 |
| 普通静态全身立绘 | 可从自己的战斗视觉或独立静图使用；没有一个全局必需的“CG 文件”接口 | 核心参考；用于身份对照、静态展示或场景构建 | 已有普通和领域 768×768 RGBA hero 图 |
| 顶部面板头像与描边 | `Ui.IconTexturePath`、`Ui.IconOutlineTexturePath` | 推荐自己的头像，避免新角色仍显示原版脸 | 可从批准原图或当前 hero 裁出头部；最终小尺寸头像、描边和槽位适配未制作 |
| 角色图标场景 | `Ui.IconPath` | 可复用框架场景结构，再替换自己的贴图 | 当时版本未制作专用图标 scene；可从原版模板接入 |
| 角色选择小肖像 | `Ui.CharacterSelectIconPath`、`CharacterSelectLockedIconPath` | 推荐自己的身份图；锁定版按解锁流程确定 | 可使用批准原图/当前 hero 作为源图；未交付独立的最终选择图/锁定图 UI 替换 |
| 角色选择大型背景 / “CG” | `Ui.CharacterSelectBgPath` 是场景路径，不等于普通卡面图片 | 进阶展示，可做独立场景或用已有立绘排版 | 当时版本未承诺新绘完整选择页背景 CG；hero 能成为前景素材，版式、背景与 UI 留白需单独设计 |
| 选择转场 | `Ui.CharacterSelectTransitionPath`，材质资源 | 可使用原版或模板通用转场 | 当时版本无新转场材质；复用实际存在的原版资源 |
| 地图标记 | `Ui.MapMarkerPath` | 推荐与角色一致的小图标 | 可从头部提炼；目前没有宣称新的地图图标已替换 |
| 能量球 / 能量计数器 | `Scenes.EnergyCounterPath` | 必须有可运行资源，视觉可复用 | 可复用原版计数器；当时版本未制作整套自定义能量球 UI |
| 营火、商店角色 | `Scenes.RestSiteAnimPath`、`MerchantAnimPath` | 非战斗场景需要可加载视觉；可临时用模板/原版回退 | 有自己的静态 hero 和 relaxed 动作可供后续接入；未声称营火/商店布局 scene 已运行通过 |
| 卡牌拖尾 | `Vfx.TrailPath`、`TrailStyle` | 可用原版通用拖尾 | 当时版本主要范围是自己的卡面/角色素材；没有声称新拖尾特效已接入 |
| 多人指向与石头剪刀布手势 | `Multiplayer.ArmPointingTexturePath / ArmRockTexturePath / ArmPaperTexturePath / ArmScissorsTexturePath` | 联机功能存在相应槽；可先沿用原版 | 当时版本未画四个完整 UI 手势；战斗爪部件不自动等于这些 UI 资源 |
| 音效 | 选择、转场、攻击、施法、死亡的 FMOD event 路径 | 可使用游戏已有音效路径 | 当时版本没有生成或交付原创角色配音 / 音效 bank |

“可复用原版”表示在用户安装的游戏中引用其真实资源路径，不是把原版文件重命名成自己的新绘素材。默认原版回退适合让模组先运行；若最终产品要求所有界面都显示沃利贝尔，就把相关身份槽列为后续 UI 美术任务，而不是在完成清单里提前勾选。

## 2. 这轮实际存在、已经打开检查的静态图

以下路径以独立动画仓库内的 `animations/` 为基准。V3 静态图由当前已修正的角色渲染；旧版 `parts/normal/head_idle.png` 和 `parts/domain/head_idle.png` 不属于当前交付。批准原图位于动画仓库根目录的 `references/identity/volibear_approved.png`。

| 实际文件 | 尺寸 / 格式 | 适合直接做什么 | 还不能直接声称什么 |
|---|---|---|---|
| `previews/idle_loop_hero.png` | 768×768 RGBA | 普通形态的透明全身静态展示、角色身份参考 | 不是已经适配选择界面所有遮罩和留白的完整 CG |
| `previews/domain_idle_hero.png` | 768×768 RGBA | 领域形态静态展示、两形态对照 | 不是一套独立选择页背景或全屏领域特效 |

后续从批准原图或当前 hero 派生 UI 头像时，应围绕头部裁切、增加安全留白并实际缩小观察。头像辨识优先依靠眼部纹样、头部轮廓和颜色关系；不要把整张 768 全身缩成很小的头像后期待辨识度不变。新头像需要独立验收，不能恢复旧版头部切片。

## 3. 头像、选择图与 CG 的规格不要从卡面尺寸推导

1000×760 是此前核实的普通卡面大图规格，不是角色头像或选择页 CG 的通用规格。`CharacterSelectBgPath` 还是一个场景资源，不能把一张 JPG 路径填进去就称为集成完成。

后续实现这些 UI 槽时，应读取目标游戏构建中相应场景的 TextureRect、AtlasTexture 区域、遮罩、描边和布局。保持它原来的锚点及显示范围，再从当时版本源图输出正确尺寸。若当前环境没有目标 scene 或游戏 DLL，就保留为“源图可用 / UI 导出未做”，不要捏造一个官方固定头像尺寸。

## 4. 对 Goal 的执行约束

动画 Goal 的完成范围是自己的角色帧、静态 hero、分层源图、清单、预览、适配源代码和验证记录。它不因没有全新营火背景、选择页 CG 或多人手势而被迫无限追加绘制，也不把这些未做项计作已经交付。

若后续 Goal 明确包含完整 UI 替换，先保留同一角色身份参考，基于批准原图/当前 hero 派生顶部头像、选择肖像、锁定版和地图标记；再做选择页大场景。每个派生图拥有独立路径与验收记录。不得把一张尚未适配的头部裁图直接当作所有 UI 槽的最终成品。

## 主要来源

- [CharacterAssetProfile：场景、UI、音效、多人资源槽](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfile.cs)
- [CharacterAssetProfiles：原版路径与逐项 fallback 合并](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfiles.cs)
- [ModCharacterTemplate：真实 Custom*Path 属性与 PlaceholderCharacterId](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/ModCharacterTemplate.cs)
