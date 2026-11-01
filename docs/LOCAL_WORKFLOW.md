# 本地构建、打包与受控游戏验证

此流程适用于Git检出，或把本轮源码覆盖包解压到已有本地仓库后的目录。入口是
`tools/local_delivery.py`，请在仓库根目录执行。它按顺序完成版本检查、当前DLL重编、
回归、资源构建、可选游戏验证和打包；任一步失败即停止，不沿用旧DLL冒充新构建。

当前维护环境已实际执行生产逻辑回归及两套普通Godot资源构建。由于缺少
StS2 0.107.1 / 59260271本体与程序集，本轮整Mod编译、游戏内批次及真实双端网络
仍没有通过证据。下列命令是已实现的执行入口，不能把命令存在当成实机已通过。

## 1. 准备本机工具

| 项目 | 要求 | 入口检查 |
| --- | --- | --- |
| 游戏 | 已安装StS2 **0.107.1 / 59260271** | 核对`release_info.json`、游戏程序及`sts2.dll`、`GodotSharp.dll`、`0Harmony.dll` |
| Godot | 普通 **4.5.1 stable Mono/.NET**发行版，完整解压 | `--version`必须是`4.5.1.stable.mono.`开头 |
| .NET | **SDK 9.0.320**，不是只有Runtime | 仓库`global.json`固定版本，不允许自动滚动到其它SDK |
| Python | **3.10或以上** | Windows建议python.org发行版；入口为子进程启用UTF-8 |
| BaseLib | **3.4.7** | 自动获取并验证固定发行包摘要；可复用正确缓存 |
| Linux显示 | `xvfb-run`及可用的图形环境 | 游戏验证使用虚拟显示；Windows使用私有后台桌面 |

工具下载与方法来源：

