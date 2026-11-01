# 实施续作检查点（2026-11-01）

## 当前规则：原生兽化、普通Godot与统一受控验证

用户最新要求覆盖下文历史兽化规则：**消耗原卡，再在原牌堆生成新兽形**。
材料保留自己的模型、永久牌组关联和正常耗尽响应；新T01/T02有独立战斗身份，
不复制CloneOf、DeckVersion或任意第三方附着。“就地”使用原生Bottom插入及满手规则，
不为维持原槽位改写牌堆。永久牌组中的原牌不变。

BeastForms现在只调用CardCmd.Exhaust、combat.CreateCard和AddGeneratedCardToCombat。
必须观察到本次耗尽历史才允许生成；外部取消、旧历史、重复进入和等待后失效不会白给新牌。
升级、仍有效的临时费用与保留通过原生公开写接口转移；唯一窄适配是经过签名检查的费用列表
和临时保留getter只读访问。原全卡Harmony覆盖、第三方类型继承链注册、私有身份/目标改写、
旧费用克隆侧表及IsConverted已删除，依赖方已迁移到返回的新牌引用。

正常开发入口为 **[LOCAL_WORKFLOW.md](LOCAL_WORKFLOW.md)**：

```sh
python tools/local_delivery.py --game-dir GAME --godot GODOT_4_5_1_MONO --dotnet DOTNET_9_0_320 --verify-native
```

核验后保存本机路径；后续`python tools/local_delivery.py --verify-native`即可。
顺序为当前DLL fresh build、一次完整回归、普通Godot资源导出/检查、归属部署、
受控游戏批次、安装ZIP。普通Godot固定4.5.1 Mono，导出源码脚本并实际核对PCK内容；
无需额外MegaDot编辑器。资源单独入口不生成DLL/安装包，也不写部分游戏配置。

原生验证由NativeVerificationSuite串接：410牌面分支、48生命周期、356原生卡牌视图、
同进程原生检查点恢复；`all`模式增加既有动作/声音检查并要求真实音频后端。
真实付费出牌仍走PlayCardAction/ActionQueueSynchronizer，选牌走CardSelectCmd.UseSelector。
无系统/视口点击、键盘或按钮伪信号；一次无Mod退出对照后只启动一个Mod批次进程。
旧native-run/UI catalog不属于这条路线；不要用其历史结果替代新规则验证。

源码覆盖ZIP现含删除清单：local_delivery只清理摘要匹配的已废弃源码/测试文件。
包仍不带.git和本机config；私有音频及PCK仍放在忽略路径。不能再只解压后直接运行旧测试，
应先走统一入口完成旧文件清理。若本地旧文件被修改，保留文件并报告冲突。

**证据边界仍明确保留：**本轮生产兽化与选择器在命令边界替身下执行，独立协议及反例回归
可以运行；两套PCK已通过普通Godot真实加载/播放/资源检查。现环境仍缺锁版本体和程序集，
整Mod当前DLL绑定、四组游戏阶段、当前完整安装ZIP、双端网络、实际跨进程恢复未完成。
UseSelector入口有锁版API索引，完整接口及加载链参考实际上游源码；它们仍须本体编译确认。
领域C01外部Prefix冲突、C02混合/未知来源保守保留和C03网络未验证状态没有因兽化重构消失。

当前实现项为IMPLEMENTATION_TODO的M36–M39；以下章节保留接续背景，与本节冲突时以本节为准。

## 前轮机制与兼容性复核（2026-11-01）

用户要求核对全部特殊机制，重点迎战、领域、玩家信息、其他Mod与多人。最终玩法以
`reference/bear-forge/docs/volibear/DEVELOPMENT.md`为准：领域只压制对敌方有利的特殊贡献，
敌方负面效果、必要事实和到期清理继续；没有改成整招跳过或删除整个混合Power。

本轮修复：迎战确认真实动作入口、正常跳过限敌方阶段、单体/群体的轮次与重置守卫、
意图演出不计入吸收；领域敌源状态对队友的保护统一到全场判定，反馈归实际持有者，
无效持有者不占补偿去重名额，对敌不利的增伤不被中和；兽化适配覆盖第三方类型及晚加载
继承链，检索/回收使用BaseLib按玩家提供的手牌容量。能力数值、原敌方目标、原生随机数和
原牌网络身份保持现有契约。卡牌/遗物补齐自定义机制悬停说明；迎战牌悬停还读取当前共享
账本列出已用行动的存活敌人，查看提示不会消费行动。领域状态文字区分全队压制和本人收益。

以下限制仍然存在，不能据本轮局部回归宣称已消除：

- `DomainSteamEruptionEffects.CheckHandoffPrefixes`会拒绝公共伤害入口或瀑布巨人阶段入口的
  外部Prefix；正常初始化会检查，所以这是一类明确的跨Mod冲突。不能直接移除检查，必须先
  在锁版游戏里证明异步来源绑定不会被同入口重入错误消费。
- Hex/Tangled/Smoggy/Ringing等混合/未知来源会保留原生贡献并输出
  `DOMAIN_CARD_SOURCE_UNSUPPORTED`，可能漏压敌方部分；第三方新增的私有状态机或直接写值
  不会自动得到完整领域适配。当前结构是统一来源判定加较重的锁版原生适配层。
- 生产声明仍为单人候选。双玩家边界夹具只检查共享机会、作用范围和所有权，不是双客户端
  联机。当前存档路径是原生房间入口检查点重建；战斗sidecar没有独立的中途快照协议。
  真实联机、并发请求、断线重连以及动作重放能否恢复这些状态，仍需锁版原游戏验证。
- 现环境仍缺少StS2 0.107.1/59260271程序集。完整当前DLL、真实游戏与悬停渲染、双端网络
  未执行；命令边界替身与独立Harmony验证必须分别标明。

继续验证沿用下方T01–T05入口；本轮新增回归进入`python -B -m unittest discover -s tests -v`，
不另造平行玩法模拟器。对应实现项为IMPLEMENTATION_TODO的M32–M35。

## 最新恢复检查点：Mode 7交付

用户已授权持续完成、GitHub推送及PR，不再逐阶段征求确认。Mode 7的实现判定是：
假设所有已实现行为正确，既定产品范围没有缺项；正确性必须另有实际证据。
范围为89卡／178牌面、两遗物、完整机制、角色动画、能量UI、战斗VFX、双音频、
存读档、安装／卸载及实际游戏流程。

本轮找回`e1eb166`及其后的未提交美术／音频工作，在新分支`codex/mode7-completion`
继续。确认GitHub主分支仍为`6545593`，没有覆盖更新。恢复出的两遗物PNG、能量动画、
耗尽历史锚点、物理命中映射、全部雷伤入口及整批迎战语音接线均保留并重新核对。
新增修复包括B04格挡等待后失效目标守卫、私有音频真实时长回退、完整分发许可／音频出处，
以及领域／兽化地面光环按原生角色尺度放大至1.8倍。详见M28–M31。

当前既定产品功能均找到生产实现和正常入口。独立Python／C#回归、两套音频解码及
Godot4.5.1资源构建／播放／渲染已执行；英文音频的11个固定公开源也已重新下载并验证。
资源预览覆盖两遗物、能量变化、全部40种特效及深浅背景。真实引擎资源渲染与原生游戏
流程分别记录，不能把前者写成后者。单次证据仍只保存在被忽略的artifacts／.local下。

**剩余游戏环境阻塞：**当前环境未安装StS2 0.107.1／59260271，完整工程构建实际在
`CheckGameReference`处因缺少`Sts2DataDir/sts2.dll`停止；当前DLL、Harmony组合、正常流程、
隔离存读档及完整安装ZIP尚未完成。

GitHub连接此前未包含目标仓库，创建分支返回403。用户随后把目标仓库加入连接范围，
现已实际创建`codex/mode7-completion`分支。线上交付使用该独立分支与PR；已有用户授权持续有效。
恢复目标游戏环境后沿用下方既有命令完成T01–T05。两套资源ZIP仅替换PCK，必须配套同一版源码构建的DLL。

用户另要求可直接解压到已有本地Git仓库的覆盖ZIP。该包按仓库相对路径包含基线`6545593`
之后的全部改动文件与当前`.gitignore`；私有原始／处理音频及两份最终PCK放在被忽略的
`.local/`内。包不带`.git/`或`.local/config.json`，保留接收机器的Git历史和本机配置。
前轮包没有删除文件；本轮删除旧兽化实现，已加入摘要清理清单和统一入口，详见顶部。
完成清理后`git add .`不会纳入这些尚未被跟踪的私有文件。若本地以前强制跟踪过私有文件，
`.gitignore`不会自动取消其跟踪。

完整目标仍未完成，用户已批准持续实施，不再逐阶段请求授权。最新目标以 OVERNIGHT_PLAN / TEST_SPEC 为准：89卡/178牌面、完整机制与表现、正式敌人覆盖；BaseLib 取代 RitsuLib。

## 当前执行入口

用户最新要求：实际缺失必须落成清单、commit/push，之后逐条完成并打勾。以 [IMPLEMENTATION_TODO.md](IMPLEMENTATION_TODO.md) 为当前执行清单，下方长篇记录只作历史背景，不再用“继续收尾”代替明确条目。

## 本轮追加：遗物、能量、表现接线与双音频（2026-11-01）

用户已明确授权推送GitHub或创建PR，并要求在发布前完成可独立处理的美术／特效／音频改进。
M22–M28记录于IMPLEMENTATION_TODO。两遗物现用原创透明PNG，普通／放大／悬停图均接到
VolibearIcons；能量场景有真实运动的周边电弧与只读原生Label反馈，脚本不挂在会被BaseLib替换的根上。

补齐的表现接线包括耗尽等事件使用已有真实历史牌面锚点、按实际physical cue选择命中特效、
全部雷伤重载共享订阅入口、真正迎战开始后的挑战语音及全体调用去重。主要机制与卡牌数值没有重写。

音频说明与英文源URL见`assets/animation/audio/profiles/README.md`。`open`是离线默认；
`riot_en`为9英文发声＋2官方Q研发SFX，其余43 cue回退。W/E/R独立SFX确切媒体尚未取得，
不得把VO文件或研发样例称为当前客户端完整音库。所有Riot媒体只在忽略目录；公开Git保存清单与工具。
两方案均已构建完整资源PCK并进行Godot加载、实际播放／解码及清理检查；不能据此称原生游戏验收通过。

`python tools/audio_profiles.py package --profile open|riot_en --godot <Godot4.5.1-mono>`生成
资源替换ZIP，仍需要匹配的新DLL。此机器缺少StS2锁版程序集，不能生成本轮最终DLL或完整安装ZIP。
后续原生验证仍按下一节接续，不能拿历史DLL搭配新PCK宣称本轮完整包已完成。

## 本轮复核后的续作入口（2026-11-01）

复核基线为`6545593`。89卡/178牌面、两遗物和主要机制具有生产实现；复核新增M16–M21见IMPLEMENTATION_TODO：原生卡牌分类、B04等待后的终局守卫、低血初始快照、重演动作、三类验收入口及打包许可路径已修复。批准资产与玩法数值保持原样。

当前环境已执行可运行的Python和.NET9逻辑回归，并用Godot4.5.1 Mono重建PCK、执行资源与特效生命周期检查。这里没有锁版游戏程序集及可运行游戏，因此没有执行完整Mod编译、Harmony实际组合或正常游戏流程；T01–T05的原生部分继续保持未完成。具体测试结果在本轮对话中，运行输出只在被忽略的临时目录中。

接到安装了StS2 **0.107.1 / 59260271** 的机器后：

1. 配置`.local/config.json`的`game_dir`、`dotnet`及所需Godot路径。`python -B tools/dependencies.py fetch`获取固定BaseLib3.4.7；其原始许可现在随仓库提供。
2. `python -B -m unittest discover -s tests -v`，先补跑本轮跳过的原生/平台检查；`python -B tools/dev.py build`编译当前DLL。
3. `python -B tools/build_assets.py --godot <Godot4.5.1-mono>`重建当前PCK。退出测试进程后再部署同一候选，避免在活动实例中替换程序集。
4. 按[HEADLESS_TESTING.md](HEADLESS_TESTING.md)的新批次入口执行T02/T03/T04。Windows统一使用`--display background`，Linux使用`--display xvfb`；保持私有资料目录。使用`--use-deployed`连续检查已部署的同一候选。
5. `python -B tools/native_run_pair.py --execute-native --display background`执行正常三战存档、必要重启及Continue；Linux改为`--display xvfb`。工具只接受本次新建的私有profile，不接受已有存档路径。
6. 原生问题修复后重新构建DLL/PCK，再运行`python -B tools/release_package.py`生成完整安装包。当前没有可替代这一步的新ZIP。

单独运行SDK逻辑测试时可把.NET9的`dotnet`放到PATH，或设置`VOLIBEAR_DOTNET`；无需伪造`game_dir`。仅有SDK不能使游戏引用检查通过。

## 上一换机记录：阶段一自报完成，下一步T01（历史）

用户要求先完成阶段一再commit/push，然后在另一台机器继续。当前IMPLEMENTATION_TODO的P/M/V/A实现项已全部完成；T01–T05未开始。不要重开无界实现审计，也不要把编译成功当行为验收。所有作者已冻结，无游戏进程、无待收构建作业。最新冻结后Release构建成功；完整编译仅3处旧EnemyExplorationProbe CS8602，最后增量编译0错误。新领域表现包括已存在适配的实际执行取消门与原生Damage/GainBlock/Power/Play/Draw/关键词/费用实际消费边界，预览不准入。新的Harmony IL安装与运行行为尚未验证，正是T02任务。

另一台机器：
1. 拉取main，先读IMPLEMENTATION_TODO和本节；本节之后都是历史过程，不得沿用旧未完成或活跃作者状态。
2. 按README配置本机.local/config.json（game_dir/dotnet），安装匹配StS2 0.107.1/59260271、.NET9、BaseLib3.4.7。游戏程序集、本机配置、存档不在Git，不要为了编译而提交它们。
3. 直接进入T01：`python -B -m unittest discover -s tests`。修真实失败，已知tests/test_release_package.py旧candidate-not-accepted断言与当前packaged-build状态需要核对维护，不删测试掩盖失败。`python -B tools/dev.py build`为Release入口。
4. T02验证正常入口新增Harmony安装及组合，再按T03/T04复用现有真实队列hook。保持同一个私有后台游戏实例批量，不用OS键鼠/抢焦点；隔离普通/云存档。正常native-run不装DevelopmentBootstrap。现有headless run_once支持卡批次，但CLI批次参数仍需在T03接好，别扩新测试平台。
5. .local/packs与.local/release未提交；另一台用`python -B tools/build_assets.py --godot <Godot4.5.1-mono可执行文件>`重建资源包。当前本机新PCK为173580064字节，构建器资源与效果生命周期检查通过，批准图像/音频未改。最终ZIP仍旧版，必须在T05用测试修正后的DLL/PCK重生成，不能直接交旧ZIP。
6. 持续goal属于会话而不是Git；新会话按此清单恢复两阶段目标（实现阶段已完成，继续T01–T05）。本机在本次提交后不继续改动，方便换机衔接。

## 此前推进过程（goal revision13，历史）

用户明确要求继续。有限M14c核对已完成，21条事件绑定/3类动画处理列入清单并push `c3e0501`。不是94个资源全未写。除V04最后领域表现执行门之外，其余代码已整合；尚未统一勾选/提交代码，不能把清单commit当实现commit。

主新增GameplayPresentationReceipts与Bridge.Semantics，接真实Scry overlay Push、持久咬痕及其余语义消费者；动画作者b87已freeze Bridge/Motion，读取trigger/fallback/segment/timed/arbitration。主已补兽化材料按T01/T02实际形态选择动作，以及transfer在Convert真实提交后、Converted观察者前发布。原LightningCmd/BeastForms公开签名保留重载。aa907生产receipt作者已freeze。10554仍独占V04领域通知尾项（已有适配执行门、真实Damage/GainBlock Hook消费隔离、最后Chains/Artifact/Burrowed），主不并改其文件。

