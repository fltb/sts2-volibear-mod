# 换机续作检查点（2026-10-31，Windows）

Linux 检查点之后已在新机器（Windows）重建开发环境，headless 闭环跑通。目标未完成：
玩法、卡牌、雷伤、领域与正式迎战都还没有实现，当前只有探针和验证脚手架。

## 本机环境

已安装并核实：

- StS2 **0.107.1 / 59260271**（Steam，`release_info.json` 与 appmanifest 一致）。
- .NET SDK **9.0.320**，隔离安装在 `%USERPROFILE%\.dotnet`，未替换系统运行时。
- 仓库根 `.local/config.json`（被忽略）：

  ```json
  {"game_dir": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Slay the Spire 2",
   "dotnet": "C:\\Users\\float\\.dotnet\\dotnet.exe"}
  ```

- Python **3.12.10**（`%LOCALAPPDATA%\Programs\Python\Python312`）。微软商店版不要用：它在这个
  宿主上以 Low 完整性级别运行，写不了游戏目录和宿主 Temp，表现为 `Permission denied` 与
  NuGet 锁超时；独立安装版是 Medium，正常。
- 虚拟环境 **`%USERPROFILE%\venvs\sts2-volibear`**，含 Pillow 13、NumPy 2.5.4、SciPy 1.18.1、
  fonttools 4.68。它故意放在仓库外：本会话的宿主会对**工作区内**的可执行文件降权到 Low，
  仓库内的 `.venv` 因此同样写不了游戏目录。换到普通终端后仓库内 `.venv` 可用。
- ffmpeg/ffprobe 9.0.2（`%LOCALAPPDATA%\Programs\ffmpeg\bin`，已加入用户 PATH）。
- Node 24 / npm 12；`assets/animation` 与 `assets/cards` 已装 Playwright 1.62.1 及 Chromium。
- 官方 Riot 录音 153 条已按 `official/inventory.json` 重新下载，11,873,857 字节，
  `build_catalog.py --check` 通过（153 解码，目录一致）。

Windows 上必须设置 `PYTHONUTF8=1`：仓库内脚本按 UTF-8 读写文件，默认 GBK 代码页会在
读取报告时抛 `UnicodeDecodeError`。克隆时必须保持 LF：全局 `core.autocrlf=true` 会把
换行改成 CRLF，`export_config_sha256` 等字节级校验随即失败；仓库已加入 `.gitattributes`
（`* -text`）并在本仓库设置 `core.autocrlf=false`。

构建侧两点：csproj 关闭了 `NuGetAudit`（探针只引用本机游戏程序集，不需要包源，审计会让
restore 在离线时卡住并报一个误导性的锁错误）；`dev.py build` 在 `project.assets.json` 比
csproj 新时传 `--no-restore`，避免每次循环重复 restore。

```powershell
$env:PYTHONUTF8='1'
$py = "$env:USERPROFILE\venvs\sts2-volibear\Scripts\python.exe"
& $py tools/dev.py doctor
& $py tools/dev.py test
& $py tools/headless.py --scenario baseline --repeat 2 --frames 5000 --timeout 180
$env:VOLIBEAR_TEST_ENGAGE='1'   # 可选迎战变体
```

部署守卫会拒绝覆盖字节已被改动的已部署文件（`Previously deployed file changed`）。确认那是
自己的改动后，删掉该 mod 目录里的自有文件和 `.local/deploy/Volibear.json` 再 `deploy` 即可。

Steam 必须保持关闭：运行器传 `--force-steam=off`，并隔离 `HOME`/`APPDATA`/`LOCALAPPDATA`。

## 实际达到的状态

- Python 契约测试 21 项通过；net9 DLL 编译零警告/零错误；部署只写自有文件，`undeploy` 可回收。
- 模组在真实 headless 进程中加载：`LOAD_OK` 与 `ISOLATION_OK steam=false` 均出现，
  user-data 目录与 Steam 关闭状态在模组内部断言。
- 战斗基线（Windows，2026-10-31）连续两个新进程全部通过：
  `20261031T140510Z-07f9ffa5`、`20261031T140528Z-8752ebca`。真实怪物 `DamageCmd.Attack(6)`
  使玩家 80→74；原版打击 AutoPlay 使目标 15→9；`round 1→2`；`testMode=false`。
  更早一次同构通过为 `20261031T130756Z-d47bb1dc`、`20261031T130814Z-62d1fbd6`。
- 迎战变体（`VOLIBEAR_TEST_ENGAGE=1`）通过：`20261031T140749Z-b1c1a028`。吸收 3、格挡
  27→30、完成回调一次、重复请求不执行、后效再攻击 1、跳过目标 TakeTurn 一次。
- discovery 通过：`20261031T140604Z-59512ef2`。
- 卡图仓 `card_repo.py verify` 通过：89 张、356 个导出、89 张唯一母图。
- 运行音频 `validate_audio.py` 通过：47 声音 / 54 cue / 26 段动作。

## 退出期引擎错误

`--nomods` 对照进程在完全相同的构建上产生同样的 RID 泄漏（Environment、DummyTexture、
DummyMesh、DummyMaterial、DummyShader、ShapedTextDataAdvanced、FontAdvanced、
FontAdvancedLinkedVariation 及资源总数）。因此运行器现在每次调用先跑一次原生对照，只容忍
对照出现过的类别，出现任何新类别即失败；运行期错误仍然一律失败。这不是"退出干净"，
只是把泄漏归因清楚，报告里保存对照证据。

## 未完成项

1. 雷伤、格挡、领域 Tier 2、正式卡牌与初始遗物：未实现。
2. 迎战死亡、战斗结束、多段、坚甲、非攻击、召唤、多目标、状态机多轮/下一招、意图播放与
   原版对照：未验证。当前只覆盖单次攻击与单敌行动。
3. Windows 只有 `--headless`；没有窗口/虚拟显示路径。门/资格/战斗清理与存档范围未验。
4. RitsuLib 仅研究，尚未安装；PCK、中文与角色动画接入未开始。
5. 退出期引擎泄漏未解决，只在门禁里与原生对照区分。

## 代码风险提示

`EngagePrototype` 顶部注释待更新；`Reset` 尚未接入战斗结束；无 `SpawnedThisTurn` 拒绝是
首轮初始敌人的验证所需，召唤目标资格未验证；只跳过 `TakeTurn`，原意图播放仍会执行。
异常执行应终止场景，不得重试已发生部分效果的动作。不得把简单敌人与单次攻击的成功扩大为
全怪物或全卡牌兼容。
