# 沃利贝尔卡片素材仓库 · V7 完整成品

**89张卡图已全部落到实际PNG：26张用户指定固定原图，63张真实重绘，包含追加返工的U28；四套游戏导出共356个PNG。** 87张主卡与T01、T02两张衍生牌均已包含。卡号、卡名、费用、基础和升级效果保持原卡表。

解压后双击 **`START_HERE.html`**，再进入卡图浏览器。也可直接打开 `cards/index.html`，无需服务端或联网。

## 四张追加返修（2026-10-30）

B01、C12经用户授权解除旧锁定；连同U36、T02完成真实重画及独立复审。C12背后错位辫饰已删除；旧图与旧清单备份于 `reports/revision_v7/before_four_card_revision/`。本次26张固定母图与104导出字节保留检查见 `reports/revision_v7/four_card_preservation.json`。此前总览/质量榜/ZIP是历史交付，当前图像以离线图库和asset_manifest为准。

## 先看这些

- **全部成品**：`cards/index.html`，可按卡号、中文名和效果搜索，筛选牌型、稀有度、表达层级、26张固定图或63张重绘；可按重绘评分从高或低排序。
- **U28与U35**：U35原图固定；U28改为后侧俯视、可见敌人和V形回雷。直接对照在 `previews/v7/U28_U35_comparison.jpg`。
- **全套总览**：`previews/v7/` 中四张带卡号总览，覆盖全部89张。
- **逐卡检查**：详情包含1000×760大图、真实125×95彩色/灰度、遮罩导出、实际观察和固定基准对照。63张重绘均有完整对照板。
- **质量排序**：`reports/revision_v7/QUALITY_RANKING.md`，另有JSON、CSV。五项各20分，是独立审稿的主观比较；结构硬伤必须先修，分数不能抵消硬伤。
- **继续执行计划**：`00_GOAL.md`。当前队列已完成；后续按新要求只修改受影响卡，正常返修无需逐卡确认。

## 本轮完成范围

固定原图：B03、C05、C06、C08、C09、C13、C18、C22、C24、C26、U03、U17、U19、U21、U23、U25、U35、U39、U40、R09、R12、R17、R18、R23、R24、R31。

这26张的母图及104个游戏导出已与上一交付逐字节比较，结果见 `reports/revision_v7/locked_preservation.json`。其他63张均有真实生成原图、精确工具请求、实际审稿和新导出。最终文件身份由 `data/asset_manifest.json` 的SHA256绑定。

重绘将同向巨爪、圆团式风暴熊和混乱零件拆成不同画面关系：承力接触、完整身体动作、环境轨迹、器物变形、整体剪影。防御检查掌面、掌背与爪尖的一致方向；侵染检查外部对象、接触和局部转换；风暴用连续大形表达。详细标准在 `docs/ART_REVIEW_V7.md`。

生成作者之外的审稿者对候选做交叉复审；最终根审逐张看原图、两张固定基准、250/125缩图、灰度和两种遮罩。发现问题的版本退回真实重画，最终批准只对应当前图像SHA。生成记录里的 `visual_approved:false` 是作者不能自批的原始状态；正式结果以 `reviews/<ID>.json` 为准。

## 直接使用的目录

| 用途 | 路径 | 数量与规格 |
|---|---|---|
| 审定母图 | `cards/masters/` | 89张，无文字和卡框 |
| STS2大卡面 | `production/sts2/Volibear/images/card_portraits/big/` | 89张，1000×760 RGB |
| STS2小卡面 | `production/sts2/Volibear/images/card_portraits/` | 89张，250×190 RGB |
| STS1大卡面 | `production/sts1/VolibearResources/images/cards/*_p.png` | 89张，500×380 RGBA，按牌型遮罩 |
| STS1小卡面 | `production/sts1/VolibearResources/images/cards/*.png` | 89张，250×190 RGBA |
| 本轮原始生成输出 | `cards/source_v7/` | 63张，保留真实输出字节 |
| 最终提示词 | `cards/prompts/` | 89份；本轮63份为实际工具请求原文 |
| 实际审稿 | `reviews/<ID>.json` | 89份当前批准与母图绑定 |
| 固定基准对照 | `reviews/v7/comparisons/` | 63张，大图/缩图/灰度/遮罩 |
| 导出检查板 | `cards/proofs/` | 89张 |
| 原卡表 | `data/cards_source.json` | 89个真实ID，编号空缺按原表保留 |
| 当前执行清单 | `data/v7/redesign_plan.json`、`state.json` | 63张完成、剩余0 |
| 必要编辑输入 | `references/generation_inputs/` | 最终版本所需的历史编辑目标与可移植映射 |

基础和升级版本共用同一插画。复制目标游戏对应的 `production/` 子树，并让工程资源路径对应 `asset_key`。本包交付素材与映射；STS2角色注册、玩法代码及目标版本的实机集成仍由游戏工程完成。

## 保留的VFX与其他两个包

本卡片包继续包含 `vfx/`：40种透明效果、1070帧、16套机制符号、89张卡的219项表现绑定与10项全局规则。打开 `vfx/index.html` 可播放。卡号与规则未改，本轮重绘不会改变这些绑定。兽化示例中显示的T01也同步为V7卡图，特效与时间线保持既有版本。该预览为静音；声音和人物动画在独立动画包。

三个ZIP分别是**卡片包、动画包、参考素材包**，均为完整repo，单独解压，不需要拼接。当前卡片版本V7；动画和参考沿用已交付版本。本轮没有重做人物动画或音频。TR1/TR2/TR3仍按交付范围分级，说明在 `docs/ASSET_SCOPE_TR.md`；动画包内部最新清单是动画和音频范围的依据。

## 检查与维护

仅预览或取用PNG无需安装依赖。需要验证时：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/card_repo.py verify
python3 scripts/verify_checksums.py
```

`verify` 核对原规则、当前审稿、母图、原始生成到母图的实际裁切、356个导出像素/遮罩/尺寸及图库链接。`verify_checksums.py` 校验交付文件列表。现有包开箱即可使用，无需先重建。

`python3 scripts/card_repo.py rebuild` 仅重导出已审重绘卡，保持26张固定母图和游戏PNG字节。它不生成新图、不批准美术。`gallery` 可从已审素材刷新离线图库和技术报告。

浏览器验证可复现：

```bash
npm install
npx playwright install chromium
npm run test:browser
```

可用 `VOLIBEAR_CHROMIUM` 显式指定本机兼容Chromium。脚本实际打开89个详情，检查基础/升级文案、所有链接、缩图、固定/重绘筛选、双向评分排序、手机宽度与VFX导航；结果写入 `reports/revision_v7/browser_validation.json`。

## 来源与历史

`reviews/v7/generation_*.json` 保存真实请求及版本历史；其中制作环境的绝对路径是原始审计信息，当前可移植映射见 `references/generation_inputs/manifest.json`。被淘汰的完整废稿缓存不进入交付；仅保留最终编辑链必须用到的输入，并标明它们不是游戏成品。

`data/v7/redesign_plan_initial.json` 和 `prompts/v7/` 是初始设计历史，当前请求以 `cards/prompts/` 为准。V3/V4/V5报告保留作历史，不代替本轮批准或本轮浏览器检查。外部原作风格资料集中在独立参考包；本包保留身份图、26张固定基准和实际所需输入。
