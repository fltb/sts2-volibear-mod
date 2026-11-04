# 当前源码交接：PR #1

当前分支：`codex/mode7-completion`。当前范围以 [RELEASE_PLAN.md](RELEASE_PLAN.md) 为准；
实施条目见 [IMPLEMENTATION_TODO.md](IMPLEMENTATION_TODO.md)，本地 Agent 直接使用
[LOCAL_AGENT_TASK.md](LOCAL_AGENT_TASK.md)。本页替换此前累积的历史检查点，旧分支、旧 DLL、
旧测试计数和旧 UI 自动化结果不再作为当前候选的通过证据。

## 最新美术与文案优化（2026-11-05 凌晨）

- 用户要求停止跑测试，继续优化图形与文案：领域禁用遮盖、能量框、卡牌耗能框、领域雷圈。
- 新资产为 AI 生成后本地处理，来源、处理脚本与哈希记录见 [ui/source/energy_20261105/provenance.json](../assets/animation/ui/source/energy_20261105/provenance.json)：
  - `energy_orb_charged.png` / `energy_orb_empty.png`：充能 / 空能量球；`energy_master.png` / `big_energy_empty.png`：充能 / 空状态纹章；`big_energy.png`：卡牌耗能环（中心压成单色不透明以托住数字）；`domain_suppress_seal.png`：领域禁用符文；`domain_storm_aura.png`：领域雷电地带贴图（1024×353）。
- 表现接线：[energy.gd](../src/Volibear/Presentation/energy.gd) 用贴图球替换原扁平圆环，并把原生 Label 的数字居中到球面（只调位置/字号/描边，仍不写入数值）；[DomainStormRing](../src/Volibear/Presentation/DomainStormRing.cs) 改为双层加法贴图 + 呼吸缩放 + 12 支程序化电弧，半径 300、地面椭圆与退出清理契约不变；[PowerPresentationDisabledVisual](../src/Volibear/Presentation/PowerPresentationDisabledVisual.cs) 禁用药符改用新 seal；敌人领域压制悬停文案改为“领域压制 / 该敌人的特殊机制已被领域禁用；普通攻击仍然有效。”
- 真实验证：`power-presentation`（`20261104T184124Z-e1590117`）与 `domain-visual`（`20261104T185738Z-f4f9a525`）两个原生短场景 passed；截图逐张查看：充能/空能量对比明显、耗能数字清晰、雷电圈有厚度、意图被符文盖住。
- 已知遗留：引回归 1348/1359 通过，2 项旧艺术期望仍描述已被替换的程序化美术（`test_energy_states` 的像素/亮度断言、`test_domain_spirit` 的 Line2D 结构断言）；按用户“不跑测试”指示本轮未改测试，后续接续时需同步这两项。

## 最新交付（2026-11-05，riot_en 私有音频版）

- 用户裁决（11-04 晚）：领域禁用标记不显示文字，只用图标盖住被禁用的效果与意图；“本战”这种默认文本也不显示。只改表现与悬停文案，未改玩法、数值或原生 Power 结算。
- 本机拉取线上最新 `b81b5c8`（其冷构建门 527.557 秒通过）后实施：
  - [PowerPresentationDisabledVisual](../src/Volibear/Presentation/PowerPresentationDisabledVisual.cs)：受压制状态图标改为“暗化底 + 单枚 domain_suppress 符文”覆盖；生物级标记为无文字符文，按原生意图行居中对齐并盖住意图图标；移除常驻文字与 Label，悬停仍显示“已被领域禁用”。
  - [PowerStackPresentation](../src/Volibear/Presentation/PowerStackPresentation.cs) / [DomainPower](../src/Volibear/Core/DomainPower.cs)：永久领域数量标签为空，悬停说明改为“领域持续。……”；`docs/文案审核.md` 永久领域条目同步，临时领域仍显示剩余轮数。
  - [regression.py](../tools/regression.py)：补入拉取提交新增的 Windows-only 跳过原因 “Windows Job descendant ownership contract”，Linux 引用门不再把该另一平台检查误判为未执行。
- 定向：完整引用回归 1359 项通过（1350 通过、9 项另一平台固定跳过、0 失败）；真实原生短测 `20261104T160127Z-809cd9bc` passed，人工查看截图：敌人意图被符文盖住、无“已被领域禁用”文字、雷甲合计 7 保留、永久领域无“本战”。
- 成品（riot_en 私有音频版，含 2026-11-05 美术）：[Volibear-0.1.0-StS2-0.107.1-riot_en-private.zip](../.local/release/Volibear-0.1.0-StS2-0.107.1-riot_en-private.zip)，173,248,430 字节，SHA-256 `3ef0dc2534a82a5c1b4f268fc3578e23dbf5f3c95694f1a90563888405068419`；18 项包内容，含 Volibear DLL/PCK/JSON、BaseLib 3.4.7、riot_en 音频来源与许可、安装说明。DLL `f1bf6db81055cca0bf899fbf1cac8b5a3e1acf5a7627d302f5d3eb3b0f0b88f1`；PCK 176,579,380 字节（riot_en）。Riot 媒体只位于忽略目录并随私有包分发，不进入公开 Git；人工听感与审美批准未执行，不冒充自动检查通过。
- 本机验收范围（如实边界）：完整引用回归 1359 项通过（1350 通过、9 项另一平台固定跳过、0 失败）；真实原生短测 `20261104T160127Z-809cd9bc` passed 并逐张检查截图；native suite 已真实执行并通过 domain-suppression 三场（含本轮图标化禁用 UI 断言）与 architect-ending，随后在 471 秒被项目窗口性能守卫 `WINDOW_PERFORMANCE_FAILED sustained FPS below 10` 主动停止（该轮 .NET gen2 GC 累计 95.6 秒/1315 次，10 秒采样出现 1–7 FPS 的加载停顿；运行期间桌面另有浏览器等程序，可用内存约 4GiB）。因此 card-face 完整批次、card-lifecycle、presentation、正常流程、跨进程恢复与双端多人未在本机收口，A2–A7 不声称通过。
- 包生命周期：对本 ZIP 实际执行安装、同包更新与卸载验收通过（BaseLib、其它 Mod、存档与固定游戏文件摘要保持不变；`scope=filesystem-only; no game launch`）。
- 平台边界：POSIX 窗口路径的 native 与多人为串行调度（并行编排仅 Windows/background），600 秒监督门与本机性能守卫无法同时满足；本轮因此使用同一 `deliver()` 的完整串行路径（`.local/tools/run_release_serial.py`，忽略目录）并保留未执行项，没有把超时或中断写成通过。基线 b81b5c8 已在 Windows 机器通过完整冷构建门（527.557 秒）；本轮相对基线的差异仅为 UI 表现与文案、测试/oracle 及 Linux 平台跳过原因，未改玩法、数值、存档与网络逻辑。

## 最终交付结果（2026-11-04）

- **当前源码候选700479f完整冷构建发布门通过**：外部CLI总墙钟527.557秒（8分47.56秒），监督回执527.469秒；固定600秒限额内完成，exit0、package_accepted=true、cleanup_complete=true。不是各阶段分别计时达标，也未把资产构建、回归、原生检查、打包或安装卸载挪出CLI。
- [完整安装ZIP](../.local/release/Volibear-0.1.0-StS2-0.107.1-20261104.zip)：172153337字节，SHA-256 `8689928cb633ec12e715fd2a2400e18de0ae941578868c8ebbe9e48153b78c92`；15项包内容，锁StS2 0.107.1/59260271、BaseLib3.4.7，open音频、不含私有音频。DLL摘要 `a2a3c5aa479fe6bac1ff0286e8887a9cb81b6e5c649dc36a9fe07841cb20a414`。
- [总验收summary](../.local/release-acceptance/run-1jb7k_cl/summary.json) A1–A9全部passed；[硬截止回执](../.local/release-deadlines/run-_9911m4f/deadline.json)确认清理及包放行。完整引用回归1357项：1355通过、2固定Linux-only跳过，无缺失必需检查。410牌面固定205+205精确once、全48life、356图册、actions、原生正常流程、同进程保存、S2独立进程重启、双本地客户端及文件系统安装/同包更新/卸载全部原检查通过。没有Steam公网或任意第三方Mod兼容认证。
- 本轮阶段：DLL2.844秒；回归68.437秒与强制冷资产50.922秒并行；部署1.015秒；NativeSuite429.594秒与多人66.516秒并行；打包7.547秒、安装生命周期17.500秒。主进程040931Z-3bd74169、图册040931Z-43405f9f，二者no_runtime_errors=true，完整分片合门true。
- 已检查本轮升级R01大图与1920领域蓝灵体/宽雷圈截图，未更改用户已批准的视觉或文案。机器summary不冒充人工审美或听觉批准，human_hearing仍not_performed；音频结论只限自动播放/PCM及增益检查。安装生命周期是最终ZIP文件系统验收，没有另起已安装fixture游戏。
- 以下保留本轮实施及失败证据作为历史，不能把旧包或旧失败轮混作此次交付。本次交付完成后无需再重跑最终门；后续产品变更须另建当前候选证据。

## 本轮实施过程（2026-11-04，历史记录）