- [Godot 4.5.1官方归档](https://godotengine.org/download/archive/4.5.1-stable/)：选择.NET/Mono版本，保留同一压缩包里的配套文件。
- [.NET 9官方下载](https://dotnet.microsoft.com/en-us/download/dotnet/9.0)：安装SDK 9.0.320，可与其它SDK并存。
- [Python官方下载](https://www.python.org/downloads/)。
- [BaseLib 3.4.7发行页](https://github.com/Alchyr/BaseLib-StS2/releases/tag/v3.4.7)。
- [上游StS2 Mod模板Setup](https://github.com/Alchyr/ModTemplate-StS2/wiki/Setup)允许在MegaDot不便获取时使用匹配版本的普通Godot.NET；[Godot官方PCK导出文档](https://docs.godotengine.org/en/4.5/tutorials/export/exporting_pcks.html)说明标准资源打包方式。模板是社区上游，不代表MegaCrit保证所有插件都兼容。

这里固定普通Godot4.5.1 Mono和`gl_compatibility`，通过标准`--export-pack`导出。
四个运行脚本保留GDScript源码，PCK头必须为Godot4.5.1 / format 3；构建后实际加载包，
逐个核对脚本字节并拒绝旧编译脚本/重映射。游戏运行使用你已安装的游戏程序，
不另行下载MegaDot编辑器，也不把普通Godot资源检查称作游戏验证。

首次获取BaseLib、补齐Python包需要网络。只有缺少Pillow时才创建仓库内的
`.local/build-python`虚拟环境，避免修改全局Python。默认open音频无需FFmpeg。
若私有覆盖包已经带有通过摘要检查的riot_en处理音频，复用即可；从纯公开源码首次
重建riot_en时另需PATH中的`ffmpeg`、`ffprobe`，入口会为处理步骤补齐NumPy。

## 2. 覆盖源码与首次执行

先关闭已运行的游戏。在已有本地Git仓库根目录解压源码覆盖ZIP，使`src/`、`tools/`、
`docs/`与原目录合并。包内不包含`.git/`和`.local/config.json`，本机Git历史与配置继续保留。

这次删除了旧兽化类型补丁和对应旧实验项目。覆盖包携带
`.local/delivery/obsolete-files.json`；入口在编译前只删除路径及SHA-256都匹配的旧文件。
缺失文件直接跳过；本地修改过的旧文件保留并报告冲突，不按通配符清目录。
出现冲突时，将自己的修改保存到仓库外再合入当前实现，不能直接删除修改内容或绕过检查。
从Git更新则正常使用Git记录的删除，不需要该清单。

Windows PowerShell或命令提示符，在仓库根目录执行这一条命令，替换三个工具路径：

```powershell
python tools/local_delivery.py --game-dir "D:\SteamLibrary\steamapps\common\Slay the Spire 2" --godot "C:\Tools\Godot\Godot_v4.5.1-stable_mono_win64.exe" --dotnet "C:\Program Files\dotnet\dotnet.exe" --verify-native
```

若本次还要把动作、动画和实际音频捕获加入**同一批游戏进程**，在首次命令末尾直接加：

```powershell
--presentation-mode all --audio-driver WASAPI
```

Linux对应示例：

```sh
python3 tools/local_delivery.py --game-dir "/path/to/Slay the Spire 2" --godot "/path/to/Godot_v4.5.1-stable_mono_linux.x86_64" --dotnet "/path/to/dotnet" --verify-native --display xvfb
```

Linux动作/声音捕获同样在这次命令末尾添加`--presentation-mode all --audio-driver PulseAudio`，
或使用本机实际可用的Godot音频后端。Dummy不计声音通过，驱动不可用会失败。

路径与版本检查全部成功后，入口把路径合并保存到`.local/config.json`；失败不写入半份配置。
后续同一机器只需：

```sh
python tools/local_delivery.py --verify-native
```

音频和表现模式参数是本次选择，不会隐式记住；需要时仍在这条命令末尾加上。
可参考`tools/local_config.example.json`了解三个字段，不必手工建立配置。

## 3. 一条命令实际做什么

1. 核验工具、锁定游戏版本、程序集和平台显示方式；预检旧文件清单。
2. 清掉摘要匹配的已废弃文件，保存有效本机配置，获取固定BaseLib。
3. **重新编译当前源码DLL**，使后续原生元数据检查读取的是本次候选。
4. 执行一次完整`unittest discover`。跳过项仍由测试输出保留，不转换成通过。
5. 用普通Godot导入、导出并检查PCK，覆盖动画、178张卡图、UI、VFX、音频及源码脚本兼容。
6. 若指定`--verify-native`，按已有归属记录部署候选，先运行一次无Mod退出对照，
   再运行**一个Mod后台进程**，完成所有选择的阶段并正常退出。
7. 只有前述所选步骤全部成功，才生成完整安装ZIP，包含当前DLL/PCK/JSON、
   固定BaseLib、许可、安装说明和逐文件摘要清单。

已有同名部署文件若不属于本工具，或被本地修改过，入口会停止，不能自动覆盖其它来源。
安装BaseLib可以复用完全一致的固定版本，不接管其它模组。游戏运行期间不要更换DLL/PCK。

默认安装包输出：

```text
.local/release/Volibear-0.1.0-StS2-0.107.1.zip
```

有三个不同用途的入口：

| 命令 | 实际范围 |
| --- | --- |
| `python tools/local_delivery.py --doctor` | 只核验已配置的工具、版本、路径和旧文件冲突；不构建、不启动游戏 |
| `python tools/local_delivery.py` | 当前DLL、完整回归、PCK和完整安装包；不声明游戏运行通过 |
| `python tools/local_delivery.py --verify-native` | 上述步骤，加统一受控游戏批次；游戏失败不产出本轮成功安装包 |

首次doctor也需要传入三个路径。若只有Godot和SDK、没有本体，可执行：

```sh
python tools/local_delivery.py --resources-only --godot "/path/to/Godot4.5.1Mono" --dotnet "/path/to/dotnet"
```

这只生成和验证资源PCK，不写半份游戏配置，不生成DLL或完整安装包。

## 4. 游戏内受控验证范围

`NativeVerificationSuite`在同一游戏实例内依次运行以下阶段。每个独立案例可以清理旧run、
建立新run或房间，但不会为每张牌关闭并重启游戏。

| 默认阶段 | 范围 | 关键证据 |
| --- | --- | --- |
| card-faces | 410个有限案例，包含178基础/升级牌面及约定分支 | 原生付费动作、目标、历史、材料与新兽形独立身份、独立期望值 |
| card-lifecycle | 48个案例 | 回合/重演/费用/清理边界及正常动作队列 |
| presentation | 356个普通/Inspect卡牌视图 | 游戏视口输出；选择all时再覆盖动作/声音捕获 |
| save-load-same-process | S2原生检查点写入和同进程恢复 | SaveManager、原生RunState/RunManager加载、真实磁盘JSON及恢复后状态 |

出牌通过`PlayCardAction`提交给原生`ActionQueueSynchronizer`，保留支付、目标判定和原生历史。
选牌通过`CardSelectCmd.UseSelector`提供返回的候选对象，检查拥有者、数量、重复项和对象身份。
不直接调用`OnPlay`绕过出牌，也不发送系统点击、键盘、`Viewport.PushInput`或按钮伪信号。
旧`native-run`/界面catalog驱动没有接进这条默认路径。

当前环境已经核对锁版API索引中的UseSelector入口，其余完整接口及存档链有实际上游Mod源码参考；
没有本体程序集就无法完成锁版绑定。新生产选择器的替身边界测试和语法检查不能代替该编译门。

默认整个suite预算为3600秒、216000帧。每次使用新建隔离profile、禁用Steam接入，
不读写普通/云端存档。Windows私有后台桌面不切换前台；Linux使用xvfb。
一次原版无Mod进程用于区别引擎已有的退出噪声，随后才是一个Mod批次进程。
这里的“一次批次”没有隐去这个单独对照。

如果当前候选已经部署而只需重新定位一次确定的失败，可直接运行下层入口：

```sh
python tools/native_suite.py --execute-native --use-deployed
```

它默认仍跑完整批次，不重新构建或部署。可用`--card-face-cases`和`--card-lifecycle-cases`
给出明确逗号列表缩小诊断；缩小后的通过不能替代完整批次结果。没有自动重试或每例重启。

这套suite不覆盖全部正式敌人的完整状态矩阵、真实双客户端通信、断线重连、
跨进程恢复，也不能代替人工观看动画或听声音。领域已知C01/C02及网络C03见
[实现清单](IMPLEMENTATION_TODO.md)。它们不会因基础批次通过而自动勾选。

## 5. 如何判定成功、在哪里看失败

成功时入口末尾输出`INSTALLER BUILT:`与实际包路径，并明确本次是否要求游戏验证。
游戏报告必须`status=passed`且所有`checks`为true；不能只看程序退出码、一个成功标记或截图存在。
额外的运行时错误、缺阶段、重复结果、跨PID回执、失败的磁盘存档核对都会使批次失败。
没有Git或不在仓库时仅将来源元数据记为不可用，不影响这些真实判定门。

| 文件位置 | 内容 |
| --- | --- |
| `.local/asset-build/<id>/` | 普通Godot导入、导出、PCK脚本和资源检查日志 |
| `artifacts/headless/<run-id>/report.json` | 本次原生运行总状态、检查明细和原版退出对照 |
| 同一`artifacts/headless/<run-id>/`目录 | 标准输出、引擎日志、隔离profile及阶段捕获 |
| `.local/release/<包名>.zip`内`PACKAGE.json` | 实际安装文件版本与逐文件SHA-256 |

遇到`DELIVERY STOPPED`或`Native suite failed`时，根据首个错误处理，再重新运行对应入口；
工具不会自动删除存档、换游戏版本或修改当前失败证据。具体情况：

- 缺少`release_info.json`或版本不符：`--game-dir`必须是锁版游戏根目录，不是mods或程序集子目录。
- SDK或Godot版本不符：安装表中的准确版本并传正确可执行文件；Godot必须是Mono/.NET。
- 构建出现游戏API缺失：保存完整编译错误，这属于本体绑定失败，不能复制旧DLL绕过。
- 未归属或摘要改变的部署文件：按原安装来源的清单处理，保留本地修改后再部署。
- 受控动作或存档oracle失败：保存整个该run目录；当前候选没有通过，不能将其报告改成成功。
- 动作/声音模式没有真实音频驱动：在开始同一批次前选择可用后端，或明确仅做cards模式。

## 6. 两套音频、安装与卸载

默认`open`使用47个开放声音覆盖54个cue。私有`riot_en`覆盖9条英文发声和2条Q研发音效，
其余43个cue保留开放方案。切换时从源码重建**一份完整PCK**，不依赖叠加多个资源包的顺序：

```sh
python tools/local_delivery.py --audio-profile riot_en --verify-native
```

输出`.local/release/Volibear-0.1.0-StS2-0.107.1-riot_en-private.zip`，保持在忽略的`.local/`。
私有覆盖包已含原始/处理音频和两套已检查PCK；公开Git不收录这些二进制。
`.gitignore`只阻止尚未被跟踪的文件入库，不会自动取消以前强制跟踪的私有文件。

完整ZIP的手工安装/卸载见[INSTALL_ZH.md](INSTALL_ZH.md)。源码入口自动部署的版本可用：

```sh
python tools/dev.py undeploy
```

该命令只移除有归属记录且摘要仍一致的Volibear文件；保留BaseLib、其它Mod、游戏文件和存档。
如果只是把源码覆盖到Git仓库，不会自动安装到游戏；如果只拿到PCK资源替换包，也不能单独安装成Mod。

## 7. 本轮兽化的实际规则

原牌保持自己的模型与永久牌组关联；转换时先正常消耗它，再生成有新战斗身份的T01/T02。
攻击材料生成裂骨之爪，其余材料生成风暴之躯。新兽形继承升级、仍有效的约定费用与临时保留；
其他附魔、负面附着、任意第三方修饰器、CloneOf和DeckVersion不会被复制。

“就地”采用原牌堆的原生Bottom插入，满手按原生生成规则处理，不强改手牌槽位。
消耗响应照常运行；如果其他模块取消本次耗尽、拥有者失效或战斗结束，不凭空生成。
若耗尽响应把材料取回，它的正常效果保留；真实发生过本次耗尽仍可生成新兽形。
已有兽形不会再次消耗和生成。永久牌组中的原卡未被改造成兽形，战斗新牌也没有伪装成原卡。

当前实测是生产代码配命令边界替身的回归及独立资源运行；实际第三方Mod组合、原生选择/支付/耗尽
响应、当前游戏存读档与多人同步仍必须由上述本体编译和对应游戏测试给出证据。
