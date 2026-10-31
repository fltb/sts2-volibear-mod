# 89张卡牌的特效绑定

这是逐卡的表现层契约。事件名是本包定义的可移植语义名，**不是声称已存在的 STS2 API**。游戏逻辑发出真实结果，播放器只播放对应素材。基础、升级、条件分支和能力后续触发均保留原卡表。

| ID | 卡牌 | 特效文件ID | 重点时序/条件 |
|---|---|---|---|
| B01 | 打击 | claw_slash | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| B02 | 防御 | guard_gain | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| B03 | 霆爪 | claw_slash, lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| B04 | 挺身迎战 | guard_gain, claw_slash, roar_wave | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C01 | 逼近 | claw_slash | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C02 | 双爪 | claw_slash | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C03 | 轰雷重击 | heavy_impact, lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C04 | 擂首一击 | heavy_impact, weakness, roar_wave | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C05 | 雷霆爪击 | domain_enter, claw_slash | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C06 | 进逼 | claw_slash, guard_gain, card_draw | 攻击意图分支只展示实际获得的格挡；另一分支只展示实际抽牌。 |
| C07 | 追嗅 | claw_slash, card_retrieve | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C08 | 撕开伤口 | claw_slash, wound | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C09 | 雷霆横扫 | claw_slash, lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C10 | 以牙还牙 | guard_gain, roar_wave, absorb, counter_release | 先格挡，再实际迎战与吸收，最后根据已结算伤害显示反击；VFX不把吸收再加到伤害。 |
| C11 | 正面迎敌 | guard_gain, roar_wave | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C12 | 厚重皮毛 | guard_gain | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C13 | 呼吸 | card_draw, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C14 | 雷霆护身 | guard_gain, domain_enter, counter_release, card_exhaust | 基础牌消耗、升级不消耗，读取实际card_exhausted事件；反雷是后续敌人攻击段结果。 |
| C15 | 重整爪牙 | card_retrieve, cost_reduce | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C17 | 蓄力 | strength | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C18 | 显圣 | domain_enter, weakness | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C19 | 追猎准备 | armor_retain, charge | 留住的是所选攻击牌，不显示角色留甲状态。 |
| C20 | 乘势追击 | claw_slash, card_draw | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C21 | 稳住阵脚 | guard_gain, domain_enter, card_draw | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C22 | 雷震 | claw_slash, lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C24 | 霹雳 | lightning_strike, card_draw | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C25 | 雷引 | cost_reduce, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| C26 | 接地 | energy_gain | 共享返能限次由规则确认；不能每次看到雷光就返能。 |
| U02 | 狂雷渐起 | cast_charge, lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U03 | 屹立 | guard_gain, armor_retain | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U04 | 战痕 | cast_charge, guard_gain, strength | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U05 | 挟山 | heavy_impact | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U06 | 三重撕裂 | claw_slash | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U07 | 崩山 | heavy_impact, cost_reduce | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U08 | 暴怒撕咬 | guard_gain, bite_hit, mark_bite | 强化读取出牌前咬痕；命中即登记，完全格挡/致死命中也可登记。 |
| U10 | 磨砺爪牙 | card_draw, strength | 等待下一张攻击的强化可跨回合；不在回合结束取消其UI。 |
| U11 | 暴风再临 | card_replay | 重演完整牌效；不追加一次出牌或成长。 |
| U12 | 原始力量 | lightning_growth, card_draw, card_exhaust | 本轮雷伤增幅不等于永久雷电成长，状态使用不同逻辑ID。 |
| U13 | 力量归身 | strength | 临时力量转正不显示重复的两次力量获得。 |
| U14 | 迎战准备 | guard_gain, cost_reduce, card_exhaust | 升级不消耗；按实际消耗事件播放。 |
| U15 | 暴风换气 | card_purify, card_draw | 所选另一张手牌先净化消耗作为费用，完成费用后才播放本牌抽牌。 |
| U17 | 古老直觉 | card_retrieve, card_discard, card_draw | 查看、弃置、排序与抽牌均等玩家实际选择；不预播未选弃牌。 |
| U19 | 风暴不散 | cast_charge, card_draw, domain_enter | 入场和每次实际迎战后各自读取抽牌、领域变化；领域延长不重复完整展开动画。 |
| U20 | 势不可挡 | claw_slash, energy_gain, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U21 | 雷霆余威 | cast_charge, energy_gain | 按部署实例，每回合实际阈值达成触发一次；入场已达标也由规则发事件。 |
| U23 | 迎风咆哮 | roar_wave, weakness, guard_gain | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U24 | 饮血而战 | claw_slash, lightning_strike, lifesteal, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U25 | 猎物未倒 | cast_charge, card_draw, cost_reduce | 此前目标计数与每回合首次条件由规则确认，抽到的攻击才显示减费。 |
| U26 | 愈战愈烈 | cast_charge, strength | 第2张攻击的力量在其伤害前取得；只消费权威事件序列。 |
| U27 | 淬躯爪击 | claw_slash, guard_gain | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U28 | 雷霆反扑 | guard_gain, roar_wave, absorb, lightning_strike | 吸收增量归迎战发起者；只显示完成后实际全体雷伤。 |
| U29 | 雷霆渐盛 | lightning_growth | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U31 | 万钧连踏 | heavy_impact, lightning_strike | X=0不播放伤害命中特效；实际支付X决定重复段，不从图集帧计数。 |
| U32 | 迎雷 | cast_charge, domain_enter, cost_reduce | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U34 | 雷甲 | cast_charge, guard_gain, thunder_armor | 群体雷伤是一次完整逻辑雷伤，增甲不按受击敌人数重复。 |
| U35 | 霹天雳地 | guard_gain, lightning_strike, roar_wave | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U36 | 奔雷 | energy_gain, card_draw, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U37 | 风暴汇聚 | lightning_strike, domain_enter | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U38 | 雷势奔袭 | claw_slash, cost_reduce | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U39 | 雷暴先兆 | guard_gain, domain_enter, card_retrieve | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| U40 | 雷路贯通 | lightning_strike, energy_gain | 此前至少2次雷伤读取出牌开始快照；返能共享限次，非当前动画闪电条数。 |
| U41 | 破皮见骨 | claw_slash, feral_claw, feral_body, feral_transfer, cost_reduce | 仅合法攻击材料成功转换后显示爪形，临时减费随同原实体保留。 |
| U42 | 蛮荒护体 | guard_gain, feral_claw, feral_body, feral_transfer, cost_reduce | 非攻击材料转换成躯形（T02），不能误变爪形。 |
| U43 | 循着本能 | card_retrieve, feral_claw, feral_body, feral_transfer, cost_reduce, card_exhaust | 检索占用手牌位并完成取牌，再转换同一实体，之后显示减费。 |
| R01 | 风暴形态 | cast_charge, guard_gain, domain_enter | 永久领域无倒计时归零效果；死亡或战斗结束仍清理。 |
| R02 | 不动神躯 | cast_charge, guard_gain, armor_iron | 坚甲维持格挡，但溢出伤害仍可扣血；不以盾光屏蔽受伤/死亡动作。 |
| R05 | 全身之力 | guard_gain | 直接格挡乘3的真实正增量驱动视觉；0变0不播增甲。 |
| R06 | 天人合一 | strength, guard_gain, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R07 | 天崩地裂 | lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R08 | 雷霆万钧 | claw_slash, lightning_strike | 4次随机目标由规则逐段给出；VFX禁止自己抽签或复用首个目标。 |
| R09 | 众敌皆来 | guard_gain, roar_wave, absorb, lightning_strike | 所有敌人各按剩余行动机会迎战；原攻击目标不改，吸收归发起者。 |
| R10 | 这场战斗尚未结束 | card_retrieve, cost_reduce | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R12 | 解放本能 | card_draw | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R13 | 重返蛮荒 | heal, domain_enter, strength, card_exhaust | 领域内治疗、领域外展开是互斥分支；力量正常展示。 |
| R14 | 不休之猎 | cast_charge, cost_reduce, card_draw | 升级入场才抽牌；同一目标连锁减费只更新实际受影响的单体攻击牌。 |
| R16 | 愈战神躯 | cast_charge, strength, armor_retain, guard_gain | 升级入场格挡；之后力量/敏捷按完整牌效结果，非命中段重复。 |
| R17 | 天雷决 | lightning_strike | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R18 | 雷池 | cast_charge, lightning_strike | 入场、回合结束和本回合首次迎战后分别读取权威雷伤事件。 |
| R21 | 雷霆化身 | guard_gain, card_draw, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R23 | 裂天 | lightning_strike | 三次雷伤结算三次表现，不能把同一条雷的分叉数当作结算段。 |
| R24 | 雷涌 | energy_gain, card_draw, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R25 | 风暴重临 | domain_enter, card_retrieve, card_exhaust | 只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。 |
| R27 | 旧日重临 | feral_claw, feral_body, feral_transfer, cost_reduce, guard_gain, card_exhaust | 允许选0张，0张不播放转换成功；逐实体读取爪形减费或躯形格挡。 |
| R28 | 熊灵侵染 | cast_charge, feral_transfer, feral_claw, feral_body, card_draw | 入场/起手后的合法选择确认时先传递至外部卡牌，再以成功转换事件收尾；不把角色头部变形。 |
| R29 | 不再为人 | card_retrieve, feral_claw, feral_body, feral_transfer, cost_reduce, card_exhaust | 升级先完成回收，再固定手牌集合并逐张兽化；兽化后抽到的新牌不纳入本次集合。 |
| R30 | 我即荒野 | cast_charge, feral_claw, feral_body, feral_transfer, cost_reduce, guard_gain, energy_gain | 首次爪形/躯形奖励分别独立，按权威格挡与能量事件表现。 |
| R31 | 天声震落 | guard_gain, domain_enter, guard_break, heavy_impact, lightning_strike, card_exhaust | 目标破甲先于物理伤害；其他敌人的雷伤集合排除实际主目标。 |
| T01 | 裂骨之爪 | claw_slash, card_exhaust | 形态继承材料升级/减费/保留；两次伤害后消耗，战后恢复原实体牌。 |
| T02 | 风暴之躯 | guard_gain, lightning_strike, card_exhaust | 躯形增甲后全体雷伤再消耗；无角色永久体型替换。 |