- 11:07用户明确批准固定两组并行：完整410按原请求偶/奇索引205+205，复用原主玩法与图册两个进程，总8/峰5不增加。主七阶段保持第一组牌面及全48生命周期/actions/正常流程/保存；图册进程先原356图，再同进程原第二组牌面。原逐案fresh run/付费/身份/清理和两层media oracle不减，总门验证精确once/disjoint union、原顺序、独立token/实际PID及严格完整包络；局部runIdentity不作跨进程比较。
- 新CatalogFaceSuite协调器、路由及Host守卫已完成，截图段不启用gameplay scope；C#9定向项含原生API/故障边界/1391恢复断言通过。Python100定向项通过；新包络拒重复字段、类型伪装、乱序与尾部错误，现有原oracle未放宽。新SDK测试独占临时目录，回归白名单43；完整引用回归1353项（1351通过、2固定Linux-only跳过）57.980秒通过。独立终审发现并补齐主suite收据与actual owned PID/token绑定，101定向项再次通过，终审闭合。两组有界实机run-rfwj04az实际221.454秒全部通过且root清理归零：68+68牌面/8life/完整356图册与actions/S2/完整MP，主032854Z-7f1a7e83、图册032854Z-f1807f14，card_face_partition_exact_once=true。随后按校正预算执行一次强制冷资源最终门：run-popmtlqk，外部CLI475.553秒/监督475.469秒，exit1，cleanup_complete=true、package_accepted=false，未打包。冷资源47.297秒、完整回归59.172秒、MP66.125秒、native411.797秒；两个205牌面和48life行为断言、356图/S2/MP完成，但主生命周期同run第二战出现3条Godot SwapGCHandleForType“Handle is not initialized”：U20-upgraded(run26)1条、R30-base(run47)同次实例化2条。runtime门正确拒绝；不能过滤或重写失败回执。已核关键Dispose在后续EnterRoomDebug内部，而非MapTask：Map后两帧候选位置无效，已完整撤回且未实机采用。最终只在life第二战原EnterRoomDebug await期间恢复PreloadManager.Enabled=true，保留原NAssetLoader enqueue/dequeue/Process完成点，using finally恢复原值；不改GC/yield/lease/速度/断言。15定向项含70恢复断言/API通过，独立终审通过，回归白名单44。单次全部48life实机040426Z-32af7428在108.784秒通过（含同轮stock），完整旧行为oracle与严格runtime-error门全绿。现据此准备修复后的完整冷构建门，不认领确切stale资源身份，也不改写前次失败报告。
- 分组前按136实测加权的完整发布仍约642–701秒，因此未盲跑最终门。两组当前预期约8–10分钟，仅为估算，仍须新并行实测确认；最终继续强制冷资产构建并保留595+5监督。

- 用户明确最终完整gate（构建、检查、实机、打包、报告）总墙钟必须≤600秒；禁止把每阶段各限10分钟冒充达标，禁止无修改反复重跑。4a1ade6后的旧长批已由用户取消，不能再执行旧70–90分钟路径。
- 已实现但尚未证明完整放行：独立父监督595秒工作+5秒清理/报告，Windows Job及Linux subreaper清理跨代子进程；阶段日志/summary持续记录真实耗时。deadline及delivery定向测试通过，Linux内核清理未实测。
- 回归新增4进程整模块调度，完整发现/执行ID、nonce、退出码及精确skip严格校验；未审计模块仍单桶顺序执行。资产新增按全部输入、工具、PCK及四份校验日志摘要绑定的复用；原有无回执PCK不能追认缓存，下一次真实构建仍为冷构建。并行和缓存单元/短worker测试通过，完整1280+引用回归尚未执行新并行路径。
- 原生玩法批次仅作用域内用游戏公开Instant速度并关闭预加载，退出还原；发现原生菜单会重置preload，已在新局前重新应用。11case和后续3case原断言通过，但单case仍约3.5–4.5秒，不足10分钟目标。GC新增计时证明它仅占数十毫秒，不能将瓶颈误归GC；没有跳过清理或改Core。
- 静态目录捕获改为等待真实原生Tween/可见状态及绘制完成而非固定sleep；20261103T163112Z-f60a619b的356张原始截图全部通过，目录实际137秒。曾考虑目录插入/移除使用Instant，但该未验证改动已撤回；整个表现验收保持正常速度，不加速角色/特效/声音或卡片查看Tween。
- 广泛纹理驻留候选已撤回：初次泛型Array.Dispose接口错误及GetDependencies虚拟资源错误均定位并修复；20261103T165129Z-aed4c3e4单case通过、6次真实wrapper重绑且held归零，但未有效提速，所以不保留复杂度。
- 新增仅显式VOLIBEAR_TEST_PROFILE_LOADS=1启用的7处同步热点观察（scope结束卸载，不替换任务/结果）。20261103T170136Z-7764087d单case完整通过：场景加载仅自有volibear_combat.tscn占1328ms，其余资产毫秒级；每次新局和进房各有额外约1秒。锁版源码定位NTransition.RoomFadeIn(false)：Instant分支无return，随后仍走0.8秒Tween及并行的0.2秒延迟回调（不是相加1秒），解释两处不必要的视觉等待。
- 当前仅针对这两项实测热点修复：test-host作用域推进原生RoomFadeIn(false)视觉Tween至真实finished、保留原Task与回调；另只持有已加载且内容指纹严格不变的自有SpriteFrames模板，全部新Node/Model和原生缓存清理仍照常。自有动画为42条、1536帧引用、26底层atlas；读图头的保守RGBA+mip估算约1.52GB，原256MiB广缓存无法覆盖。新方案只持已有一份模板，不复制图像；作用域后释放，不延伸到正常表现验收。两项合并后20261103T171722Z-fcd85a6e单case通过，进房从2396ms到350ms；20261103T172843Z-0c7182d5新增12种复杂组合全部通过，53次完整指纹捕获合计98.854ms、held归零。
- 仅空牌库fixture的Draw→Exhaust准备使用原生命令skipVisuals，保持逻辑移牌、状态跟踪和AfterCardChangedPiles；实际测试出牌/耗牌不改。R12空分支原5799ms降至169ms（20261103T175036Z-a27b30dc通过）。只读帧指标证明剩余新局/进房耗时主要在同一ProcessFrame内，不是显示帧率等待。
- 硬件Vulkan对照20261103T174441Z-58817835四case通过但未提速，相关驱动选择代码已撤回，保持默认D3D12。诊断点扩至14处：最新新局651ms、进房336ms，LoadRunAssets仅1.04ms、GenerateMap65.7ms、进房同步节点约10ms；不能凭这些不完整前段观测猜缓存。随后使用本地.NET9兼容dotnet-trace做3case整段采样（20261103T180217Z-af8cff7a，三case通过）；trace在17042ms后尾截断，report topN拒绝，但此前405041条事件有效，12308–16355ms完整批次窗O/C配对无异常。主线程仅0.126ms托管等待，781ms采样落在VolibearEffects.Attach→Node.AddChild→effects._ready，而非C# NCombatRoom._Ready。
- 据此审计并持有第二个精确只读effects SpriteFrames模板（40批准atlas、1070帧、保守估算459276288 bytes），两模板合计1981808640 bytes，仍小于2GiB总边界。完整指纹、缺cache fail closed、释放全部引用均保留，未保留Node/Material/音频源；4定向tests含真实接口编译及238 doubles断言通过。
- gameplay-only scope临时MaxFps=240，退出/构造异常均还原（原0/60/144矩阵及普通范围no-op）；没有改时间尺度、physics、VSync或角色Tween时长。最终frame保险216000避免高fps提前quit，总595+5秒墙钟不变。整合后的6case 20261103T181705Z-49f05ac5全部通过：warm新局322.6ms、进房72ms、quiet148.6ms，普通action44–116ms、空牌库87ms；两模板held2→0，最终MaxFps还原60。
- 有界集成20261103T182643Z-f0d7dc29全部通过：3face+3lifecycle、完整356静态画面/动作、普通流程/同进程保存及真实2进程恢复。静态单卡inspect只观察真实cardTween完成+所有可见端点alpha+FramePostDraw，不等不可见双箭头的额外0.1秒，不推进/kill动画；大卡R01升级及1920领域原图已人工查看。七阶段实测：domain33.354s、architect17.053s、3face7.547s、3life7.010s、presentation157.208s、product47.176s、save9.082s。按完整410/48推算仍超600，未启动最终门；正在审查fixture原生批量准备、领域机械批次作用域和独立网络/恢复阶段的并行边界，正常剧情表现不加速。
- 新并行预检run-26cqxidz在36.343秒失败并完整清理（非最终门）；20261103T190345Z-64137cc9 domain阶段counter frozen通过但position frozen失败。新增domain gameplay scope已完全撤回，原生产文件/测试净diff为空，保持1px与全部原标准。锁原生Sandpit方法明确await真正Tween，没有证据归因初始Tween未完成，不加猜测sleep。S2/MP真实取消且父Job active归零。诊断wrapper曾在游戏启动前被.local/tools命名空间遮蔽而ImportError，显式加入ROOT修正，不影响正式入口。
- PNG两层完整校验各最多4线程，无通过/解码缓存；428图完整report与串行完全相同，14.274→7.132秒，30定向测试通过。回归整模块白名单现28、上限6、独立默认1、发布6，16调度测试与48发布/总deadline测试通过，未重开全回归。
- 两处首回合starter准备只在精确10card类型/唯一HuntersHeart/己敌无Power/无modifier守卫下调用一次原生集合Add，所有逐卡hook/视觉/身份/顺序不减；Lifecycle第二战保留原逐卡。最新192254Z-c630744e真实6face/4life已通过；新增starterSetup最初被严格旧schema拒绝，已明确新增字段并严验5搬运/10目标/身份类型顺序/Draw/Bottom/正常视觉，旧断言不减，90实收据篡改均拒绝。原失败报告不改写，完整原始收据用原生产stock噪声过滤及当前独立oracle离线重验全部通过。
- product-flow仅公开Instant+240fps，finally恢复、不关preload、不持资源、不patchfade。首次加速揭示原队列动作完成早于TravelToMapCoord尾部，不能忽略disposed TextureRect错误；现精确observer保留原Task，等待完整原旅行与refresh/vote尾部，再记到达/退出。真实普通流程从47.176→9.597秒，最新无runtime error。并行S2与完整MP各自成功，6face/4life/actions整支159.360秒且清理归零，仍非最终全量。
- 完整引用回归首次6worker/29模块执行1334项（1332通过、2固定Linux-only跳过），71.611秒；串行桶70.359秒为瓶颈。又按独占项目/输出写集审计拆出13 SDK模块，当前白名单42，16纯合成调度测试通过。42布局与catalog集成后的完整引用回归实际1340项（1338通过、同2固定Linux-only跳过、无缺失必需检查）通过，墙钟51.931秒。
- 新完整Task被动观察保留原Task/异常/执行上下文，1067定向断言通过；194425Z-7e3c0d66三case真实通过。暖LoadAssetSets同步毫秒以下、原Task完成133–141ms，LoadRunAssets总150–157ms；不是HashSet瓶颈。锁版UnloadAssets把Dispose排入CallDeferred，yield间隔可能含真实延后释放，不删yield或清理、不新增缓存。quiet时钟包含room-entered，预算不得双算。
- 已批准独立完整356静态目录批次与主玩法/actions并行，原主七阶段/付费动作/正常流程集成仍保留，新增一真实进程（共8、峰5），同轮stock仅内存共享，原两层媒体oracle全部保留。90定向测试通过后，一次300秒根Job预检run-y7q29rxk实际275.078秒全部通过并清理归零：136face覆盖全部89模型及重点分支、8长life、完整catalog/actions/S2/MP。主195723Z-c5077f85七阶段依次32.977/16.750/114.592/20.092/37.998/9.610/8.992秒；catalog195723Z-c34f1ebd完整356图及两层原媒体oracle成功。已实看新的R01升级大图及1920领域图，角色/宽雷圈/数字清晰。仅此有界样本通过，正按模型/分支计时推算最终410/48预算。
- 当前没有600秒内成功的完整发布报告，没有新成品ZIP；以上开发短测不冒充最终gate。

