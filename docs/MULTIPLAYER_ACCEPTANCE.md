# 多人、存档和断线恢复验收

本 Mod 的生产玩法使用原生有序动作、原生玩家选择同步、原生卡牌身份与原生房间存档。这里的双端入口已实现有限验收的全部阶段；本会话没有游戏本体，因此 **原生两端运行结果仍为 `NOT_RUN`**。Python 反例测试和 C# 适配器测试的通过不能替代这项结果。发布检查必须在用户本地运行此入口并保留它生成的报告。

## 本地运行

先通过 `tools/local_delivery.py` 完成锁版构建、PCK 打包和部署。入口使用该流程写入的 `.local/config.json`，也可显式加 `--game-dir`。

Windows：

```powershell
python tools/multiplayer_suite.py --execute-native --use-deployed --display background
```

Linux：

```bash
python tools/multiplayer_suite.py --execute-native --use-deployed --display xvfb
```

整个批次使用一个独立无 Mod 退出基线，以及同时存在的两个游戏进程。主机和客户端各使用一个新的隔离 profile，禁用 Steam，两端通过游戏自带 ENet 在 `127.0.0.1` 上连接；每端在同一进程里完成新局、断线、回主菜单和多人存档恢复。默认每端 900 秒总进程上限、108000 帧退出上限，单阶段最多等待 90 秒。没有逐用例重启，没有键鼠、Viewport 输入、按钮信号或伪造点击。

退出码 `0` 仅表示该次报告所有门禁通过；`1` 表示原生进程或证据失败；`2` 表示参数、环境、基线或启动前条件不满足。最终控制台打印 `report` 的绝对路径。完整报告位于 `artifacts/multiplayer/<run_id>/report.json`；每端的原始日志、独立 profile 和 PID 回执保存在对应的 `artifacts/headless/<run_id>-host|client/`。日志和存档属于本机证据，不提交到 Git。

## 实现的七个阶段

| 阶段 | 真正执行的原生路径 | 独立检查 |
|---|---|---|
| `native-checkpoint` | `NetHostGameService.StartENetHost`；客户端 `JoinFlow.Begin(ENetClientConnectionInitializer, SceneTree)`；`StartRunLobby` 两端就绪；`NGame.StartNewMultiplayerRun`；`RunManager.EnterMapCoord` | 两个原生玩家 ID `1/2`、两个独立 OS PID、实际 ENet transport、原生 checksum 和 replay writer 均开启；原生 `current_run_mp.save` 存在；记录真实起手状态 |
| `simultaneous-engage` | 两端只提交各自拥有的 B04，均走 `ActionQueueSynchronizer.RequestEnqueue(new PlayCardAction(...))` | 两次实际付费、两条实际执行回执；共享敌人只行动一次；起始遗物只给实际先完成迎战的发起者抽一张；两端完整快照一致 |
| `owner-scoped-domain-lightning` | 主机付费 C05，客户端付费 B03 | 领域轮数为 `[1, 0]`，各持有者雷伤批次计数为 `[1, 1]`；客户端不会继承另一名玩家的攻击附雷；两端能量、效果与状态一致 |
| `native-beast-identities` | 两端各付费 R29；生产 `BeastForms` 经 `CardCmd.Exhaust` 和 `AddGeneratedCardToCombat` 创建实体 | 四个材料真实消耗、四个原生生成历史；每名玩家的材料与 T01/T02 使用四个不同 combat-card ID；升级和共享下一次费用优惠保留；新卡无 `DeckVersion`；两份永久牌组不变 |
| `normal-turn-boundary` | 每端各调用自己玩家的原生 `PlayerCmd.EndTurn` | 原生共同结束回合；已经提前使用的敌人行动不再重复；下一正常轮迎战恢复；领域在正常起手抽牌后到期；雷伤计数归零 |
| `engage-before-disconnect` | 下一轮再次提交两端 B04 | 确实存在已经使用的共享机会，随后才进行真实断线；防止用全新空状态冒充恢复验收 |
| `native-checkpoint-rejoin` | 客户端真实 `NetClientGameService.Disconnect`；主机观察 peer 数降为零；原生清理；主机 `LoadAndCanonicalizeMultiplayerRunSave(1)`；新建 `LoadRunLobby`；客户端重新 `JoinFlow.Begin`，由主机发送原生 load-join 存档；`RunState.FromSerializable`、`RunManager.SetUpSavedMultiplayer`、`NGame.LoadRun` | 保留原玩家 ID；恢复原磁盘房间断点的完整状态；迎战账本没有旧机会残留；不是第二端另开一个自己的单机存档；检查原生磁盘写回与最终清理 |

