# 可独立重建的必要源快照

本目录只保存生成本特效库所需的项目输入。`manifest.json` 逐项给出原项目路径、字节数和 SHA。`volibear_approved.png`和`B01.png`保留原图；`T01.png`已同步为本轮V7审定卡图，用于外部卡牌接受兽化的示例。效果帧、时间线与规则绑定保持既有版本。

`card_animation_bindings.json` 是从上一版工程继承的动作与卡牌语义输入。它内部的 V3 / V4 标记和“VFX 尚属设计规格”文字是原文件的历史状态；该快照为了可追溯性保留原字节，**不能用来判断本轮交付状态**。当前实际特效、89 卡绑定、检查和接入范围分别以本目录上级的 `manifest.json`、`card_vfx_bindings.json`、`reports/` 与主包集成说明为准。

`audio_cues.json` 只是一份音效逻辑 ID 接口快照，使本 VFX 目录在卡片包中也能独立校验。实际 WAV / OGG 成品与声音来源在动画包的 `audio/` 中。没有把接口 JSON 当作音频文件。

后续卡表发生变化时，先更新卡表源快照和源清单，再人工更新 `scripts/build_bindings.py` 的逐卡表；脚本会在卡牌 ID 集合不一致时明确失败，不默默替新卡编造效果。