## Windows 当前接续：状态聚合短测已通过（2026-11-03）

已拉取开发分支031b47c；main只有较早合并内容，后续工作继续提交codex/mode7-completion。按下面19:30交接执行定向验证，不重开已交付旧范围。

- 当前Windows定向回归58项通过（含26模型/257只读规则、48项UI生命周期及15项锁版ABI检查）；生产Release编译0错误/12项既有nullable警告。
- 当前open资源包已重新导出并通过资源、效果生命周期和音频profile检查；PCK为175451000字节。当前DLL/PCK及固定BaseLib已按归属部署。
- 补齐Windows runner显式`--windowed --resolution 1280x720`；状态短测增加只读Win32真实窗口检查，未使用输入/激活调用。窗口实际client=1280×720、outer=1298×767，有标题栏/系统菜单、可见可用、非工具/置顶/禁止激活/穿透、非最小化/最大化；运行于原有未切换私有桌面。
- 本次短测`20261103T121505Z-2df04bfb`通过：83个聚合UI样本、原生格挡history严格[3,4]、合计+7、悬停主标题唯一、占位节点生命周期及普通付费出牌均通过，无新增runtime error。四张原始截图已逐张查看：雷甲单图标7、多份雷伤说明、坚甲无无意义层数、永久领域“本战”均清晰。报告/截图仅留artifacts。
- 起初用包名直接调用unittest造成两个测试模块无法导入同目录fixture；改为测试目录的标准导入路径后上述58项两轮通过，没有删除或放宽断言。此前提前启动的完整入口已在编译阶段取消，未进入游戏验收，不计通过。
- Windows短测改动已提交并推送为fc33db3。随后完整入口在引用回归阶段出现失败，已停止，未进入游戏发布验收，也未生成新包。
- 用户要求Windows/Linux使用统一runtime test层：当前正在收口`runtime_platform`/`runtime_test`、共享MSBuild属性及现有fixture入口迁移；同一套场景/断言不分叉，SDK-only/Harmony-only不强加本体依赖，必需依赖在严格模式下直接失败。
- 已修复Windows构建解释器的全局NuGet锁/MSBuildTemp访问冲突：子进程临时目录/锁隔离到artifacts/runtime，禁用跨启动身份的编译服务器复用；父Python文件系统测试保留短临时根，原生长路径fixture使用实际Windows扩展路径，不放宽260字符预算。没有修改全局权限或删除全局缓存。
- standalone Godot已共用隔离user://与既有可信CA方案，仍严格拒绝错误；能量图使用导入Texture2D API读取。批准源PNG字节/hash与inline字节保持冻结，三张可重建图对不同Pillow/zlib以PNG格式、mode、尺寸及RGBA像素逐字节严格复现，不要求压缩编码字节相同，不使用容差；没有修改批准图。
- 完整引用回归发现的旧平台假设已定向修复：25个实际安装器清单（含PowerStackVisual八target/九patch）、带转义中文literal的scanner定位、Windows路径分隔符、真实目录重定向和Linux依赖mock。Windows采用真实junction验证重定向拒绝与外部字节保留，POSIX保留symlink；未把Windows目录junction称作文件symlink。
- 对应定向验证：安装链/文本17项、文件系统/runner 93项、短profile/回归判定14项、Godot/冻结UI 11项全部通过。Riot私有来源11份已按原SHA256下载并处理为11覆盖/43开放回退，完整解码及来源身份9项通过；工具、来源、处理结果仅在忽略目录，人工听感未声称完成。
- 本轮完整严格引用回归已通过：1227项运行，1225项成功，仅2项Linux专属检查在Windows明确跳过；0失败、0错误、0缺失必需检查。统一层已提交并推送fa61f76。
- 随后最终入口A1重新编译、1227项引用回归（230.887秒）和175451000字节open PCK全部通过，但无Mod对照20261103T133546Z-fb4e0528在检查venv启动链下出现Windows系统证书库读取错误，suite未开始；失败摘要为.local/release-acceptance/run-wmxo_oqx/summary.json。未过滤该错误或禁用TLS。
- 已修统一入口：检查/构建仍用隔离venv，原生suite/恢复/双端改由宿主Python启动，依赖通过严格ABI/目录校验后的PYTHONPATH接入，长批前实际导入扩展。68项定向测试通过；相同proxy/dotnet/音频设置、真实桥接与Pillow导入后的无Mod短对照20261103T134948Z-399f6ee0成功，exit0、无运行时错误。失败诊断现在保留stock run_id及错误原文。下一步才是修正后的最终完整放行；旧ZIP仍不是本轮成品。
- 6a54242最终验收已结束但未放行：1240项引用回归运行，1238通过/2项Linux专属跳过；实机20261103T140306Z-33405c8c正常退出、无运行时错误。410牌面及48生命周期各由原校验器再次验证通过，领域/建筑师/角色/BaseLib/正常流程无校验错误，同进程保存恢复有完成回执。唯一失败为presentation的75条source gain校验：cue/file全部正确、playing全部true，但volume全部0。
- 根因已定位：新隔离profile没有初始化prefs，实际mute_in_background=true；私有后台桌面没有焦点，生产音频正确遵循后台静音，将源gain置0。总线PCM有声不能替代Mod源音效通过。报告artifacts/headless/20261103T140306Z-33405c8c/report.json，汇总.local/release-acceptance/run-wppowtkt/summary.json；跨进程恢复/联机/安装卸载/新ZIP未执行。
- 已修测试前置条件：新建owned离线profile的原版/modded prefs均独占创建schema2、mute_in_background=false；恢复保留原字节，不动日常/云存档或生产静音规则。共享profile定向138项通过。只读原生音频预检移到长批前，记录实际焦点/偏好/滑块并提前拒绝静音。
- 第一次actions短测20261103T152453Z-8ad9fabd证实prefs及滑块正确，但在1920域动画检查失败：生产几何由0.2秒Timer更新，probe仅墙钟等0.25秒，未保证跨到Timer更新；先前1920截图仍有实际动态。只修probe为最多180帧/5秒内必须观测真实点列变化，冻结仍失败，不触发生产Animate或改变批准雷圈。
- 修改后生产编译0错误/12项既有警告，15项音频/profile定向通过；actions短测20261103T153046Z-c76769c5全部通过、无新增runtime error。76个实际声源全部playing=true且gain>0（最小0.004435169）；两分辨率实际雷弧均跨2帧观察到变化，13/10ms，两张原始域截图已查看。没有重跑410/48长批。补充S2跨进程恢复20261103T153325Z-aa9e899a通过；双端联机20261103T153728Z-e4bc0cb5-multiplayer全部通过，包含真实付费动作、断线、checkpoint和重连，部署候选未变化。至此音频/表现、冷恢复和双端均已定向收口；上一整轮报告仍为failed，必须如实保留，尚不能把补测写成一次完整发布入口通过。下一步是修正后的完整最终放行及新ZIP。