行为用例使用显式受控 fixture：在保留第一间真实地图战斗的磁盘检查点后，两端通过原生调试入口进入 `SlimesWeak`，以相同顺序移动手牌、创建待测试卡牌、设置测试能量/敌方 HP，并选择原生小叶史莱姆的原始 `TACKLE_MOVE`。付费出牌和敌方行动随后完全经过生产实现与原生网络队列。受控房间及之后的动作不得覆写初始检查点；这由原始磁盘 SHA-256 验证。它测试跨端玩法和恢复机制；正常全流程通关由独立产品流程入口负责。

共享目录只存放带当前 pair、阶段、角色、PID 的“已准备”标记。它不传输游戏动作、存档、卡牌选择或双方玩法状态。实际输入经过 ENet，实际磁盘存档只在主机读取，客户端通过原生 load-join 消息取得它。两端日志中的状态在事后交给 Python 对照，不能用于驱动另一端。

## 0.107.1 的真实恢复边界

本次核对使用公开反编译参考 `zhiyue/sts2-rl-agent` 的固定提交 `5d874e855ae1d0550d5c30416fadd7dbb0d133b7`。该提交的 [GAME_VERSIONS.md](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/GAME_VERSIONS.md) 明确标注游戏 `v0.107.1`、release commit `59260271`。这些是 API/控制流参考；项目不复制或分发游戏源码、游戏程序集或游戏资源，本地仍须以用户安装的锁版程序集编译运行。

精确控制流如下：

1. [JoinFlow.Begin](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Multiplayer.Game/JoinFlow.cs) 根据主机报告的 `RunSessionState` 选择新大厅、载入大厅或 `AttemptRejoin`。`NetService` 在 `Begin` 内才创建，`NetServiceUpdateLoop` 使用传入的真实 `SceneTree`。不能在调用前读取服务，不能向这个锁版接口传空 `SceneTree`。
2. [RunLobby.HandleClientRejoinRequestMessage](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Multiplayer.Game.Lobby/RunLobby.cs) 能给原名册玩家返回 `ClientRejoinResponseMessage`。它调用 [RunManager.GetRejoinMessage](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Runs/RunManager.cs)，后者打包 `ToSave(null)` 和 `NetFullCombatState.FromRun(...)`。消息类型存在不等于原生产品已经实现热恢复。
3. 真正消费 `JoinResult` 的 [NJoinFriendScreen.JoinGameAsync](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Nodes.Screens.MainMenu/NJoinFriendScreen.cs) 在 `InLobby` 和 `InLoadedLobby` 分支初始化对应原生界面；在 `Running` 分支创建 `NetError.RunInProgress` 错误提示并断开。该分支不恢复模型，也不调用动作重放。
   另一个调试消费者 [NMultiplayerTest.JoinToHost](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Nodes.Debug.Multiplayer/NMultiplayerTest.cs) 的 `Running` 分支明确抛出 `NotImplementedException`，消息为“Run re-joining has yet to be implemented!”。同文件的 `RunReplay` 是独立的 `.mcr` 回放入口：它调用 `SetUpReplay`、恢复动作/选择等 ID 起点并逐条执行 `CombatReplayEvent`；`JoinToHost` 不调用这个回放入口。
