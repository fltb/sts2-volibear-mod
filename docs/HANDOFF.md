# 换机续作检查点（2026-10-31）

用户要求暂停开发并提交。目标未完成，自动目标已暂停。

## 换机配置

仓库已包含资产、生产工具/参考材料及此次独立编写的开发工具；游戏本体、SDK、反编译资料、测试存档与日志不提交。安装合法 StS2 **0.107.1 / 59260271** 及 .NET SDK **9.0.320**。当前自动运行器为 Linux 实现，其他系统需适配进程组、启动文件与音频诊断。

在仓库根目录创建被忽略的 `.local/config.json`：

```json
{"game_dir":"/absolute/path/to/Slay the Spire 2","dotnet":"/absolute/path/to/dotnet"}
```

```sh
python3 tools/dev.py doctor
python3 tools/dev.py test
VOLIBEAR_TEST_ENGAGE=1 VOLIBEAR_TEST_AUDIO_ADAPTER=1 python3 tools/headless.py --scenario baseline --repeat 2 --frames 5000 --timeout 120
```

音频诊断需 C 编译器及本机原游戏 FMOD 扩展，不替换原文件。关闭迎战环境变量可跑无迎战对照。全部测试须禁用 Steam 并隔离 HOME/XDG；不要手工改普通存档。

## 实际达到的状态

- 13 项 Python 测试通过；net9 DLL 编译零警告/错误；游戏原生初始化和隔离断言通过。
- 真实 headless，TestMode=false：原生怪物攻击使玩家 80→74；原版打击 AutoPlay 造成6点伤害。不是手动出牌/能量动作队列验收。
- 可选迎战：仅包装测试用单张打击的 OnPlay Task；卡牌前效→真实 Monster.PerformMove→完成回调→后效。吸收从 DamageBlockInternal 实际返回值计量。
- 简单史莱姆场景：吸收3、格挡30→27、完成回调一次恢复至30、重复请求不执行/不完成/零吸收，后效实际再攻击1。目标剩余生命15→8。
- 原正常敌方阶段跳过目标 TakeTurn 一次；原生战斗历史中目标恰好行动一次，所有敌人历史条目数与敌人数量一致；回合1→2。尚无下一招/多轮完整验证。
- 最新测试本机运行标识 `20261031T122149Z-4903b5f4`；场景及独立迎战证据校验通过，进程退出0，但严格总报告 FAILED：退出引擎资源泄漏未解决。此前两次独立进程通过基础迎战断言，但不能称干净集成通过。
- FMOD NOSOUND 预加载诊断解决启动/音库/监听器错误；renderer/text/resource 退出泄漏仍存在。显式 xvfb 路线曾遇敌方回合等待超时，未验收。

## 下一步与未完成项

1. 先解决严格退出错误；不要删错误检查或用模拟战斗冒充通过。
2. 继续迎战死亡、战斗结束、多段、坚甲、非攻击、召唤、多目标、状态机多轮/下一招、意图播放与原版对照；窗口/资格的战斗清理及存档范围。
3. 当前 completion 回调是开发测试效果，不是正式遗物/能力事件系统。当前补丁不作为普通角色玩法注册。
4. 雷伤、领域 Tier2、正式卡牌/初始遗物、角色动画/PCK/中文集成尚未完成。RitsuLib 仅研究，尚未安装。
5. dev.py 的 logs/undeploy 等工具入口待完善。

## 代码风险提示

EngagePrototype 的旧顶部注释尚待更新；Reset 尚未接入战斗结束，计数器生命周期待完善。无 SpawnedThisTurn 拒绝是首轮初始敌人的验证所需，但召唤目标资格未验证。只跳过 TakeTurn，原意图播放仍会执行。异常执行应终止场景，不能重试已发生部分效果的动作。不得将简单敌人成功扩大为全怪物兼容。
