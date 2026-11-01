# 角色界面素材

本目录包含 14 张既有角色 UI 与四张新增多人手势。既有角色选择、锁定、顶部头像、多人描边、地图标记和备用角色画面由批准原图等比缩放及裁切取得，未重画原图体型。新增手势是独立绘制资源，不覆盖批准角色母图或卡图。

132×195 选择头像、128×128 头像/地图标记、74×74 能量主体和 24×24 文本能量符号，依据社区作者模板的实际文件尺寸。它们是可用的约定尺寸，不宣称是引擎硬限制。1920×1080 选择背景左侧留出信息区域，人物过渡图使用相同位置。

`manifest.json` 列明每张图的用途、尺寸、来源和 SHA256。`source/energy_emblem.svg` 是可编辑的能量符号。

四种手势是 pointing、rock、paper、scissors。结构参考 Riot 官方沃利贝尔原皮模型；视角、长前臂比例和笔触参考 StS2 原生 Ironclad 手势及实际游戏截图。第一套不符合用户要求的插画已替换。当前均为 422×1200 RGBA，按原生 TextureRect 的保持比例居中规则显示。原生旋转 pivot 属于 Control 坐标，不能当作 PNG 像素坐标裁切素材。

`source/multiplayer_hands/` 保存四张生成源、完整提示词及参考来源；`scripts/prepare_multiplayer_hands.gd` 只做等比尺寸准备，不拉伸爪子，也不生成新姿势。原版参考图不进入 Git 或 PCK。手势通过 `CustomArm*TexturePath` 接正常角色 getter；资源解码与四图差异由实际角色契约检查，视觉批准单独记录。

角色没有新增坐姿、复活手绘片段或专属饼干遗物。对应使用既有 relaxed 动作、明确状态切换及原生合法兜底。状态图标在 `../vfx/icons/`，卡牌肖像在 `assets/cards/`。

从仓库根目录检查：`python3 -B assets/animation/ui/scripts/validate_ui.py`。本次技术报告写到忽略目录 `artifacts/ui/technical_validation.json`；`reports/` 中旧记录仅属历史素材交付。

旧 UI 裁切重建脚本会保留并验证四张手势的源与成品摘要。不要为普通 Mod 构建重新生成母图或重画手势；统一入口 `tools/local_delivery.py` 直接使用当前清单。

运行时使用 BaseLib。角色选择、转场材质、能量场景与 getter 的当前接线以 `src/Volibear/Content/VolibearCharacter.cs` 和 `src/Volibear/Presentation/` 为准；旧 `integration_sts2_v5` 文档仅记录早期资源示例。
