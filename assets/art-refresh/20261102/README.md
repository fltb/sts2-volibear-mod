# 2026-11-02 美术改版来源

## 本轮范围

- B01 打击：依据用户向下挥爪草图重绘动作，真实 `edit_image` 输入为原批准 B01 与 B03；保留同一熊爪身份、白/深蓝毛块、青色爪和灰紫背景。
- 14 种实际运行时自定义状态图形：真实 `edit_image` 输入为本机锁版游戏 PCK 提取的力量、格挡、无实体图标。新符号沿用简单轮廓和双面平涂，未把原版图标直接作为输出。
- 原版参考仅保留在忽略目录 `.local/art-refresh/native-references/`，不随仓库分发。
- 其他 88 张卡图、角色动画母图、动画帧及 VFX 动画图集均未更改。

## 来源与候选

- [打击原始候选](<B01-candidate-01.png>)、[状态原始候选](<status-candidate-01.png>) 均保留未处理版本。
- [来源记录](<provenance.json>) 包含编辑方式、实际参考摘要、裁切与透明度处理、生产路径。
- [打击审阅记录](<B01-review.json>) 明确是实施者审阅，不冒称独立审阅或用户批准。
- `previous/` 保留被替换的 B01 原母图、导出、原始审阅/提示和原状态 PNG。历史批准不转移到新像素。
- [状态预览](<status-preview.png>) 使用纯深色底方便查看；生产 PNG 均是真实 alpha。

## 状态图排列与接线

预览按从左到右、从上到下排列：

| 图形 ID | 状态/用途 | 生产资源 |
| --- | --- | --- |
| domain | 领域 | `icons/powers/domain.png` |
| thunder_force | 雷势及持续雷势 | `icons/powers/thunder_force.png` |
| thunder_armor | 雷甲 | `vfx/icons/64/thunder_armor.png` |
| iron_armor | 坚甲 | `vfx/icons/64/iron_armor.png` |
| retain_armor | 留甲 | `vfx/icons/64/retain_armor.png` |
| energy | 返能 | `vfx/icons/64/energy.png` |
| cost_reduce | 攻击减费、迎战准备及历史减费 | `vfx/icons/64/cost_reduce.png` |
| replay | 暴风再临 | `vfx/icons/64/replay.png` |
| enhance | 磨砺爪牙、天人合一 | `vfx/icons/64/enhance.png` |
| thunder_growth | 原始力量 | `vfx/icons/64/thunder_growth.png` |
| counter_thunder | 反雷 | `vfx/icons/64/counter_thunder.png` |
| bite_mark | 咬痕 | `vfx/icons/64/bite_mark.png` |
| bear_spirit | 熊灵侵染 | `icons/powers/bear_spirit.png` |
| wilderness | 我即荒野 | `icons/powers/wilderness.png` |

资源前缀为 `res://VolibearArt/`。Power 图标小/大版本是64/256；既有 VFX 状态图标同时保留32/64/128/256四档。两种兽形能力由 Lead 将原卡面路径改接新常量。复用原版力量/Flex 的原生图标保持不变；未用于自定义状态的另外六个旧 VFX 符号不在本轮重绘范围。

## 加工参数

B01：1448×1086 原图中央裁切 `[11,1,1436,1084]`，得到1425×1083母图；Lanczos导出250×190/1000×760（StS2 RGB），250×190/500×380（既有 StS1 RGBA）。

状态：1254×1254原始透明图按4×4等分切片，alpha 50%阈值去除低透明噪点；trim后等比缩至224像素范围，置于256透明画布中央；Lanczos生成各档RGBA，最终清空外圈1像素以去除缩放振铃。不是绘制棋盘格，也没有把纯色背景当透明。

## 实际验证

本轮用锁版 Godot 4.5.1 建立独立资源工程，实际导入并 `load()` 52 张生产纹理（48状态+4卡图导出），核查尺寸、解码、所有状态真实alpha、透明边界及非空实心内容。专用回执位于忽略目录 `.local/art-refresh/verify/result.json`；未运行游戏或完整发布gate。完整PCK接线及最终游戏验收由Lead统一完成。