## Windows 原交接：状态单图标聚合（2026-11-03 19:30）

用户本次要求统计现状、commit/push，转到另一台 Windows 继续开发。本机停止在源码交接，不启动长批发布验收；新状态聚合安装包尚未生成。下方已交付记录属于前一版，不能作为本轮候选通过证据。

### 已实现

- 26种状态展示规则（25种主状态＋临时力量派生）：同一持有者、同模型类型/ID合并一个图标；简单收益求和，复杂独立效果显示份数；取优效果用max/min；不可叠加标志不显示无意义1；永久领域显示“本战”。
- 雷甲3+4显示7，保留两份模型及分别获得格挡；不改Core、数值、来源、次数、独立首次额度、保存格式和网络结算。
- 原生状态栏只隐藏重复节点并压紧布局，保留完整原生节点/模型列表；变值、代表移除、最后一份移除、树重入和未绑定多人占位节点均有处理。
- 悬停在UI出口聚合，不修改全局PowerModel.HoverTips；保留禁用说明和其它关键词，仅删除与主状态同名的本Mod自身词条。单份文案简化为“共1份。”加完整效果。
- 主要入口：[只读规则](<../src/Volibear/Presentation/PowerStackPresentation.cs>)、[原生UI适配](<../src/Volibear/Presentation/PowerStackVisual.cs>)、[真实短场景](<../src/Volibear/PowerStackUiProbe.cs>)、[独立回执判定](<../tools/power_stack_evidence.py>)。

### 验证统计与准确边界

- 交接前最新源码：44项Python定向测试全部通过（11项stack＋10项原状态呈现＋23项runner）。其中C#内部检查：26模型/257项只读规则、48项UI生命周期替身检查、15项锁版真实程序集ABI检查。不同层级计数不混作真实游戏案例数。
- 最新生产Release编译通过，0错误、12项nullable警告（11项既有probe，1项新规则Localization可空分析）；未部署该次新DLL。日志仅在本机：[交接检查](<../.local/logs/power-stack-windows-handoff-check.log>)。
- 首轮实际游戏短测`20261103T050039Z-a1fb090f`通过：25模型/46文本资源行、9阶段原生占位节点生命周期、83个原生聚合UI样本；真实付费普通U34＋升级U34＋C24，保留雷甲[3,4]两份、显示7，一次雷伤总格挡+7。无新增runtime error。原图已检查。
- 首轮之后新增的“悬停同名去重、单份文案简化、截图等瞬态浮字结束、原生格挡history严格[3,4]及主标题唯一断言”尚未重新在游戏执行。旧报告不能通过新增字段判定，不能补写/伪装新报告。
- 曾组合运行失败于两个UI测试工程共享obj/bin，已改`--artifacts-path`按工程隔离；两遍专项及本次44项组合回归均过。该失败发生在构建/开游戏之前。
- 本轮尚未执行完整regression、Windows实机、冷启动恢复/多人最终验收，也未更新ZIP。旧包仍是下方`9e1db8d`版，不含状态聚合。本机无运行中测试/游戏任务，持久交付goal暂停以便换机。

### Windows 接手顺序

1. 拉取`codex/mode7-completion`，先读本节和[AGENTS](<../AGENTS.md>)。既有规格/资产保留，不重生成旧卡图。
2. 准备StS2 **0.107.1 / 59260271**、普通Godot **4.5.1 stable Mono**、SDK **9.0.320**、BaseLib **3.4.7**；按[本地流程](<LOCAL_WORKFLOW.md>)重新配置本机路径。`.local/`、`artifacts/`、游戏程序集、旧报告、安装包及Linux配置不随Git迁移。
3. 开发阶段可用`local_delivery.py`带本机三个路径、不带`--verify-release`完成首次构建/资源准备；此时生成的ZIP只是未做原生验收的开发候选。接着运行`python -B tools/dependencies.py install`和`python -B tools/dev.py deploy`部署自有文件。不要把测试工程编译当作生产DLL更新。
4. 先运行最新短场景（Windows runner的后台模式；先核查本机窗口行为满足当前约束）：

   ```powershell
   python -B tools/headless.py --use-deployed --scenario power-presentation --repeat 1 --display background --audio-driver WASAPI --timeout 120 --frames 10000
   ```

   检查83行、history `[3,4]`、同名主标题只出现一次及4张实际截图。失败先定点修复，不启动全量gate调试。
5. 收口后才执行`python -B tools/local_delivery.py --verify-release --audio-driver WASAPI`，完成当前候选单机/恢复/多人/安装卸载与新ZIP；更新本节结果。已有旧完整验收不必当开发循环反复重跑。

## 前一版已完成交付（2026-11-03，历史基线）

- 生产源码提交`9e1db8d92c8e1d0fb86d4f5fcbef922d3a26ff80`已推送既有PR分支。之后仅更新完成说明，产品字节不再改变。
- [完整安装包](<../.local/release/Volibear-0.1.0-StS2-0.107.1-20261103.zip>)已生成：172114199字节，含Volibear DLL/PCK/JSON、BaseLib 3.4.7及许可/安装说明。ZIP CRC、包内Volibear三文件与最终部署字节一致。
- [统一验收摘要](<../.local/release-acceptance/run-ghenodyt/summary.json>)A1–A9全部passed；[最终日志](<../.local/logs/final-release-20261103-r4.log>)exit0。1198项回归完成（8项Windows专用skip）；全部单机7阶段、跨进程保存恢复、两端ENet真实付费/状态一致/断线恢复、最终ZIP安装/同包更新/卸载全部通过。两端无新增runtime error。
- 最终单机`20261102T211825Z-2b5e0231`、多人`20261102T222137Z-48b87fb7-multiplayer`。r4 job`bash-703b9df4aab8475b`已收集exit0，不得重复启动。
- 雷圈/能量实机图已向用户展示；人工听感、Steam传输及公网体验未执行。默认包为open音频，可选riot_en保留既有构建支持。
- [全怪物支持清单](<DOMAIN_MONSTER_SUPPORT.md>)保留明确未实现边界：Hopper逃脱/倒数、木桩事件超时离场、TheForgotten新增敌方Dex收益，以及未配置直接贡献的持续badge。调查完整，不宣称全特殊机制均已支持。

## 前序收口记录（2026-11-03 03:30）

- 最新视觉已在真实游戏检查：`20261102T191032Z-06b62561/domain-visual` 原图显示大范围电光带/竖电弧、血条状态前置、纯色中心费用图、明显能量空满。旧细圈已被替换。原report保留首次oracle错误，不篡改历史；按energy.gd语义修正_has_value是“已解析”而非“满能量”，既有7原图独立重验通过（`.local/logs/domain-energy-existing-capture-recheck.json`），无需重新开游戏。域三阶段全部16/16区；能量空/满均亮31.92/103.70、蓝像素0/1631。
- 最新定向`20261102T192430Z-5218e581` passed：单游戏进程自身减益12项+熊/铁甲两种真实建筑师结局均通过，exit0/无runtime_errors。终局节点改显式初始化，并在native结算移出视图时仅解绑帧循环、不撤销最终领域状态；重入可恢复帧循环。熊80HP不变、无死亡、领域6弧/1.22倍/半透明与胜利快照一致，普通角色保留原路径。
- 最新已部署生产DLL SHA256 `abc2074ee2b2ec08e768446949356282286bbec941cefeefd9968997c49f638d`；新PCK `2206624ae6b5c40042377297a14c9b5e5974ceb28838feda469dcc4ede4ae255`。生产Release与部署字节核对一致。44项集中回归、后续终局窄回归、17项像素oracle、资源打包与空态无pulse的新验证均过。
- 最终r3已结束exit1、job已收集：`.local/logs/final-release-20261103-r3.log`。1193项回归完成（8项Windows skip）、资源验证、单进程全部7stage及跨进程checkpoint恢复均passed：`20261102T193246Z-516647ae/native-acceptance-report.json`。多人`20261102T203639Z-310404f5-multiplayer`玩法/付费/断线/checkpoint恢复断言全passed，但host/client各6次新runtime error使发布停止；尚无新ZIP。不能重跑整套gate调试。
- 多人唯一错误已窄修并实测：task-16按原版合法的先Ready后Model/复用路径，null安全读取已锁版核验的`_model`字段，setter立即刷新，树进出重绑/退订；不改Core/过滤器。task-17复用独立power-presentation短场景，抽取报错所用原版多人场景的真实NPower，天然Ready、原生命令与setter完成9阶段，包括空模型、晚绑定、同帧重绑、领域进出、节点重入与释放后回调。`20261102T210309Z-826b2951` exit0/runtime0，全9阶段通过。旧25模型oracle漏同步批准PNG路径，依据批准provenance/导出尺寸/hash独立纠正；所有25模型46文本资源样本和9阶段复验通过：`.local/logs/power-presentation-native-recheck.json`，保留原报告不篡改。16项生命周期+94项锁版引用检查及33项相关Python回归通过。未重跑多人suite或单机长批调试。
- 当前生产DLL及部署已统一为`000c04bb8d7be0eed875f0f4b29d64e7c0c6c51d82fc659c5a25d9202b8c3ead`；PCK不变。task16/17均已交付，无活跃游戏/后台job。待冻结源码、完整新候选最终验收与打包；r3是旧候选的通过证据。
- 最后完整包目标仍为`.local/release/Volibear-0.1.0-StS2-0.107.1-20261103.zip`。新UI修复会改变DLL，旧单进程通过回执属于r3旧候选，不能伪装成新DLL的通过证据。

