# V5：独立 Godot 美术播放器与 STS2 接入源码

这里交付一个可用 **Godot 4.5.1 标准版**打开的独立播放器，以及面向 **STS2 / RitsuLib / C#** 的接入源码。播放器直接读取本仓库已经交付的角色图集、独立特效和音频；不需要游戏 DLL。`src/` 是 `integration_source_uncompiled`，本次没有将它编译成游戏 Mod，也没有宣称它通过游戏或联机测试。

## 先看实际资产

在 Godot 4.5.1 中导入本目录 `project.godot` 并运行。播放器默认从同仓库读取：

| 内容 | 路径 | 用途 |
| --- | --- | --- |
| 无内嵌特效角色图集 | `../animations/clean/manifest.json` | 26 个动作/变体、940 帧；优先用于游戏接入 |
| 独立特效 | `../vfx/manifest.json` | 40 组、1070 帧；按实际源/目标坐标播放 |
| 音频 | `../audio/manifest.json` | 54 个逻辑 cue；47 个音频文件 |
| 动作音效时序 | `../audio/action_cues.json` | 每动作进入事件和一次性时间点，不在每帧重播 |
| 卡牌演出语义 | `../vfx/card_vfx_bindings.json` | 卡牌→演出映射，是本项目契约，不是游戏原生 API |
| 角色界面与状态图标 | `../ui/manifest.json`、`../vfx/icons/manifest.json` | 14个角色UI PNG；16组符号的4尺寸PNG与SVG |

播放器的“Sync SFX + effects”默认开启。角色动作、特效和音频也可分别选择。兽化传递与卡牌效果指向手牌示意位置，普通攻击指向战斗目标；受击/死亡相关命中特效指回角色。暂停身体动画会暂停尚未触发的动作事件；已经开始的独立效果/声音继续自己的生命周期，需一起停止时使用 “Stop all loops / FX”。这是美术检查工具，不模拟战斗规则。

Godot 4.5.1 的无窗口资产检查：

```bash
godot --headless --path integration_sts2_v5 -- --self-test
```

该命令真实读取图集、构造 `SpriteFrames`、检查帧区与数量、定位末帧、解码所有逻辑声音入口，并测试实例拥有的循环音效/特效清理。结果写入 `reports/godot_self_test.json`。如果运行环境的用户数据目录不可写，可先设置 `XDG_DATA_HOME` 到一个可写目录。报告中的输入 SHA-256 绑定运行时读取的 manifest；输入在检查期间发生变化则失败。

本轮已用官方 Godot 4.5.1 实际完成上述检查，最终 C 的 26 动作 / 940 帧、40 组特效 / 1070 帧、54 个声音入口通过。成品资源包位于 `../exports/VolibearArt_v5.pck`，已在另一个没有解包资源的空工程中实际挂载，并解码角色图集、特效、音频、14 张角色界面纹理和 16 组状态符号。详细结果与边界见 [VERIFICATION_STATUS.md](reports/VERIFICATION_STATUS.md)；这些结果没有扩展为 C# 编译或 STS2 游戏内验证。

## 将资源放进 Godot / MegaDot 工程

在目标 Godot 工程中创建一个**空的** `VolibearArt` 目录，运行：

```bash
python3 integration_sts2_v5/stage_assets.py --output /absolute/path/to/YourProject/VolibearArt
```

脚本复制运行时需要的 26 张角色图集、40 张特效图集、各自 JSON、Ogg、事件清单、角色UI和状态符号。它强制选择 `animations/clean`，不会把带预览特效的图集当作独立特效底图。WAV 母版、原始逐帧 PNG、审核截图继续保留在作者仓库，无需全部塞进运行时 PCK。目标目录非空时脚本拒绝覆盖，以免旧文件混入。

打开目标工程，让引擎导入 PNG/Ogg，再使用与游戏匹配的 MegaDot/ Godot .NET 导出 PCK。JSON 要作为额外资源包含，PNG/Ogg 应通过正常资源导入。当前模板 `export_presets.cfg` 可用于本独立工程的资源包试验，但它不注册 STS2 角色。游戏 Mod 通常还需要程序集、Mod manifest 和角色/卡牌模型，不能把此目录直接改扩展名当游戏 Mod。

也可以用本交付的完整脚本执行隔离 staging、真实引擎导入、资源 PCK 导出与另一个空工程的挂载验证：

```bash
python3 integration_sts2_v5/build_asset_pack.py \
  --godot /absolute/path/to/Godot_4.5.1 \
  --output /absolute/path/to/exports/VolibearArt_v5.pck
```

脚本不覆盖已有输出、不改作者图集，所有导入缓存均写入临时工程。成功后输出 `.pck`、`.report.json` 和 `.build.log`，包括输入 manifest/脚本/成品 SHA-256。验证工程不允许存在解包后的 `VolibearArt`，所以不能意外从本机原图回退读取。PCK 只放命名空间资源及引擎导入元数据，不打入C#样例、审核图或聊天资料。此资源包仍不等于已注册角色的 Mod。

## C# 文件职责

| 文件 | 实际职责 |
| --- | --- |
| `src/VolibearSpriteFrames.cs` | 图集加载、26 序列校验、RitsuLib `AnimatedSprite2DBackend` 状态机、领域/低血量待机、临时兽化姿态 |
| `src/VolibearCueAudio.cs` | 按 cue 加载音频、冷却、同 cue 并发上限、循环去重、停止与销毁；显式接收游戏当前音量 |
| `src/VolibearVfxPlayer.cs` | 透明特效图集、源/目标定位、循环去重、token 停止、实例清理 |
| `src/VolibearPresentationController.cs` | 一次已提交动作的事件调度、动作序号去重、中断取消、退出清理 |
| `src/VolibearUiAssets.cs` | 已交UI纹理到实际RitsuLib槽位的映射；不会把PNG当作场景/转场材质 |
| `src/VolibearNativeAudioAssets.cs` | 可选的原生5个角色音效槽映射，利用BaseLib已有资源音频桥；宿主须与时间线声音去重 |

源代码以 RitsuLib commit `772f280964f2efc7c7e2f29fc59844e68616dd57` 的实际 API 为依据。依赖 `.NET 9`、`GodotSharp 4.5.1` 和用户实际游戏程序集。没有附带缺失 DLL、虚构游戏测试或伪造编译产物。接入人员须按目标游戏/框架版本编译，并完成下述宿主边界。

## 宿主需要明确提供的内容

详见 [HOST_HOOKS.md](docs/HOST_HOOKS.md)。关键是：游戏模型负责结算、目标、随机数、存档和联机；表现层只消费已经提交的事件。兽化手牌必须把效果终点放在被转化的牌上，不能靠切换角色待机动画假装机制完成。领域退出、死亡、战斗结束和场景销毁时需停止由该实例创建的循环效果与音频。

角色整张序列已经带正确的内部前后遮挡。运行时不要再拆开身体、腿、肩关节和辫子，也不要把新的特效层塞回身体贴图。图集 `pivot_px=[250,442]` 是本交付约定，不是所有 STS2 角色的统一尺寸要求。

研究证据、可选资源清单、音频来源状态见 `docs/`。Riot 官方语音没有混入本轮音频包；实际声音来源和许可在仓库的 `audio/` 文档中。

