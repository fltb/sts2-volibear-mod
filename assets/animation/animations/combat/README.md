# 战斗动作补充 · 2026-11-18

14 套新增动作、358 帧、24 fps。保留 `clean/` 的 26 套 / 940 帧原资源，运行时合计
40 套 / 1298 帧。新增动作使用现有 `skeletal_v9` 的绘制部件、网格、熊爪形状及身体
比例；差异来自肩、肘、腕、头、躯干和脚部 IK 关键帧，没有重新绘制角色，也没有
把普通攻击换一个名字充当新动作。

| Clip | 动作区别 | 接触帧（从 0 计数） |
| --- | --- | --- |
| `backhand` | 收肘后反手掠出，远爪护胸 | 7 |
| `double_claw` | 近爪先挥、远爪追击 | 7、15 |
| `claw_flurry` | 近、远、近三段交替，各段有独立收肘 | 6、12、18 |
| `sweep` | 压低重心，长弧横扫，头随肩回转 | 10 |
| `uppercut` | 屈膝蓄势后向上挑击 | 10 |
| `lunge` | 低身前送肩爪，近脚实际前踏后收回 | 8 |
| `ground_slam` | 双臂抬起后向下砸击，膝盖承重下沉 | 14 |
| `stomp_chain` | 近脚、远脚、近脚轮流提膝落踏 | 8、17、24 |
| `bite_rend` | 张口前探咬住，再向后撕扯 | 9、17 |
| `thunder_call` | 单臂高举唤雷，另一臂护胸 | 13 |
| `chain_channel` | 两掌交替导引三次雷弧脉冲 | 9、15、21 |
| `storm_channel` | 双臂展开托起风暴，释放时下压咆哮 | 15 |
| `iron_guard` | 双臂交错护胸，沉下重心保持支撑 | 9 |
| `primal_charge` | 双爪收拢蓄势，展开胸部抬头咆哮 | 13 |

## 资源与结算边界

PNG 为 512×512 RGBA，8 列图集，脚底锚点仍为 `[250, 442]`。原绘制风格、分层
覆盖和关节约束均沿用。领域颜色、雷电、命中特效由独立 VFX 层负责，图集中没有
烘焙雷电；领域状态可以复用这些动作而保持自身效果。

`manifest.json` 及每个图集 JSON 包含帧矩形、逐帧 RGBA SHA256、源文件校验、接触帧和
骨骼关键点。构建检查源文件与图集一致后，才将这套资源加入生产 SpriteFrames。
接触帧只用于显示同步，不触发伤害、格挡、随机选敌、音频或任何游戏规则。

生产 `actor.gd` 的 `combat_impact(hit_index, sequence="")` 允许已确认的命中把动作向前推进至对应
接触帧；它不倒播、不重启，也不会覆盖受伤或死亡。提供序列时，先绑定再判断段号，
因此无原生 Cast 触发的纯雷首批不会继承上一张牌的计数；单参数调用继续当前序列。
`resume_action(clip, hit_index, sequence="")` 由宿主在实际原生动作触发或确认的卡牌
伤害批次后调用：原动作仍播放时保留进度；已返回待机、受到伤害或被嵌套
动作覆盖时，从该段接触帧前 4 帧恢复。超过已有接触帧数量的第四／第五等实际段，
在新的原生触发到来时重用最后一段的短起手；重复或更旧的段编号不会重播。宿主为
每个原生 CardPlay 传入独立的视觉序列 ID，物理段与雷电批次分别使用 `:attack`／`:cast`
后缀，嵌套牌、混合伤害及下一张同动作牌的段号不会混用。
重放无需重新执行长蓄势或首段语音。死亡拒绝
新动作，普通动作结束后返回宿主当前指定的待机／领域／低血姿态。

## 重建与检查

在仓库根目录运行：

```sh
OPENBLAS_NUM_THREADS=1 python assets/animation/animations/combat/render_combat.py --jobs 4 --preview .local/combat-motion-preview
python -m unittest tests.test_combat_motion_assets tests.test_assets tests.test_asset_pack_cache
python tools/preview_combat_motions.py --godot /path/to/Godot-4.5.1-mono --dotnet /path/to/dotnet --display :93 --output .local/combat-motion-godot
```

前一条命令渲染既有骨骼绘制部件，并拒绝任何空帧或碰到画布边缘的帧。后一条命令
用 Godot 4.5.1 的真实 viewport 渲染生产场景、生产 `actor.gd` 和逐帧资源，输出动作
对照图、视频与生命周期检查结果。捕获使用固定 1440×1080 SubViewport，并对每帧的
标题和 14 个标签区域做一致性检查，避免窗口尺寸变化造成裁切。它不加载 StS2，不等于游戏内、联机或打牌验收；
这些边界需要在对应本体环境单独验证。
