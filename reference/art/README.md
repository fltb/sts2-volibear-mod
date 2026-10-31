# 沃利贝尔参考素材仓库 · V5

打开 `START_HERE.html` 可以离线浏览本包。

本包是独立研究资料仓库，不需要拼接其他压缩包。动画与卡图成品分别放在各自的仓库包中。

## 保留内容

- `identity/`：原始批准角色参考，作为体型、体态、白毛/深蓝身体和爪形依据。
- `project_examples/`：B01、U19、U37 三张正向例；分别用于基本爪击、简洁肩背防御和明确的空间施法因果。
- `style_examples/`：30张已经挑选的原作卡面，覆盖五角色，逐图标明用途与来源。
- `motion_examples/`：官方沃利贝尔 Q/W/E/R 短动作片段，以及 Mega Crit 发布的 Silent 动画预览；用于节奏、重量和二次运动研究。
- `research/`：此前研究记录与本轮结构修正标准。此前研究记录中的439张指当时研究样本量，不是本包文件数；本包仅保存精选30张。

`reference_manifest.json` 记录实际保留文件、原始来源及校验值。参考图与本项目生产图在不同目录，不把原作画面作为项目成品。

## 结构历史与当前优先级

V4 的结构检查补充在 `research/08_SOURCE_PRESERVATION_V4.md`；本轮优先采用 V5 肩部与遮挡规范；它补充并纠正 V3 对腰髋保全和爪面方向的漏检。精选参考图和视频保持不变。旧风格文档中把旧B02、旧U28、旧R28用作先导图的建议已经过时；今后采用本包三个正向例以及成品仓库的新修正版。旧研究结论不会自动成为游戏引擎硬性规定，项目默认阈值和动作映射仍是本项目设计。

## V5 新研究与当前规范

- `research/STS2_SUPPORT_V5.md`：截至2026-10-27的Godot/C#、SpriteFrames、音频、领域/兽化表现与多人边界。
- `research/ART_ASSET_COMPLETENESS_CHECKLIST.md`：真实槽位核查与TR1/TR2/TR3范围，不是ZIP分卷。
- `research/ASSET_SCOPE_TR.md`：本次已制作资产、原版回退与未编译游戏接入的明确区分。
- `research/UI_PROFILE_MAP.md`：PNG、场景、材质、卡池能量图标的实际对应，避免填错资源类型。
- `research/V5_SHOULDER_AND_OCCLUSION.md`：本轮肩背尖块与辫子遮挡的修复判断。
- `audio_sources/`：真正采用的CC0声音来源、许可与处理说明；不附官方Riot对白。声音成品和源录音在动画包，参考包保留资料索引。

原有精选媒体保持不变，没有重新加入全量研究卡图。研究材料不能替代真实目标游戏版本的编译和实机验证。网页与第三方角色参考是研究来源，不因此成为本项目可任意再分发的生产素材。

离线页面已附中文字形子集与OFL许可。可选复测：安装Node/Playwright后运行 `npm run verify:browser`；已有Chromium可设置 `VOLIBEAR_CHROMIUM`。浏览器截图只用于制作验收，不打包；实际查看记录保留文本与SHA。
