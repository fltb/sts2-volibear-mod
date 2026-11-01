# 原生后台验收与证据边界

当前构建和发布入口是 [LOCAL_WORKFLOW.md](LOCAL_WORKFLOW.md) 中的
`tools/local_delivery.py --verify-release`。本页说明它实际执行的测试、进程边界和失败判定。
当前维护环境缺少 StS2 **0.107.1 / 59260271**；当前源码的完整游戏引用编译和下述原生运行
结果均为 **`NOT_RUN`**。生产实现、测试源代码和本地可执行命令已经编写；缺少本体不能用来
省略实现，也不能把历史 DLL、替身回归或普通 Godot 资源预览写成当前游戏验收通过。

## 1. 完整入口与有限诊断入口

第一次运行时配置游戏、普通 Godot 4.5.1 stable Mono/.NET 和 SDK 9.0.320 的真实路径，
详见 [本地工作流](LOCAL_WORKFLOW.md)。已配置的 Windows 机器：

```powershell
python -B tools/local_delivery.py --verify-release --audio-driver WASAPI
```

Linux：

```sh
python3 -B tools/local_delivery.py --verify-release --audio-driver PulseAudio --display xvfb
```

使用本机实际可用的音频驱动。完整入口强制 `presentation-mode=all`：当前 DLL fresh build、
`regression.py --require-native`、PCK 导出与检查、归属部署、原生单进程批次、S2 跨进程恢复、
双端网络全部成功后才生成完整安装包。需要本体的测试跳过不算通过；另一操作系统专属检查
可以记录为跳过。`--verify-native` 只增加单进程批次，默认表现模式为 `cards`。

已部署同一候选后，可直接定位原生批次及恢复失败：

```powershell
python -B tools/native_suite.py --execute-native --use-deployed --verify-restart --presentation-mode all --audio-driver WASAPI --display background
```

Linux 把显示改为 `--display xvfb`，音频改为本机后端。只定位五阶段时可省略
`--verify-restart`；只检查牌面表现时可选 `--presentation-mode cards`，但这两个缩小范围的
结果都不能替代完整发布验收。多人诊断命令见第 6 节。

`native_suite.py` 要求显式 `--execute-native --use-deployed`，不会自行拿旧 DLL 替代构建，
也不会在导入模块或查看帮助时启动游戏。`--card-face-cases` / `--card-lifecycle-cases` 接受
`all` 或明确的逗号分隔用例；未知、重复、空用例在创建运行前被拒绝。

## 2. 进程与输入政策

| 批次 | 实际进程安排 |
| --- | --- |
| 五阶段及角色契约 | 一个无 Mod 退出对照；一个 Mod 游戏进程串行完成全部案例。独立案例之间原生退出房间/返回菜单并新开 run。 |
| S2 跨进程恢复 | 五阶段成功后，额外运行 prepare、resume 两个不同游戏进程，共用一个新建隔离 profile；复用刚才的新无 Mod 对照。 |
| 多人 | 另一个无 Mod 退出对照；两个同时存在的游戏进程，各有独立新 profile。每端在同一进程里完成建局、断线和加载存档重联。 |

Windows 的 `background` 创建未被选中的私有桌面，保留真实渲染且不切换用户桌面。
运行器不调用 `SwitchDesktop` 或 `SetThreadDesktop`；Job Object 和桌面句柄按归属释放。
Linux 的 `xvfb` 使用独立虚拟显示。当前入口拒绝普通前台窗口作为替代，不采用最小化抢焦点。

所有当前原生验收禁止 OS 键鼠、Viewport 输入、合成点击、按钮回调或按钮伪信号。
出牌使用真实 `PlayCardAction` / `ActionQueueSynchronizer.RequestEnqueue`、合法目标及原生支付，
选择使用下节限定的原生决策接口。不能用直接调用 `OnPlay` 或 AutoPlay 代替付费行为证明。
测试可为有限卡牌/多人行为案例显式布置夹具；普通 `product-flow` 则严格拒绝状态夹具。

