# 沃利贝尔 V9 · 完整重叠部件动画

> **2026-10-30 返修候选已原位重导**：肘点、肩根、内部髋腿覆盖、攻击曲线、脚底约束及辫子灰度已修改。26 段 / 940 帧完整解码与图集验证通过；本轮完整视觉审查尚在进行，下面旧 V9 审图结论不自动适用于当前文件。当前状态见 [返修检查点](../../reports/animation_revision_v10/STATUS.md)。

打开 [index.html](index.html) 查看 26 段动作；下方可逐个隐藏部件，检查身体补底。页面直接读取同目录 JS 与 PNG，不依赖 fetch、CDN 或网络服务。GIF 在 [previews](previews/)；推荐先看 [三动作并排 GIF](previews/joint_demo.gif) 与 [原图／静态拼合对照](review/reference_comparison.png)。

18 个绘制层（17 个逻辑部件加肩根内缘）：躯干、头、背刺、两条辫子，以及两侧上臂／前臂／手掌、大腿／小腿／脚。本次重新补绘完整近臂与双腿，整段大腿含髋根归入腿层。肩根内缘跟随上臂、位于胸背后方，近臂主体盖住辫子；关节之间保留重叠。31 个骨骼节点（含根节点与末端节点），16 张加权网格；肩肘腕、髋膝踝实际驱动运动，辫子使用分段骨链。

静态以批准参考的体型、站姿与识别特征为基准，原图对照图保留在 review/reference_comparison.png。肩根和辫子局部经过重绘，接受自然的图形差异，不以零像素差作为验收标准。近侧手臂覆盖辫子；抬臂或屈腿露出下层胸侧／髋部是正常行为，露出的部分必须完整。

本轮攻击先屈肘蓄势再挥击，近肩局部角度范围 54°、肘部动画偏转范围 48°，释放与回收保留弧度。髋根在骨盆与大腿之间渐变权重，肩根固定在胸部骨架上，没有附加平移。

26 段共 940 帧，24 fps，512×512 透明 PNG、26 张图集、26 GIF、26 无损透明 WebP。24 段使用完整部件加权骨骼；`die` / `domain_die` 保留完整倒伏逐帧绘画。GIF 为循环审查预览，实际动作循环标志和事件时间以 manifest / 图集 JSON 为准。领域动作交付无染色、无独立 VFX 的角色底图；领域效果由宿主叠加。

`character.tscn` / `project.godot` 是原生 Godot Skeleton2D + Bone2D + Polygon2D + AnimationPlayer 源工程，使用同一骨架、权重和逐帧姿态采样。它不是 Spine JSON。场景不会执行伤害、随机目标或 VFX 结算。骨骼源工程未在本环境启动 Godot 验证，游戏接入维持 `integration_source_uncompiled`；PNG / GIF 交付不等于游戏实机通过。

已完成全部 PNG / GIF / WebP 解码、图集逐帧一致性、源文件 SHA、事件保持与画布边缘检查。实际查看 67 页全部 940 帧，以及部件表、原尺寸高风险姿态和静态参考对照。没有声称完成浏览器动态播放、Godot 运行或用户艺术批准。详细记录见 `technical_validation.json` 与仓库 `reports/animation_revision_v9/visual_review.json`。

## 重建

需要 Python 3、Pillow 与 NumPy。在仓库根目录运行：

```sh
python3 animations/skeletal_v9/scripts/build_parts.py
OPENBLAS_NUM_THREADS=1 python3 animations/skeletal_v9/scripts/render.py --extremes
OPENBLAS_NUM_THREADS=1 python3 animations/skeletal_v9/scripts/export.py
python3 animations/skeletal_v9/scripts/export_godot.py
python3 animations/skeletal_v9/scripts/validate.py
python3 animations/skeletal_v9/scripts/refresh_viewer.py
```

任何源层／rig／动作变更后，旧看图记录都不能自动沿用。先查看少量极端姿态，再导出全部动作并逐页审查。`source/provenance.json` 保留补绘说明与源 SHA。