## 窗口与可见雷圈纠偏（2026-11-03，前序过程）

- 用户重新授权：普通1280×720、有标题栏、可移动可交互的NORMAL测试窗口，不全屏/置顶/抢焦点；先修测试代码，再做短场景；脚下雷圈用户实际看到缺失，先补可见效果，不以节点计数代替截图。具体硬约束已写AGENTS。禁止gate开发循环，完整成品交付目标不变。
- 最终r2回归1165项通过（8项Windows专用skip）；资源重建通过。随后native批在用户纠偏时中止：沙坑6、骑士14回执通过，自身减益场仅创建房间，未完成断言；末尾name_changed根因未定，不能归因为已修或SIGTERM。没有新成品ZIP、没有完整native验收通过。
- 窗口旧保护创建时no_focus=true会令锁版Godot X11设置UTILITY/override_redirect；已撤去持续NO_FOCUS与鼠标穿透。一次短测已实际NORMAL、有标题栏、1280×720、无ABOVE/FULLSCREEN，但启动active window切换且mode!=0错误拒绝正常最小化，task-10继续定点修复；禁止未经修复原样重跑。
- 雷圈战斗/终局节点原ZIndex=-1；现改+2，统一入场即有Points的完整闭环与动态电弧，增宽加亮、additive/unshaded，持续随角色与退出清理保留。5项针对测试及生产编译已过、DLL已部署到隔离测试游戏；尚未通过真实画面验证。
- task-11已新增domain-visual单战斗五阶段原始PNG（before/entered/sustained/moved/exited）与独立原图像素oracle，11变异/解码测试通过。Lead已接ModEntry与headless --scenario domain-visual；正常窗口修复后先跑此短场景并read_image看实际雷圈，再收口最终gate。
- 窗口已真正闭环：`20261102T174410Z-442bd415` stock exit0，NORMAL/标题栏/1280×720，无ABOVE/FULLSCREEN；pre-map的进程限定USER_TIME=0提示生效，startup/ready及外部before/after的active窗口均保持0x600003。仅验收工具新增77行X11 hint适配，不是成品依赖。普通最小化/最大化允许。
- 雷圈真实短测 `20261102T175810Z-03935879` passed，无runtime_errors；Lead已read_image检查sustained/moved/exited原始PNG，确认蓝色放大熊脚下持续亮电环、移动跟随、退出恢复。此前误把测试程序集编译当生产DLL构建，已纠正为显式生产Release构建+deploy，源/部署DLL SHA256同为3a8d67cdac3e25bd7971711287f74834e2c071c3fc4bee3b870c00494d598b5a。
- 开发短场景明确`--use-deployed --repeat 1`，先真实Release编译与部署。CLI默认重复次数已从2改为1，新domain-visual/architect-ending拒绝重复运行并给90s/5400帧默认预算，15项runner测试通过。避免默认开发入口先做全回归；一次误触全回归的SDK环境失败已用固定DOTNET_ROOT/PATH仅针对5类重验通过。
- 持久goal现已恢复active/armed，revision7、round7。当前没有游戏在运行，继续定向开发，不跑最终gate。
- **最新用户视觉裁决优先于上面旧细圈试验**：旧截图虽有圈但被否决；要求位于状态UI后、更大包住角色、有厚度的闪电领域。Lead新增DomainStormRing：半径300、宽电光/48片渐变电墙/12支升起短雷，Z=0并在Visuals子树首位，避免原+2盖血条与原-1落入背景。战斗/终局统一Populate/Animate；当前新样式尚未生产构建或看实际截图。
- 用户同时指出能量空满同样、费用中心闪电盖字。task-14 hover-feedback正在改真实能量状态表现、纯色费用中心+特色边框、授权UI专用生成入口/清单，保留其它批准图；task-15 domain-fix正在扩展五帧短场景半径并新增原生能量空满截图/像素对比。等两项完成后统一DLL/PCK构建部署。
- 自身定向`20261102T180204Z-24829c35`及`20261102T181837Z-1c2881a3`均在Weak时长断言退出；已追到锁版BaseLib SelfApplyDebuffPatch对自定义角色自施减益清SkipNextDurationTick。task-13按实际完整链修fixture并新增13项包装链检查通过；Core没改，尚待生产重建复测。不能复活只看原生Apply就假定skip=true的错误结论。
- 终局`20261102T182310Z-e4933c02`观测：熊HP80保持/deaths0/domainEntries1/enteredtrue/shadertrue/scale1.22/原始快照一致/胜利记录1/loss0，唯arcs=0导致失败。额外先存前房间真实save已解决缺backup的原生错误。Lead把终局节点改显式Populate与ProcessFrame/TreeExiting订阅，不依赖Mod动态Node类未触发的_Ready；与新雷圈一起待构建复测。

## 最新收口（2026-11-03，前序记录）

- 用户已批准文案回填；指定雷霆余威改“每回合第2、4、6……”且最终剧情从死亡改进入领域。下方旧“待审核/冻结生产文案”描述为历史边界，已被此次批准取代；旧TEXT_REVIEW原样保留。
- task-8完成：全部批准文案回填，178牌面数值/费用/25Power/26关键词/9敌方组/17贡献/四句剧情/菜单有新增精确稿件对照测试。知识恶魔与骑士独立词条；Power悬停统一前置“已被领域禁用”。85+5+1+14项定向测试通过，无玩法/数值变更。
- task-9完成：VolibearArchitectEnding仅替换真实RunManager.WinRun最后死亡流程，保持原OnEnded胜利快照/记录，熊保留HP、领域入场后原生结算；其他角色仍原死亡。实例限定IsGameOver终局标记确保正常退出与新局。原生IL/状态契约+oracle5项、24-adapter完整安装链2项通过。
- Lead把domain-suppression三场32断言、Architect两角色终局/存档/屏幕对照接入NativeVerificationSuite同一进程，严格oracle和顺序验证一起接入；suite14项工具测试通过。
- 最终候选源码已冻结，已启动统一 `local_delivery.py --verify-release --audio-driver PulseAudio --display window`；本轮输出目标 `.local/release/Volibear-0.1.0-StS2-0.107.1-20261103.zip`，完整日志 `.local/logs/final-release-20261103.log`。须读取本次完整回执后判断，不把启动视为通过。

## 本轮领域与美术修复（2026-11-02 晚，历史过程）

