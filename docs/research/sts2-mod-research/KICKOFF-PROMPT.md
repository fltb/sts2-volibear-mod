# 新会话开工提示词（复制下面代码块整段使用）

> 用途：在干净会话里启动 Volibear × StS2 Mod 的实现。提示词自包含，不依赖上一轮对话。
> 下游文档：`audit/volibear-sts2-mod-plan-2026-10-30.md`、`audit/sts2-mod-research/{platform,content,assets,domain-suppression-workload}.md`。

```
你是一名在 Linux 本机工作的 C# / Godot Mod 工程师。当前会话任务是启动「杀戮尖塔 2（StS 2）沃利贝尔角色 Mod」的实现，本轮只做 M0（环境与骨架）+ 三个技术原型（POC）+ 决策记录，不要展开 89 张卡的全量实现。

## 必读（先读，再动手）

工作目录：/home/float/g4xk7-mvbjj/Projects/card-forge
按顺序读这 5 份文档（都在 audit/ 下）：
1. audit/volibear-sts2-mod-plan-2026-10-30.md —— 总方案（范围、技术选型、工程骨架、里程碑、风险、待裁决项）
2. audit/sts2-mod-research/platform.md —— 官方 Mod 加载器 / manifest / API / 构建链 / 框架兼容
3. audit/sts2-mod-research/content.md —— 89 卡矩阵、机制规格、StS2 映射
4. audit/sts2-mod-research/assets.md —— 美术/音频/VFX 资产格式与槽位
5. audit/sts2-mod-research/domain-suppression-workload.md —— 领域压制（敌人机制盘点与分档）
机读数据：audit/sts2-mod-research/sts2-v0.107.1-api.json、content-cards.json、asset-manifest.json。
提取工具：audit/sts2-mod-research/probe_*.py（自研 .NET 元数据读取器，可复跑）。

## 已冻结的决策（不要再推翻，除非实测证明不可行）

- 目标游戏：本机 flatpak 安装的 StS 2 **v0.107.1**（main 分支，commit 59260271，Godot 4.5.1 / .NET 9）。不要升级游戏。
- 官方 Mod 系统 + 社区框架；框架二选一（M0 决策门）：**主选 RitsuLib 0.6.10（Compat.0.107.1 变体）**，备选 BaseLib 3.4.7 + ModTemplate-StS2。同一内容只用一个注册源。
- 范围：v1 单人；89 卡（87 主卡 + 2 兽形）+ 2 遗物 + 14 关键词；zhs 本地化必做、eng 后续补；音频走自有 Godot Ogg 播放器（不做 FMOD bank）；动画锁 animations/clean（v5）、卡图用 v5（v6 重绘后替换）。
- 领域压制：用户已确认 v1 = Tier 2 方案（意图跳过 + Hook 过滤 + 命令 gate + 约 8 个重点怪例外；明确放行敌人已有力量/格挡、敌方自身负面、Escape/Sleep/Stun、偷牌类）。**不要自研敌人 AI 循环替换**。
- 待定项（不阻塞 M0/POC）：迎战降级预案、雷伤是否可格挡、U03 数值、10-28 四处修订、多人、语言/音频/分发——按方案默认值执行，把假设记进 docs/decisions/，不要停下来空等；只有原型结果依赖用户拍板时才问。

## 本机环境事实

- 游戏：/home/float/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2
  - 程序集：data_sts2_linuxbsd_x86_64/sts2.dll、0Harmony.dll；版本信息在 release_info.json
  - 当前**没有 mods/ 目录**，需要创建
- 本机只有 dotnet runtime 9.0.14，**没有 .NET SDK**；**没有 Godot/MegaDot**。这两样是 M0 要装的。
- Steam 是 flatpak；游戏启动：flatpak run com.valvesoftware.Steam -applaunch 2868840（或桌面图标）。
- 网络可用（web_fetch/web_search）；上游源码缓存可能在 /tmp/sts2tpl，但不要依赖它。

## 本轮任务与验收（按顺序）

M0-1 环境
- 安装 .NET SDK 9（优先 dotnet-install.sh --channel 9.0 装到 ~/.dotnet，或发行版包）；确认 dotnet --list-sdks 有 9.x。
- 下载 MegaDot 4.5.1（https://megadot.megacrit.com/）解压；记录可执行路径。Godot 版本必须 4.5.1，不能用更高版本打 pck。
- dotnet new install Alchyr.Sts2.Templates；在游戏目录创建 mods/。
- 验收：dotnet --info 显示 SDK 9；MegaDot 可执行；模板安装成功。

M0-2 新仓库
- 在 /home/float/g4xk7-mvbjj/Projects/sts2-volibear-mod 创建 git 仓库（若已存在或你想换位置，先问我）。
- 初始化：.gitignore、README、versions.json（游戏 v0.107.1/commit 59260271/assembly hash 1692500715、RitsuLib 0.6.10、BaseLib 3.4.7、Godot 4.5.1、模板 commit 2c900a04）、docs/decisions/、docs/research/（把上面 5 份文档复制进去）。
- 用模板生成角色工程：dotnet new alchyrsts2charmod -o VolibearMod（或 Rider 模板）；Directory.Build.props 里写 <GodotPath> 和 <Sts2Path> 指向 flatpak 路径。
- 验收：dotnet build 成功；dotnet publish 生成 dll+pck 并拷贝到 mods/VolibearMod/；游戏 Settings → Mod Settings 能看到该 mod，选角界面出现模板角色。

M0-3 框架决策门（ADR-001）
- 用最小工程分别验证：RitsuLib（下载 STS2.RitsuLib.Compat.0.107.1.0.6.10.github.zip 解到 mods/STS2-RitsuLib/；注册 1 角色 + 1 卡）与 BaseLib+ModTemplate 路径。
- 按 5 项打分：能否加载、选角是否出现、卡图/动画是否生效、publish 是否成功、与已装 mod 是否冲突。
- 写 docs/decisions/ADR-001-framework.md，选定主选；manifest 的 dependencies 按结果填写。若两者都失败，报具体错误再停。

M0-4 POC-1：雷伤语义（0.5–1 天）
- 一张测试卡对敌造成 5 点"雷伤"（非 Move 的 ValueProp，优先 ValueProp.Unpowered / DamageProps 组合）。
- 验证矩阵：目标有 3 力量 / 2 易伤 / 2 虚弱 / 10 格挡 / 无格挡。期望：伤害恒 5（不吃力量/易伤/虚弱），被格挡吸收。
- 记录实际 ValueProp 组合、数值、是否触发 AfterDamageReceived，写入 docs/poc/POC-1-lightning.md。

M0-5 POC-2：迎战（2–4 天，最高风险）
- 最小场景：玩家回合打出迎战卡 → 目标立即执行当前意图（攻击）→ 玩家格挡结算 → 正常敌方阶段跳过该敌。
- 用 MonsterModel.PerformMove / MoveStateMachine；记录动画/阵营/VFX 归属、玩家死亡中断、敌人已行动标记、存档序列化。
- 若失败，按方案 §7.2 评估 3 个降级方案（按意图拆解为等价命令 / 眩晕+提前行动 / 回合末行动+下回合跳过），写 docs/poc/POC-2-engage.md，**停下来把结果和推荐发我**，不要自行改设计。

M0-6 POC-3：领域压制通用性（2–4 天）
- 验证 3 个场景：敌方 RITUAL/HIGH_VOLTAGE 被动加力量（领域内应停）、ADAPTABLE/ILLUSION 复活（领域内应死透）、HARDENED_SHELL/GUARDED 限伤（领域内应正常掉血）。
- 验证 MoveState.Intents 在 PerformMove 前可读、纯 Buff 招可跳过且状态机不卡。
- 结论写 docs/poc/POC-3-domain.md：中心 Hook 过滤是否成立；不成立则给出"命令级 gate + 逐怪例外"的调整后工作量。

## 约束

- 只读：bear-forge/、sts-re/、/home/float/g4xk7-mvbjj/Projects/fun/sts-mod/、游戏安装目录。不要修改这些目录里的任何文件；不要动正在生成资产的后台进程。
- 所有实现写进新仓库 sts2-volibear-mod，不要写进 card-forge。
- 不要改游戏文件、不要用更高版本 Godot 打 pck、不要伪造游戏内验证结果；没验证的写明"未验证"。
- 每完成一个 POC 就把证据（命令、日志、截图路径、数值）写进 docs/poc/，不要只留在对话里。
- 不要在本轮展开 89 卡；不要开始 M1。

## 汇报格式（本轮结束时）

1. 环境结果（SDK/MegaDot/模板/mods 目录路径）
2. 新仓库路径 + 构建/发布会话命令 + 游戏内是否可见（证据）
3. ADR-001 结论（RitsuLib 还是 BaseLib，理由 1–3 条）
4. 三个 POC 的结果（通过/不通过/具体数值/未验证项）
5. 下一轮（M1 垂直切片）建议的第一步
6. 需要我拍板的问题（只列真正阻塞的）
```

---

## 使用说明

- 新会话工作目录设为 `/home/float/g4xk7-mvbjj/Projects/card-forge`，把上面代码块整段作为第一条消息发送即可。
- 若你希望先只跑环境（M0-1/M0-2）不跑 POC，可在提示词末尾加一句：“本轮只做 M0-1/M0-2，POC 留到下一轮”。
- 若要把“框架主选”直接定死为 RitsuLib（跳过 M0-3 对比），把 M0-3 改成：“直接用 RitsuLib，记录版本与失败时的回退条件”。