4. [NetFullCombatState](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Entities.Multiplayer/NetFullCombatState.cs) 提供状态采集、网络序列化、反序列化、匿名化与诊断输出；它没有把诊断记录还原为正在执行战斗的方法，消息也不携带完整动作重放序列。不能把它的名字当作任意战斗帧保存/恢复能力。
5. 本验收采用实际可用的 [LoadRunLobby](https://github.com/zhiyue/sts2-rl-agent/blob/5d874e855ae1d0550d5c30416fadd7dbb0d133b7/decompiled/MegaCrit.Sts2.Core.Multiplayer.Game.Lobby/LoadRunLobby.cs) 路径：先保存的房间断点，再重新建大厅、原玩家加入、原生 `SetUpSavedMultiplayer` 和 `NGame.LoadRun`。原生 `LoadIntoLatestMapCoord` 重新进入该房间。它不是继续原来已经打出的那一串战斗动作，也不是从任意暂停帧继续。

因此，**针对锁定游戏版本，交付的恢复承诺是断线后重开原生多人存档大厅并恢复房间检查点**。没有把游戏原生尚未接通的运行中热重连补成另一套网络协议。Steam 传输、跨机器网络、远端选择界面和原生 replay 文件的播放也不由这条 loopback 入口证明。

### 原生保存写回的允许变化

多人文件名来自 `RunSaveManager.multiplayerRunSaveFileName`，为 `current_run_mp.save`；不能误用单机 `current_run.save` 和 `LoadRunSave()`。主机走原生 `SaveManager.LoadAndCanonicalizeMultiplayerRunSave`，客户端走主机的原生载入消息。

`RunManager.CanonicalizeSave` 会刷新 `save_time`；`SetUpSavedMultiplayer` 在主机调用 `IncrementNumReloads`。证据校验只允许这两个变化，以及已经锁定核实的 `SerializableMapPoint.can_modify` 缺省恢复。时间必须落在实际 canonicalization 调用的 UTC 秒边界内；其他 JSON 字段逐项严格比较，永久卡牌、遗物、随机状态等不能被“忽略存档字段”的宽松比较掩盖。

## 生产状态审查

| 状态 | 生产归属与生命周期 | 保存/多人的处理 |
|---|---|---|
| 迎战共享机会 | `EngageOpportunityLedger`，按战斗对象、敌人对象、正常轮编号；首次 await 前同步预留 | 所有玩家共享同一敌人机会；`CombatSetUp`、`CombatEnded`、原生 `CombatManager.Reset(bool)` 清理；恢复房间后从原生动作重新产生 |
| 迎战吸收窗口 | `AsyncLocal` 窗口带战斗 generation、轮次、发起者 | 旧异步 continuation 必须通过当前战斗/generation/轮次检查；不能把旧局格挡吸收或完成奖励带进新战斗 |
| 雷伤批次/监听器 | 每战斗、每持有者的 `LightningBatches` scope | 正常轮/玩家回合独立计数，原生重置关闭旧 scope 和订阅；不以本地玩家 UI 身份决定效果 |
| 原生持久卡能力 | 生产 power 实例及内部状态，每个部署实例独立 | 在实际有序动作中部署和结算；房间重开时按原生房间流程重新生成，不保存假中战斗快照 |
| 永久牌组/升级/遗物 | 原生 `SerializableRun` 及 BaseLib 注册的模型 | 走原生保存；兽化只消耗战斗材料并生成独立 T01/T02，不替换永久牌组实体 |
| 起始/升级遗物回合限制 | 战斗引用和持有者回合时钟 | 新战斗引用自然重置一次性判定；双端原生动作保持相同结算顺序 |

此次审查没有证实必须新增生产自定义网络协议或自定义中战斗保存格式的缺口，因而没有添加这两类机制。若未来切换游戏版本、接入第三方任意帧存档或真正启用热恢复，则必须重新审查新恢复入口是否重放每个原生动作、是否需要恢复新增状态；当前版本上界检查会拒绝未经验证的游戏版本。

## 本会话已执行的检查

- `tests/test_multiplayer_suite.py`：16 个测试通过。包括真实双任务并发启动的路由边界，以及缺端、缺阶段、伪造/复用 PID、跨端 MVID 不同、付费缺失、错误 owner、重复敌方行动、双发起者奖励、领域串号、兽化身份复用、关闭原生 checksum、磁盘篡改和错误恢复承诺的负向检查。
- `tests/test_native_lobby_api.py`：实际 `NativeLobbyApi` 和 `DispatchProxy` 代码执行 20 个断言通过。未知/歧义 API、错误参数、未知 listener 回调和原生异常不能被吞掉。
- `tests/test_engage_adapter.py`：9 个有限用例、60 个断言通过，直接编译生产 `EngageCmd` 与账本；新增“第一人挂起时第二人预留失败”和“真实动作已开始后重置，旧 continuation 在新战斗后恢复”两组。后者覆盖新战斗对象与复用战斗对象两种 generation 边界。
- 新增的三个 C# 入口文件通过 Roslyn 语法检查。这不是游戏程序集引用检查。

以上均如实保留 `native-network=NOT_RUN` 或同等标记。待本地门禁实际通过后，保留两端原始回执及报告，才能把本次候选构建的 ENet 双端范围标为已验收。