原生批次默认总进程预算 3,600 秒 / 216,000 帧，上界分别为 14,400 秒 / 864,000 帧。
S2 prepare/resume 默认每个进程 300 秒 / 30,000 帧，可用 `--restart-timeout` /
`--restart-frames` 调整到允许范围。没有逐卡重启或无限重复选项。死亡、预算耗尽、缺少要求的
流程覆盖和缺回执都失败，不因为进程最终退出零就算通过。

## 3. 真实选择接口与卡牌奖励决策

`CardSelectCmd.UseSelector` 只在受控作用域内安装 `ICardSelector`，读取原生提供的候选，
检查玩家归属、最小/最大选择数量及候选身份，再交回合法选择。锁版接口的奖励返回值是
`CardRewardSelection`，不能沿用旧的 `CardModel?` 签名。

**仅安装 Selector 并不能驱动非 TestMode 的卡牌奖励。** 锁版 `CardReward` 会创建真实
`NCardRewardSelectionScreen`，其 `OptionSelected()` 等待原生屏幕决策，内部不查询 Selector。
因此普通流程只在隔离验收作用域内，给这个原始异步决策方法安装窄 Harmony prefix：

1. 保留原生奖励生成及真实选择屏幕，等屏幕完成初始化和一帧。
2. 从该屏幕实际 `_options` / `_extraOptions` 中选择，验证结果确实是本次候选的引用，返回其索引。
3. 由原生 `CardReward` 继续同步选择、加入永久牌组、记录历史及播放 VFX。
4. 完成或异常退出时撤销该 patch 和 selector。未开启隔离流程时保持原始方法。

这里没有调用按钮信号/回调，没有直接完成屏幕内部的 `TaskCompletionSource`，没有把卡手工
加入牌组冒充领取。独立 oracle 除检查声明，还核对候选成员身份、实际牌组增量和奖励结果。
正常流程另有两处锁版窄访问：调用原始 `NTreasureRoom.OpenChest` 房间任务，以及只读观察
`NRewardsScreen._isTerminal`。它们不模拟输入。

[真实 API 合同项目](../tests/native/native-flow-contract/Program.cs) 直接引用本机 `sts2.dll`
和 `GodotSharp.dll`，不用自建接口替身，核对 **18 项**元数据合同，包括奖励返回值、选择屏幕、
同步器、商店/地图/宝箱入口，以及 `PlayerCmd.EndTurn` 的真实 `void` 返回类型。
这只是绑定检查；游戏行为仍由下面的原生批次验证。

锁版控制流参考：[CardSelectCmd](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Commands/CardSelectCmd.cs)、
[CardReward](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Rewards/CardReward.cs)、
[NCardRewardSelectionScreen](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Nodes.Screens.CardSelection/NCardRewardSelectionScreen.cs)。
这些参考不替代用户安装程序集的实际绑定；仓库不复制游戏反编译原文。

## 4. 单进程的五个阶段及独立角色契约

协调器为 [NativeVerificationSuite](../src/Volibear/NativeVerificationSuite.cs)，独立汇总为
[native_suite_evidence.py](../tools/native_suite_evidence.py)。五个阶段的顺序固定：

| 阶段 | 实际覆盖与验收依据 |
| --- | --- |
| `card-faces` | 410 个有限案例，覆盖 178 个基础/升级牌面和约定分支；实际付费、目标、卡牌身份、牌堆、历史与独立期望。 |
| `card-lifecycle` | 48 个生命周期案例，覆盖回合、重演、选择、临时费用、身份与清理。 |
| `presentation` | 默认 `cards` 检查 356 个普通/Inspect 渲染视图；`actions` / `all` 增加动作和实际音频捕获，需明确非 Dummy 音频后端。 |
| `product-flow` | 用注册的沃利贝尔角色新建真实种子 run，核对正常起始状态；至少三场真实胜利、卡牌奖励、合法地图到达、休息及付金币买牌。独立重算动作/能量历史、候选与牌组差异、商店收费、治疗/升级及地图结果。 |
| `save-load-same-process` | 原生 SaveManager 写入、加载和 RunState/RunManager/NGame 恢复；核对真实磁盘 JSON、checkpoint 和清理。 |