- 用户已授权全部开工，当前规则先落于 AGENTS.md；持久 goal `goal-cbb6de6a-8596-4782-8ec8-e0c82c3c54a6` 已 active。
- **最新文案边界：用户要求全部清理防御/工程文本及空泛金句，先交纯Markdown审核，不直接回填。** 已交付 [文案审核](<文案审核.md>)，建筑师剧情置首，89卡178面数值展开，全部机制/状态/遗物/角色/UI文案随后。用户在 [旧review](<TEXT_REVIEW.md>) 的21条修改优先保留；两稿均冻结，禁止覆盖、重新导出或擅自回填。审核稿来源分片在 `docs/review/`，内部卡牌映射在忽略目录 `.local/plain-review/`。具体要求已写入 [AGENTS.md](<../AGENTS.md>)。
- `tools/export_text_review.py` 已适配新增敌机制/禁用贡献的独立命名空间，修复重复ID；14项窄测试通过。首次两项源码manifest一致性检查撞上并发编辑，测试现从一次不可变源码快照执行，保留全部一致性断言后通过；未导出到审核稿。
- 领域新三场定向probe与工具入口已完成；Lead已接 `ModEntry` 与 `VolibearBootstrap`。`--scenario domain-suppression --domain-suppression-family all` 默认同进程新鲜沙虫/骑士/自debuff三场，工具独立校验32项断言与沙坑冻结/恢复坐标数值，其中3项观测骑士负面状态进入领域前/中/后真实NPower叉线、自身badge与HoverTips。入口接线及更新oracle的13项工具测试通过。当前未运行游戏。
- 原生引用窄测试：自身状态37项（含仅怪物可持有的Shriek/Plow不虚标为玩家禁用）、沙虫5项、Harmony绑定28项；禁用反馈87项、关键词5项、canonical2项；工具定向已通过。task-4、task-5均已完成：既有领域测试/两旧probe与oracle已适配，37项定向测试通过；原生IL验证28项通过（引擎未运行）。全怪物审计保留121类及47类减益逐项基线/当前结论，G04跳虫逃脱、G05事件木桩超时、G06敌方新Dex收益及G08未配置持续标记仍明确未实现。玩家审核稿与生产文本未修改。
- Lead完成实际Release整合编译（锁版引用），exit0、0错误、11处探针nullable警告；日志 `.local/logs/integration-domain-review-build.log`。新UI观测helper与入口均编译通过。构建仅更新本地bin，未部署/启动游戏。CRLF文件使默认git diff --check报行尾空白；按仓库现有CRLF行尾口径 `git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check` 通过，无实际尾随空格。
- 全怪物实现调查由独立审计进行，锁版原生源码位于忽略目录 `.local/domain-audit/native`，baseline在 `.local/domain-audit/baseline-src`。最终文档 `docs/DOMAIN_MONSTER_SUPPORT.md` 必须全部明确已实现/未实现，部分机制拆步骤，不留待确认。
- domain-fix 团队成员负责 Core/Domain*、针对测试及新原生领域验收probe；hover-feedback 负责词条/悬停/禁用反馈；Lead负责灵体形态与集成；美术子代理负责打击与状态图标资产。保留所有会话前既有未提交修改。
- Lead已新增实时脚原点1.22倍放大、72%透明蓝色shader及六条护体雷圈，进入/持续/退出/死亡/清理接线完成；原生表现probe已增加实际比例、材质、动画及退出恢复断言。4项窄测试含真实Godot shader解析通过；后续源码修改仍需整合编译/原生表现验证。
- **审核待合并纠错**：复核发现 `MechanicGlossary.EnemyEntries` 的 KNOWLEDGE 归给KnowledgeDemon，却写成骑士Dampen/Hex的升级/虚无机制，纯审核稿沿用了这项错配。知识恶魔实际为Disintegration/MindRot/Sloth/WasteAway四种选择惩罚；骑士升级/虚无应另列。生产与用户审核稿均未擅改，用户下一次反馈时先读取最新人工修改后定点修正，不能照错稿回填。
- Riot 官方R参考已读取实际第4秒帧，原视频仅在 `.local/domain-reference/`；来源见 `docs/DOMAIN_VISUAL_REFERENCE.md`。
- 23:16执行一次整合引用回归：1141项、1130通过，3失败+1类初始化错误、8个Windows限定跳过+1个Harmony路径缺失跳过，76.458s。完整回执 `.local/logs/domain-integration-regression.{json,log}`。逐项已定位修复：Tick新增灵体呈现调用的测试边界补齐（11定向通过）；正常安装清单更新23个真实适配器且验4个禁用UI补丁、Harmony改读锁版配置路径（3定向通过、无skip）；领域完整模板spec同步、安装说明检查改实际安装/卸载契约而非固定防御句（23定向通过）。未重跑整套回归，不能把旧failed JSON改为passed；最终收口时使用新回执。
- 资源PCK已实际重建并通过import/export/兼容性/资源/特效/open音频验证（`.local/logs/domain-art-resource-build-fixed.log`，175430888字节）。首次stage因新绘制图标没有editable_svg失败；已修stage_assets按raster_source只复制4档PNG、不复制旧SVG/母图，新增2项定向测试通过。旧独立PCK verifier也同步10绘制+6SVG，并根据已存在的4张多人手势将UI校验更新为18；独立挂载/解码回执 `.local/logs/painted-icon-packed-verification-fixed.json` passed=true，64图标PNG、26角色图集940帧、40VFX图集1070帧、54音频解码全部通过。未部署，未改审核稿或生产文案。
- 尚未启动本轮真实游戏或release gate。先完成实现与定向验证，最终一次收口放行；失败读取完整回执后定位修改，禁止无修改重跑或gate调试循环。

## 最新完整门禁（2026-11-02，release46，失败后修复中）

- 完整命令已运行；1115测试/80.817s通过（8个平台限定skip），PCK/特效/riot_en验证通过。
- 新鲜原生run `20261102T090149Z-d98b986f` 正常退出，无新增运行时错误；表现媒体、正常流程等回执完成，但整体门禁失败，冷恢复/多人/最终ZIP未执行。
- 牌面四例C07/U43失败为校验器误用物理抽牌堆顺序。锁版FromCombatPile IL确认Draw使用Rarity再Id稳定排序；已精确修复等稀有度候选预期，23测试通过。未重写旧报告或宣布整体验收通过。
- R28两生命周期少一次可选决策为真实生产缺陷：打出能力的来源卡离开牌堆，BeastSelection.Live错误阻断仍有效Power的回合钩子。正在修复Power独立生命周期并加回归；随后失败短批和新鲜统一门禁。
- 媒体完整性和最终ZIP安装/同包更新/卸载及A1–A9报告入口已接入；自动媒体不冒称主观听感/审美验收。

## 当前执行入口收口（2026-11-02，speed45）

- 用户要求全部程序化入口、全部跑完、正式ZIP交付；正常路径只运行命令读取报告，失败才修复，不手动操作游戏。
- 1FPS诊断：运行时max_fps=60/low_processor=false/VSync开启；只在新隔离profile关闭VSync即恢复60FPS，非时间缩放。
- headless/save_load_pair/save_load_catalog_pair/native_run_pair全部profile写入vsync=off/fps_limit=60；窗口外部脚本启动30秒后每10秒采样，连续3次低于10FPS退出失败，禁止低帧率盲跑。
- 正式headless CLI两例B01短批speed45通过，run_id=20261102T085018Z-15f44d49，9checks全true，退出0。建局3580–4854ms/出牌416–484ms，稳定60FPS；不是完整410/48通过。
- 最终生命周期/自动媒体验收正补齐统一入口；完整verify-release尚未运行成功。旧结果不能拼接成最终通过。
- goal resume仍被runtime拒绝，未宣称自动续作已恢复。

## 本地续作（2026-11-02，native17）

- 商店 Node2D/Spine 错误已增加仅匹配自有场景的适配，并显式接入正常 ModEntry；
  已核实原生 Ready 仅负责 Spine 初始动画，无额外状态初始化被跳过。素材和场景未改。
- 严格回归第18轮：1033 项、1025 通过、8 跳过，201.917 秒；包含新增商店作用域逻辑测试
  与全部22个正常安装器的实际 Harmony 安装链检查。替身测试不代表商店实跑通过。
- native17 已结束：商店原路径不再报错；正常产品流程 completed，实际3场战斗、26次付费出牌、
  3次奖励选牌、1次商店购买、1次休息。进程零退出且无运行时错误；整批仍失败，冷恢复未启动。
  失败仅为表现音频身份/播放采样及异步战斗结束节点清理检查，原报告保持失败不回写。
  日志 `.local/logs/native-merchant-17.log`；游戏批次 `20261102T020631Z-fab678ff`。
- 修复校验端按已验证 runtime profile 区分 Riot 11条覆盖和 open 回退；捕获端在实际 Emit/PlaySound
  返回后立即只读观察声音，避免软件渲染跨帧漏采短声音；节点清理改为有限等待真实 CombatEnded
  释放而非固定2秒，不主动调用 StopAll/Dispose。音频身份/接线8项回归通过。
- native18 被用户主动停止（SIGTERM），不是通过；日志 `.local/logs/native-audio-18.log`。
  用户随后明确授权 GPU、桌面窗口及快速模式，并选择“继续，先检查 GPU 并测速”。
  旧沙箱隐藏 /dev/dri，桌面 :0 也只能 llvmpipe；切换 danger-full-access 后 glxinfo 实测
  AMD Radeon Graphics (rembrandt)，Accelerated: yes。旧批次日志已有 ACCEPTANCE_SPEED Fast，
  所以主要瓶颈不是未开启快速模式。显式 --display window 已适配，102项定向测试通过（4平台跳过）。
- GPU19 (`20261102T054035Z-52097fec`) 游戏日志确认 Vulkan/AMD RADV REMBRANDT + Fast，
  两个R09牌面/U02生命周期完成，但表现清理30秒超时。确切原因是 probe 在队列外调用 Kill，
  原生 Kill 不检查胜利，故从未发出 CombatEnded；不是原版退出噪声，也不是生产节点泄漏。
  probe 已补原生公开 CheckWinCondition 安全点，保留真实事件清理断言，生产 bridge 不变。
- GPU20 被无Mod启动输入异常拦住；GPU21用户取消。严格regression22完成1046项/1038通过/8 Windows跳过。
- 用户已批准 A1–A9 完整正式交付方案：最小表现→冷恢复/多人排雷→冻结候选完整门禁→感官/最终包安装→交付。
  Goal已更新revision5，但resume工具拒绝（paused必须用户恢复）；当前轮照授权继续，不能谎称自动Goal已恢复。
- GPU22 Vulkan无Mod对照300s超时；window现切硬件AMD OpenGL Compatibility（非llvmpipe）。
  GPU23对照通过，`20261102T061044Z-72fe04ab`表现动作捕获正常退出、无新增runtime错误，
  真CombatEnded后visuals/voices=0、oldRootAlive=false、roomAttached=false。
  校验端曾错误比较authoring WAV字段（stage_assets本来删除），现按准确runtime投影修正；
  同次原生捕获经原有stock过滤重新校验errors=[]，见该目录revalidation.json，原失败report保留。
- 冷恢复24尚未进入保存阶段：无Mod对照`20261102T061727Z-4b90429d`300s超时，
  main menu约5s/Common preload194s，出现static string退出错误。正在检查frame-based退出与异步预载竞态，
  不盲目延时/重跑；未改生产代码。A8委托补最小最终ZIP生命周期验证工具。