全构建pwsh-40933e562b7f4762、pwsh-8fbd1dbe7c734ad9均成功0错误/3旧probe警告，输出已收；之后主还有上述兽化动作修正，最终需再build。运行effects.gd咆哮目标锚点已修，资源pack重建pwsh-5aaac65005af43af成功，全部输出已收：173580064 bytes，批准图像/音频逐字节不变，构建器资源/生命周期检查通过；不是游戏验收。Godot位于LOCALAPPDATA/Programs/godot-4.5.1-mono/Godot_v4.5.1-stable_mono_win64/下console exe。没有运行完整测试或启动游戏；ZIP仍旧，阶段二T01–T05未开始。接V04 freeze后最终整合编译/diff，勾选实现清单并commit/push，再立即阶段二。

## 此前推进（goal revision12，历史）

清单已push于15aae42，领域补丁已push于ddaf508。用户要求更新goal并开始执行，已edit+resume为revision12/armed。M12四文件已freeze且正常接线完整。M14a/b由主接管Bridge三处机械收口：CanvasItem锚点类型、Tick到期与死亡/终局/退出清理，实际费用receipt已接。全构建先发现该类型错误，修后pwsh-4e4d8f3f733848d3成功0错误/3旧probe警告（输出已收）。当前仅M14c有限表现事件核对及M15最终确认未收口；b03只读核对，不再改Bridge。没有运行测试或游戏，阶段二尚未开始。按IMPLEMENTATION_TODO逐项勾选推进。

## 此前两阶段执行状态（goal revision10，历史）

- 用户要求的初始commit/push已完成：main与origin/main均为`1c8990e1d786ea29f4dc7fb49b9daacf48bd1f91`，作者fltb <fltbk@outlook.com>，没有强推。goal `goal-1d63ebb0-0a2b-41bc-8c03-869ba9fefaee`已按新指令edit+resume至revision10；下面revision7/blocked旧记载只是历史。
- **仍在阶段1补真遗漏，尚未开始新一轮正确性测试。** 89卡/178牌面及两遗物静态审计有实际实现，但领域遗漏真实存在，故此前“全部写完”不可沿用。已交付ZIP仍是初始commit版本，不含本轮补丁。
- 已补并接普通入口：六类玩家负面、Tender/永久负力量敏捷与Possess返还、八类敌源状态及Wither强化、Galvanic/VitalSpark/Tainted/PaperCuts、偷金/Sandpit强杀/Fat逃跑/Surprise召唤及赃款返还、额外敌方正伤害/被动力量格挡。共享PowerCmd提交adapter已增加真实choiceContext并接debuff/stat/Tainted记录与精确取消门。
- Stock/Adaptable/TestSubject及PainfulStabs保尸：f4a新增AdditionalRevivalEffects两文件，主已接Install与AfterDomainOpened；作者仍在补ToughEgg实际孵化正HP重置/清负面保护性阶段。不得吞整move或伪造死亡。主另补DomainSummonEffects.Additional四实际出生调用（LivingFog/TwoTailedRat/Fogmog/TheObscura），保混合攻击/计数/HasSummoned和已提交子实体；尚待统一编译及阶段2运行验证。
- 表现b03已补低血30%入35%出、选角/胜利语音、真实治疗/返能及已提交能力/卡牌VFX；仍续作真实净化卡锚点保留与实际目标减费receipt。不要用不可见伪节点或grant来源牌冒充减费目标。
- 最近主全构建`pwsh-1967954629b14527`已收：special/additional/passive/presentation首组及四召唤整合0错误/3既有probe可空警告；随后已接ControlledEffects.NextPlayDiscount.Grant与TargetCosts.SpendResolved真实减费receipt，保原支付Task身份。ToughEgg及表现最终尾项仍待下一构建。各作者最小独立编译不是完整安装或行为验证。当前没有游戏进程；本阶段未新增测试、未运行测试或游戏。普通diff --check的CR告警来自既有index/working均CRLF且attr/-text，保换行使用一次性git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check已通过，不改变持久Git设置。
- 活跃作者：f4a3c6cf-d7b9-4da2-81d3-f9d088945219独占AdditionalRevivalEffects*.cs继续ToughEgg；b03e1fc6-c935-4717-ad83-da647fad3857独占PresentationBridge/Cues及可新增CostPresentationReceipts继续实际减费。6e、70eff、fd738各生产文件已freeze。主独占共享接线、DomainSummonEffects、统一构建/部署/游戏。
- 下一步：收两作者有限生产尾项→统一构建并核普通入口/实际diff→确认已识别实现遗漏全部闭合→阶段2复用现有测试修真实失败、同后台实例队列hook批量→重新打包。不要先开无限probe研究，也不要把未运行的IL安装检查称已通过。

### 上一交付阶段的记录

### 最新用户决策：提交推送后，先核实实现完整，再验证正确性

用户已明确要求先commit/push当前已交付实现，再将goal更新为两阶段：1）确认功能确实写全，遗漏先补；2）确认写全之后，复用现有测试与真实队列hook验证正确性、修复失败并更新包。此前停止测试仅为上一阶段指令，现已由此更新。实现审计不以未测试冒充缺实现；测试阶段不以编译/打包成功冒充行为正确。继续禁止OS键鼠/抢焦点与逐case重启；保持同一后台进程批量运行及普通存档隔离。新顺序亦已写入AGENTS最高优先级。

当前安装包已生成并交付；Release编译通过。尚未完成本次要求的实现完整性复核或最终全量正确性验证，不能据此前交付措辞推定二者已经完成。

### 此前用户决策：停止测试建设，直接完成代码并交付

用户已明确撤销“完整测试覆盖作为交付前提”，要求只写完功能并打包；已写入仓库AGENTS最高优先级章节。下方全覆盖待办和旧goal文字不再作为本次交付阻塞。所有作者已停止测试扩展并冻结，没有因为未测而确认新的生产缺陷。

已完成实际产品收尾：普通ModEntry接入VolibearInspectPortraits，正常Inspect使用批准大图、手牌保留小图；修正模组清单旧“M0未实现”描述为中文产品说明。全部当前源码通过Release编译，0错误、3个未接入普通流程的EnemyExplorationProbe可空警告。未再运行测试或启动游戏。便携包已改为产品命名/packaged-build标识，不宣称全量验收，随附固定BaseLib及中文安装说明。打包已成功，交付物为[Volibear安装包](../.local/release/Volibear-0.1.0-StS2-0.107.1.zip)。所有主后台作业均已收，无游戏进程在跑；交付后只按用户新请求工作，不重启旧覆盖率研究。

持久goal revision7仍是旧文字：在agent消息触发的回合尝试按用户新指令更新时被工具拒绝（requires direct human turn）；下一次直接人类回合应更新为功能实现/打包交付，不得因旧goal文本恢复用户明确叫停的测试。

### 17:20 历史状态（已被上方用户最新决策覆盖）

- 用户再次明确：一个后台游戏实例连续跑，不得每用例重启。旧逐case批次 pwsh-c4f39ce88dd84954 已依指令取消并收输出，最后中断C12-base-dexterity；此前报告保留。已确认无sts2/console进程。当前无主game/后台作业。
- 最小化窗口+SW_SHOWMINNOACTIVE实测仍抢焦点，已弃用。现background模式用CreateDesktop创建**未切换**的私有桌面，子进程STARTUPINFO.lpDesktop指定，永不SwitchDesktop/SetThreadDesktop/SendInput；正常原生GPU渲染、Dummy音频；job清理连同desktop释放。35工具单测通过，stock+B01弱势+Hopper off真实运行：前台全程仅LOL、0输入、desktop句柄表归零。不要再回到OS鼠标或每例启动方案。
- 冻结356构建实际Hopper全部8case全门PASS。B02两面plain/dexterity/frail、B01两面各分支、B03、C01/02/03/08/09及C12早期分支已通过（不把重复运行相加计覆盖）。未跑剩余牌面等单进程batch。
- 新Steam四keeper after-hp/after-damage曾FAIL是旧sole IsEnding/history前提误套；f4a已窄修独立oracle且4原receipt离线revalidate通过，**未重写旧report/未称游戏重跑**。两set-hp已nativePASS。sole-ending三case原始FAIL保留；f4a新增独立自然TreeExited/audioTail观测已freeze、41定向单测通过，未编译/未native验证，不动业务Core或原29语义。
- 音频资产收尾已实际PASS：47资产/54cue/26序列/7源录音；official目录153原始音频解码一致。固定FFmpeg8.1.2在.local工具目录，独立树运行原验证器，资产字节不改；不代表人耳听过。9个生产状态机测试（含5个真实隔离编译行为mutants）再次通过。
- a978现在最高优先级交单进程card-face batch+共享NativeAcceptanceRunHost（已有源码、未统一编译），其398冻结点存在已发现的combat-card索引采样时点bug，**不要部署原398**；下一freeze包含修复。其余§7边界继续同作者。7022独立写48上下生命周期case、复用host，同进程新run；52写合法native-run全流程，不装debug bootstrap；b03写G5真实viewport/本游戏PCM，不捕系统音频；e56补正式敌人独立语义oracle（已23模型进展，不计G4完成）。这些新入口均未统一接ModEntry/headless，作者未freeze前不可部署组合。
- 主已加单例R09-summon→OvicopterNormal的共享bootstrap映射；batch host须自行同样选原生encounter。12个paid slime选择文件已用现工具生成，尚未native执行。后续先等a978最小batch freeze→统一稳定快照编译→单私有桌面进程连续验收，不再重启数百次。

**用户最新纠正：停止键鼠尝试，改用hook出牌验收。** 不再启动manual_input/SendInput、夺焦点或要求用户停用桌面；实际PlayCardAction→RequestEnqueue支付/选择/结算入口已存在，继续使用，不能改为直接调用OnPlay绕过扣费。两次窗口尝试均0鼠标包，第二次OS拒激活，未获得普通OS输入通过证据；用户不要求继续这条路线。旧G6 OS输入作为阻塞的路线已被新指令取代。

最新主作业均已收：356快照build0/0、实际block modifier25与15安装组合55通过；Basic2 B02/B04四处0props改Move，原生B02两面plain/dexterity/frail六case全部PASS。Hopper off行为oracle通过但headless preloading报Dummy texture t=null，外部门FAIL，不能豁免；后续用游戏内hook继续验收，非OS输入。当前无主game job。全回归仍待最终freeze；a978在live补§7（390冻结副本在artifacts/card-face-author-freeze-390），e56正式paid敌人驱动已freeze但G4未完成。资产verify通过89卡/356导出/89独图；audio验证因进程PATH无ffmpeg失败，official catalog check尚未执行，需使用已配置ffmpeg位置再验证。

