# 当前检查记录 · V7

- `revision_v7/QUALITY_RANKING.md`：61张实际重绘的独立视觉排序；JSON/CSV包含各轴、定稿尝试、基准和实际观察。
- `revision_v7/locked_preservation.json`：28张固定母图与112个游戏导出和上一交付逐字节相同。
- `revision_v7/browser_validation.json`：V7离线图库实际执行结果，覆盖89个详情、筛选/排序、文本、链接和窄屏；不是游戏内测试。
- `revision_v7/portability_audit.json`：真实来源、最终编辑链和必要参考的文件核查。
- `technical_validation.json`：原卡表、母图、批准记录、实际裁切、356个导出像素/遮罩/尺寸和图库绑定。
- `revision_v7/DELIVERY_V7.md`：完成范围和最终验收入口。

当前正式批准是 `../reviews/<ID>.json`，逐版生成与退回在 `../reviews/v7/`；作者生成记录不自行批准。

V3/V4/V5子目录和旧baseline记录是历史审计，可能引用当时的图像SHA或制作路径，不代表本轮图像仍有旧缺陷，也不能代替V7审稿。旧设计历史不纳入当前待办队列。
