# 本地构建、完整验收与打包

从 PR #1 的当前源码开始，在仓库根目录运行 `tools/local_delivery.py`。
需要交给本地 Agent 时直接使用 [LOCAL_AGENT_TASK.md](LOCAL_AGENT_TASK.md)。
交付范围由 [RELEASE_PLAN.md](RELEASE_PLAN.md) 定义。

## 1. 工具和版本

| 项目 | 要求 |
| --- | --- |
| 游戏 | StS2 **0.107.1 / 59260271**，完整已安装目录 |
| Godot | 普通 **4.5.1 stable Mono/.NET**，完整解压 |
| .NET | **SDK 9.0.320**；`global.json` 固定选择 |
| Python | **3.10+**；Windows 建议 python.org 发行版 |
| BaseLib | **3.4.7**；工具下载并核对固定发行包摘要 |
| Linux显示 | 完整表现验收使用有硬件 GPU 的 `--display window`；`xvfb` 仅作有限诊断，不以软件渲染替代硬件验收 |
| 音频 | 完整表现验收需要本机可用的 Godot 音频后端；Dummy 不计此项通过 |

工具来源：[Godot 4.5.1](https://godotengine.org/download/archive/4.5.1-stable/)、
[.NET 9](https://dotnet.microsoft.com/en-us/download/dotnet/9.0)、
[Python](https://www.python.org/downloads/)、
[BaseLib 3.4.7](https://github.com/Alchyr/BaseLib-StS2/releases/tag/v3.4.7)。

用户提供的 [ModTemplate Setup](https://github.com/Alchyr/ModTemplate-StS2/wiki/Setup)
说明匹配版本的普通 Godot .NET 可作为 MegaDot 后备，发布时应同时生成 DLL、PCK 和 JSON。
此仓库固定上述工具组合，C# 直接引用游戏程序集，独立资源工程使用 `gl_compatibility`，
GDScript 以源码打包，随后实际挂载 PCK 并核对四个运行脚本字节。
`Volibear.sln` 可用于 IDE；完整交付仍走这里的发布入口。

## 2. 第一次执行

Windows，在游戏没有运行时执行，替换三个实际路径：

```powershell
python -B tools/local_delivery.py --game-dir "D:\SteamLibrary\steamapps\common\Slay the Spire 2" --godot "C:\Tools\Godot\Godot_v4.5.1-stable_mono_win64.exe" --dotnet "C:\Program Files\dotnet\dotnet.exe" --verify-release --audio-driver WASAPI
```

Linux：

```sh
python3 -B tools/local_delivery.py --game-dir "/path/to/Slay the Spire 2" --godot "/path/to/Godot_v4.5.1-stable_mono_linux.x86_64" --dotnet "/path/to/dotnet" --verify-release --audio-driver PulseAudio --display window
```

音频驱动名称使用本机实际可用的值。路径检查成功后保存到 `.local/config.json`，
以后 Windows 同一机器只需：

```powershell
python -B tools/local_delivery.py --verify-release --audio-driver WASAPI
```

Linux 换为对应音频驱动即可。`--verify-release` 自动选择 `presentation-mode=all`，
并要求真实音频后端；不能把 `cards` 或 Dummy 检查当作完整表现验收。

## 3. 这条命令执行的阶段

1. 核对 SDK、Godot、游戏版本/构建号、程序集与执行程序。预检旧源码覆盖清单。
2. 保存有效本机配置，准备固定 BaseLib；需要 Pillow 时在仓库内建隔离 Python 环境。
3. 重新编译当前源码 DLL。构建失败时停止，不沿用此前 DLL。
4. 执行一次 `tools/regression.py --require-native`。需要游戏引用的检查必须实际执行；
   另一操作系统的专属检查允许跳过，仍记录在报告中。
5. 导入、导出并检查完整 PCK：26 动画/940 帧、178 牌面、UI、40 VFX、音频与运行脚本。
6. 部署当前 DLL/PCK/JSON 与固定 BaseLib。已有文件按归属和摘要核对，不接管其他文件。
7. 一次无 Mod 退出对照后，在一个后台游戏实例内执行角色契约、牌面、生命周期、表现、正常流程和同进程恢复。
8. 同一候选进行 S2 跨进程 prepare/resume，复用刚才的无 Mod 对照。
9. 再执行两个真实 ENet 客户端的多人批次，包含独立无 Mod 对照、断开与原生检查点重联。
10. 只有前述阶段都成功才生成完整安装 ZIP，附 DLL/PCK/JSON、BaseLib、许可、安装说明与摘要清单。
11. 在专用最小本体文件副本内，对该 ZIP 自动执行安装、同包更新、卸载，核对其他 Mod/存档哨兵、BaseLib 和本体文件摘要不变；失败不打印成功交付。
12. 无论成功失败，`.local/release-acceptance/run-*/summary.json` 和 `summary.md` 汇总 A1–A9 状态、失败原因及最终包摘要。自动检查不冒充人工听感或审美认可。

正常验收只运行这条命令并读取最终报告；失败才修复、重跑，不需要 Agent 手动操作游戏。隔离profile固定 `vsync=off`、`fps_limit=60`；POSIX窗口启动30秒后每10秒采样，连续3次低于10FPS自动失败，避免异常低帧率长跑。该设置不修改日常存档，也不改变游戏时间倍率。

Windows 使用未切到前台的私有桌面；Linux 完整验收使用已验证 GPU 的窗口路径。
窗口输入防护须经短批验证后再跑全套；最新状态见交接，不把普通窗口等同于独立桌面。
单人批次不会逐卡重启，
真正的磁盘恢复使用两个进程，多人使用同时存在的两个进程。所有测试使用新建隔离 profile，
不发送系统键鼠、Viewport 输入或按钮伪信号，不读取普通/云端存档。

## 4. 原生检查究竟覆盖什么

| 阶段 | 实际检查 |
| --- | --- |
| character-integration（独立回执） | 同进程先检查 4 个角色手势、语言重载后的真实文本、Architect 对话、DustyTome 及既有 R18 的原生 JSON 往返；物品栏身份不变 |
| card-faces | 410 个有限案例，含 178 牌面与约定分支；真实付费动作、身份、牌堆和独立期望值 |
| card-lifecycle | 48 个案例，检查回合、重演、临时费用、选择和清理 |
| presentation | 356 个普通/Inspect视图；完整模式另检查动作与实际音频捕获 |
| product-flow | 原生正常起始角色/牌组，在真实 run 中完成至少 3 场战斗、奖励、地图、休息、商店购买；死亡、超时或缺少要求的房间失败 |
| save-load-same-process | 原生 SaveManager 写入与加载，核对真实磁盘检查点和恢复状态 |
| S2 restart | prepare 退出后，由不同原生进程恢复同一隔离存档，校验两阶段身份和磁盘内容 |
| multiplayer | 两个原生网络进程：有序付费动作、竞争共享迎战、领域持有者、兽化新牌身份、回合推进、真实断开和原生检查点恢复 |

这些是有限的可执行验收。正常流程批次覆盖前期流程，不是完整三幕自动通关证明。
多人验收是本机 ENet 真实网络，Steam 平台传输、跨公网环境和人工观感分别评价。
没有把自建战斗快照格式加入生产 Mod；保存与恢复沿用目标游戏提供的入口。

原生选择器的 `CardRewardSelection` 返回类型及正常流程调用的关键接口，另由
`tests/native/native-flow-contract` 的 18 项合同对本机实际 `sts2.dll` 核对。
替身测试不作为这些接口绑定已经通过的证据。

普通选牌使用 `CardSelectCmd.UseSelector`。该锁版的奖励屏不读取普通 selector，
因此正常流程验收在它原始的 `OptionSelected` Task 决策边界提供实际候选索引；
屏幕创建、同步、授予、历史和 VFX 仍走原生代码，受控作用域结束时撤销适配。
角色契约在自然 run 之前的专用夹具执行，不把可能消耗 RNG 的检查混进正常初始状态。

## 5. 输出与成功判定

默认安装包：

```text
.local/release/Volibear-0.1.0-StS2-0.107.1.zip
```

| 输出 | 内容 |
| --- | --- |
| `artifacts/validation/regression.json` | 实际通过、失败、报错、跳过与未执行的必需检查 |
| `.local/asset-build/<id>/` | 本次 Godot 导入、导出、资源/脚本/特效/音频日志 |
| `artifacts/headless/<run-id>/report.json` | 单进程原生批次、隔离与运行时检查 |
| 同目录 `native-acceptance-report.json` | 单进程批次与跨进程恢复的合并结果 |
| `artifacts/save-load/<pair-id>/` | prepare/resume 的报告、进程身份和保留的隔离 profile 位置 |
| `artifacts/multiplayer/<pair-id>/report.json` | 两端报告索引、逐阶段断言、候选摘要与网络状态 |
| ZIP 内 `PACKAGE.json` | 包内实际文件的版本、依赖来源、逐文件 SHA-256 |

入口末尾的 `INSTALLER BUILT:` 表示本次所选阶段成功后生成了包。
完整验收还应看到原生与多人报告 `status=passed`，所有必需 checks 为 true。
缺阶段、重复/旧回执、错误 PID、运行时异常、磁盘不一致或两个客户端分歧都会失败。
没有 Git 的源码覆盖目录仅将来源元数据记为不可用，其他检查继续生效。

日志和报告保留在忽略目录，供本地 Agent 定位。不要手改报告或存档来使失败变绿。
任何修复后的最终包应重新执行完整命令。

## 6. 较小的入口

| 命令 | 用途 |
| --- | --- |
| `python tools/local_delivery.py --doctor` | 检查本机路径和版本，不构建/部署 |
| `python tools/local_delivery.py` | 当前 DLL、严格引用回归、PCK 与安装包；不执行原生游戏 |
| `python tools/local_delivery.py --verify-native` | 增加默认单进程原生批次；默认只做卡面表现 |
| `python tools/local_delivery.py --verify-release --audio-driver DRIVER` | 完整构建及本节全部原生/恢复/网络阶段 |
| `python tools/regression.py` | 无本体环境的可用回归；明确列跳过项 |

已部署同一候选后，定位单人/重启失败：

```sh
python tools/native_suite.py --execute-native --use-deployed --verify-restart --presentation-mode all --audio-driver DRIVER
```

定位多人失败：

```sh
python tools/multiplayer_suite.py --execute-native --use-deployed
```

两个命令都使用本机配置和默认私有显示模式。`native_suite.py` 支持明确的
`--card-face-cases` / `--card-lifecycle-cases` 子集用于定位，子集结果不能替代完整验收。
详细进程和边界见 [HEADLESS_TESTING.md](HEADLESS_TESTING.md)。

只有 Godot 和 SDK 时：

```sh
python tools/local_delivery.py --resources-only --godot "/path/to/Godot4.5.1Mono" --dotnet "/path/to/dotnet"
```

此命令生成并验证 PCK，不生成 Mod DLL 或完整安装包，不写半份游戏配置。

## 7. 音频、安装与旧源码包

默认 `open` 已包含完整开放音频，不需要 FFmpeg。完整命令加 `--audio-profile riot_en`
会使用可选英文来源；若准备文件已通过摘要校验就复用，否则需要 FFmpeg/ffprobe 和网络。
私有包输出到 `.local/release/*-riot_en-private.zip`，两方案均使用一个完整 PCK。
来源和回退表见 [音频说明](../assets/animation/audio/profiles/README.md)。

玩家安装与卸载见 [INSTALL_ZH.md](INSTALL_ZH.md)。最终 ZIP 的研发隔离验收使用
`python tools/package_lifecycle.py --package <ZIP> --game-dir <隔离游戏副本> --action install`：
默认仅检查/规划，加 `--execute` 才落盘；随后以 `update`、`verify`、`uninstall` 验证生命周期。
`--save-sentinel <存档>` 可重复指定要保持字节不变的文件。拒绝不明归属开发部署，不覆盖其他 Mod。
安装/更新异常会恢复本工具已写入的文件和原始归属状态；如外部改动导致不能安全回滚，保留
报错路径中的 `volibear-recovery-*/RECOVERY.json` 和旧字节供恢复。此机制不是断电/强杀的多文件原子提交。
不要删除恢复备份或用失败的新清单认领旧文件；成功卸载只删匹配归属的三个 Mod 文件，不卸 BaseLib。

研发部署回收使用
`python tools/dev.py undeploy`，只删除归属可证且未修改的 Volibear 文件，保留 BaseLib 和其他数据。

若此前使用源码覆盖 ZIP，旧文件删除清单在 `.local/delivery/obsolete-files.json`。
入口仅删除路径和摘要均匹配的废弃文件；本地修改过的旧文件保留并报告冲突。
通过 Git 更新则由 Git 记录正常删除，不需要覆盖清单。

## 本次维护环境的证据边界

独立生产逻辑、真实 Harmony、普通 Godot 的两套资源构建可在维护环境执行。
2026-11-03，当前源码候选已完成统一完整发布门禁：实际编译与资源验证、全部单机批次、跨进程冷恢复、两端ENet，以及最终ZIP的安装、同包更新、卸载与字节核对。
最终包与报告入口见 [HANDOFF.md](HANDOFF.md)。人工听感、Steam传输及跨公网体验尚未执行。