- 用户明确“这一轮必须交付成品”。**下列旧章节的fatal-parity/通用observer/lineage研究路线不再是下一步**；不新增平台或自造发布门。完成既定功能→冻结→集中原生验收→重生成安装包；不得把候选或单测计数称成品。最新完整离线基线仍736，不把后续定向测试相加冒充全回归。
- 真实缺陷Hopper已修：新增DomainHopperDecision/Effects/Effects.Patches，精确C移除门与M物理提交门（原BeforeCardRemoved/GetResult后）分别重验；取消M保C与此前history/hook残余，跳对应Loot/Swipe mount；已提交M保原后续。4体复用生产SummonRegistration，未改共享Apply/原BeforeDeath/Escape，没有debt archive。49定向checks/3Python通过；f4a独审两窗口无当前固定路径P1/P2。主接ModEntry第15Install，完整实际源码组合已在178快照执行：15 installers/55checks、audio50、gate34、Lightning14、ordinary26通过。未知/热安装/foreign变换不扩结论。
- 卡面真实paid/choice probe新增CardFaceAcceptanceProbe + tools/card_face_evidence.py；89 IDs/178faces/**268cases**入口完成，非仅实例化。178冻结副本在`.local/acceptance-snapshots/card-face-178`，同源完整Mod编译0error/1 nullable warning（146行，作者正修），与同版本oracle配套。作者a978仍在live补§7分支，已允许续写；不要以268入口存在宣称G2通过。
- 主已接card-face-acceptance scenario、headless run_once参数card_face_case/CLI --card-face-case；路由缺native receipt拒绝定向33测试通过。隔离bootstrap核实际UserDataRoot/Steam关闭后仅runtime Prefs设Fast，日志ACCEPTANCE_SPEED记录，不读改普通prefs。dev doctor已修官方BaseLib UTF8 BOM解析，21工具测试通过。csproj加PathMap，不改资源。
- 主game job `pwsh-452d9eebd2d94484`已收exit0：stock `080809Z-e3295d73`成功，B01-base-plain `080827Z-6595e795`、B01-upgrade-plain `080840Z-c507e61e`、B02-base-plain `080852Z-321b3776`真实paid/HP/history/能量分别PASS，独立oracle与所有外部隔离/退出门通过。已安全部署178冻结DLL/manifest+原PCK，非旧684版。**现在唯一game job `pwsh-eab051db54ec4446`**串行剩余265case，复用该真实stock对照，使用冻结oracle/每次核DLL未变化，遇首失败停止；勿另起game或覆盖部署。3例不是178全通过。
- f4a已对原11 OPEN做锁版有限源复核，可作为有理由N/A而非PASS：Single/MultiAttackMove、One/TenHp为dummy；3个Mock为test models；3个TheAdversary为已注册未接内容（不臆称用途）；TunnelerNormal为未入池encounter。它们全source只有自身定义+AbstractModelSubtypes，未被四Act/事件/召唤接入；ModelDb177/182/265–285经Acts→ActModel144/169派生正式列表，不把类型目录视作生成列表。DevConsole可强开不等正常可达。**Tunneler正式怪物仍必须保留**：Hive94→TunnelerWeak16/20可达；原raw catalog的REACHABILITY_UNRESOLVED只反映发现阶段，不伪改历史catalog。
- 包装脚本tools/release_package.py、14测试、docs/INSTALL_ZH.md已freeze；`.local/release/Volibear-candidate-0.107.1-59260271.zip`为旧构建候选9 entries/169902151 bytes，含固定BaseLib3.4.7原文件/license，不含游戏程序集/存档/研发设置。最终需用验收后DLL重新生成，当前不是成品。PCK中STAGED_ASSETS等历史provenance绝对key不是运行依赖；不得为自加全字节grep门重打批准资源。
- 活跃委派：7022正写DomainHopperProbe+oracle/tests（Core已freeze），8原生cases/scenario domain-hopper/ThievingHopperWeak；52正写Steam keeper六正例+sole-ending负控，保原29，纯probe/oracle与steam_native_protocol向后兼容参数；a978补全部§7；f4a只读分类原11 OPEN类型。各writer不game，主独占ModEntry/bootstrap/headless及全mod/game。
- 桌面只读核实：前台为League of Legends Client PID9496/HWND397044，非旧LockApp；输入包0。普通窗口验收不得在用户操作其它窗口时盲目夺焦点。
- 精确下一步：收上述native job；处理真实失败（优先离线复现），整合冻结Hopper/Steam probes和§7，统一全build/正式测试后串行完整现有机制+卡面验收、普通窗口输入/表现/存读档/安装卸载，最后重生成并交付包。未完成G2/G4/G5/G6等不能省略；不再以另一轮研究报告结束。

## 较早增量：Summon A档注册/退休已接入离线候选（goal round3）

- 52已freeze/释放全部文件；主已收pwsh-3abaf20f5a2240ed：完整Mod build **0 warnings/errors**，正式全离线 **736 tests/52.489s/OK**，包含当前actual14-source安装组合。无game/deploy；本机安装包仍旧候选。goal revision4 active/armed，未完成。主无未收job、无writer。
- 生产已接入：弱actual-box map跨Reset保留；实际await调度前bind；birth vs resume、source/kind校验；原SetResult/SetException前close且closed脱payload；exact单次Forward票据保旧epoch与unknown屏障；SpawnBot pre-combat/Ovi pre-slot退休门。无Outer/Revival/严格death迁移。f4a冻结源+现DLL独立 **CLR186、原生IL/双安装顺序142、全源组合exit0**通过；只证明该A档，不是fullReset游戏验收。
- f4a未freeze源审抓到P2：新birth AfterDeath经closed旧power索引借权限而成功吞掉原native异常。52已用实际CanAttachDeathBirth(!closed||cancelled)修，f4a现源复核堵住反例：closed未取消旧索引不给新Task授权；已消费取消保legacy sticky；真正oldTask墓碑仍拒。MatchingEvent/veto未改。另已补shared root+2child Close/错源kind/GC强引用释放及每method全部await anchors方法多重集合；f4a已冻结源复核及现DLL复验，本轮P2可关闭；尚未执行实际Infested世界反例，不冒称原生回调验收。注册抛错fatal-parity仍NOT_RUN，不拿GetResult fault充数。
- 主补3显式csproj的SummonRegistration链，实际MSBuild默认/旧自包含override两分支通过；两audio显式项目另build0/0。DomainSummonD17Probe改Payload，退休/closed仅metadata、不猜owner/不Snapshot/不移除Domain，live JSON不变；原strict oracle未改，22组退休meta负例含在9方法PASS与736。全源实际gate及probe **7case34checks**已主与f4a各执行通过，另Lightning14/ordinary26/fullchain55/audio50均在组合marker中。
- §9.2/15.8已落A状态契约和生产相关测试映射；锁版Fabricator helpers到SpawnBot实际是static readonly options字段load（不是instance），无中间Combat/Rng/slot方法读取。不能把metadata形状叫native reset通过。
- **精确下一步**：先补当前生产bridge的awaiter注册自身抛错fatal parity（复用已修phase2a原生fatal等待/父进程诊断思路，不能正常退出或timeout算通过、不另造framework）。随后再收B/C原子接线与postAdd安全，边界见下节52评估；A不涵盖Outer首次wait、实际后选move/history/performing flag、严格death callback链。当前没有game/deploy；不反复上应用调试。

## 较早增量：雷伤响应链行为回归与召唤接入边界（goal round2）

- 主已收pwsh-7286f42b30134461：完整Mod build **0 warnings/errors**，全正式离线 **733 tests/49.405s/OK**。无game/deploy。源码/测试仍大量untracked，未commit；不得把源码新结果当当前已安装包。
- 新Core/LightningResponseDispatch.cs被实际LightningBatches.Notify调用，保原guard closed→CanUse→samecombat→round→playerTurn、一次快照、Active检查与串行await；Subscription/Scopes/Reset未改，是既有正确语义的可测试抽取，不是新规则。
- 正式tests/lightning_responses直接Compile helper+LightningCounter，9命名序列44断言，Python入口13方法；新增/移除/串行受控Task/close/fault/cancel不退款/实例/嵌套/空集合。主另加全源码CLR harness的LightningResponseAdapterTests，实际Subscription.Invoke/Dispose及Reset关闭两个owner共14check；原生类型仅身份，不读world。原callback不假完成，settle后禁后续。f4a源审与现DLL9/44及实际14独立通过，无窄delta P1/P2。
- §15.7已加状态机与测试映射，明确未取消已进入回调，也未执行native CanUse/HP/轮次。7022/f4a均已freeze/释放，无writer/background job。末尾git默认diff --check将既有CRLF行当trailing whitespace报exit1；以一次命令cr-at-eol识别Windows换行后通过，未修改配置或批量改旧文件。新文件untracked不由git diff覆盖，已读源/编译/回归/独审。
- 52c只读完成旧Summon V2与现production接入评估：**下一步优先A档，仅已进入并确权的Summon批次**；复用实际box调度前绑定、弱tombstone、一次性kind+subject handoff和terminal close，保本轮已测pure decision。无需新history producer，不再新建泛探索stage/driver。
- A档候选取自.local/domain-summon-integration-stage的RegistrationHub/Coordinator及migrated/DomainSummonResetRepair的BindRegistration/Close/Ticket/Early guards；不是整包替换。不直接抄V2 Enter要求PendingMove/PendingCallback（缺dispatcher会让正常来源全部Unknown）；不要整句抄Reset只generation++去改变Attempts/veto生命周期。优先改Tasks实际box身份与注册时序，现production ret-only rebind无法覆盖inline-beforeLeave。
- A档需补/跑：actual registration→inline/resume/reset前后known-retired，unknown不能补生；stale Forward exact一次ticket不重生current且helper前置读取单独核；SpawnBot pre-combat/Ovi pre-slot的known-retired guard早于失效解引用；Add提交前/后分开，已提交child的GetResult/Minion/StartStunned/cleanup不能被吞。旧V2已有专用CLR/IL测试可复用，必须改编为当前production相关正式测试，不仅跑冻结副本。
- B档oldOuter首次await→source属于另一原子接入：SourceDispatch/EarlyIntentEmitter/Topology/Hub与当前Dampen Outer AwaitBound必须统一，禁止叠第二await rewriter。C档Infested严格death还需Kill→Hook→callback完整handoff，不能抢Revival已替换锚点。未集成B/C，不能声称fullReset。
- EarlyRetired旧方案只针对白名单初始意图旧invocation退休；CaptureIntent在native首await前**额外读一次NextMove**，不等于await后的actual Selected，不能发History credit，不能借phase1/2a通过升级无干扰观察。same-epoch改意图照常执行、无/错witness不earlycut的旧反例须保留。A档不需要新增此读。
- 尚未解决：entry/ret builder.Task getter扰动/cached CompletedTask出生身份、postAdd完整reset、Forward helper失效读取、foreign patch中途变化。2a仅手写三await，单调site不能直接套Ovi/Infested循环。旧V2只受控quiescent安装；phase1不支持通用structural splice，不可贴标签替代专用emitter验证。

## 较早增量：召唤/复活状态机与已知过期门修复（goal round1）

- 主已收pwsh-df661c12bb374380：完整Mod build **0 warnings/errors**，全正式离线 **720 tests/46.240s/OK**。无game/deploy；实际安装仍旧候选。用户“先状态机→单测→集中真机”顺序保持，goal未完成。
- Core/DomainSummonDecision.cs保原嵌套DeathDecision API/行为，DomainSummonEffects改partial；Core/RevivalDecision.cs原顶层类原样移动，DomainRevivalEffects适配逻辑不改。四个显式源码旧测试项目补新文件；SummonSource/RevivalSource旧自包含override仅未override时才默认加入DecisionSource，主实际MSBuild求值默认/override两支均通过。
- 唯一玩法delta：实际CancelAtGate区分Unknown(no binding)/Current/StaleKnown(已知frame或batch世代失效)。Unknown保持原生不冒认；StaleKnown在既有precreate gate阻新创建，不设置Decision.Cancelled、不回滚、不改Forward/原Task。此前已知过期和未知合并returnfalse是这个窄处的fail-open。
- 新正式tests/domain_lifecycle_states直编两个实际纯生产源，7命名序列74断言；Python入口11方法（7行为+接线/runner）。涵盖已允许首child边界后取消剩余、Close/prevented/独立批、三态归属、复活pending/confirmed/committed/domain、引用身份、仅未开始回调可跳。
- 主另加tests/domain_steam_v1/SummonBoundaryAdapterTests.cs，调用真正privateFrame/Binding/Batch及实际Reset/CancelAtGate，6case16check；使用原生类型未初始化对象仅作身份，不执行native世界。Unknown current/old false，known oldframe/oldbatch/futureframe true；fixtureTask不换、Domain取消位不伪设。已并入既有实际14-source CLR harness/Python门，720包含它。
- 主额外build四旧项目audio_receipts/audio_receipt_probe/domain_revival/domain_summon_effects全部0/0；实际msbuild Compile项目求值支持旧self-contained source override，不改旧冻结stage。7022作者已freeze/释放全部文件；f4a已独立源对照确认decision原样移动，纯DLL7/74及实际适配门6/16和既有组合DLL均通过，未见该窄delta P1/P2。无并发writer或后台job。
- **完整reset仍OPEN**：Tasks清空后旧resume变Unknown；Ovi/Fabricator到gate前原生解引用；post-Add继续/清理；旧Forward新开子调用。此次只修已知拥有的过期frame恰好到达既有gate的路径，不声称旧native await已取消或所有召唤安全。状态图§9.1/15.6明确此界限。
- 下一步继续真实生命周期缺口与偷牌归还实现/单测；不要以新增纯kernel覆盖代替fullReset/native验收，也不要恢复空过回合探索。

## 较早增量：状态机驱动的第一批实现已整合

- 用户顺序不变：状态机→生产实现相关单测→稳定后集中真机；goal revision4 active/armed。本轮没有启动游戏、没有部署；已安装候选仍是此前684版本，不能把最新源码内核结果当已安装包证据。
- 主已收pwsh-c8e1ec9f2d1b4978：完整Mod build **0 warning/error**；全正式离线 **709 tests/46.927s/OK**。临时目录里的部署/卸载与CLI拒绝输出属于离线工具测试，不是实际游戏部署/运行。
- 新正式Core/EngageOpportunityLedger.cs已被EngageCmd使用，唯一账本保存early/action两个round事实、引用身份、可信currentcombat、generation。Reset与实际combat切换均撤销旧window，补A→B→A；原实际PerformMove/初始MoveNext/吸收/responders次序不改。不宣称取消原生await或解决全native reset。
- 主发现作者漏了EnemyMatrixProbe/EnemyExplorationProbe反射旧ConsumedRounds/ActionRounds会运行时失败，已改为Engage的只读EarlyOpportunityEntryCount/NaturalOpportunityEntryCount；两者分别统计nullable.HasValue的本战留存条目（真实action含早迎战的那次，不是natural-only/current-round）。保原JSON键，不恢复第二套字典。新第8内核序列+静态接线契约覆盖此兼容。
- 迎战正式8序列共85断言，Python另有runner负控与静态契约；f4a已独立现DLL8case/85全通过、源对照无新P1/P2，限机会内核/窗口权限，不是原生动作与SpawnedThisTurn验收。作者7022已完成并释放文件写入权。
- 首批gameplay_state_sequences现在9个Python方法：8正向命名序列 + 5个隔离行为变异（重复附雷、同轮扣领域、失效雷票据、费用值相等混身份、Steam永远压制）全部须编译成功后被指定断言杀死，主定向9/14.124s/OK已收pwsh-39c8161efbfc432a；这些均包含在最新709。
- 状态机图文档§15已更新精确U/C/S/N层级、adapter方法、G7变异、迎战8序列；README已链接。文档是设计/测试映射，不是发布通过账本。
- 87已完成E13源核：玩家侧完整Add初始化后，后续新牌可迎战child；Player→Enemy清SpawnedThisTurn但round不增，故同轮提前消费仍阻正常阶段重复。Enemy侧新召唤被既成快照或flag门阻当侧动作，Enemy→Player才round++；同牌R09固定集合不纳child，后续新牌重新集合可纳。§3.1已补图；不加blanket !SpawnedThisTurn guard。四类原生场景仍待集中验收；仅源码推导，未跑游戏。当前无writer/native/background job。
- 52c两项fault诊断窄修已冻，作者重跑196+parity通过；runtime语义不改、不phase3。旧一次未定位parity失败仍保留。
- 注意choice stage仍NOT_READY且保留旧probe快照：以后集成必须rebase最新Engage诊断接口，不可将旧快照盖回live；当前不改冻结stage或清旧失败。

## 较早增量：状态机先行

- goal revision4保持active/armed：**先游戏状态机→实现相关单元测试→离线回归→稳定候选集中真机验收**，当前不启动游戏、不逐修改部署。用户说开快速模式，隔离配置仍未验证。
- 主新增[状态机图与测试映射](GAMEPLAY_STATE_MACHINES.md)：整局/出牌/敌人机会/领域/净化/贡献/雷伤/兽化/部署/历史/选择/召唤/死亡/偷牌/存档表现，提交边界、异常和交叉序列；§15分U/C/S/N，不声称全部AI或89卡行为完成。
- 主新增tests/gameplay_state_sequences项目，直接编4实际生产内核；正式Python入口tests/test_gameplay_state_sequences.py有8命名序列。首编CS0165局部checks初始化顺序修正；8例通过。全正式离线回归pwsh-94cb4927700d48d5已收exit0：692 tests/29.023s/OK。之后独审补Steam无领域允许伤害/未确认拒收益两侧与文档付款后选择失败不退款，再定向8例全通过；该后补版未重跑整692。无游戏/部署。
- e9独审指出并已修：付款前非法输入与付款后牌效选牌中断分开；补真实adapter方法/静态test/缺失behavior映射；Steam不能只测取消后0伤害。纯内核编排不证明原生支付/实际HP。
- 当前写入作者 **7022e272-dcd1-4a19-97ce-08cbd74bfeab**：独占Core/EngageOpportunityLedger.cs、Core/EngageCmd.cs、tests/engage_opportunities项目及Python入口、必要test_engage_lifecycle.py结构更新。抽实际机会账本并被生产调用，reference身份、预占、自然/提前消费、跨轮、reset与A→B→A generation；保原真实PerformMove/MoveNext观察/吸收/responders/native guards，不擅改SpawnedThisTurn资格。仅纯项目构建/定向offline测试，不Mod完整build/game/deploy；主集成后再回归。不要与其并发改这些文件。
- 3eda选择transport release.seq漏验P2已窄修，ff独立9方法+5反例通过；整体仍NOT_READY/不可部署，完整Power/Move链未实现，旧Knowledge FAIL保留。
- 52c phase2a已冻196，f4a独立现DLL2×196与单fault-parity通过/3对fatal相同；仅手写3await CLR fixture，不是native/history/emitter。原一次parity未定位失败保留。主让52c仅修timeout时输出诊断和FIRST marker缺失可能过顺序断言两小项，不扩phase3。
- dd actual14 composition stage已冻55+6拒绝+6dispatcher组作者通过，未独立复验/未集成。keepalive完整journal/settlement/native probe仍未实现。

## 较早开发策略：用户已明确调整

- 用户要求：**开发优先单元测试、可重复离线回归与真实程序集 CLR 组合测试；应用用于稳定候选集中验收，不反复启动游戏调试。** 主停止扩大空过回合探索，不改一次就启动应用。goal 已 edit 为 revision3、active/armed、max256。用户说已开启快速模式；未核实隔离测试配置，不擅改普通存档设置。
- 当前无主game/job在运行。最后pwsh-43ed703a1c484f60已收exit0，054453Z-39c39b96原清单34–50独立17例全公共门/探索门PASS（仅两回合baseline，不是出牌或完整AI）；选择.local/enemy-exploration-current-34-50-28b0337f/selection.json。此前Knowledge053339失败及31/32整run未PASS状态不改。
- ff只读诊断完成：Knowledge首招原native BlockingPlayerChoiceContext→FromChooseACardScreen(index协议)必须UI选牌，旧WaitFor无modal推进；旧日志没现场UI，不能追称精确await已实测。ff固定只读不能写，主新建stage作者 **3eda191c-6839-4d14-b7bf-38f057a261d4**，仅.local/enemy-exploration-choice-stage。现transport子集实际refs编译，原ChooseCurse→选择call-edge+Reserve/Show/FromIndex/Sync与focus PushInput select；下游OnChosen→Power/outermove严格图未做，gate仍拒Knowledge/NOT_READY，不能当可部署修复。后续先离线测试与审查。
- dd nongeneric-proof已14a独立现DLL6accept/10reject及inlineReturn<SignalAfter通过，仍仅人工CLR。拟5个Dampen V1 metadata exports已14a纯方案认可，仅授权stage副本，保原callvirt、4参数/opaque值/原Task，拒未知postfix与其它patch；完整journal/原子freeze/late-event门必须保留。当前主只读看到游戏loaded coreclr.dll FileVersion9,0,725,31616 commit3c298d9f00936d651cc47d221762474e25277672，不能称宿主已证proof的.NET9.0.22/privatefield硬门满足。

## 早前增量：13:30前后（以下运行状态已被上节覆盖）

- **主现无game，所有main jobs已收**。pwsh-edbeb6a379164991：原冻结80清单21–30项 **052316Z-234c050f全10PASS**，两回合end-turn/ANY、completeAiCoverage=false；选择.local/enemy-exploration-current-21-30-35670844/selection.json，原80不动。前20仅旧候选证据，不能说当前全30/fullAI。
- 随后31–50选择.local/enemy-exploration-current-31-50-8092a469/selection.json，pwsh-57302950d5c84d57已收exit1，**053339Z-c130e82f FAIL**：第三KnowledgeDemonBoss CURSE_OF_KNOWLEDGE_MOVE 后 next Play or native terminal 等待超时（exit2/no_runtime_errors=false），caseCount3/completedfalse；前2KaiserCrab/Knights原始BUDGET_EXIT但整run未PASS，后17未执行。ff只读诊断原生选择界面/暂停点与合法程序化UI推进，不能放长超时/跳case/强改phase掩失败。尚未确认根因；当前候选未重部署。
- 阶段1两P2修冻后**f4a独立现Stage.dll 13GREEN+87PASS**，只关闭quiescent/nongeneric metadata边界内两个洞；generic target硬拒/EarlyGuard→Dispatch恢复。主已授权52新.local/observer-runtime-transport-stage **2a仅真实CLR transport**：手写真实3-await状态机走snapshot原SharedHub/真实builder注册，不手动Bind，不借尚不存在的native structural recipe。opaque/internalreceipt与immutablefacts、Domain先全bind、每sink隔fault、existingTask/no sync getter、signal先撤权/returned与threw分维度；historyproducer/nativeOuter/fullchain/driver/game均未做。旧V2/v3和阶段1冻结。
- 14a已评新独立native-primary-keepalive-mount-mechanism-v1后置机制契约可单独实现，**不替代原8强门**。dd现仅先做nongeneric小CLRproof：真实typed caller原Task/returnedref，真实nongeneric entry+History原call-edge+Dampen形状dispatch→AfterApplied/原Task，不能powerref+时间区间充因果，手调/同ref重入/skip借链都拒；sync m_task为空与async inline完成偏序先验。outerGuard固定NOT_OBSERVED、legacyStrongContract OPEN、solo null原因UNDETERMINED。旧FAIL不回填，不开Profiler/ReJIT，不patchsharedgeneric。还没有8个新native结果。
- README已纠正不可加载/RitsuLib/未开展过引擎验证的过期描述，明确BaseLib3.4.7开发候选与未完成验收，未改资产或core。
- 以下较早主jobs均已收： pwsh-d1069c2aa6674411最终14/14全部原生/common PASS：foreign-retention043947-9a17ca07、late-phase044115-cf0d4780、late-powerless044243-48939986、nested-command044411-ddbc240b、nested-damage044541-1b39d151、off-veto-followup044712-a716f982、ordinary044848-e0bb8e23、overflow045018-2f35dc5b、pending-reset045149-4fb5b932、post-max045319-32872000、post-protected-hp045445-51788ee3、pre-max045613-1c8a72a5、toggle045741-3d20beee、veto-source-retained045912-5f25e3cf（均20261101T…Z）。结合前7，**原Steam29当前21PASS、1FAIL（external-after-damage043424）、7NOT_RUN**，不是全29。pending-reset仅adapter reset，非fullCombatReset。S3两mode已真PASS见下，684正式（含50audio永久回归）PASS/build0/0/安装候选不变。
- dd获准新独立keepalive stage，但**先仅generic guard共享JIT观测方案/CLRproof**，不改core/live/原gate，不先大扩8。14a方案有条件通过：8明确profile native-primary-keepalive-v1/版本，新solo-ending-apply-refusal负控；旧FAIL保留。真实LeafSlimeS Add在ABOUT后，包含合法初始化/Prepare(false)/room历史变化，settle后baseline；boss活时两primary，仅HP0窗口keeper唯一；全interval事件/所有typedrefs不变。外generic可returnnull，内nongeneric也可拒后返回未挂载mutable，所以nonnull不等于mount，真实guard/ApplyInternal/PowerReceived/AfterApplied/taskreturn同attempt闭环。共享泛型不能hardcode Domain或影响别的T，先Domain+另2referenceT交错/嵌套/早null负控；不额外IsEnding查询冒原guard。原任务全部settled再freeze/dispose，独立真实cleanup只杀keeper，不杀veto活boss、不混胜利治疗。
- 新.local/steam-keepalive-stage/generic-proof已冻：真实.NET9.0.22/Harmony、Strength/Dexterity/Weak实际Power类型的人工async-shaped命令，baseline9/9正确；仅闭合Strength MoveNext加dup guard观察后，Dex/Weak共6/9真实Task<T>/结果类型错成Strength（earlynull也Task类型错）。**14a独立现DLL复跑确认**，不是仅标签错误；拒绝当前closed-shared generic patch方案，不能取__originalMethod闭合类型当runtimeT。非nativePowerCmd执行、不否定所有generic方案、不称内部根因已单独证明。当前outergeneric guard无可接受observer，8profile仍未实现/未验证；dd只读设计typed caller精确edge/non-generic路线，不能AsyncLocal下一getter/额外查询/请求T冒充实际calleeT。
- shared新.local/observer-shared-contract-stage **阶段1仅metadata/lineage**已冻，作者86 actualHarmony/PE checksPASS，但f4a已发现P2：无recipe Insert/DeclareLocal/InsertBranch能改变真实body而绕过orig/Parent投影（x+1→1）；主确认，52冻结待最终清单，尚不签收/不进阶段2。最窄拟无recipe能力只限Model，真实emission拒，新增实际反例；不得靠扩大文档能力绕过。f4a最终另报第二P2：Patch/Unpatch返回后Current/Record仍可补InstallCandidate（0→1人工Validate再Commit），主读确认并统一授权52修；实际mutation窗口返回/异常必须立即封采，Commit仅冻结候选，新增返回后人工/重放补票负控。同时target闭合generic身份若不实现须硬拒、恢复EarlyGuard→Dispatch一致性。86仍仅作者证据，两个P2未闭合，待修冻独审。角色静态界线/鲜明emissiontoken/clone-consume/label-EH-local/实际排序/installed交易receipt与replay/candidate区分；**仅支持same-position replacement，任意splice/reorder/新增EHbranch硬拒，不能迁现有early-cut**。native只读Outer8pins未patch；runtime binder/history/terminal/noThrow尚未实现，阶段2未授权。旧V2/v3冻结不动。cfe保持旧36冻，兄弟通信由主代转。
- Hopper12旧stage六文件v2及21oracle方法已a3最终独立窄审通过两个新P2，仍未与shared/debt整合、native全NOT_RUN。debt stage同owner no-op P2已fcb独立23+50现exePASS，仅关闭该授票洞；87bridge/其他回归为作者证据。具体driver observer兼容/幂等安装额外判断/archive/reset/durable/强ref生命周期未解决，不允许发布称完整。
- 下一main：可继续原80选择的剩余60敌人bounded探索（前20仅旧候选证据，保持原选择文件不改），或按依赖准备其它限定native回归；等待dd genericproof/f4a stage1窄审。新部署前仍需full tests/build及无game。普通OS输入仍上次LockApp证据，未解锁，不称G6。goal仍active/armed/rev1/256（最新get_goal round0），未complete/blocked。

## 早前增量：12:12前后（部分被以上覆盖）

- **当前主源/已部署：V1普通攻击协同 + Domain probe正确pipeline目标 + Steam音频leaf-first早观测 + 独立S3-only catalog。build0/0、684正式tests PASS**（pwsh-6c234cd1746d41c0已收）；新增S3五文件及唯一隔离scenario branch，S1/S2与生产14顺序不改。S3完整60测试已在主683/684套内跑过；14a独立58只读通过（2写文件测试未独立跑），七helper逐字不变/无Routes或Damage/lethal，非S3所有入口硬拒。**S3 same/restart现已真实PASS，精确边界与token见下一项**；S4/S5仍未支持。
- 早观测第一版Steam off **040432Z-4233113f FAIL保留**：common全true，真实stop/music两错已消，只剩ambient[1,3,1]缺stop2。原NCreature.StopSfxLoop确调用SfxCmd.SetParam；先patch调用者会在叶尚未hook时JIT/inline。主仅交换三tuple到 **SetParam→music→StopSfxLoop**，dd只读依赖核对无阻断；不改core/raw/期望，新增static依赖顺序回归。须新进程，幂等旧进程不重建体；尚不声明根因完全证实。
- **leaf-first新Steam off041318Z-8f51870b/on041447Z-52da4421全部common+原gate PASS**（pwsh-c4f5fc3ec37543be已收exit0）。不扩成29/听感/无观测器生产。**S3新same-process041632Z-002a7f7e、restart042047Z-3b4c794e（prepare+resume）全部checks/独立pair/disk门PASS**（pwsh-95b142a95de84d33已收exit0）；仅178native masters/clones的room-entry重建、paidB02扰动、programmatic native UI，不是中途存档/G6/全S4S5。
- **余27首批pwsh-146a950337d142df已收exit1**：after-block042653Z-05774cc5、after-hp042823Z-132cdc82、after-removed-reentry042954Z-f5e3dcff、before-block043122Z-cf8718b8、before-hp043254Z-53e16a54全PASS；**external-after-damage043424Z-b1c4f778 FAIL**（common全true，Domain=0/cancelled=false与ambient等9错），余21未跑。当前累计7/29真实PASS，不说29通过。原nativePowerCmd.Apply103在IsEnding时return；原CombatManager.IsEnding无活primary且无ShouldStopCombatFromEnding即true，SteamPower该hook在ABOUT移除后失效，soleboss HP0 await窗口原Domain Apply不可达。dd正在只读诊断/提明确native keepalive fixture方案，须保原solo-ending拒Apply负控，不强制ending flag/手调AfterApplied/救援扫描/放松期望。
- **当前运行pwsh-d1069c2aa6674411**：14不依赖上述8HP0-powerless窗口的variants（foreign-retention/late-phase/late-powerless/nested-command/nested-damage/off-veto-followup/ordinary/overflow/pending-reset/post-max/post-protected-hp/pre-max/toggle/veto-source-retained）串行firstFAIL即停；8受影响保持失败或NOT_RUN，不叫skipPASS。禁止并发game/deploy。正式AudioObservationTests已接，包装原55全链一次并保26+DomainProbe，50audio emission有marker硬门；**pwsh-ca23f9af35b94be9已收684全PASS**，只tests改无需deploy。所有旧失败保留。
- Hopper旧stage六文件v2已冻，a3独立重放原18错误tape全实质REJECT/worker无world读取/CLR96现exe通过；后发现合法task-only插入误拒和完整额外guard攻击误受，两项仅oracle+fixture再修，现 **21方法PASS且a3独立两原反例/合法延迟复验闭合**。严格完整动作集合/全程HP-damage前缀/只透过已验证task-result，未借ApiAttempts/ledger。12合成正例不称enginePASS；共享桥尚未接，全部12native NOT_RUN。
- 独立hopper-debt-stage新receipt/DeathBridge原50receipt+87bridge+234/8/67/26/17/36及9protocol作者PASS。fcb发现NativeBodyTrusted按owner信任的同Id后置no-op留Witness P2，已精确PatchMethod+exactly1修；**fcb独立现exe23bodytrust+50receiptPASS**，只关闭此P2。actualKill边仅IL、正cap是synthetic债forwarder，engineNOT_RUN；archive/reset/durable/强引用生命周期仍未实现。InstallDeathBridge owner-only幂等及NativeReceipts.Install owner+Entry判断仍未扩审。新strictBody拒旧driver同步observer，必须逐具体方法/顺序审，不能owner白名单。
- 52c新shared V2整合层真实14+Hopper/两对双序258、CLR326、68/99/110作者PASS，f4a源码窄审无新P1/P2；runtime/source/early十文件与冻结V1相同，只有四owner BeforeHub/Summon生产类名/V2拓扑。**Coordinator仅当前specs/affected验证，全局覆盖来自fullchain Check，不是任意foreign patch全局事务。** 主批准下一层先与cfe设计Observer接口，两个stage均冻，尚未写实现/解开native硬拒。唯一Hub before-schedule actualTask→独立Observation local（覆盖unowned），pristine site-key+显式replacement lineage，Selected仅原getter、Dispatch仅实际原调用、一次historyticket真实producer/newobj/append；无source/取消权限、无另await桥、不借Latest或adapter verdict。兄弟send被工具拒，主代转，不能绕。

## 早前增量：11:50前后（部分被以上覆盖）

- **当前已部署V1协同修，真实正常14模块初始化已恢复，不再是下节启动失败候选。** fcb独立窄审后主精确替换CardResolutionHooks、Steam.Damage/Install三文件，paid scope→唯一native dispatcher→Domain→responders完整保留，真实owner Volibear.CardResolution先于Steam。build0/0、622回归PASS（pwsh-800b4f15a4be4418已收）。随后正式接tests/domain_steam_v1的真实生产源码编译与14实际Install/双序+26managed合作检查，由Python unittest调用；现在 **623正式tests全PASS**（pwsh-3c227a9648c4453d已收）。两个manifest边界仍不代替BaseLib/scene/content原生启动。
- 新Steam off **034247Z-37ddb39b仍FAIL，但全部common true/exit0/实际mod_initialized true**（pwsh-5a06ce1c95bb48ed已收），仅audio observer三错：stops空但initialLoop=true/final=false，music[1,1,5,5]缺phase2，ambient[1,1]缺phase3/stop2；期望[1,2,1,5,5]和[1,3,1,2]保持不改。原native源确有这些call，public小包装late observer预JIT-inline盲区有静态风险但不先断言核心无漏。dd获新stage最窄仅domain-steam专属提前安装3audio观测（在14之前防inline，Active仍probe开始、其余6仍原时点），不改core/gate，不从adapter捏事件，待冻审再新token验。旧030541启动FAIL和新观测FAIL均保留；on及余27 NOT_RUN。
- V1 D03首035046Z-491fa439 FAIL（cea78已收）是probe仍patch旧private OrdinarySegment，非普通14加载失败。主改DomainContractProbe为nameof(OrdinaryAttackPipelineV1)、props/dealer/card索引1/2/3，原trace/gate不变；正式V1回归增加真实Probe.Install及共享pipeline prefix/postfix各1检查。重build0/0+623PASS、部署后新 **D03 035913Z-dbd77779、B04 040038Z-b5bc3394全部原生/common PASS**（pwsh-8c50cbdc08a34303已收exit0），D03仍nativeTwinStrike代理不扩C02。
- 14a已窄审early-audio2文件无新增阻断、但仅允许实验非已确诊。主已接ModEntry第一句PrepareForTestScenario及observer3audio提前/其他6原时点/Active原时点，core/gate期待不改。现在 **pwsh-0ab3d8d95e364445** build0/0后跑623正式回归，须收；通过后主deploy并新tokenSteam off/on。当前没有game，最后部署版本尚未early-audio。
- Hopper新12driver/oracle被a3独立实跑18坏tape误接受，尚不可native验PASS。新agent6eedb07e独占修旧hopper-stage的driver/observer/oracle/fixture/两docs，冻结核心四文件不动；actualTask/typedgraph/完整body-commit-task因果/终态要补，worker只读Task不读Godot世界，sample回主线程明确时点；原cached completed Task跨不同invocation共享可合法，不能只唯一Task判断。e6dc另独占全新hopper-debt-stage做unmounted/partialthrow设计与实现，原stage不改；真实BeforeDeath call-edge admission+owned commit nonce，不fake power/不借Latest/不丢债，archive/reset未实现。
- 9cc S4/S5 lethal observerList命令/HP/return重复与跨command P2已由14a关闭，但Died仍缺sameAction其它Kill的独立归属（时间窗不能代替call边）；fullstage继续冻。主已授权另新save-load-s3-stage仅提取S3 catalog178安全副本，完全不包含/安装Routes或Damage，case非S3硬拒，S1/S2不动，178refs/serial字段/真实Continue/JSON全值相等与白名单全保留。新S3尚未接入/native；原save门证明JSON结构/值相等，不夸原始字节完全一致。
- cfe Observer v3新增fresh ticket/entry同attempt重放拒绝与completedTask墓碑；6f已独立现DLL无export复跑+36契约+自写整链mutation验证。原Task/重复MoveNext行为及原异常保留，第二history UNMAPPED；UNKNOWN不回补。native仍NATIVE_COMPOSITION_PENDING_REVIEW、注册只after-return观测、不冒共享桥完整捕获、11root/closureOPEN保留。
- 52c 11:37 shared V1冻结子集获f4a3只读窄审无source-provenP1/P2（326CLR/五方各110为作者证据，非引擎）。新domain-summon-integration-stage109真实源码同assembly+新CardResolutionV1+迁移共享模块正在14全链，已找到Audio/Contributions/Dampen vs Hub的真实拓扑冲突；获准只新副本明确subscriber-before-Hub，不能仅Priority.Last/不能关Audio，须实际排序/两序/late rollback。原11:37/live不改。任意unowned实际selected move仍原native tail，postAdd fullReset清理仍unsupported，不能扩大flag安全。

## 早前增量：11:10后（部分被以上覆盖）

- **当前已部署622-build Steam候选存在初始化冲突，不能声称可加载/可玩。无running game/job，失败已收。** 主接生产8文件、probe5文件、gate3+测试3、ModEntry安装及domain-steam测试分支、Bootstrap WaterfallGiantBoss/RoomType.Boss、DomainPower.AfterApplied顺序await Revival再await Steam、headless --steam-case 29项。build0/0，**622 full tests PASS**（pwsh-989b1e7c7c3f44db已收）。原audio源码断言要求return Revival，主改为drawclock→恰一次awaitRevival→恰一次awaitSteam有序严格断言，没删旧机制。
- 首native **Steam off030541Z-9ad82373 FAIL**（pwsh-faf011d6adb94752已收exit1/timeout，on及余27未跑）：ModEntry在AttackMachine安装失败，原CreatureCmd.Damage callsite数0 expected1；不是BaseLib prefix阻止。主读CardResolutionHooks.cs81–97确认真实owner **Volibear.CardResolution**，其222–228已在AttackCommand.Execute.MoveNext把Damage改为OrdinarySegment，262–283必须完整保留nativeDamage→Domain附件→ordinary responders。旧Steam80组合漏CardResolution，不能称完整现行链兼容，旧报告保持FAIL。
- dd获仅stage协同修授权，方案：CardResolution显式versioned V1 ordinary callsite/dispatcher合同，完整ordinary pipeline单处保留，Steam exact AttackCommand dispatcher仅在真正nativeDamage调用瞬间设置/消费/恢复ticket，不跨整个helper；HarmonyAfter实际Volibear.CardResolution、双安装序唯一anchor/未知拒绝。不能简单count0过、调安装顺序、绕旧helper或猜private方法。需补完整ModEntry所有Install目标交叉与真实组合。main尚未应用这个新修，等stage编译/测试与独立复审，再复制最窄源改、build/fulltest/deploy、新token首off/on重试。
- 52c已收到同一冲突，不重复dd AttackDamage；其当前五方双序73项metadata/rollback、actual-adapter CLR257项仍只是五方，不等于全production。same-owner新epoch/unowned新attempt不误清flag、nativeTask/异常及退休tail有fixture，Observer未接。新Infested授权仅exact Kill→Hook→callback票或actualTask tombstone，不再power→Latest；未知新directAfterDeath仍native，已消费veto查询与授权分开。
- 9cc S3–S5 latest87tests/compile0/0新冻，14a正只读再审lethal P1修。新增SaveLoadPersistenceDamage.cs（若未来集成不能漏），Priority.First观察原HP结果、原IsEnding bool、原SetResult相同result及Died，不插假history/不改native参数；最后lethal严格要求history缺席和真实paid source/result/HP0/Died，实际Nibbit42..46、B03分段8+3。旧schema2其余身份修保留，所有S3–S5nativeNOTRUN。

- ff3525aa独立只读分类已完成：十未解析monster全部在AbstractModelSubtypes.All与ModelDb.Init无条件注册，无mock/debug/Act排除；只可标REGISTERED_CONCRETE/NO_DIRECT_NATIVE_COMBAT_CALLSITE_FOUND，不可test-only/unreachable。Mock短名实际为MockAttackMonster/MockIntangibleMonster/MockReattachMonster。TunnelerNormal非debug（默认false）、不在当前80Act表（Hive为TunnelerWeak），但FightConsoleCmd34–45可按registered ID进入；SaveUtil39–42/CombatRoom91–105可从EncounterId恢复、RoomSet144–163 queued NormalEncounterIds仅非Deprecated+Monster过滤也可进入factory（Chomper.ScreamFirst=true+Tunneler）。普通版本是否自然产生该save仍OPEN。十monster的SaveUtil93–96已找到调用仅history/display/stats，不可误称saved-monster直接combat恢复；外部/dynamic/mod/test生产路径未闭合。已告cfe保留十一root/closureOPEN，不删未知分母。无执行/native证据。

## 早前增量：10:56后（部分被以上覆盖）

- main当前无running job/game，Standing两例已收 **pwsh-39c069ea2b954128 exit0**：base025135Z-285f2dc0、upgraded025351Z-27b42ef3全部common+standing gate原生PASS。真实Mayhem/PaelsEye自动U03→同round额外turn保留→后续普通turn再衰减，精确Block写/clear/原power生命周期/history三类原顺序。仅初始enemyHP500/energy30和后续声明GainBlock补40 fixture，不扩paidU03/Domainclock/Barricade/OS输入。
- 已正式接StandingExtraTurnProbe、tools/standing_extra_turn_evidence、tests、ModEntry与headless scenario `standing-extra-turn` / `--standing-case` 两variant；Bootstrap默认SlimesWeak无需改。新 **593tests全PASS，build0warning/0error并已deploy**。首次测试因stage source断言路径仍指tools目录失败，主仅改指正式src/Volibear，之后全量重跑PASS；未放松断言。pwsh-e98433fc055c456a失败已收；修后前台命令11.6s PASS。
- 只读foreground再次确认HWND66272/PID8632为LockApp Session1，**0输入包**。不要尝试物理出牌或把Default desktop/Godot focus当解锁。
- Steam第四core fcb复审无新正常原生路径阻断；仍provisional弱bucket/唯一UnreturnedBinding回绑，不是shared registration，不声称首ret多frame/EC全证明。14a新增nested child/parent history source交换假通过已由dd仅protocol/tests修，真实stageId直属child D2/A2或D2、parent D0/A0/Move精确顺序；28tests/29positives和14a8独立坏tape均PASS/拒错。**可进入限定29native验收，尚未正式接线/部署/运行**。主正在核精确复制清单与scenario/RoomType，先等dd只读manifest；核心冻结供52c迁移。
- 52c shared stage现实际Summon+Dampen迁移副本双序、加Hopper+Revival四方双序emissionPASS，非游戏；主批准再取最新冻结Steam快照。新Outer retired tail需在source GetResult后且OnMovePerformed/history前退出、原exception保留。主要求same-owner跨epoch不清新attempt的IsPerformingMove；作者确发现IL local outcome跨await丢失，正在改exactTask frame+flag token compare，不能把emission当行为证明。Hook.AfterDeath显式Kill→HookTask→callback single-ticket已做，原Revival语义体不改，仍需真实CLR/negative与五方组合。
- cfe observer已实际执行复现两P1（旧task错记新epoch完成、Changed手工append借marker）及4oracle假通过，不再只是静态。获stage-only修invocation/实际wait后selection和dispatch/one-shot producer entry/branch→commit/严格offset+row+chronology，组合仍阻断、不禁生产模块。9cc正修S4/S5 last-lethal故意缺History及真实Nibbit42..46/B03分段8+3独立fixture；不可合并旧虚构最后damageentry。e6dc已获仅stage实现Hopper native driver/oracle，原unmounted/archive/partialthrow发布阻断仍在。

## 早前增量：10:30前后（部分被以上覆盖）

- **10:45 main当前无running job/game，全部已收。Dampen七variant全native PASS**（pwsh-c99534c5067c4c39 exit0已收）：off023420Z-628ce9fd、on023551Z-0d4550df、enter-await023722Z-6184a11e、exit-await023855Z-43828359、enter-pair024028Z-91015049、exit-pair024159Z-64fb879e、departure024328Z-73625b91。真实精确pair/多caster/restoration/player独立negative，不扩写Reset游戏行为或未来共享桥版。最新正式 **580 tests PASS**（pwsh-d4e8b7f7da85484b已收），生产Dampen独立桥已接线/deploy、build零warning/error。goal重读active/armed/revision1/rounds0，不complete。
- **下一主执行**：Standing extra-turn stage 14a复审无新P1/P2、12tests+独立同构变异拒绝；可正式接其probe/gate/tests、headless/persistent路由，build/fulltest，再串行base/upgraded真实2cases（先读stage接口，HP500/energy30仅初始fixture允许，后续只GainBlock补40，不改HP/回合/clear）。若尚未接线先做余60 Act bounded chunk，别同时deploy/game。Steam第四修已冻再交fcb core/14a协议；9cc正修S4/S5原生最后一击无History的P1；cfe正修observer完整审发现，52c协调shared桥，e6dc开发Hopper真实driver/oracle。
- 18个已定义Summon native variants全PASS：pwsh-277efaeb25294a98旧7+余8已收，加之前3例。**pending Reset完全不在这18例中**，不能扩写生命周期安全。
- Act bounded探索首20/80全native PASS：第一10=015812Z-4a0baa1b（pwsh-f6645aa92f6840c4），第二10=020947Z-db880cf4（pwsh-77836711b5c84b45），均已收。每root只2turn/ANY合法结束，不是完整AI/branch，余60未跑。冻结80输入原件不变；两分块选择在.local/enemy-exploration-chunk01-17da0f010931及chunk02-7e752ec9ed84。此20运行在Dampen接入前的生产版本。
- Dampen core修后fcb第二审无新阻断，stage81scope/49registration/5rollback/12stale等为CLI不冒充game；main又独立4个gate反例复测PASS。已拷入Core/DomainDampenTransactions.cs、DampenLifetime.cs、Probe及gate/tests并接ModEntry/bootstrap/headless新scenario/domain-dampen-transactions与--dampen-case。主仅对两diagnostic hook字段显式=null消警告，未改生命周期语义。未来shared bridge重构后必须重验，当前独立桥不能与新Hopper/Summon独立注册桥共存。
- 首个Dampen native off **022057Z-95b38e71正式FAIL保留**（pwsh-f499fac9af3f4e2a已收）：所有common真，但gate有两个独立oracle缺陷。主读真实KnightsElite37–44证初敌为Flail→Spectral→Magi，旧fixture漏Flail，typed对象也少1；现固定3敌原序/9+second，不改生产阵容，25个Flail类型/顺序/ref/id负控。另一为gate泛ERROR扫到已匹配stock退出泄漏；主加runner-only dampen_protocol_log：仅成功stock+匹配类别、唯一token SHUTDOWN后移除已允许teardown行的协议视图，原日志/common/diagnostics不动，marker前与之后任何非teardown/unsupported/fatal保留，6专门负控；standalone gate仍严格。不得把旧报告改PASS，当前新token七例重跑。
- 6f只读Summon审计完成：Reset清CWT/Attempts使known-stale降unknown；首次ret绑定可能晚于continuation；Ovi wait后先slot解引用、Infested先music、Fabricator新helper先CombatState判断，均早于旧preAdd gate，Resettrue脱离后预测NRE/旧状态mutation，不声称已native证明newcombatspawn。defaultWait无combatCT，Reset不保证任务消失；已commit Add需保留Minion/初始化/原Kill cleanup。67旧offline检查没有pending resume。
- 新可写agent **52c8ed99-b914-4709-85b2-f0faa191ebb0** 仅.local/domain-summon-reset-stage。339真实CLR/IL/kernel断言与2registration-throw子进程通过，实际组合证Dampen↔Hopper/拟Summon双序丢await anchors，当前Steam↔liveSummon发射通过不扩未来。主已读DESIGN批准stage副本协调单owner registration transport（显式local receipts/原Task/EC/绑定在调度前）、精确Outer MoveState.PerformMove dispatch transport，以及Hook.AfterDeath dispatch与liveRevival协同副本；不准改任一冻结原件/live。现注册13sites/rollback迁移实验中，尚非Summon完整修复、所有nativeNOTRUN。至少Dampen/Summon/Hopper/Steam/Revival组合，不能只验旧Release DLL。SharedHub不授ambient权限，不猜Latest，不吞未知调用，未知锚点拒绝。
- Steam第三审旧2P1正常路径静态闭合，但dd获第四轮stage窄修：同Creature跨Reset旧owner HP lease阻塞新epoch，需epoch lease隔离/旧Frame只释放旧lease；rearm allscopesclosed须含owner-wide Active/HpActive；gate新2P2为snapshot不落stage begin/end区间、history跨root时间倒流仍过，另完整history identity清单约束finalCount。29native均NOTRUN。14patch含Damage/SetHp/SetMaxHp观察，实际BaseLib282 prefix owner清单仍待native；源码未见两publicprefix不是运行证明。
- Hopper冻结三修复+新registration bridge已交a3再审：234ledger/8offline native commit/67IL/26scope/17新regression/36旧组合；tracked-owner forgery不downgrade、Escape只在actual CreatureEscaped提交后、cancel与nohistoryReturned释放reservation、删unique-subject借票。原unmounted/archive/partialthrow发布阻断与无engine driver/oracle仍在。不得用旧36组合签新Dampen兼容。
- 14a正在只读复审schema2（81tests）再Standing extra-turn（12tests）。schema2已改实际MoveHistory/DamageHistory/typed实例/真实paid action/base+enchanted守恒，但**新审发现S4/S5 WinNormally可能强求不存在的last-lethal DamageReceivedEntry：原Damage先HP0→IsEnding=true故不写History**，正在核源码，禁止当81synthetic通过即可native。所有S3–S5NOTRUN，S1/S2四模式旧PASS不变。
- Standing stage修后记录实际BlockChanged/setter/ClearBlock21event、原Apply/source/集合生命周期6event、跨类型原History顺序/dealer/epoch，并严格ID整数/master映射/playId顺序；只stage，两nativeNOTRUN。
- cfe observer首稿冻结，23contracts/13真实PE anchors/自有synthetic actualHarmony通过，仍未加载game/native。6f现只读审发现真实集成硬冲突：拒任何既有transpiler但liveDampen和Revival都patch Outer；另StartMove在outer初wait前取NextMove，而native wait后才选，fixture捕获时点不同。origin除精确StunInternal外natural/reactive/Engage均UNKNOWN；无natural numerator，不升级inventory OPEN/10未知/Tunneler。

## 早前增量：09:15后（部分被以上覆盖）

- main当前无running job/game；全部后台已收。生产DLL仍551-build已deploy；最新正式full suite **564 tests PASS**（pwsh-e4e3672b978a4ada，新增Body target独立fixture锚定/负控）；新S2仅oracle一常量修，不需部署。goal active/armed，不complete。
- **S2 same+restart新token均原生全gates PASS**：same003937Z-558844bc/PID17300；restart004347Z-0863a43d，preparePID22772/resumePID23532。pwsh-e8f5aa185b2441ca已收exit0。含升级master、combat-only Claw/Body/零费不漏入room-entry checkpoint，新clone恢复正确形态/目标/升级/成本。旧002916保持FAIL。合S1，基础两case×same/restart四模式均PASS，S3/S4/S5仍stage，不扩写全存档。
- **被动23variants全部native PASS**：原11 +本批余12（pwsh-47fa564c260b4333 exit0已收）：ritual open/close/post005041Z-1e2c587b/005243Z-489e3681/005446Z-9298fb24；plating5 005648Z-40e6ece8/005852Z-3be07364/010056Z-1403eb6d/010258Z-b49b8b3f/010501Z-56e7fe37；curlup2 010707Z-e89c4468/010901Z-09b80e4b；skittish2 011055Z-5c2c6ac4/011249Z-0078e699。只对应明确来源/窗口，非全部敌行为。
- **下一主执行**：串行domain-summon-contract回归旧7+剩D17八（headless.DOMAIN_SUMMON_CASES排除已PASS fabricator-attack-close/infested-wait-open/ovicopter-partial-open），300s/16000frames/window，同成功stock evidence。首失败停/保留报告并按实际根因修，勿并发deploy/game。之后80act-root bounded探索已备，不能代替4cells/branches。
- Steam二审拆两人：14a5906b-f50f-4212-a729-492766686f17（oracle/observer）与fcb（core）已完成，仍拒发布；dd已获stage-only修复。新2P1：外部untagged Damage HP0→AfterCurrentHpChanged/AfterDamageGiven→Kill前开域仍绕ShouldDie；一次终死veto留下TerminalStarted使后续正常无Domain EXPLODE永久空转。dd核实SetCurrentHp也有同样write→hook→Kill窗，一起修纯owner生命周期lease，不tag/抑普通伤害；TerminalAttempt释放放在实际PerformMove尾完成后，区分cancel单次cleanup与未来合法native self-followup。
- Steam oracle仍有checkpoint terminalKillCommitted/writes漏验、trace计数不验顺序（合成正例自己错误initial→cleanup→terminal）、changes.stage任意字符串、observer记录args+count而非actual appended entry身份/内容/最终归属。全部要求修+固定负控再独立复审。public Damage prefix同dealer nested偷PendingDamage票的第三方interop边界也须明确/测，不声称任意兼容。仍全部22+新增nativeNOTRUN。
- Dampen a3完整review已收，b03 stage-only修中：P1 Reset丢task使known-stale降格untagged/native并降新战斗AllCards；outer首await后才建epoch也可重生；无ticket另一EC同power callback漏ActivePowers冲突；首次ret前actualBox重绑竞态**已由确定性CLR fixture实际复现（不是native）**。b03正做精确AwaitUnsafeOnCompleted registration桥，在原awaiter可调度前绑定actual box，原Task/awaiter/GetResult/EC/异常保持；需重审，不改其它live模块。11已实测oracle falseaccept（typed ref混淆/phase时序/IDs/残留caster/Unhandled exception等）和第五Reset方法owner名单/lateInstall rollback都须补。7nativeNOTRUN，禁止发布。
- Hopper e6dc独立stage首稿交付（234ledger/8offline实际registry等方法/49IL/25scope/36组合）；仍无engine driver/独立gameplay oracle，且unmounted debt/Reset强引用archive/部分return异常为发布阻断。不能因quarantine就说牌没丢。只stage，未发布。
- 9cc schema2独立S3/S4/S5 stage61tests与编译通过，producer/oracle对照中，全部NOTRUN/未发布。cfe新.local/enemy-branch-stage/PLAN已审，批准仅PEReader静态metadata inspector+inventory contract；不得Assembly.Load执行game/extra调用delegate或RNG，runtime observer另审。真实branch/graph分母不闭合保留OPEN/UNRESOLVED/unknown upper，不删10根；原生STUNNED动态状态/不可见条件节点/随机权重两次调用/原生Force与probe-force分开。

## 早前增量：08:38后（部分已被以上覆盖）

- main目前无running jobs/game。S2same首个002916Z-2441ae28已收FAIL（pwsh-6d210e96cd9d449f），全部common+disk通过，唯一interrupted form metadata：oracle错误把Body.target写Self，实际/冻结T02 fixture4023–4028均AllEnemies。U03+兽躯cost0/canonical1/upgrade1/Block12/Lightning3/Exhaust/master身份正确，加载恢复Power/Self/cost1/Block12/Decay3也正确。main已读冻结fixture并批准9cc仅修oracle+独立锚定/错误target负控，生产与probe不变；等待发布后**新token S2same+restart重跑**，旧报告保留FAIL。
- E02保留格挡真实迎战 **003357Z-72c819c1 PASS**、B04 **003544Z-a928e931 PASS**（pwsh-3fd4ab9a27e24d05已收）。不是OS正常窗口输入证明。
- Steam dd stage实际native HP/block/max变化序列、move/attack/damage History入口与Entries、AfterRemoved调用/完成、loop registry stop/music参数观测已补，7probe-only patches/76组合检查，15Python methods；正在补foreign veto/retention/nested/reset native负控，仍未publish/native。注意foreign ShouldDie=false时native HP仍0会递归Kill最多10，probe须实际AfterPreventingDeath恢复HP，独立记录vote/恢复/Died/retry；不把该原生递归误算adapter bug。
- Hopper新e6dc独立stage已读DESIGN：未挂载debt只quarantine且Reset强引用archive明确不是生产解决方案，主明确这两项是完整覆盖/发布阻断，不准宣称完整D10；继续三admission+合法mounted3段return/source task证明。未发布。

## 早前增量：08:25后（部分已被以上覆盖）

- 当前main所有后台job已收、无game。goal已重新读取确认active/armed、revision1、roundsStarted0（不是已完成）。最新生产build **551tests版本零警告/错误且已部署**；后新增Python短profile工具，正式full suite **561 tests PASS**（pwsh-ff22edf509144e36已收），无新DLL变化。HEAD仍8b563f79742ba89c9a97e75f068cef852864df36、dirty、index空、无commit/push。
- **Coupon12原生全部PASS**：expiry234353Z-fc14098b、B04 234950Z-7d5ecee1、C04 235123Z-38b18853；剩9 pwsh-9f6bd87cd2254c8e全PASS（000509Z-ac0fb78d、000642Z-dcff67e3、000815Z-ea948850、000946Z-5e9dd472、001119Z-06170e25、001300Z-608a1031、001438Z-14e174b7、001614Z-e3e1985a、001746Z-2b1e73cc）。旧C10 235258Z-c04158d9为oracle把异类券当同类max的FAIL保留；main确读TEST_SPEC139+frozen DEVELOPMENT48“同类max”，按异类各-1→C10付0纠正独立oracle，生产未改，完整自洽错误付款反例亦拒绝。
- **Primal两例全native PASS**：paid232706Z-10f71ca0、extra234134Z-b68900db。后者真实Mayhem/PaelsEye额外turn维持快照，再真实EnemySideEnd到期；Leaf第二phase自然GOOP非重复TACKLE，精确新Slimed来源/时序已修并严格验证。旧232839失败保留。非OS输入，Strength下降/升级/反雷等其它窗口仍未覆盖。
- **Audio38steps原生全gates PASS 000204Z-cdd75f9c**：7cue类别、14已commit receipt、14dispatch、14新Playing Ogg stream。真实泛型TemporaryStrength→Strength保留silent=true为0cue负例；另加非泛型existing Apply→Modify独立ticket正例，仍严格14，不降成13。旧37step234629Z-80d187bb正式FAIL保留。观察routing/stream/effective volume，**heard=false，未验听感**。
- **S1 same+完整process restart原生均PASS**：same232201Z-2c6c187f；新restart002100Z-99618033（preparePID20908/token0456c40814cd，resumePID9932/tokenb282f972f04c）两phase全部common+save+disk gate真，pair真。旧restart235541Z-4c947dc3保持FAIL：存档gate实际true，但第二进程24 shader_cache创建错误。
- restart错误已只读证明为Godot4.5.1基底DirAccessWindows加\\?\\后SetCurrentDirectoryW路径过长206（旧hash目录272→276），首次CreateDirectory成功、复用时chdir失败+already-exists，非ACL；未改ACL/注册表/删cache/豁免error。新tools/save_load_profile.py只创建`.local/p/<12hex>`唯一owned profile，UTF16+前缀+尾斜杠NUL预算安全，拒重解析/碰撞/越界；A/B同env/root，保留cache与旧证据。save相关77测试/真实Win32同路径两次chdir通过。报告仍artifacts/save-load，新增profile.json指实际root。纯Python改动，不需deploy。
- **下一步立即S2 same-process+restart**（新短profile runner），再E02/B04、余passive12、旧summon7/余D17八、80act-root bounded探索（冻结inputs/prereq已备），继续正式4cells/branch与完整流程/卸载，不称完成。
- 只读OS查询（0输入）：OpenInputDesktop成功名Default，但foreground HWND66272/PID8632，Get-Process确认仍LockApp Session1。不可仅desktop=Default或Godot Focused=true就判解锁。PC/物理输入仍不要伪focus/反复尝试。
- Steam a3独立review发现两个P1（veto新死亡覆盖已confirmed phase；power-less HP已0的真实death未绑定导致BeforeDeath开域可能提前Remove绕ShouldDie）、oracle6个falseaccept/缺逐阶段/真实history和cleanup、Install失败无rollback、Reset与provisional重绑组合待测。dd已获**stage内修复**权限，已有P1/rollback/Reset/逐阶段mutation进展，但真实观测/probe补全尚未交复核；**未发布/接线/native**。
- Dampen b03独立stage core编译+组合和58实际scope事务已过，补probe/gate中，未发布。Hopper只读a3不能写（委派scope固定）；新可写stage agent **e6dc69d2-1eb6-46b9-a8e2-7446ad53c946**负责.local/hopper-stage，只stage/offline，先未挂载debt/部分return设计；已补发a3详细实证。9cc已恢复.local/save-load-v2 S3/S4/S5：S4 fresh首房固定Nibbits并非seed随机，须真实胜首房/跳奖/合法第二Slimes，两个不同未Consumed目标+手牌空位drawpile充足才能验证draw2/0；禁止复位Consumed/改NumberOfRuns。
- diff卫生：默认git diff --check对CRLF文件逐行报尾空白（exit2）；诊断使用一次性`git -c core.whitespace=cr-at-eol diff --check`无实际空白问题且PASS，未改git配置/批量改用户行尾。

## 早前增量：07:30后（部分已被以上覆盖）

- 07:30已向用户如实报告未完工并继续goal，原生/输入/全AI/领域余行为/存档余场景/听感等不能扩写完成。所有main后台jobs目前已收、**无正在运行game**。goal仍active/armed，勿complete。
- 最新全源码build零警告错误、**547 tests PASS**（pwsh-a5a9238506194533已收），含新audio probe/runner接线。**此547 build尚未deploy**；当前game安装仍527 build，已通过下列原生。058刚发布Primal extra GOOP窄修（10focused tests、stage编译通过，尚未main重建），正同法修CP-expiry；等其冻结后一起重新build/test/deploy。
- **S1 same-process native存退续新token232201Z-2c6c187f-same-12d742ff3545全common+save_lifecycle+disk PASS**。native强制按钮API非OS输入；真实B02支付、房间入口checkpoint重开、NumReloads+1、new instances、master deck/relic/原定义与完整原生map往返。旧224005/225423两个FAIL未改。S1restart/S2same/restart仍NOT_RUN，下一阶段要跑。
- `pwsh-eb50483619744d9e`已收：9余Revival+4DCC均PASS，加早先late得到Revival10全PASS。首Primal paid231924Z-42024f8e仅oracle布局错误FAIL：SlimesWeak真实small/medium/other-small四布局，旧small/small/medium不可能；058仅修oracle/test，旧布局现在拒绝，原报告保留。
- `pwsh-caa7ef6c774d431a`已收：**Primal paid新232706Z-10f71ca0全gatesPASS**，真实snapshot3→Strength6/Unify6后C24雷15、B01普通18。extra232839Z-fe652b51 FAIL：第二敌方阶段LeafSlimeS自然GOOP产生Slimed，探针错只接受round1 mediumSticky，抛异常中断native；不是生产U12已证实失败。058正窄修精确round2/ownerTurn3/Enemy/activeLeafS GOOP/1Slimed来源，按CannotRepeat真实后继修独立oracle，不强制动作/删历史，修后需新token。
- Coupon12 oracle同四真实布局也已修（仅gate/tests）：真实medium slot1、R09迎战顺序与expiry block分配按roster，48positive/旧不可能布局拒绝，C#生产/probe无改。Coupon12真实仍NOT_RUN。
- Audio新2probe files+gate已接 `audio-receipts`，env VOLIBEAR_TEST_AUDIO_RECEIPTS=1，37steps/14receipt、原PlaySound前后及stream/settings只读。bootstrap+CLI+2arg gate路由已测；`*_FAILED`如Audio失败亦纳入runtime_errors。547 build包含，未部署未native，routing/stream-start/heard分层，全部heard=false，禁止强unmute。
- Steam完整stage `.local/steam-stage`已冻结待a3独立只读adversarial review，**未发布/未接线/未deploy/native**；dd123ledger/19实际scope事务/12emission/4顺序72checks+14probevariants。a3审source/Reset/祖先cleanup/foreignShouldDie、分项damage与StopAmbient；问题回传后dd修。
- b03 Dampen只读计划：实际source DampenMove唯一Apply与AfterApplied ledger.Add→Downgrade紧邻区段，需成对门控防假返还；未发布。9cc批准独立schema2扩展S3 178 mastercards、S4 replacement relic、S5-finished/S5-reward-commit，stage中，冻结S1/S2，不冒充Orobas UI或自然获得卡。
- 下一步：收058窄修→build/test/deploy；新Primalextra/audio37；S1restart/S2两模式；Coupon12、剩D17八+旧七、剩passive12、E02/B04 ordinary turn回归；再80天然act-root探索（冻结输入/prereq已备），仍不能称完整4cells/branches。PC与物理输入待真正解锁，无伪focus。

## 早前增量：07:20（部分已被以上覆盖）

- main最新已部署527-tests build（零警告错误），之后新增save原生map往返proof/80selection tests，正式full discover **541 tests PASS**（pwsh-c30ed21f2d924838已收），这些无额外生产C#变化。StringSeed字段已修并部署。无commit/push。
- **当前唯一main native job pwsh-eb50483619744d9e**：9个余Revival+4贡献+U12两例串行，前13已全PASS，当前U12待输出。不得deploy/另开game直到收完。Reattach-late早先新token223806Z-fc0d5b49全PASS，因此 **Revival10全部原生PASS**（不含Steam/双死亡generation/普通paid terminal）。DCC四例hex231212Z-32a96c9a、tangled231400Z-ad4deeed、smoggy231542Z-eb98098f、ringing231734Z-99e7a9b5全部原生全gatesPASS；仅4typed contribution，不是插卡/affliction写入/mixed分摊完整覆盖。
- **完整6case探索224445Z-a0cf2373原生全gatesPASS**，4Act/真WIN/真LOSS及fresh-run cleanup。80act-root selection准备好：`.local/enemy-exploration-80-prepared/enemy-exploration-inputs/selection.json`，同目录catalog.json/prerequisite-report.json+smoke artifact精确冻结；严格helper已通过，80cases 22/20/20/18各一次，turnBudget2/end-turn/ANY合法提前终局。全80仍NOT_RUN，非完整AI/4cells/branch覆盖。
- S1same首次224005Z-6f3b2bfb FAIL：Self B02误传player目标导致取消，Finished但未支付；probe改target=null并真实AfterEnergySpent/history/energy-1/block+5/discard/context硬检查，已部署。第二次225423Z-9b62e492 common/disk全true、付款已真发生，但精确reload整树gate失败。
- S1第二失败已确切溯源原生serializer quirk：SerializableMapPoint.CanBeModified默认true且WhenWritingDefault，初写false省略→load true→重写true。仅10处points.can_modify missing→true及num_reloads+1；无time/deck/relic/rng/coords/startTime变化。oracle现按**精确acts[*].saved_map.points[*]**路径建立预期（已有须bool true）、其余整树相等，新增真实native serializer/deserializer C# proof与否定，save67 tests PASS。旧报告仍FAIL。**下一空闲时立即新token重跑S1 same-process**，不需再deploy此纯oracle修；成功再S1restart/S2两模式。不要称已有存退续验收通过。
- U12 probe新3files已接主route `primal-contract`、env VOLIBEAR_TEST_PRIMAL_CASE、`--primal-case`，2cases `U12-paid-snapshot`/`U12-native-extra-turn`；真实付费R06→U12→R06→C24雷15/B01普通18；Mayhem+PaelsEye合法零manual额外turn、公开5padding后自动打、真实EnemySideEnd才清快照。当前native批正跑，未出结果不算PASS；Strength下降/负值/升级/领域反雷等仍缺。
- 07:30单次检查提醒 schedule-4d11a8f6-f094-4cc3-a85c-bd6a8c8559c2 已设，仅报告真实进展继续goal，不完工/不中断native。
- agents：dd Steam stage 6partial+14variants，118ledger/72组合emission，未发布未native；b03 Dampen只读/独立stage事务方案，当前4贡献已全PASS；fcb独立真实audio receipts/routing vsstream-start vsheard probe stage，未发布；9cc save源码冻结等待S1新run；cfe80selection已冻结；058U12发布后待native失败支持。PC/物理输入仍等待真正解锁，不伪造focus。

## 早前增量：06:32后（部分已被以上覆盖）

- 最新main build **0warnings/0errors +509 tests PASS，已deploy**（pwsh-73b3c1a3a89f457e已收）。包括audio published helpers、Reattach stale入口修、Revival版号规范化、PC只读诊断、SaveLoadContractProbe新route。**目前无main运行中的后台job/游戏**；此前所有job已收。goal仍armed/incomplete，下一步立即继续串行native，不需人类再次授权。
- **下一步优先**：新token `domain-revival` 的 `reattach-late`，随后其余9REVIVAL_CASES，全门槛；再完整 `enemy-exploration` 6case smoke（selection `.local/enemy-exploration-smoke-selection.json`，catalog `artifacts/headless/20261031T193327Z-4b4ff955/enemy-catalog.json`）。同成功stock201446 manual-report里的stock_teardown_control，window/timeout240/frames8000；smoke timeout1200/frames70000。部署已完成，不必再重复部署未改源码。
- 旧456版13case batch pwsh-0b4a7ad86f7d49f2已全部收：**D17 fabricator-attack-close222859Z-1f77a51e、infested-wait-open223028Z-1e7e6983、ovicopter-partial-open223159Z-ffa4fcad全部原生全gates PASS**。余D17八例及旧七例尚须最新回归。
- Revival旧批10例均保持FAIL：九例唯一gate错误是native Version发`v0.107.1`而该probe独立schema要求`0.107.1`；main仅producer剥单个leading v，oracle未改。reattach-late221742Z-1a5b604b额外真实NRE：retired owner的ReattachMove在DoReattach guard前已解引用CombatState。dd新增weak monster→原ticket来源，真实MoveNext首调用在SFX/状态读取前取消stale callback，保留已HPcommit/合法/续await；44+32+16 checks、12patch/2入口/组合1745通过，已并入509版，**原生修后尚未跑**。
- headless.error_lines现把`[Volibear] *_ERROR`失败标记也计runtime error；原先caught probe NRE仅使scenario/exit失败却no_runtime_errors=true，已加强而非豁免，新增负控。旧报告不改。
- PC仍FAIL/其它2未跑：Godot源码说明native非embedded Window hover依赖OS receiving-window/真实指针；LockApp是高可信解释，但旧run无实际embed/focus字段，不声称已观测那些值。058新只读诊断已部署，全部原断言/输入/gate不改；**真正解锁前不再重复PC或物理输入尝试，不NotifyMouseEntered/warp/fake focus/embed**。
- 新save入口已接ModEntry `save-load-contract`→SaveLoadContractProbe.Install（无DevelopmentBootstrap）。独立tools/save_load_pair.py：`--execute-native --case S1|S2 --mode same-process|restart --display window`，专属profile、真实normal EnterMapCoord checkpoint、native ForceClick Pause/SaveQuit/Continue（not mouse/G6）、重启A/B不同PID/token。48 unit tests通过，**实际存退续S1/S2仍NOT_RUN**；S3/4/5未实现。只有明确fresh StartedWithNeow=false合法起点Monster，不伪造flag/存档字节。A全gate+disk验证后才B，实际路径default/1/modded/profile1/saves/current_run.save。
- 活动delegations：dd继续.local Steam独立stage（目前ledger118过、native adapter未完整，未发布）；058实施U12 paid snapshot+真实Mayhem/PaelsEye额外turn两新probe，公开draw5 padding fixture，未发布；9cc刚发布save4新文件可后续修native失败。cfe只读unreached-root-audit已落.local：10个registered MonsterModel仍UNRESOLVED，TunnelerNormal有conditional developer/save entry不等于ordinaryAct/debug-only，分母未扩；fcb音频源码已发布且509编译，实际播放/听感仍未验。
- 后续还需Coupon12、DomainCard4、余passive12、正式enemy4cells/branches、其它Tier2/完整流程/普通输入/音频/卸载等；07:30仅检查点，不能宣称成品。无commit/push，index空、dirty。

## 早前增量：06:12后（部分已被以上覆盖）

- main最新正式build零警告零错误、456 tests PASS，已deploy；新Summon D17、DomainCardContributions生产/4 probes、Coupon12、修后PC confirm、永久领域sentinel、探索setup/loc均已接线。新旧Summon↔Revival两顺序实际emission通过。Git index仍空，dirty，无commit/push。
- PowerPresentation首run213641Z-30ff6e20 FAIL找出真实永久领域bug：native SetAmount把int.MaxValue截成999999999，旧IsPermanent失效。现CardResolutionDuration.Permanent=999999999，保留有限扩展防撞哨兵；native setter12checks+旧Domain31通过。新run220916Z-6f871b42原生46rows全gates PASS，旧失败未改。
- Prepared guard修后213942Z-b1ae8456全gates PASS，Prepared4现全部通过。PC fixed214115Z-84fc91fc失败在不可GrabFocus的Confirm（holder实际成功）；改viewport本地鼠标confirm后221040Z-c1aa7062仍因hover未落到enabled confirm失败。058继续精确诊断，不能伪造窗口focus/改为SetResult/放宽；OS物理输入仍LockApp阻塞，不算G6。
- 6case探索214512Z-2d544475 FAIL：完成BUDGET/WIN后真LOSS进入summary，SaveBadgesToProgress缺角色stats。原因是probe direct StartNewSingleplayerRun+shouldSavefalse绕过正常lobby的GetOrCreateCharacterStats，非正常菜单路径生产缺陷。cfe已在每case起跑前补同原生前置、声明fixture、不写progressfile/不造badge/不跳summary；loc四pronoun改native camelCase并补titleObject。已部署，整6case仍待重跑，禁止拼接旧3case当PASS。
- **当前native job pwsh-0b4a7ad86f7d49f2**：456版串行Revival10（reattach五种再illusion五种）+D17优先fabricator-attack-close/infested-wait-open/ovicopter-partial-open；assertion失败继续独立case，runtime/init失败停。必须收完后才deploy/另开game。此前pwsh-6ee0f22061f54a4f、1dffb107cc7f46a8、b00fbb3464db48e1、306ea26a8da94375、1a662cc32ef74b1b均已收。
- 音频8files刚由fcb发布源码但尚未main build/deploy：5类正power和净化/检索真实receipt；实际MoveNext+builder rebind+completion前Close+commit window，保留CardContributions wrapper，组合1745checks通过，新增正式Python discover wrapper3tests。Domain.AfterApplied保留。播放/听感/真实触发仍NOT_RUN。
- dd正在独立stage SteamEruption/WaterfallGiantBoss完整死亡保护→ABOUT_TO_BLOW→power移除→EXPLODE→terminalKill slice，方案需真实分项提交/来源generation/不回滚block或HP/不额外CheckWin/不自await，未发布。9cc正在stage真实save/load独立probe+pairdriver：原生room-entry checkpoint重开战斗而非midcombat状态恢复；现bootstrap shouldSave=false不可用于save验收。拟S1/S2 native ForceClick Pause SaveQuit/Continue标签不是鼠标；同process/全重启专属profile双phase握手，尚无实际存档证据。
- 下一步收当前job→修真失败；新版6case探索重跑；Coupon12/DomainCard4/余12passive/旧summon7+剩D17继续串行；普通输入、完整AI4cells、存档/全流程/听感等仍未完成。07:30不是完成承诺。

## 早前增量：05:36（部分已被以上覆盖）

- 最新main完整build 0warning/0error，415 Python tests PASS，已在旧批结束后deploy owned files。包含修后的Prepared guard、Revival安装及DomainPower.AfterApplied钩子、PreparedChoice3、PowerPresentation、EnemyExploration接线；仍是未完成候选。无commit/push。
- 已收完18-case job pwsh-a551d5ddac084d80：persistent剩14全部PASS，合并此前5即19/19机制用例PASS；Prepared dynamic/native-domain/replay-paid PASS，guard因fixture FromMonster后重复Targeting失败（source已修，新DLL待重跑），保留旧失败。Matrix MVP203231Z-0224c4ec和RH-upgrade-turns203554Z-d0c47cdf此前已全gates PASS。
- 已收完9-case job pwsh-a8bd9b4548c2430d：newapply五种off/on/open/close/post、initialPlating off/on、Suck off/on均真实全gates PASS，末个213112Z-cb6a418b。合并Ritual off/on即passive23中的11已过；剩余原Ritual/Plating边界及CurlUp/Skittish12未运行。Suck LASH仍明确为选择真实move的机制fixture，不是自然AI。
- Revival只覆盖Reattach/Illusion：9cc审出foreign保留票污染、取消后stale callback仍先动画、Kill completion前depth未闭合三项，dd已窄修；44decision+32身份组合+12真实Harmony emission+12Python tests通过。main以当前旧Summon模块与新Revival实际两安装顺序emission通过，保留3native death anchors；对应job pwsh-c4184ebc39f44468已收。两个死亡generation、HP已提交窗口、async AfterRemoved重入、正常付费牌胜利末端仍未验，不从显式CheckWin探针推导完成。
- PreparedChoice3是原生visible holder GrabFocus/Viewport.PushInput/真实选择同步与ActionQueue支付，不是OS鼠标。PowerPresentation是25models/46行真实HoverTips与Texture资源尺寸读取，不是视觉或听感识别；25说明完整smartDescription与13能力语义PNG已部署。
- EnemyExploration新独立6case smoke（4Act+BUDGET/WIN/LOSS）已接线，尚未游戏跑。runner新增matrix_selection/matrix_catalog/matrix_prerequisite_report及CLI；helper精确原bytes独占冻结输入，explore必须通过完整smoke runner report公共8+scenario gate、诊断、hash/token及native artifact复验，不能仅拿completed artifact冒充成功。focused10/10在main权限下PASS，子权限曾WinError5但未改ACL。
- **当前唯一native主job pwsh-6ee0f22061f54a4f**：新415-test部署串行PowerPresentation→Prepared guard→PC3→reattach-off/illusion-off，任一失败即停，尚未收结果。禁止期间deploy/另开game。
- a3仍stage新D17召唤模块+11新probe，未发布：真实Create/Add前guard、strike入口只记录不消费、per-item已提交保留，双顺序与Revival emission通过；旧production仍entry-only有已知D17缺口。b03 stage Hex/Tangled/Smoggy/Ringing4精确贡献，真实PowerCmd提交点来源ledger，mixed/unknown保持native且不声明支持；不等于Affliction写入/塞牌覆盖。fcb stage最小音频receipt，不能只小async入口Prefix，尚未发布/播放验证。
- Windows仍LockApp外部阻塞物理输入；未重复尝试，不得绕过。下一步先收当前job并修真失败，然后跑6case探索smoke、Revival其它8变体、余12passive及召唤D17新模块；后续全敌动作覆盖、存档/完整流程/安装卸载及实际输入仍待完成。07:30只作检查点，不是完成保证。

## 早前增量：04:32（部分已被以上覆盖）

- main最新完整build零警告零错误，363tests PASS；当前Git HEAD为8b563f79742ba89c9a97e75f068cef852864df36，dirty，index没有暂存项，无commit/push。
- 新部署已含DomainPassiveEffects.Install、兽化Type/Target原生backing同步/Clone/Reset修复、relic生成牌身份修复。runner/ModEntry/bootstrap已接全部23 passive cases、Prepared4、enemy-matrix-mvp；普通passive13来源门禁仍按各独立工具判定，不能将尚未跑的用例说成通过。
- 新原生全gates PASS：ritual-off195426Z-1c4cfbdf、ritual-on195625Z-9e2c8241；U32-max-coupon200050Z-234eb568（实际ActionQueue支付，非鼠标）；新兽化F01 200220Z-793d55c2/F02 200408Z-18ade5d8；Infested-on200739Z-a4eacd50（实际死亡/0spawn/胜利/结束）；U25-purification200906Z-e6d58e4b（新token、修正后严格两条真实draw history）。先前U32计划脚本拼错case名max-expiry导致脚本在两Ritual之后退出，已改为实际max-coupon，未伪称机制失败或跳过。
- RH-upgrade-turns200557Z-4540173e失败：原生medium STICKY_SHOT生成Slimed，probe初始10身份表不认识它。058已修只读生成牌registry、nativeindex/owner/master/source/history/全5pile严格门禁，Twig=1/Leaf=2且未知仍报错，不改遗物或敌招；最新版正在复测。
- **鼠标输入明确外部阻塞：Windows锁屏。** 新布局版194746Z-a23f15bf已过ready但前台非owned；显式opt-in版201446Z-e5d6c199一次SetForegroundWindow=false，仍0packets。main实际GetProcess确认前台PID8632是Session1 LockApp.exe。不能继续重试或绕焦点；待人解锁后用既有 `tools/manual_input.py --timeout 180 --ready-timeout 150 --frames 10000 --activate-owned-window`。默认仍不请求焦点，opt-in验证无人输入/owned PID+job+HWND/单次请求/严格逐packet门禁。31stagedtests与10activation复测已通过。不能写普通鼠标付款已通过；U32是另一个真实native queue付款证据。
- 新可复用成功stock位于201446Z-e5d6c199/manual-report.json的stock_teardown_control，run201214Z-8a52ac86，900frames真实window成功；也可用此前成功stock，保持strict errors对照。
- **当前唯一主线程后台job pwsh-dbd50e1e3b5b429c**：已部署363-test版，运行enemy-matrix-mvp(timeout900/frames30000)，若runtime干净随后RH-upgrade-turns。还未收结果，禁止期间deploy/开第二game。前述manual以及pwsh-b24fe2697623435b、pwsh-d4e21249b37945d1均已收集完。
- Matrix只做同一Godot进程2个fresh native run/同seed/每战2个真实EndPlayerTurnAction→3Player Play边界，再预算退出/真实ReturnToMainMenu；初始bootstrap warmup不计。实时History.Changed复制，旧refs/queue/choice/scope检查。不是完整AI/全部带状态跨战压力，也没有胜负流程。成功后先扩Act映射，再80registered遭遇探索；event-only要真实event路径。
- 目录澄清：Architect可由EnterNextAct→TheArchitect终局事件到达，但source仅Enemy-side display+NOTHING/HiddenIntent、无战斗选项，不可裸开CombatRoom冒充boss；另3是player-side pets，1abstract段不算额外实体；剩余无formal根者保留UNRESOLVED。85/107仅registered-combat闭包，不等于全内容/全部动态根。
- 新待实际跑：23passive（已跑ritual-off/on，余21）、persistent19（已通过U21-deploy-at-three/U26-before-effects/R02-no-consumption/U25-purification/U32-max-coupon，余14）、summon7（已过infested-on，余6）、relic4（修后均待）、Prepared4（全部待）。新passive env仍VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE；newapply5/initialPlating2/Suck2各独立gate。Suck的第二LASH是显式选择真实可达move的mechanism fixture，不是自然AI覆盖。
- Prepared4全部真实PlayCardAction支付非AutoPlay：PR-training-dynamic-spells、PR-training-native-domain、PR-guard-instances、PR-replay-paid。测试初始energy10/enemyHP500明确fixture，R09选真实攻击move不是自然随机路径。C19/U39选择等6项仍NOT_RUN；058继续stage真实choice小批，不改现4schema。U10只训练下张Attack，R07/R09普通Skill不得消费；训练计算支持原生雷伤不意味着扩大U10资格。
- dd71在.local实施Reattach+Illusion完整死亡/待复活slice（未发布未Install），以后main接Install及DomainPower.AfterApplied await DomainRevivalEffects.AfterDomainOpened(Owner)。无nested CheckWin：正常ActionExecutor170已有safe nativecheck；不能Killagain、不能只改veto留尸、不能回滚已提交HP/误删活段。Steam/Adaptable/Stock及其他mixed死亡被动仍未实现，不扩大覆盖。a3/cfe/fcb/b03目前交付后idle；9cc仅.local额外回合设计，不改19schema。
- 下一步：收当前job；如失败先定位；然后以短串行批次优先Prepared4、剩余persistent14、passive23各source关键新Apply/Plating/Suck对照以及summon/遗物。保持main独占fullbuild/deploy/game；锁屏只阻鼠标，不要暂停其它目标或把goal标blocked。

## 早前增量：03:42（部分已被以上覆盖）

紧接下列记录后的更正：U25-purification失败已定位为外部oracle错把净化分支当replay，漏计真正抽到status的原生History.CardDrawn（native先记录历史再自身draw hooks）。9cc将purification严格固定为direct-status→replacement两条，replay仍1条，新增缺项/乱序/多项负例，31比较器测试通过；旧raw修正oracle校验True，旧failed报告未改，仍建议新token重跑。另cfe发现RunManager.EnterNextAct直接创建未注册TheArchitect事件，Architect有真实终局可达根；**85/107仅已注册根闭包，不是最终全集**，必须扩充分母，调查中。19persistent当前暂稳schema等待main实际跑，不立即加extraTurn字段。

- 最新全量build零警告零错误，301 Python tests PASS。当前源码包括新manual布局修复、persistent全部19cases、第二遗物4cases、DomainPassiveEffects及首批PassiveContractProbe10cases；**301是静态/工具/隔离IL测试，不是301个原生游戏场景**。
- 已完成并收集全部主线程后台jobs，无运行中游戏：pwsh-01170a327cd54ed3（E01新生命周期PASS，首次catalog文本FAIL）；pwsh-6cb0392089b54e66（首次普通输入FAIL）；pwsh-01f79364bca24af2（下述6场5PASS1FAIL）。下一次可安全部署。
- 新原生E01 191803Z-32c37fb9全gates PASS，证明main改MoveNext/Reset后的基本迎战仍成立；E02/B04及跨战/放弃仍待复测。
- **89卡178面原生catalog已PASS**：193201Z-4937748e，含牌池、费用/类型/关键词、精确中文、6玩家文本覆盖、zhs→eng→zhs重载、178普通/大图读取。首次191945Z-c95c2e2a有76文本不符=38面×reload；已修正文与native重复消耗、B02/3/4措辞、R14冻结简述、T01句式，机制/fixture/oracle未改。不能将catalog等同89牌效通过。
- **原生注册来源分母发现已PASS**：193327Z-4b4ff955，4acts、65events、80act+5event=85encounters、107monster types、3live样本。executedActions/verifiedTransitions/verifiedBranches均0，G4 NOT_RUN。cfe正设计同进程真实encounter-matrix与补查14未解析类型，不可称全敌人兼容。
- persistent实际窗口：PP-U21-deploy-at-three193449Z-f1d4a07d PASS，PP-U26-before-effects193614Z-a0825b51 PASS，PP-R02-no-consumption193916Z-d56c80de PASS；**PP-U25-purification193748Z-a65ebc47 FAIL**（runtime干净exit0，仅独立断言false），9cc正在定位，禁止放宽。其余未跑。最新19-case源码增加U25原生PommelStrike→Hellraiser→Strike嵌套，U32真实ActionQueue.RequestEnqueue(PlayCardAction)支付/非法目标拒绝，尚未部署/实测。
- manual首次192623Z-6e6e25ea FAIL：MANUAL_PLAY_ERROR Missing visible native input anchor；无鼠标packet发出，不能说支付失败/成功。已看manual-before.png：卡牌底部裁切且回合横幅未退。b03已改用真实NHandCardHolder.Hitbox，等待启用+可见+3次几何稳定，裁剪交集内坐标，保留所有守卫，增加逐节点diagnostic及failure PNG。最新main已编译通过，下一步应优先部署后重跑tools/manual_input.py --timeout180 --ready-timeout150 --frames10000。
- 可复用的新成功原生窗口stock：192350Z-22bef86a，900帧耗约153秒，strict successful=true；完整e存192623Z-6e6e25ea/manual-report.json的stock_teardown_control。别用90秒误判此控件加载，也不豁免headless纹理错误。
- relic4cases已接ModEntry/headless（relic-contract、RELIC_CASES/env），compile通过，尚未跑；行为标签是native升级链/响应不是Orobas对话或普通支付。
- **DomainPassiveEffects尚未Install接线**：6准确被动来源+3实际command MoveNext提交边界+Reset(bool)，stage实际Harmony emit/撤销与26IL/decision checks通过，无游戏验收。PassiveContractProbe10cases也尚未接ModEntry/headless；支持ritual/plating各off/on/open/close/post，SlimesWeak，控制真实await中领域开关/未标记nested/已提交不回滚；新Apply分支与Curl/Skittish尚未native验收。a3正准备独立CardPassiveContractProbe并会要LouseProgenitorNormal/PhantasmalGardenersElite bootstrap。
- fcb只读实验确认cost/nativeTarget/Keywords/Retain消费者正常，但优化sealed具体消费者可绕过Type/TargetType leaf覆盖。main已批准其窄修原实例backing同步及Clone/Reset原值，仍在.local staging；未当作真实GUI已失败，不要自己同时改BeastForms。
- 活跃children：058已完成文本/relic；b03布局修复完成；9cc定位U25真实失败；a3扩展passive原生fixture；fcb兽化Type/Targetbacking窄修；cfe同进程encounter执行方案。main独占fullbuild/deploy/game。无git commit/push。

## 早前增量：03:10（下列部分已更新）

- pwsh-fccb53e8851c417e已收集，exit0，13个真实窗口场景全部通过：新版D01、draw-expiry、修复后的F01，以及flutter/soar/intangible/slippery/hard-to-kill/shell/artifact/thorns/reflect/heal。首批压制机制有实际证据，但不是107敌人状态覆盖。新F01日志CONTENT_OK=89，X转换前后同cost对象，真实raw CostsX由true变false，未再见GetRawText缺文警告。
- 最新全量构建0警告0错误、252 Python测试通过（已含manual全部18项）；新增ManualPlayProbe缺History namespace及Encounter nullable警告已由main修正。manual工具遗漏--bootstrap已由main修复，Pillow依赖已移除，严格stdlib PNG验证保留。普通输入尚未运行。
- 源码现已含第二遗物ImmortalHeart，原生Orobas/Touch/GetUpgradeReplacement/RelicCmd.Replace链，Starter稀有度与nativeBlackBlood一致；行为未验收。新CardCatalog/EnemyCatalog/Persistent7/DomainSummon7/Manual探针全部已提供；main已接ModEntry，headless已接除独立manual运行器外的各场景。对应bootstrap精确选择ChompersNormal或Fabricator/Ovicopter/Phrog encounter和Elite房型。
- main刚修Engage生命周期：CombatManager.Reset(bool)递增generation；旧async窗口不能跨战计吸收/发完成；意图await后重新验证；自然动作观察改实际PerformMove.MoveNext首次入口，防小async入口内联。3项静态契约及全量编译通过，**新变更还需E01/E02/B04及R02原生回归**，不沿用旧通过冒充。
- Source最新构建尚未部署到游戏（13场仍用上一部署）。下一步重新build/test/deploy，先E01与catalog；再独立manual_input.py --timeout180 --ready-timeout150 --frames10000，原生窗口对照900帧可能需接近180秒，勿用90秒硬猜。普通输入要求游戏实际前台，逐packet核验，不抢其它应用焦点。
- 后续运行persistent7、domain-summon7、enemy-catalog并修真实失败；058正在写第二遗物native链探针。其余正式卡牌效果/选择/保存/终局/全敌人矩阵仍未完成。子代理误git add的3个enemy-catalog文件已仅取消暂存，源码保留；无commit/push。

## 当前检查点：02:45（下列工作状态部分已被最新增量更新）

- 全部89张卡定义现已进入生产源码：4基本+33直接+16选择/回收+2兽形+5历史+7兽化+10准备效果+12持续能力。主线程全量构建0警告0错误、Python166测试通过；这不是178面或89牌效引擎全验收。
- 规则reference已与上游47个TS及文档核对冻结。R06/U10按冻结实现也强化动态U05及原生R07/R09雷伤；只有C19限定固定攻击段。六项“设为0费”仅改展示，原非叠加−1机制保留。
- D01原生窗口完整通过20261031T182130Z-2681dda9：首次await临时Task替换为真实Task，已以同一退出frame重新绑定，未改76/88/88期望。随后D02 182423Z-2251d99f、D03 182551Z-ec0c5035、L02 182718Z-65f0931f、draw-expiry 182841Z-23fec6a4均完整通过。它们是机制探针，D02/D03原生TwinStrike代理，不冒充16个正式卡夹具全通过。
- F02原生窗口完整通过183218Z-77209932。F01 183029Z-e9ae49dc在转换X牌时失败：AutoPlay内联读取旧CostsX，而setter读取转换值。新修复对同一个CardEnergyCost更新真实Canonical/CostsX后备字段，保留原modifier/_base，Reset恢复；已全量编译，等待F01重跑。
- 当前已接线：BeastForms、AttackHistory、TargetCosts、PersistentBlockHooks、DomainEnemyEffects首批12补丁、DomainSummonEffects（Fabricator/Ovicopter/Infested）、PresentationBridge。召唤补丁仅23个状态/元数据检查，不是原生行为证明；Surprise及复杂复活/偷牌/孵化/沙坑等仍未完成。
- cfe新增CurrentChoices、Domain后逐普通段IOrdinarySegmentResponder、精确单次DrawObserved；补抽/嵌套普通Draw不继承观察器。Draw原生SetResult前关闭请求，净化分派走精确callsite。新阶段尚需回归D01/draw-expiry/U25。
- 主线程已实跑历史58状态检查+8原生IL检查；不等于正常支付/悬停/UI通过。TargetCosts精确使用PlayCardAction已解析目标，不依赖晚设置的CurrentTarget。
- InlineModelLocalization已加入：BaseLib的inline字符串只在ModelDb.Init注入，随后语言重载会丢失；现在GetTable按已有注册模型重新合并本mod字符串，无重复注册。旧F01反复缺T01/T02描述，修复需实际catalog/F01验证。
- 最新集成89卡+桥接的headless D01 184132Z-fb7f08af牌效断言通过，但整体失败：无mod原生900帧对照184114Z-b475dd2c出现texture t=null。不可白名单或宣称完整通过。窗口300帧对照182037Z-70874031确实成功，约53秒；窗口900帧可能超90秒。该原生错误并非仅提前退出可解释。
- 活动PCK已推广effects superset，173580016字节：26动作940帧、178大小卡图、40VFX、47Ogg/54cue、六UI路径、10SVG图标。原始资源未改；低层解码播放/清理验证通过。桥接已接线但实际音画覆盖仍待验证，部分能力图标仍复用nativeStrength。

### 当前工作与交接

1. 主线程唯一拥有全量build/deploy/游戏进程。当前后台任务pwsh-fccb53e8851c417e依次跑最新部署窗口D01、draw-expiry、F01、10个domain-enemy-contract案例；采用上述真实成功窗口对照，日志不缓冲。完成后必须收集，失败不放宽。
2. b03e1fc6-c935-4717-ad83-da647fad3857正在新增真正Windows SendInput的B01普通出牌探针/运行器；严格原生支付、原始卡实体、非AutoPlay、HWND/PID/token/geometry前置验证。尚未运行。
3. dd71a2ff-d193-45ef-bc03-0421f0d83379正在新增CardCatalogProbe与外部比较器，89/178原生关键词/升级费用/中文字串/语言重载/贴图解码，等待主线程接线。
4. 9cc5a33a-fec5-404e-a4a4-197bddd0bcc1正在新增持续能力原生探针，先6个用例，19fixture中其余明确NOT_RUN；涵盖U21全局偶数、U26牌效前、U25精确抽牌、R02。
5. 058106ab-d191-4fa1-a5db-505ace4544c2正在补第二遗物万古不灭，须核对StS2实际获取/替换路径，不能猜Boss稀有度或同时叠装两遗物。
6. 正式敌人分母候选85encounters/107models仅静态审计，完整敌人/动作/状态矩阵尚未执行；121命名空间源码含测试/宠物不能当正式分母。完整流程、三连续战斗、保存重启、安装卸载及终局仍待完成。Goal保持未完成，不按时间或代码量宣称完成。

## 历史实施进度（以下已过时，保留问题演进）

- BaseLib3.4.7 官方发行物已校验、通过所有权守卫安装，真实游戏0.107.1加载成功（282 patches / 0 failed）。仅保留 BaseLib 一套角色/卡池/遗物注册；卡/角色/遗物使用稳定 CustomID。
- 新原生 PCK 已打包：26动画/940帧/178大小牌面，独立 Godot 导入、导出、挂载及动作播放校验通过。旧资源 junction 不再部署，仅清理已登记且目标一致的旧 link，源美术未改。
- 原生角色场景在真实游戏内成功创建；B01/B02/B03 的 AutoPlay 效果测试通过（6伤害/5格挡/主11其余3）。运行 `20261031T172137Z-588ff72e`，无运行期/关闭逻辑错误；退出资源泄漏类别匹配独立原生对照。**这是效果验证，不是支付/普通输入/视觉验收。**
- 最新Python全套101通过（工具/依赖/夹具/资源/33张新增牌静态66面/运行结果比较器）；C#零警告零错误。独立89卡/178面夹具的16机制示例仍未由对应真实输入完整执行。父线程实际运行生产雷伤计数24断言、领域状态31断言通过；不是Harmony/游戏行为证明。
- 中文窗口 `20261031T174048Z-f4fcbf17` 完整门禁通过，截图before/after已检查：自有本体、卡图、头像、能量UI可见，遗物仍NOPE占位待新图标。当前为AutoPlay效果测试，不是普通输入验收。UI六路径已整合；角色构造完成后调用继承的RegisterSceneConversions，避免bootstrap绕过ModelDb.Preload导致Control→NEnergyCounter转换漏注册。
- 生产迎战E01 `20261031T174115Z-2a587487`完整门禁通过。E02 `174230Z-8740b2fb`、B04 `174255Z-497a5670`效果断言通过但原生对照失败，整体仍失败，须重跑。对照300帧可能提前退出导致native texture t=null，已延长到900并保留严格错误门禁；不可把这个错误加入白名单。
- DirectEffects.cs新增33牌，连同基本4张现有37张定义，已编译；静态66牌面/成本/目标/Exhaust一致，不宣称运行完37张。兽化T01/T02仍由新子代理实施。
- 真实领域D01 `20261031T175105Z-1b264f93`失败：领域1/雷势2存在，但两次B01只造成普通6+6，无附雷/批次。其它环境门禁通过；子代理正在定位CardResolutionHooks的实际scope/segment调用，**不得修改期望76/88/88或标已通过**。
- DomainEnemyEffects首批12精确补丁已接入口并编译（减伤/伤害上限/Artifact/Thorns/Reflect/活敌治疗，保留生命周期）。99个stub隔离断言仅子代理运行，真实敌人验证未跑。复活/偷牌/召唤/复杂保护阶段仍未实现。
- Core/EngageCmd 已接入 B04：真实 PerformMove、await前占位、实际 DamageBlockInternal 返回值累计、只跳过提前消耗的敌方行动与意图、完成响应；初始遗物每个玩家TurnNumber首次完成抽1。生产迎战完整E套件尚未执行，不能用旧原型通过替代。
- LightningCmd / Core/LightningBatches / LightningCounter / StormChargePower 已编译：明确批次、全阻挡计数、范围一次、持续雷势、不把任意Unpowered当雷伤。新的中文窗口内容运行进行中，尚未验收。
- 本地 ILSpy9.1.0.7988 在 `.local/dotnet-tools`，使用 DOTNET_ROOT 与 DOTNET_ROLL_FORWARD=Major；固定版全程序集反编译到 `.local/game-source`（必须保持忽略），按命名空间目录可读。121 Monster源码包含测试类，不能直接当正式分母；正式 ModelDb.Monsters 来自 Acts.AllMonsters。

### 当前并行分工与紧接着的动作

1. 主线程串行拥有构建/游戏部署。收集中文窗口 `content` 运行，检查截图，不以AutoPlay冒充普通玩家路径。将新的六项UI资源候选整合并复验。
2. presentation子代理 `b03e1fc6-c935-4717-ad83-da647fad3857`：六项非战斗UI原生替换已打包到 `.local/packs/Volibear-ui-candidate.pck`，不覆盖现用包。主线程需改Character六个path override并调用 VolibearPresentation.RegisterSceneConversions() 注册自有Trail工厂；再推广候选。旧包仍含临时Ironclad非战斗UI fallback。
3. 契约/机制子代理 `cfe8b589-e58f-4ac6-86a4-ec9d86e383cb`：正在新建DomainPower/CardResolution，负责每次真实出牌普通首段附雷、重放共享机会、抽牌净化与抽完后到期；**敌人有利特殊效果抑制仍由主线程负责且尚未实现**。
4. 测试子代理 `058106ab-d191-4fa1-a5db-505ace4544c2`：正在新建生产EngageContractProbe及headless场景。E01/02采用native LeafSlimeS TACKLE+Strength5形成8伤，直接生产EngageCmd测格挡5/10；B04另测，B04正确格挡是8(11)，不是5。不替换真实敌人动作，不把直接命令当普通卡牌支付验收。
5. 卡牌批量实现前仍需比对实际bear-forge与reference并冻结差异；85张其余卡、第二遗物、兽化、其他powers、正式敌人动作/状态覆盖、完整音画和普通输入流程仍待完成。

以下为旧换机检查点，历史数字不代表当前完整验收。

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
