# 实现缺失与完成清单

本清单按用户要求提交到 Git，逐项完成后打勾，不再以口头“收尾”代替进度。

**当前结论：原先“全部写完”的结论不成立。以下是实际发现的缺失及补齐状态。**
`[x]` 表示生产代码及正常接线已完成，不表示测试通过；`[ ]` 表示尚待完成或确认的具体事项。阶段一收口后立即进入阶段二，不继续无界扩大审计。

## 阶段一：补齐实际实现

### 已核实原有产品范围

- [x] P01：89张卡／178牌面及两件遗物有实际效果、升级分支与正常注册，不是测试入口占位。
- [x] P02：迎战、雷伤、兽化及费用／选择路径已有实际生产实现；正常角色、选角、战斗、休息、商店和原生存档路径已接入。
- [x] P03：正常Inspect大图已接入；安装包包含模组DLL/PCK/清单、固定BaseLib及安装说明。最终补丁需重新打包，见阶段二。

### 本次实际发现并补齐的遗漏

- [x] M01：领域对敌源Weak、Frail、Vulnerable、Shrink、Constrict、ChainsOfBinding的实际贡献抑制；保留自源代价、时长及清理。
- [x] M02：SlimedBerserker空applier的精确来源识别，不改原生applier。
- [x] M03：敌源负力量／敏捷、Tender减益与返还配对；原生总量归零移除后仍保留来源账目。
- [x] M04：PossessStrength／Speed死亡返还精确冲销对应债务，避免领域补偿白赚。
- [x] M05：八种敌源状态生成及有害执行；Wither敌方强化分离；保留Slimed抽牌、正常消耗、FranticEscape逃脱。
- [x] M06：Galvanic、VitalSpark／Tainted及PaperCuts附加惩罚；共享PowerCmd真实提交与取消接线。
- [x] M07：Vigor、背击倍率、Burrowed留甲；Territorial、HighVoltage、Enrage、Ravenous、CrabRage、Rampart被动正力量／格挡。
- [x] M08：Gremlin偷金币、Sandpit到期强杀、FatGremlin逃跑；保留金币返还与FranticEscape互动。
- [x] M09：Surprise死亡召唤、终局阻止及此前赃款返还；保留已提交子实体。
- [x] M10：LivingFog、TwoTailedRat、Fogmog、TheObscura四条实际召唤路径；保留混合攻击及正常计数／状态推进。
- [x] M11：Stock／Adaptable／TestSubject复活阶段及PainfulStabs保尸取消；已接正常Install与领域开启通知。
- [x] M12：ToughEgg孵化生命重置／清负面贡献，以及复活相关原生投票的组合接线。四文件已冻结，已核对HatchMove／Hatch、InstallDispatch及领域开启通知；运行验证归T02。
- [x] M13：低血形态与语音、选角／胜利语音、实际治疗／返能及已提交能力特效。
- [x] M14：净化卡真实历史锚点、实际目标减费特效及有限核对发现的V01–V21/A01–A03均已实现并接正常入口；运行正确性归阶段二。
  - [x] M14a：净化前捕获真实可见卡坐标，提交后播放；锚点缓存按owner/room隔离并在到期、死亡、战斗结束清理。
  - [x] M14b：真实local优惠写入与原生成功支付的目标减费receipt已接入，保留原支付Task；使用实际费用标签或其已捕获坐标，不冒充目标。
  - [x] M14c：已完成40 VFX／54 cue有限映射核对：确认以下21条事件绑定与3类动画处理需补。lightning_chain为可选连线，feral_aura音频默认关闭，footstep无批准实际事件，不计缺失；U15旧净化绑定不用于创造新玩法。
  - [x] V01：R31实际移除目标格挡→guard_break。
  - [x] V02：C10迎战后实际反击→counter_release。
  - [x] V03：C14实际反雷结算→counter_release。
  - [x] V04：已知敌方有利效果实际被领域压制→domain_suppress，不能在预览查询时伪报。
  - [x] V05：兽化目标确认→feral_transfer。
  - [x] V06：确认兽化批次→owner feral_aura一次性视觉，不开启默认关闭音频循环。
  - [x] V07：实际新增咬痕→mark_bite及实体生命周期。
  - [x] V08：实际施加易伤→wound。
  - [x] V09：实际施加虚弱→weakness。
  - [x] V10：实际卡牌蓄力→charge。
  - [x] V11：U24实际吸血恢复→lifesteal回流。
  - [x] V12：实际迎战开始→roar_wave。
  - [x] V13：U23咆哮展示请求→roar_wave。
  - [x] V14：实际能力实例部署→cast_charge。
  - [x] V15：C19实际给牌保留→armor_retain。
  - [x] V16：U10实际强化卡牌→strength；R06当前Unify不是逐卡强化，不造事件。
  - [x] V17：U12及Unify实际雷伤修正→lightning_growth；U29现StormCharge已有路径，不重复。
  - [x] V18：U33每完整雷伤批实际获盾→thunder_armor，不以部署时播放替代。
  - [x] V19：R15实际敏捷增加→armor_retain。
  - [x] V20：U17真实预览选择开启→card_retrieve，不冒充入手。
  - [x] V21：U17实际选牌移至弃牌堆→card_discard。
  - [x] A01：消费primary_motion.trigger，反击与兽化不统一提前在CardStarted播放。
  - [x] A02：接入批准domain_fallback_clip。
  - [x] A03：接入批准分段动作、临时姿态保持与领域入场优先级，不用动画计时驱动玩法。
- [x] M15：已核对M12/M14最终生产接线与实际diff；所有作者冻结后Release编译通过，资源包已重建且批准资产字节校验通过。阶段一实现清单完成；不是运行正确性验收，阶段二T01–T05仍全部待执行。

## 阶段二：实现确认后验证正确性

- [ ] T01：运行现有完整自动测试，修复真实失败；包括旧安装包状态断言与新增生产接口引起的必要测试维护，不删测试掩盖失败。
- [ ] T02：验证新增领域补丁的实际Harmony安装／组合，以及来源、混合贡献、取消、返还和必要清理。
- [ ] T03：复用现有真实队列hook批次验证卡牌／机制／敌人交互，同一私有后台实例连续运行，不使用OS键鼠或抢焦点。
- [ ] T04：复用现有入口验证表现、正常流程及隔离存读档；修复失败并回归。
- [ ] T05：用最终构建重生成安装包，核对安装内容，提交推送最终修复并给出真实结果。

## 更新规则

1. 完成一项即更新对应勾选；尚未完成的项不能因编译成功或文件存在而勾选。
2. 实现遗漏与正确性失败分开记录；不以未测试冒充缺实现，也不以已实现冒充测试通过。
3. 若发现新的明确遗漏，追加具体功能和位置，不使用“继续研究／全覆盖”之类无边界条目。
4. 不提交游戏程序集、反编译资料、本机配置、存档、临时测试产物或秘密。
