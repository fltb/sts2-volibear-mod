# V5 接入工程与资源包实际验证记录

日期：2026-10-27。引擎：官方 Godot 4.5.1 stable，`f62fdbde1`。角色资源为最终 C；独立特效为最终冻结版本。

## 已实际完成

| 验证 | 实际范围 | 结果与证据 |
| --- | --- | --- |
| 原生 Godot 无窗口自检 | 26 个角色序列、940 帧；40 组独立特效、1070 帧；54 个逻辑音频入口 | 退出码 0，`godot_self_test.json` 中 `passed=true`、`failures=[]` |
| 动画资源组织 | 按实际图集矩形和时长构造 SpriteFrames，检查所有帧区，并将每序列定位至末帧 | 自检通过 |
| 两点特效定位 | counter_release、lightning_chain、反向 lifesteal 的作者锚点映射到源/目标；端点误差小于 0.01 像素 | 自检通过；读取每项元数据，不按名称假设同一方向 |
| 卡牌与地面定位 | 侵染到实际外部卡牌示意矩形内部；重击落在目标地面 | 自检通过；侵染保留卡牌外形比例，不把整张卡牌图拉成长束 |
| 生命周期 | 单次与循环音效/特效创建、循环去重、中断、停止和释放；释放后实际 Godot instance ID 失效 | 自检通过；不是只检查数组清空 |
| 最终 GDScript 解析 | 在吼叫波前偏移修正后对最终 `demo.gd` 执行 `--check-only --script demo.gd` | 退出码 0，无解析错误 |
| 运行资源 staging | 280 个必要运行资源，153,042,977 字节；输入和复制后 SHA 一致 | [VolibearArt_v5.report.json](../../exports/VolibearArt_v5.report.json) |
| 真实 PCK 导出 | 隔离临时工程导入 PNG / Ogg，包含 JSON，执行官方引擎 `--export-pack` | 退出码 0，保留成品和构建日志 |
| 隔离 PCK 挂载 | 在另一个空 Godot 工程挂载；禁止存在未打包的 VolibearArt 目录；实际解码导入纹理/音频 | `isolated_project=true`、`passed=true`、`failures=[]` |

PCK 挂载检查计数：26 张角色图集 / 940 帧，40 张特效图集 / 1070 帧，54 个音频入口，14 张角色界面纹理，64 张状态符号 PNG 和 16 个 SVG。JSON 内容与 staging 清单逐项对应。音频入口允许多个逻辑 ID 共用同一个声音文件，本包有 47 个不同 Ogg 文件。

本轮最终自检无错误和警告。PCK 构建的编辑器导入/导出阶段日志保留了运行环境禁止本地 TCP 监听的提示；相应进程退出码为 0，随后独立空工程的挂载与实际资源解码也通过。没有将这条环境日志隐藏或改写成游戏验证结果。

## 冻结输入与成品

下表路径相对于动画仓库根目录。

| 文件 | SHA-256 |
| --- | --- |
| `animations/clean/manifest.json` | `da8680ce0d2053a641f8e8e67133f7ad41dfb3159c22192427124345e92ce403` |
| `vfx/manifest.json` | `65eba1871f70793b79f971a38a97c8c5ba64370a7553214df9b795ca6e470b23` |
| `audio/manifest.json` | `d22297d0713fa40042e5c3897ec191660f8876bf87e6032aa8ba2a3a27f54be6` |
| `audio/action_cues.json` | `5ccc73d0638905c188996d540c1017821de582e0b72af6620502f9fa6e213505` |
| `exports/VolibearArt_v5.pck` | `c655c2044a16bd56a3bf442cecc35b47c38ca96ad797734063117560ce269739` |

成品 PCK 大小为 **126,933,504 字节**。其输入清单、导出脚本、实际命令和输出校验值还保存在同目录 `.report.json` 中；`.build.log` 是实际引擎输出。暂存工程和其导入缓存已清理，作者图集没有被覆盖。

## 明确的适用边界

`src/` 的 C# 是按已固定版本的 BaseLib / RitsuLib 源码写出的接入样例，状态仍为 `integration_source_uncompiled`。本环境没有目标游戏程序集，没有编译该 C#，也没有运行 STS2 或联机测试。PCK 是资源包，不会单独注册角色、卡牌、能力或同步游戏规则。

原生 Godot 自检证明的是资源能够读取、组织、定位和释放。游戏宿主仍需要提供已经结算的动作、实际目标和卡牌节点、当前音量、状态与生命周期边界，按目标游戏和框架版本编译接入源码，然后在该游戏版本中验证。这些接口责任列在 [HOST_HOOKS.md](../docs/HOST_HOOKS.md)，没有用不存在的游戏钩子代替它们。

动画身体结构的实际逐帧观察属于独立记录 [review_visual_A.json](../../reports/animation_revision_v5/review_visual_A.json) 与 [review_visual_B.json](../../reports/animation_revision_v5/review_visual_B.json)；音频来源和许可见仓库根目录 `audio/`。这些不同证据不互相冒充。