`product-flow` 不注入测试卡、血量、金币，不用调试房间传送或强制胜利。选路基于实际地图，
战斗使用合法付费动作；事件和宝箱的原生异步任务按实际遇到的路径处理，嵌套战斗/奖励继续
由同一主循环服务。回执只报告实际经过的房间，不宣称每一种事件都被遍历。
死亡、超时、未达到三胜或缺少规定奖励/休息/商店覆盖都会失败。这是前期完整流程验收，
不是三幕自动通关证明。

此外，同一进程内的 [CharacterIntegrationProbe](../src/Volibear/CharacterIntegrationProbe.cs)
产生独立的 `CHARACTER_INTEGRATION_RESULT`，由
[character_integration_evidence.py](../tools/character_integration_evidence.py) 核对 token、PID
及内容，不增加或替代五阶段中的任何阶段：

- 四种原生手势 getter 的真实纹理解码、画布和不同像素摘要。
- `zhs → eng → zhs` 的真实语言重载及角色/Sea Glass 文本解析；恢复原语言。
- Architect 对话在第 0、1、25 次访问条件下的角色候选、重复性、说话者与实际文本。
- 原生 Dusty Tome 经 BaseLib 选择既有 R18、升级、原生卡/遗物 JSON 序列化与恢复。
- 五个专属无效原生 FMOD 键的窄过滤已安装；不把过滤存在当作可听音频通过。
- 前后库存实例、顺序和升级不变，临时创建的奖励从 run 卡状态清理。

角色契约保持在独立受控夹具中，与普通流程的新种子 run 分开。它不声称自然走完终局或
自然取得 Tome；手势技术检查也不构成人工视觉批准。当前手势已按用户反馈重画并替换第一版，
其来源与绘制指令保存在 UI 资产目录。

完整 `all` 表现模式的无 Mod 对照使用相同音频驱动。捕获只针对游戏输出；文件存在、峰值或
事件回执不自动等于听感合格。人工视觉/听感另行记录。

## 5. S2 跨进程原生恢复

`native_suite.py --verify-restart` 在上述单进程批次全部成功后调用
[save_load_pair.py](../tools/save_load_pair.py) 的 S2 `restart`：

1. prepare 在新建隔离 profile 中产生真实原生检查点，输出本次 token/PID、状态及磁盘证据后退出。
2. 运行器重新检查 prepare 原始回执、共同运行门和磁盘内容。任一失败均不启动 resume。
3. resume 由不同原生进程读取同一隔离 profile，经原生加载接口重建 run 和房间。
4. 独立 oracle 比对原始 JSON、永久牌组、恢复状态与清理，绑定两个真实 PID；Linux Xvfb 的
   包装器 PID 不能冒充游戏 PID，实际 exec 由 `native_child_exec.py` 写入专属回执。

这条路径不点击 Continue，也不使用旧 UI 的 Pause / Save-and-Quit 回调。
它验证游戏现有的房间入口 checkpoint，不把原生不保存的任意战斗帧变成自定义存档。
本次无 Mod 对照仅在当前调用内以实际结果复用；不接受旧报告文件注入成新的通过结论。
S2 两阶段沿用同一显示与音频后端。

## 6. 两端原生网络验收

部署当前候选后可单独运行：

```powershell
python -B tools/multiplayer_suite.py --execute-native --use-deployed --display background
```

Linux 改用 `--display xvfb`。默认每端 900 秒 / 108,000 帧；原生单步等待最多 90 秒。
两个游戏进程通过实际 ENet loopback 连接，游戏 checksum 与 replay writer 保持开启。
两端只提交各自拥有的卡，记录实际执行对象与历史；客户端的原始请求对象不作为执行成功证据。

七个阶段依次验证原生初始检查点、同时迎战、领域/雷伤所有权、兽化新牌身份、正常共同回合、
断线前确实用过的迎战机会，以及真正断线后重新进入原生存档大厅并恢复房间。
行为阶段显式布置有限原生夹具；双方状态、实际付费与敌人行动随后经生产逻辑和网络队列结算。
它们不能替代无夹具的单人普通流程。

共享目录仅协调准备就绪，不传输游戏动作、选择、卡牌或存档。原生 host 从磁盘载入 checkpoint，
客户端从游戏的 load-join 消息接收；恢复时保留原玩家身份。详情、逐阶段 oracle 和锁版 API
来源见 [MULTIPLAYER_ACCEPTANCE.md](MULTIPLAYER_ACCEPTANCE.md)。

