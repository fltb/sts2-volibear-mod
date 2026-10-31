# 输入优先级、卡表变化与素材复用 · V3

## 当前冻结输入

- `inputs/cards_v4_1_original.html`：原始上传卡表，不改写。
- `data/cards_source.json`：89张卡与原文规则，当前任务不调整游戏平衡。
- `data/cards_art_briefs.json`：89条当前美术简案，10张返修的主动作、镜头、身份锚点和提示词已同步。
- `references/identity/volibear_approved.png`：原始定稿造型。
- `state/style_lock.json`：当前正向例及SHA256。
- `data/source_overrides.json`：前轮已记录的规则口径差异，仅作为历史语义说明，不由美术导出脚本执行。
- 原作研究资料已移至独立 `volibear_reference_repo`；现有卡图仓库可单独使用，不需要先下载全部参考。

## 变更处理

| 改动 | 处理 |
|---|---|
| 仅数值、费用或升级数值 | 若用户授权规则修改，保留原画，复核语义与源表哈希 |
| 改名但主动作不变 | 保留ID和资产路径，更新元数据 |
| 增减副效果 | 判断主视觉是否仍准确，可复用时只复审 |
| 攻防类别或主动作改变 | 新建该卡候选，真实生图和独立审核，重新检查新卡型遮罩 |
| 新增卡 | 采用明确的新ID，不补空号；补齐母图、提示词、审稿及四种输出 |
| 删除卡 | 保留历史记录，当前manifest与源ID集共同更新 |
| 身份或体型改变 | 更新身份版本，对受影响图重新审查 |

本版维护入口是 `00_GOAL.md`，验证命令为 `python3 scripts/card_repo.py verify`，导出为 `rebuild`。不再使用旧整包的 `work/state.json` 或 `sync` 命令。精确最终生图提示词位于 `cards/prompts/`；未来修改时同步当前brief，避免旧构图复发。

## 不连续编号

缺号不代表漏画。不要补造 C16、U01、R03 等源表未列出的卡。脚本比较真实ID集合和源卡表数量。

## 与动画仓库的关系

角色动画位于独立 `volibear_animation_repo`，不在本仓库重复保存。改变视觉触发时，在该仓库修改 `animations/card_animation_bindings.json`，不要让动画事件结算伤害、抽牌、领域时长或兽化规则。
