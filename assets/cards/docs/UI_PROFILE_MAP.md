# 已交界面资源到角色槽位的对应

本页按本次 `ui/manifest.json` 的 14 个 PNG 和 `vfx/icons/manifest.json` 的 16 套符号对应实际 API。TR 为本项目交付范围分级，不是官方标准：TR1 主体成品、TR2 角色界面/机制补充、TR3 可选原版回退。文件已交付不等于该游戏场景已经注册/运行。

| 交付文件（相对仓库） | 可对应槽位 / 用法 | 接入注意 |
| --- | --- | --- |
| `ui/images/char_select_volibear.png` | `CharacterUiAssetSet.CharacterSelectIconPath` | 已解锁选角；132×195 |
| `ui/images/char_select_volibear_locked.png` | `CharacterSelectLockedIconPath` | 锁定选角；132×195 |
| 两张 `_master.png` | 编辑母版 | 528×780；不必作为游戏运行纹理 |
| `ui/images/character_icon_volibear.png` | `IconTexturePath` | 顶栏头像；128×128 |
| `ui/images/character_icon_volibear_outline.png` | `IconOutlineTexturePath` | 头像轮廓；128×128 |
| `ui/images/map_marker_volibear.png` | `MapMarkerPath` | 地图标记；128×128 |
| `ui/images/character_select_background.png` | 当前 RitsuLib `CharacterSelectBgPath` 的纹理回退 | 1920×1080。该固定版本运行时工厂先查场景，再查 `Texture2D`，纹理会包装成全尺寸 `TextureRect`；不能推断所有框架版本都支持直接 PNG |
| `ui/images/character_select_transition.png` | 转场材质的输入纹理 | 1920×1080。`CharacterSelectTransitionPath` 是材质路径，不能直接填这张 PNG；未完成目标游戏转场材质验证时保持原版回退 |
| `ui/images/big_energy.png` / `text_energy.png` | 卡池/遗物池/药水池 `BigEnergyIconPath` / `TextEnergyIconPath` | 作者模板实际提供这两个 override；尺寸74×74 / 24×24 |
| `ui/images/energy_master.png` / `big_energy_empty.png` | 能量计数器场景的贴图 | 256×256母版 / 74×74空状态；`EnergyCounterPath` 要求场景，不是 PNG |
| `ui/images/character_fallback.png` | 静态 Sprite2D 回退 | 512×512；不能冒充已经接入的战斗 `NCreatureVisuals` 场景 |
| `vfx/icons/64/<id>.png` / `256/<id>.png` | Power/status 小/大图标输入 | 16种符号；另交128/32与可编辑SVG。模型 ID、叠层数字及本地化由规则/UI层注册 |
| `animations/clean` 的 `relaxed_loop` | 商店/篝火复用素材 | 需对应场景包装；没有声称画了独立坐姿或篝火动画 |

`src/VolibearUiAssets.cs` 只返回格式兼容的纹理槽位，并保留 `BigEnergyIcon` / `TextEnergyIcon` 常量；没有用图片路径伪造材质、动画场景或音频事件。资源 staging 会一并复制 UI PNG 和图标 SVG/PNG。卡牌插画在独立卡片仓库，需在实际 Mod 工程按卡表 ID 接入。

多人指向/石头剪刀布、独立复活动画、YummyCookie 专属图、配乐均按本次 `ui/manifest.json.reuse_decisions` 明确使用原版或已有姿态回退；这些不计为新绘制的原创素材。运行时场景、材质以及具体模型注册仍由目标游戏工程完成并验证。

依据：[CharacterAssetProfile 的槽位类型](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/CharacterAssetProfile.cs) · [当前背景工厂实际支持纹理](https://github.com/BAKAOLC/STS2-RitsuLib/blob/772f280964f2efc7c7e2f29fc59844e68616dd57/src/Scaffolding/Characters/Patches/CharacterSelectBackgroundRuntimeFactoryPatch.cs#L132-L158) · [模板卡池能量图标](https://github.com/Alchyr/ModTemplate-StS2/blob/2c900a04dd2073872f677f4fb78ee2ad1e871009/content/CharacterModTemplate/CharModCode/Character/CharModCardPool.cs)