锁版正式产品未接通运行中任意战斗帧热重连；本 Mod 沿用原生的**回菜单、重建保存大厅、
恢复房间 checkpoint**。本机 ENet 通过也不证明 Steam 传输、跨公网、远端选择界面或
原生 replay 文件的播放已经通过。

## 7. 隔离、运行错误和退出对照

每次创建新的隔离 user-data 目录，并只给子进程设置相应系统用户目录环境变量。
游戏以 `--force-steam=off` 启动，该参数在引擎参数层传入；隔离 profile 单独启用 Mod。
游戏内部检查实际 `user://` / 用户目录与运行器指定目录一致、Steam 未初始化，输出
`ISOLATION_OK steam=false`。普通设置、普通存档与云存档不参与验收。
游戏安装目录和部署文件仍共享；这是测试 profile 隔离，不是操作系统安全沙箱。

运行器按创建的 POSIX 进程组或 Windows Job Object 管理进程，超时只结束自己拥有的边界。
不要在原生批次或恢复对运行时重新部署候选。完整发布入口按顺序构建、部署、验收和打包。
部署标记保存在 `.local/deploy/`，不放进游戏扫描的 Mod JSON 目录；回收只操作归属可证且
未修改的 Volibear 文件，保留 BaseLib、其他 Mod 和存档。

成功必须同时满足原生语义回执和共同运行条件：

- 进程正常退出且没有超时；阶段顺序、token、真实 PID、内容和清理完整。
- `ERROR:`、`SCRIPT ERROR:`、`[ERROR]` 及 probe 错误回执中的运行时异常全部失败。
- Godot 退出时已知资源泄漏按本次无 Mod 对照的**资源类别**比较；数量波动不直接比较。
  新类别仍失败，不能通过删除日志或豁免整个错误类别来接受。
- 无 Mod 对照自身有运行时错误、非零退出或超时，后续验收不启动。
- 独立 oracle 检查原始历史、图像/音频或磁盘内容；单个 `passed=true`、退出零或旧报告不足以成功。

无 Mod 对照说明哪些退出噪声本体也有，不声称修复了引擎泄漏。它的帧预算是独立的短启动/退出
预算，不要求与长玩法批次相等；显示与需要验证的音频后端保持匹配。

## 8. 报告、未执行项与历史工具

| 报告 | 内容 |
| --- | --- |
| `artifacts/validation/regression.json` | 本次回归结果、跳过原因与必须执行但未执行的检查。 |
| `artifacts/headless/<run-id>/report.json` | 五阶段、独立角色契约及共同运行条件；同目录保留原始日志与表现产物。 |
| 同目录 `native-acceptance-report.json` | 单进程批次加 S2 的结果与进程数量；只有加 `--verify-restart` 时生成。 |
| `artifacts/save-load/<pair-id>/report.json` | prepare/resume 原始阶段报告、真实 profile 和实际磁盘比较。 |
| `artifacts/multiplayer/<pair-id>/report.json` | 两端报告索引、网络身份、状态比较、候选摘要和恢复证据。 |

报告、日志、隔离存档、游戏程序集和反编译原文不提交 Git。只有本次实际运行报告可以升级
对应候选的验证状态；本页描述实现范围，不填入旧版本通过数来代替新的运行。

旧 `native-run`、`native_run_pair.py`、UI catalog 及旧 S3 catalog 保存驱动仍包含历史界面自动化。
它们被排除在当前无输入的发布流程之外；不要按旧命令使用前台 `window`、按钮回调或合成
输入，也不要用旧 Continue/重启回执证明当前新牌身份、普通流程或 S2 已通过。
`headless.py` 保留早期有限诊断情景，其直接攻击/AutoPlay 基线仅证明自身小范围，不替代当前
真实付费和网络验收。当前命令、批准范围和接续工作分别以
[LOCAL_WORKFLOW.md](LOCAL_WORKFLOW.md)、[RELEASE_PLAN.md](RELEASE_PLAN.md)、[HANDOFF.md](HANDOFF.md) 为准。
