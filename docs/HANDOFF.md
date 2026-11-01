# 当前源码交接：PR #1

当前分支：`codex/mode7-completion`。当前范围以 [RELEASE_PLAN.md](RELEASE_PLAN.md) 为准；
实施条目见 [IMPLEMENTATION_TODO.md](IMPLEMENTATION_TODO.md)，本地 Agent 直接使用
[LOCAL_AGENT_TASK.md](LOCAL_AGENT_TASK.md)。本页替换此前累积的历史检查点，旧分支、旧 DLL、
旧测试计数和旧 UI 自动化结果不再作为当前候选的通过证据。

## 目标与当前状态

目标是交付可从源码构建、完整安装并沿游戏正常入口游玩的沃利贝尔 Mod。范围包含
89 张卡、178 个基础/升级牌面、83 张奖励牌、两件遗物、既定机制、角色与战斗表现、
双音频、正常单人/多人流程、原生存读档和安装卸载。

生产修复、验收代码、独立预期与本地执行入口均在本 PR 实施。缺少游戏本体仅限制原生执行，
不能把尚未实现的步骤交给本地 Agent 设计或用一份计划代替测试代码。当前维护环境没有
StS2 **0.107.1 / 59260271**，因此当前完整 DLL 的游戏引用编译、原生五阶段、角色契约、
S2 跨进程恢复、双端网络及最终完整安装包的原生验收结果仍为 **`NOT_RUN`**。

四种多人手势图已按用户反馈参考 Riot 原模型与 StS2 原生贴图重画，替换第一版。
资源路径、422×1200 长前臂画布、纹理解码和差异摘要检查，
与用户对熊爪造型的视觉认可分别记录；不能写成已获视觉批准。既有批准卡图、角色母图、
动画部件和玩法数值继续保留。

## 已落实的实现与验证入口

| 部分 | 当前实现与接续要点 |
| --- | --- |
| 版本与构建 | 锁定游戏 0.107.1 / 59260271、普通 Godot 4.5.1 stable Mono/.NET、SDK 9.0.320、BaseLib 3.4.7。运行时先核对游戏版本，再安装 Volibear 补丁。`Volibear.sln` 供 IDE 使用，完整交付走 `local_delivery.py`，同时更新 DLL、PCK、JSON。 |
| 兽化 | 原生消耗材料，在原牌堆生成独立 T01/T02；保留耗尽/生成响应，按冻结规则转移升级、有效临时费用与保留。永久牌组、材料与新牌身份分开。 |
| 迎战与多人生命周期 | 全队共享敌方行动机会，首次等待前预留；完成收益归发起者。战斗引用、轮次与 generation 阻止旧异步 continuation 在重置后的新战斗结算。 |
| 领域兼容 | 原生异步方法体入口绑定来源，保留公共入口的外部补丁；卡牌混合贡献分离已观察到的敌源增量与应保留部分。正常递减、外部直接写值、玩家收益与敌方负面效果按既定边界处理。不能沿用旧文档“遇外部 Prefix 一律拒绝”的结论。 |
| 角色接入 | 四种原生手势 getter、角色/Sea Glass 文本、Architect 角色对话、BaseLib `ITomeCard` 到既有 R18 的 Tome 奖励、五个角色专属无效原生 FMOD 键的窄过滤均有对应实现。角色契约检查实际资源、语言重载、原生 JSON 恢复及库存不变，不冒充自然完成终局。 |
| 原生选择 | `ICardSelector.GetSelectedCardReward` 已改为真实 `CardRewardSelection` 返回类型。普通选牌用 `CardSelectCmd.UseSelector`；非 TestMode 卡牌奖励在原始 `OptionSelected` 异步决策边界供给实际候选索引，原生屏幕、同步、授予、历史和 VFX 保留。 |
| 普通游戏流程 | `NativeProductFlowProbe` 新开真实种子 run，使用正常起始牌组与资源、付费动作、地图投票、奖励、休息和商店；事件/宝箱按实际遇到的原生流程处理。没有注入测试卡、血量、金币、调试传送或强制胜利。 |
| 保存与网络 | 单进程原生 checkpoint、S2 两个不同进程 prepare/resume，以及两个同时运行的 ENet 客户端均有实际测试源代码、独立 oracle 和失败报告。多人通过真实加载大厅恢复 host 的原生房间 checkpoint。 |
| 工具与失败判定 | `regression.py --require-native` 不允许必需的游戏引用/SDK 检查静默跳过。原生报告核对 token、PID、阶段、真实磁盘、历史与付款；任一必需项失败就停止完整发布链。 |

详细测试范围和原始决策边界见 [HEADLESS_TESTING.md](HEADLESS_TESTING.md)。
多人 API、原生恢复边界和生产状态归属见 [MULTIPLAYER_ACCEPTANCE.md](MULTIPLAYER_ACCEPTANCE.md)。

