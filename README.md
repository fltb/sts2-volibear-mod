# 沃利贝尔 · StS2 Mod

以 BaseLib 接入的中文角色 Mod，包含 89 张卡牌、178 个基础/升级牌面、两件专属遗物，
以及迎战、领域、雷势、雷伤、兽化和配套角色动画、UI、VFX、双音频。
当前工作在 [PR #1](https://github.com/fltb/sts2-volibear-mod/pull/1) 的
`codex/mode7-completion` 分支，完整产品范围见 [交付标准](docs/RELEASE_PLAN.md)。

**当前源码已补齐本地构建与验收入口。维护环境没有目标游戏本体，当前完整 Mod DLL、原生
游戏流程和真实网络仍需在本机执行验证。** 独立回归、Godot 资源检查、原生引用检查、实际游戏
和人工视觉/听感分别记录；详细状态见 [实现清单](docs/IMPLEMENTATION_TODO.md) 与
[当前交接](docs/HANDOFF.md)。

## 本地构建与完整验收

| 依赖 | 固定版本 |
| --- | --- |
| Slay the Spire 2 | 0.107.1 / 59260271 |
| Godot | 普通 4.5.1 stable Mono/.NET |
| .NET SDK | 9.0.320 |
| BaseLib | 3.4.7，由工具获取并核对发行包 |
| Python | 3.10+ |

首次在仓库根目录执行，替换本机路径：

```powershell
python -B tools/local_delivery.py --game-dir "D:\SteamLibrary\steamapps\common\Slay the Spire 2" --godot "C:\Tools\Godot\Godot_v4.5.1-stable_mono_win64.exe" --dotnet "C:\Program Files\dotnet\dotnet.exe" --verify-release --audio-driver WASAPI
```

Linux 使用本机 Godot 音频后端和虚拟显示，例如：

```sh
python3 -B tools/local_delivery.py --game-dir "/path/to/Slay the Spire 2" --godot "/path/to/Godot_v4.5.1-stable_mono_linux.x86_64" --dotnet "/path/to/dotnet" --verify-release --audio-driver PulseAudio --display xvfb
```

入口核对版本，重新编译当前 DLL，执行严格回归，导出并检查完整 PCK，部署当前候选，
执行单进程原生批次、跨进程保存恢复和两个真实网络客户端。阶段失败即停止。
成功后安装包位于 `.local/release/Volibear-0.1.0-StS2-0.107.1.zip`。

路径保存后，Windows 后续只需：

```powershell
python -B tools/local_delivery.py --verify-release --audio-driver WASAPI
```

完整操作、较小的诊断入口、安装/卸载与音频切换见 [本地运行说明](docs/LOCAL_WORKFLOW.md)。
**交给本地 Agent 时，让它从 [LOCAL_AGENT_TASK.md](docs/LOCAL_AGENT_TASK.md) 开始。**

## Godot 与 Mod 打包

构建流程参考用户提供的 [ModTemplate Setup](https://github.com/Alchyr/ModTemplate-StS2/wiki/Setup)。
该模板允许以匹配版本的普通 Godot .NET 作为 MegaDot 的后备。本仓库采用固定的普通
Godot 4.5.1；游戏仍使用安装的本体引擎。`Volibear.sln` 可在 IDE 打开，C# 直接引用游戏程序集，
资产在独立 Godot 工程中导出。

完整发布包括 `Volibear.dll`、`Volibear.pck`、`Volibear.json`，三个文件放在同一 Mod 目录。
`tools/local_delivery.py` 负责这条发布链。图片、文本和场景有改动时必须重建 PCK；
单独编译 C# 只能更新 DLL。PCK 使用 `gl_compatibility` 和源码 GDScript，并在构建后实际
加载验证脚本、动画、卡图、UI、VFX 和音频。

## 内容与运行规则

- 初始 80 生命、3 能量，起始牌组为 4 打击、4 防御、霆爪、挺身迎战。
- 迎战执行真实敌人动作；同轮全队共享敌方行动机会，吸收和完成收益归发起者。
- 领域的敌方特殊贡献压制对全队生效；附雷、抽牌净化等本人收益按规则归属。
- 兽化先原生消耗材料，再在原牌堆生成有独立身份的 T01/T02；永久牌组不改写，
  原生耗尽、生成和满手规则照常执行。
- 多人状态沿游戏原生有序动作推进。正常存档与恢复沿游戏已有的检查点和加载流程。
  实际联网/重启结果以本地双进程验收报告为准。
- 运行初始化检查固定游戏版本。公共补丁采用来源隔离与贡献级适配，保留玩家自身效果；
  未知第三方私有直接写入仍有明确的来源诊断。

玩法权威为 [定稿规则](reference/bear-forge/docs/volibear/DEVELOPMENT.md)、
[卡表](reference/bear-forge/docs/volibear/CARDS.md) 和用户后续裁决。

## 美术与音频

当前资产为批准的 V7 卡图及四卡修订、V9 角色动画（26 序列、940 帧）、40 种 VFX。
两件遗物和能量界面已经按本轮要求更新；批准的角色母图与牌面继续保留。
四种多人手势参考 Riot 原模型与 StS2 原生贴图，使用手背视角、422×1200 长前臂比例和
简化笔触。源图、提示词和来源见 [手势资源记录](assets/animation/ui/source/multiplayer_hands/provenance.json)；
资源通过不等于用户视觉批准。

| 不灭狂雷 | 万古不灭 |
| --- | --- |
| ![初始遗物](src/Volibear/Presentation/icons/relics/big/lightning_heart.png) | ![升级遗物](src/Volibear/Presentation/icons/relics/big/storm_crown.png) |

默认 `open` 包含 47 个开放声音，映射 54 个声音事件。可选 `riot_en` 提供 9 条英文语音和
2 条有明确来源的技能音效，其余事件继续使用开放音频。完整交付命令加
`--audio-profile riot_en` 即可构建独立私有包；公开 Git 保留来源、映射和处理工具。
两方案都使用单个完整 PCK，具体说明见 [音频方案](assets/animation/audio/profiles/README.md)。

## 工程与检查入口

| 路径/命令 | 用途 |
| --- | --- |
| `src/Volibear/` | 原生内容、机制、表现与隔离验收入口 |
| `assets/cards/`、`assets/animation/` | 批准资产、导出与检查工具 |
| `python -B tools/regression.py` | 当前环境可运行的回归；报告明确列出跳过项 |
| `python -B tools/regression.py --require-native` | 本地引用检查；必需测试未执行即失败 |
| `python -B tools/local_delivery.py --verify-release --audio-driver DRIVER` | 完整构建、原生/重启/联机验收与打包 |
| `python -B tools/local_delivery.py --resources-only --godot GODOT --dotnet DOTNET` | 无本体环境的 PCK 构建与检查 |
| [HEADLESS_TESTING.md](docs/HEADLESS_TESTING.md) | 原生验收阶段、报告和进程边界 |

单人批次复用后台实例，出牌和选择走原生接口。测试不发送系统/视口输入，使用隔离资料目录，
保留普通存档和其它 Mod。`.local/`、`artifacts/`、游戏程序集与私有媒体不入 Git。

代码 GPL-3.0-only；原创资产与文档 CC-BY-SA-4.0。第三方例外及作者信息见
[LICENSING.md](LICENSING.md)。安装包包含适用许可与音频来源。
