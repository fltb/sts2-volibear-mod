# 角色界面素材

本目录把批准原图适配为实际的角色选择、锁定、顶部头像、多人描边、地图标记、能量图标和备用角色画面。人物全部来自同一原图，采用等比缩放与明确的 UI 裁切，没有重画体型。

132×195 选择头像、128×128 头像/地图标记、74×74 能量主体和 24×24 文本能量符号，依据社区作者模板的实际文件尺寸。它们是可用的约定尺寸，不宣称是引擎硬限制。1920×1080 选择背景左侧留出信息区域，人物过渡图使用相同位置。

`manifest.json` 列明每张图的用途、尺寸、来源和 SHA256。`source/energy_emblem.svg` 是可编辑的能量符号。

角色本轮没有新增坐姿、复活手绘片段、多人石头剪刀布动作或专属饼干遗物。对应接入策略是使用既有 relaxed 动作、原版回退或明确状态切换；它们不能被写成已制作的新动画。状态图标在 `../vfx/icons/`，卡牌肖像在独立卡片仓库。

重建：`python3 ui/scripts/build_ui.py`。

选择背景可由当前RitsuLib的纹理回退载入；转场PNG仍须制作材质包装，不能直接用作CharacterSelectTransitionPath。能量图片是卡池/遗物池/药水池的BigEnergyIconPath与TextEnergyIconPath素材，EnergyCounterPath仍需要场景。完整映射见 `../integration_sts2_v5/docs/UI_PROFILE_MAP.md`。