## 本地 Agent 的执行顺序

先确认游戏已退出，再按 [LOCAL_WORKFLOW.md](LOCAL_WORKFLOW.md) 配置实际的游戏、Godot 与 SDK 路径。
路径已保存的 Windows 机器执行：

```powershell
python -B tools/local_delivery.py --verify-release --audio-driver WASAPI
```

Linux 使用本机实际可用的音频后端，例如：

```sh
python3 -B tools/local_delivery.py --verify-release --audio-driver PulseAudio --display xvfb
```

这条命令重新构建当前 DLL，运行一次严格回归，导出并检查当前 PCK，归属部署，执行原生
五阶段与同进程角色契约，执行 S2 跨进程恢复，再执行双端 ENet，最后才打完整安装包。
`--verify-native` 仅是较小的单进程验收入口，不能替代 `--verify-release`。
完整表现模式需要真实音频后端；Dummy 不计声音捕获通过。

所有有限单人案例在一个后台游戏实例中串行执行，独立案例经原生清理后重新开局。
真正跨进程恢复使用 prepare/resume 两个进程；多人使用同时存在的两个进程。
单人及 S2 共用本次新跑的一个无 Mod 退出对照，多人批次另有自己的无 Mod 对照。
Windows 使用不切换到前台的私有桌面，Linux 使用 Xvfb。禁止 OS 键鼠、Viewport 输入、
合成点击或按钮伪信号；测试不读取普通或云端存档。

发生失败时：

1. 保留该次原始日志和报告，先定位首个编译、绑定、游戏或证据错误；不把后续缺回执当成另一个玩法缺陷。
2. 修复生产代码或实际验收入口；不删断言、改存档或伪造回执来通过。
3. 已部署同一候选时可用有限子集定位；修复之后重新构建 DLL/PCK 并执行完整 `--verify-release`。
4. 记录实际命令、退出码、报告路径、已执行范围与未执行项，再生成/核对最终包。

## 证据和输出

| 输出 | 用途 |
| --- | --- |
| `artifacts/validation/regression.json` | 本次完整回归的总数、失败、跳过和未执行的必需检查；以单次完整报告为准，不将多次定向结果相加。 |
| `artifacts/headless/<run-id>/report.json` | 同一个原生进程的五阶段、独立角色回执、运行时与隔离检查。 |
| 同目录 `native-acceptance-report.json` | 原生单进程批次与 S2 跨进程恢复的合并结果。 |
| `artifacts/save-load/<pair-id>/` | 原生 prepare/resume、两个进程身份、磁盘存档与隔离 profile。 |
| `artifacts/multiplayer/<pair-id>/report.json` | 两端逐阶段状态、实际网络身份、付款、断线和原生 checkpoint 恢复。 |
| `.local/asset-build/<id>/` | 本次资源导出、挂载、脚本、纹理、特效、音频检查。 |
| 完整 ZIP 内 `PACKAGE.json` | 本次实际 DLL/PCK/JSON、BaseLib、许可与各文件 SHA-256。 |

离线生产逻辑、真实 Harmony 组合、适配器和报告负控已有执行入口与定向结果；本轮完整汇总
由上述回归报告记录。资源独立渲染/解码、C# 语法检查和替身执行都不等于当前完整 Mod 在
游戏中通过。对本机真实程序集的正常流程 API 合同现有 **18 项**，缺少本体时明确未执行。

正常流程验收要求至少三场真实战斗胜利及奖励、地图、休息和付费商店覆盖；它不是三幕自动
通关证明。Architect/Tome 契约也不等于自然终局事件已走完。多人报告的证明范围是本机
原生 ENet 两端及房间 checkpoint 恢复，不包含 Steam 传输、跨公网、远端选择界面或
任意战斗帧热恢复。人工视觉和听感单独保留，尤其不能由手势图片的技术检查推导视觉批准。

## 接续约束

继续在 `codex/mode7-completion` 追加；提交、推送和更新现有 PR 的授权持续有效。
不强推、不合并或改写 main，不覆盖无法确认来源的本地改动。只保留本轮可复现的实际结果，
不恢复历史 DLL、旧源码快照或旧美术收尾脚本来绕过问题。

游戏程序集、反编译原文、本机配置、存档、日志、构建产物和私有 Riot 媒体不进 Git。
默认 `open` 音频完整；可选 `riot_en` 的来源、准备与回退见
[音频说明](../assets/animation/audio/profiles/README.md)。
玩家安装/卸载见 [INSTALL_ZH.md](INSTALL_ZH.md)；部署回收只删除归属可证且未改动的自有文件。