- 已验证替代对照：`20261102T063032Z-58d807fd`通过外部SceneTree脚本加载原始main_scene、
  --nomods，等Common实际Complete及NAssetLoader停止processing后调用原生NGame.Quit。
  Common仍耗194389ms，但正常退出code0、无static-string错误，只有原版既有资源退出噪声。
  已纳入tools/stock_ready.gd/headless；不是修改原版或忽略新错误。
- 冷恢复29已通过：artifacts/save-load/20261102T063554Z-46cfa4ef/report.json，S2 prepare/resume
  两个原生进程及真实落盘检查均passed；新无Mod正常退出对照也通过。
- 多人31失败：双方StartNewMultiplayerRun探针90s超时，尚未完成Common/角色预载；主机另有
  Dev console used before being created运行时异常，不忽略。仅原生新局/存档LoadRun加载Task
  等待改360s，网络握手保持90s，重建部署33通过。
- 多人34已真正进入战斗，双方通过native-checkpoint、simultaneous-engage、owner-scoped-domain-lightning、
  native-beast-identities；随后both native end-turn actions超时。已核实探针直接PlayerCmd.EndTurn只改本地ready，
  未提交原生网络动作；改成与NEndTurnButton相同的EndPlayerTurnAction同步队列，原断言不变，多人36进行中。
  run_id=20261102T065501Z-e62760f7-multiplayer。严格regression35：1073测试通过，8平台skip。
  A8state/sentinel/archive别名冲突已修；安装/更新有界异常回滚已实现，27生命周期测试及父级63相关测试通过。
  更新先备份精确旧字节/状态，失败回滚仅改自己新hash，冲突保留RECOVERY备份；不是断电crash-atomic。
- 多人36正常回合推进与重置已通过（六阶段），随后主机无法观察断连，出现Peer not connected发送错误；
  客户端已本地断开。run_id=20261102T070732Z-7477a35e-multiplayer；已核实立即Disconnect(Quit,true)
  不发送原生应用层Disconnection包，host忽略底层断线事件导致成员残留。改正常退出false，保持所有断言，
  多人37全项通过，run_id=20261102T072831Z-1c7c76fb-multiplayer，运行时/全部同步/恢复门禁true、errors=[]。
  这是正常退出/检查点重入覆盖，不冒称突然断网或崩溃恢复。
- 已冻结候选启动统一final-release38：tools/local_delivery.py --verify-release --audio-driver PulseAudio
  --display window --audio-profile riot_en；日志.local/logs/final-release-38.log。所有生产/工具修改暂停，
  待统一完整通过才作最终ZIP安装更新卸载与视听收尾，不拿分段历史结果充最终验收。
  release38在回归中因旧文档测试强制NOT_RUN失败（实际联机已跑过）；改验证未覆盖Steam/公网/人工边界
  而非强制过时状态，启动release39（.local/logs/final-release-39.log）。38尚未启动游戏。
  release39回归1081/8平台skip通过、资源全通过；native run 20261102T074443Z-d88e8c2f启动前
  NHotkeyManager._UnhandledInput→NDevConsole未初始化错误（136/147行），运行时门禁必失败。
  已停止bash-dc1d6c8571a14742(SIGTERM)，未继续浪费全套时间。正在检查窗口输入/焦点隔离原生参数，
  不屏蔽错误、不修原游戏、不盲重跑。只读诊断确认无--no-focus/--minimized CLI参数，
  no_focus项目设置仍允许鼠标；当前AMD硬件/Fast均已确认，五用例完成但缺逐段计时，不能猜慢因。
  子代理e729cc77-be57-4b2b-b51f-58cb8829bb76检查启动前override和外部SceneTree no-focus/mouse-pass-through
  的窄输入防护，仅工具和对应测试可改，不启动游戏；需先短批验证再重启全套。没有活跃游戏进程。
  父级已加NativeAcceptanceRunHost单调计时(start-run/start-room-quiet/exit-map/exit-menu)与FPS、
  CardFaceAcceptanceProbe actionMs；build-timing40编译0错误，已部署隔离.local/game但未跑。
  99项针对回归通过(72原生证据/发布/多人+27安装生命周期)。新实施代理e5a29ffb-8929-44a8-a21d-a75c82d414c6
  已获准测试期间独占创建隔离游戏override.cfg（拒绝既有文件，finally仅删自身原字节），加启动前no_focus与
  外部SceneTree鼠标穿透，覆盖单机/冷恢复/双端共享生命周期；不修改日常游戏，不打进ZIP。
  下一短批B01-base-plain,B01-base-strength
  用headless.py --scenario card-face-acceptance --card-face-batch ... --display window，先看计时与输入保护。
- window-timing41两例已PASS，run=20261102T081853Z-f55f7831，进程0退出且全部checks=true；
  WINDOW_GUARD_READY三项true，无启动热键错误/FocusIn；override.cfg退出后已清理。
  真实AMD但FPS始终1：每例start-run~32s、start-room~15s、action~8s、exit~9s；角色预加载200s。
  不重跑410，先查1FPS节流。只读代理2ccd574f-b572-4b19-9ce2-f323a94aefd7核对锁版帧率/后台限制。
  无运行游戏；窗口/目录及catalog回归114项通过(4skip)，另13项native_suite通过。
  catalog额外直接spawn已套guard；其原CRLF归一LF以通过diff-check。
  regression32共1069项仅1个stock成功mock缺新ready标记（8平台skip），已补fixture，63定向通过。
  A8审查发现state路径与save sentinel冲突能先删除再失败，已委托修复并加无修改负向验证。
  A8新package_lifecycle工具与文件系统/真实ZIP测试已完成，33项通过，尚待最终真实包原生启动验收。
  BaseLib实际初始化/成功patch/角色scene注册转换gate已补入完整suite，定向83项通过（4平台跳过）。
  全量门禁和双客户端仍未完成，当前仍没有最终 ZIP。

## 目标与当前状态

目标是交付可从源码构建、完整安装并沿游戏正常入口游玩的沃利贝尔 Mod。范围包含
89 张卡、178 个基础/升级牌面、83 张奖励牌、两件遗物、既定机制、角色与战斗表现、
双音频、正常单人/多人流程、原生存读档和安装卸载。

生产修复、验收代码、独立预期与本地执行入口均在本 PR 实施，不能用计划或替身测试代替原生验证。
2026-11-02 Linux 本地接续已确认用户安装为 StS2 **0.107.1 / 59260271**，并配置匹配的
Godot Mono/SDK。实际运行使用忽略目录 `.local/game` 中的完整隔离副本和逐次新建 profile，
未修改用户日常游戏安装或存档。

当前实际结果（进行中，非发布验收）：
- 修复三个原生验收代码编译错误后，完整 DLL 游戏引用编译成功。
- open 与 riot_en PCK 导入、导出、格式兼容、资源/效果/音频加载验证成功。
  Riot 的 11 条私有覆盖已下载、固定来源哈希核验及完整解码；其余 43 个 cue 保留 open 回退。
  尚未宣称游戏内播放或人工听感通过。
- 发布链第八轮在新编译 DLL 后严格回归 1027 项：1019 通过、零失败、8 项异平台检查跳过。
  必需的 Hopper 检查已在 Linux 执行，完整补丁安装链通过。报告为 `artifacts/validation/regression.json`，
  日志为 `.local/logs/full-release-08.log`。此后游戏运行发现的问题另行修复，最终仍须完整重跑。
- 首个无 Mod 游戏对照在公共资源预加载期间达到 60 秒预算。扩至 300 秒后正常退出，
  并发现退出分类仅覆盖 RD、不覆盖 GLES3 的既有引擎泄漏。已补充精确 GLES3/GL 纹理类别
  与反例检查；新建隔离 profile 的第三轮实际无 Mod 对照通过（exit 0、未超时、无运行时错误）。
  不忽略未知错误，Mod 退出类别仍必须是本次 stock 类别的子集。相关 64 项测试通过，
  其中 4 项 Windows 专属检查跳过。原生五阶段、角色契约、S2 跨进程恢复、双端网络与完整包仍未通过。
- 测试装配修复后，被动/召唤/历史/流程/Hopper 六个定向套件 32 项全部通过，Hopper 已在 Linux
  实际执行。标量消费位置改为锁版精确方法/调用顺序清单；10 个方法、14 位置、3 个破坏反例通过。
  完整安装链随后发现 TestSubject.RespawnMove 的接收者载入位置假设不符，已修为计数更新前的空栈边界，
  定向正例及 4 个破坏反例通过。随后又发现 TestSubject.Revive 的 SetMaxHp 使用泛型 TaskAwaiter<decimal>
  并丢弃结果，旧检查只统计非泛型 await；已补充 Pop 后空栈检查并固定实际 7/1 个非泛型 await。
  debuff commit gate 已精确识别音频 Close 观察器，保留原生 int 局部变量锚点，17 项检查与 4 个拒绝反例通过。
  随后真实游戏加载复现 TargetCosts 先替换 CanPlay 导致标量适配找不到原生调用；已显式让标量适配先于
  TargetCosts 执行。完整 21 个适配器安装链与早期音频观察测试通过；正在重新运行完整发布链
  （`.local/logs/full-release-08.log`），尚未把该次旧 DLL 加载失败算成游戏通过。
  补修独立 revival 测试引用后，12 个原生 IL 补丁及 3 个缺调用位置拒绝检查通过（并未执行游戏方法）。
