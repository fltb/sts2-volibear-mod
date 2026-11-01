# 本地 Agent 任务：构建、实机验收并生成完整安装包

目标仓库：[fltb/sts2-volibear-mod](https://github.com/fltb/sts2-volibear-mod)，
当前工作分支 `codex/mode7-completion`，对应 [PR #1](https://github.com/fltb/sts2-volibear-mod/pull/1)。
要求是完整可玩的 Mod，范围见 [RELEASE_PLAN.md](RELEASE_PLAN.md)。

## 你需要完成的工作

先读 `AGENTS.md` 和 `LOCAL_WORKFLOW.md`，检查本地改动并保留。取得 PR 当前源码；
不要使用此前生成的 DLL/PCK，也不要把 main 的旧代码与 PR 资源混装。
定位已安装的目标游戏、Godot Mono 和 SDK，按下面的统一入口构建并验收。
生产代码和测试入口都已在仓库；遇到编译、接口或运行错误，要修真实错误后继续，
不能把缺失程序集检查、失败场景或未运行项目改成通过。

### 第一次执行

Windows，替换三个本机路径：

```powershell
python -B tools/local_delivery.py --game-dir "D:\SteamLibrary\steamapps\common\Slay the Spire 2" --godot "C:\Tools\Godot\Godot_v4.5.1-stable_mono_win64.exe" --dotnet "C:\Program Files\dotnet\dotnet.exe" --verify-release --audio-driver WASAPI
```

Linux，使用本机可用的 Godot 音频驱动：

```sh
python3 -B tools/local_delivery.py --game-dir "/path/to/Slay the Spire 2" --godot "/path/to/Godot_v4.5.1-stable_mono_linux.x86_64" --dotnet "/path/to/dotnet" --verify-release --audio-driver PulseAudio --display xvfb
```

完成路径预检后，本机配置会保存在 `.local/config.json`。后续同一机器执行：

```powershell
python -B tools/local_delivery.py --verify-release --audio-driver WASAPI
```

Linux 将音频驱动换为本机可用的值。`--verify-release` 固定完整表现检查；不能换成 Dummy
或 `cards` 模式冒充音频阶段已经执行。默认开放音频不需要下载 Riot 素材。

## 执行要求

1. 核对 StS2 **0.107.1 / 59260271**、Godot **4.5.1 stable Mono**、SDK **9.0.320**。
   工具固定 BaseLib **3.4.7**。版本不匹配时记录实际版本，不能删版本检查继续混用。
2. 完整发布必须生成同一源码的 DLL、PCK、JSON。普通 `dotnet build` 只更新 C#；
   图片、文本、场景或脚本改动需要完整资源导出。已有 `.sln` 可供 IDE 打开和定位代码。
3. `regression.py --require-native` 要求所有适用于本机的测试实际执行。另一操作系统的
   专属测试可以跳过；SDK/程序集/完整 Mod 缺失导致的跳过会使本地交付失败。
4. 单人用例和正常流程在同一后台实例内连续执行；真正的保存重启使用受控的
   prepare/resume；多人用两个独立原生进程和本地网络。不要逐牌重启游戏。
5. 不使用系统键鼠、Viewport 输入或按钮伪信号。所有真实出牌、目标与支付走原生队列，
   所有选择使用已有受控接口。不要直接调用 `OnPlay` 来冒充玩家出牌。
6. 测试用新建隔离资料目录和原生离线/本地网络环境。保持普通存档、Steam 云数据、其它 Mod
   与用户桌面不受影响。候选游戏进程运行期间，不替换其 DLL/PCK。
7. 用独立回执和磁盘数据判断结果：实际玩家身份、支付历史、牌堆、耗尽/生成、
   共享迎战机会、两个进程的状态、保存恢复前后关系。退出码 0 或截图存在不足以通过。
8. 遗物、动画、特效、遮挡和听感还需查看产出的图像/音频；资源可加载不等于美术已获人工批准。

## 失败后继续做什么

- **编译失败**：保存首个编译错误和对应签名，直接对照本机锁版程序集/API修复；
  不把替身测试改成同一个错误接口，不使用历史 DLL 继续。
- **原生安装/补丁失败**：读取最早的补丁安装异常，核对实际方法体与匹配数；修生产适配，
  补能复现问题的回归，然后重编当前候选。
- **牌效或流程失败**：保留该次 token、阶段、玩家/目标、队列和历史。诊断时可以缩小
  native suite 的案例列表；修复后完整 `--verify-release` 仍要通过。
- **网络或存档失败**：保留两端报告和隔离 profile，核对谁提交动作、原生排序、断开阶段及
  恢复的是哪个检查点。不要凭单进程双玩家夹具宣布网络正常，也不要手改存档使断言通过。
- **资源失败**：检查当前导出输入、实际 PCK 内容和 Godot 日志；保留批准母图，不改其
  哈希来掩盖产物不一致。
- **第三方 Mod 冲突**：先记录同场启用的版本、具体共享入口和失败动作；以原生命令和
  来源隔离修复。不要通过停掉沃利贝尔核心机制来获得通过。

## 交回什么

交回 PR/提交号、实际游戏和工具版本、执行命令、完整安装 ZIP 路径，以及：

- `artifacts/validation/regression.json` 中的实际通过/失败/跳过清单。
- 原生 suite、保存重启与多人 runner 打印的本次报告路径；失败时附相应日志和隔离 profile。
- 完整安装包内 `PACKAGE.json`，核对本轮 DLL/PCK/JSON 与实际验收候选一致。
- 尚未通过的项目及首个具体错误；人工视觉/听感另列。

完整安装包默认在 `.local/release/Volibear-0.1.0-StS2-0.107.1.zip`。
可选英文方案添加 `--audio-profile riot_en`，生成独立私有包；公开仓库只提交其来源、
处理工具和修复源码，不提交录音、游戏程序集、存档或单次运行日志。