- 原生第八轮已加载 Mod 并进入战斗，发现角色验收直接 new TheArchitect 触发重复 canonical 模型，
  已改为 ModelDb.Event；第九轮暴露 DustyTome 古代人赠牌预览调用 canonical 卡的 Owner，
  已让 MechanicHoverTips 保留静态词条、仅对 mutable 卡读取战斗状态。第十轮角色集成已产出完整回执，
  第十轮完成 139/410 个付费出牌分支后触及原 3600 秒总时限，终止时有 name_changed 引擎错误，仍判失败，
  未放入退出白名单。完整发布预算改为已有支持上限 14400 秒/864000 帧，保留全部断言与用例。
  最新严格回归 `.local/logs/regression-11.log` 为 1029 项/1021 通过/8 跳过，无必需检查缺失。
  完整发布第十二轮 `.local/logs/full-release-12.log` 新编译后严格回归同为 1029 项零失败；
  原生运行完成 302/410 分支后在 B04 的 LeafSlimeS 首动 TACKLE_MOVE 前置检查失败，未打包。
  失败回执位于 `artifacts/headless/20261101T203025Z-f35b984c/`；正在核对锁版史莱姆行动与测试夹具。
  尚未完成全部原生验收。只读独立复核未发现新增生产缺陷；补充完整安装链中 CanPlayResolved 与
  ConsumedBoolean 同时保留、先后关系及显式 Harmony before 的断言，定向测试通过
  （`.local/logs/combined-scalars-12.log`）。
- 原生定向第十三轮完成剩余 108 分支中的 106 个：显式选择原生 TACKLE_MOVE 修复随机首动夹具；
  R09 同样固定两个小史莱姆攻击和中史莱姆状态行动。第十四轮 R09 30 秒超时，第三行动随后仍执行；
  第十五轮给 R09 有界 180 秒预算后两个牌面完成，48 个生命周期场景也全部完成。
  表现阶段发现 R29 转换前残留手牌导致多张 token，已用原生牌堆操作隔离指定材料。
  第十六轮 `artifacts/headless/20261102T012957Z-524a99cf/` 已走到正常商店入口，暴露真实错误：
  NMerchantCharacter 按 SpineSprite 读取普通 Node2D；另有 transient reward JSON 形状校验不匹配。
  两项正在分别修复；本轮 exit 0 不等于通过，冷启动恢复未运行，没有最终 ZIP。
  上述分段完成回执不替代修复后的一次完整发布门禁。实测 410 牌面约 3 小时、48 生命周期约 1.5 小时，
  完整单进程上限已改为 28800 秒/1728000 帧，默认短测试不变，不删用例或断言。
  transient reward 已核实为 BaseLib 3.4.7 的必有空 ModifierSave 扩展；校验要求精确字段和空列表，
  15 项反例/正例通过，旧角色回执重放无错误；商店错误仍须修复后实际重走。
- 续作先查看本次 `.local/logs/` 与 `artifacts/validation/regression.json` 的实际失败，修复后
  重新运行完整 `--verify-release` 链；编译和资源检查不等于实际游玩通过。

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
python3 -B tools/local_delivery.py --verify-release --audio-driver PulseAudio --display xvfb --audio-profile riot_en
```

本次交付要求私有 Riot 音频，必须保留 `--audio-profile riot_en`；省略会构建默认 open 包。
独立调用原生套件/严格回归时用 `.local/build-python/bin/python3`（含 Pillow/NumPy），
避免系统 Python 缺 Pillow 导致游戏运行结束后表现证据解析失败。统一交付入口会选择该环境。

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

## 2026-11-04 并行入口定向测试意外与清理

- 旧summary测试只mock `_deliver`，却调用新增监督后的CLI `main(--verify-release)`，导致跨进程绕过mock，意外执行发布前半段。发现输出后立即停止该受控job；随后全机Python/SDK/Godot/游戏进程查询为零，无相关残留。未取得停止前历史PID，不能补造进程记录。
- 单次证据保留在 `.local/release-acceptance/run-ic10ngy8`：preflight 0.140秒、工具依赖0.922秒、DLL fresh build 3.360秒；回归与资源并行启动。资源日志明确为executed冷构建，内部43.844秒、阶段44.109秒、exit0，产出175451000字节PCK；不是缓存复用。回归被中断，summary为not_completed、A1–A9均not_run，未进入部署、实机、多人、打包或安装生命周期；此轮不是完整gate通过。
- 已修两个危险summary测试：mock私有worker permit留在本进程，并将supervisor设为直接AssertionError，tearDown要求从未调用，防止再逃逸为真实发布。已检索tests全部local_delivery引用与main调用：另两处release_budget测试分别mock监督器或worker permit，POSIX路由只构造命令，未发现其它直接main导入或未隔离CLI调用。并行阶段及时记录子进程PID/command与独立日志；隔离修复后，summary/delivery/deadline/cache定向57项在5.601秒内全部通过，未启动真实构建或游戏。
- 不能把意外冷构建作为最终发布的隐含预热。本次真正600秒完整入口必须显式加 `--force-cold-assets`；该选项默认false，普通可信缓存仍保留。并行子命令转为 `build_assets.py --force-cold`，串行资源调用传 `reuse=False`，确保最终轮重新计入完整资源构建/验证。未经本轮完整报告放行，不生成或宣称新成品通过。

## 2026-11-04 原生阶段并行编排定向收口

- 仅受600秒父监督的Windows/background完整发布，在已验证DLL/PCK部署完成后并行完整NativeSuite与完整多人CLI；两支沿用同一已验证native Python环境，保留全部案例、各自stock/profile/报告及共7个真实游戏进程。两支均成功才打包；其它平台/窗口/无监督调用保持串行，S2内部顺序未改变。
- 固定2支helper只作name/command/env/验收组薄参数化，主worker独写阶段summary；Native的A2/A3/A4/A5/A7和MP的A6分别记录状态，失败取消另一入口且由外层Job最终清理全树，不把取消写成完成。
- delivery/deadline/summary定向48项在4.782秒内通过；真实短Python握手验证重叠、两支native环境、任一失败取消对方、期限不重置、平台限制与串行fallback、失败不打包。未启动game、PCK或完整回归，未据此宣称完整600秒gate通过。

## 2026-11-04 S2独立链并行与取消

- 新增显式`--parallel-restart`，仅Windows/background且verify_restart允许；受监督完整发布自动传入，直接native CLI默认仍串行。原stock成功后，同轮内存dict供主suite及独立profile的S2链共用，未新增缓存stock入口或额外stock进程。prepare→resume的完整原gate/磁盘/原始回执校验保留。
- 两线程任一异常或正常失败报告都触发取消；owned进程按单调截止短poll响应，所属线程finally唯一终止/reap，原launcher finally唯一Close。取消是独立异常，不报timeout或成功；主线程收齐两任务，只有两份完整报告均成功才放行。已进入的纯Python证据验证只能在段前后响应，仍由595秒外层硬截止兜底。
- 定向151项在5.355秒通过，无skip。真实短Python子孙树覆盖主suite/prepare/resume及spawn竞态取消，确认后代全灭、同一所属线程唯一terminate/close；另覆盖prepare失败不resume、恢复前取消、同轮stock仅一次、两任务重叠/最终AND、命令flag透传、旧串行路由及预算。未运行任何game、PCK或完整回归。与整支MP并行时共7个原游戏进程不变，峰值4个；性能仍待主agent有界原生并行短测。

## 2026-11-04 完整356图册独立并行实现收口

- 新批准的 `--parallel-catalog` 只允许Windows/background、presentation=all且verify_restart；受监督完整发布显式传入，原默认/未监督自动编排不变。成功stock后主suite(actions)、独立完整catalog(cards)、S2 prepare→resume三支共享同轮内存stock和cancel Event，失败取消并join全部线程。主7阶段及actions→正常流程同进程集成完整保留。
- 独立catalog不能只沿用较弱的standalone receipt入口：本实现保留原NativeSuite的presentation_media_checks完整链（原receipt校验+PNG CRC/尺寸/非空解码），实际images必须356，mode/token/独立owned PID严格一致。组合报告明确main actions与separate cards的PID、token、报告路径、图片目录及checks；main/S2成功但catalog缺失、少图或失败仍为failed/CLI exit1，外层不打包。
- 此显式方案总真实进程由7增至8、峰值由4增至5，只新增一个完整图册实例、无额外stock；各单人批次仍一个实例，不拆案例。未启用时原进程数/串行默认维持。固定600秒/冷资源计费/全树回收不变。
- 定向90项在5.683秒通过，无skip，包括新catalog六项和原native/S2取消/runner/delivery/summary/deadline。真实短Python三个owned worker覆盖握手重叠、三支各自正常失败取消另两支并全部回收；还覆盖stock一次/同对象、410与48默认数量、严格356/mode/身份/路径、缺catalog仍AND失败、CLI非零与禁止打包、非支持参数/默认路径。一次新测试fixture遗漏原stock必需字段被正确拒绝，补齐fixture后全通过，生产stock断言未改。
- 此轮没有启动game、PCK或完整回归；下一步由主agent进行已指定300秒根Job有界预检，以完整356图册及136face/8life加权样本实测新峰值争用，再判断最终600秒是否可行。新增回归分区数以主agent最新42项allowlist为准，不将旧分区耗时当作新配置实测。
