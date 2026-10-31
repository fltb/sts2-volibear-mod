#!/usr/bin/env python3
"""Author-maintained presentation mapping, never a combat rules interpreter."""
from pathlib import Path
import json,hashlib
from build_vfx import atomic_text
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent

# id -> visual primitives and their semantic result events. This table is
# deliberately explicit: inferred keyword matches must not invent card logic.
MAPPING={
'B01':'physical','B02':'block','B03':'physical thunder_all','B04':'block physical challenge',
'C01':'physical','C02':'physical','C03':'heavy thunder_all','C04':'heavy weak challenge',
'C05':'domain physical','C06':'physical block draw','C07':'physical retrieve','C08':'physical wound',
'C09':'physical_all thunder_all','C10':'block challenge absorption counter','C11':'block challenge',
'C12':'block','C13':'draw exhaust','C14':'block domain counter_thunder exhaust','C15':'retrieve discount',
'C17':'strength','C18':'domain weak_all','C19':'retain_card charge','C20':'physical draw',
'C21':'block domain draw','C22':'physical_all thunder_all','C24':'thunder_all draw','C25':'discount exhaust',
'C26':'energy','U02':'install thunder_all','U03':'block retain_armor','U04':'install block strength',
'U05':'heavy','U06':'physical','U07':'heavy discount','U08':'block bite bite_mark',
'U10':'draw enhance','U11':'replay','U12':'thunder_boost draw exhaust','U13':'strength',
'U14':'block discount exhaust','U15':'purify draw','U17':'scry discard draw',
'U19':'install draw domain','U20':'physical energy exhaust','U21':'install energy',
'U23':'roar weak_all block','U24':'physical thunder lifesteal exhaust','U25':'install draw discount',
'U26':'install strength','U27':'physical block','U28':'block challenge absorption thunder_all',
'U29':'thunder_boost','U31':'heavy thunder_all','U32':'install domain discount',
'U34':'install block thunder_armor','U35':'block thunder_all challenge','U36':'energy draw exhaust',
'U37':'thunder_all domain','U38':'physical discount','U39':'block domain retrieve','U40':'thunder energy',
'U41':'physical transform discount','U42':'block transform discount','U43':'retrieve transform discount exhaust',
'R01':'install block domain','R02':'install block iron_armor','R05':'block','R06':'strength block enhance exhaust',
'R07':'thunder_all','R08':'physical_random thunder_random','R09':'block challenge_all absorption thunder_all',
'R10':'retrieve discount','R12':'draw','R13':'heal domain strength exhaust','R14':'install discount draw',
'R16':'install strength dexterity block','R17':'thunder','R18':'install thunder_all',
'R21':'block draw exhaust','R23':'thunder','R24':'energy draw exhaust','R25':'domain retrieve exhaust',
'R27':'transform discount block exhaust','R28':'install spirit_transfer transform draw',
'R29':'retrieve transform discount exhaust','R30':'install transform discount block energy',
'R31':'block domain guard_remove heavy thunder_other exhaust',
'T01':'physical exhaust','T02':'block thunder_all exhaust'
}

# Effect IDs are concrete files. Event names below are this package's portable
# contract; they are explicitly NOT asserted to be native STS2 API names.
VOCAB={
'physical':('claw_slash','physical_damage_resolved','resolved_target','each_confirmed_segment'),
'physical_all':('claw_slash','physical_damage_resolved','each_resolved_target','each_confirmed_segment'),
'physical_random':('claw_slash','physical_damage_resolved','resolved_target','authoritative_random_target_order'),
'heavy':('heavy_impact','physical_damage_resolved','resolved_target_ground','each_confirmed_segment'),
'counter':('counter_release','physical_damage_resolved','owner_to_resolved_target','only_after_confirmed_challenge_sequence'),
'bite':('bite_hit','physical_damage_resolved','resolved_target','each_confirmed_segment'),
'block':('guard_gain','block_changed','owner_front','actual_positive_block_delta_only'),
'guard_remove':('guard_break','target_block_removed','resolved_target_contact','actual_positive_removed_block_only; before_following_damage'),
'thunder':('lightning_strike','thunder_damage_resolved','resolved_target','each_confirmed_thunder_segment'),
'thunder_random':('lightning_strike','thunder_damage_resolved','resolved_target','authoritative_random_target_order'),
'thunder_all':('lightning_strike','thunder_damage_resolved','each_resolved_target','one_logical_thunder_event_multiple_visual_targets'),
'thunder_other':('lightning_strike','thunder_damage_resolved','resolved_other_enemy_targets','exclude_actual_primary_target'),
'domain':('domain_enter','domain_state_changed','owner_ground','start_only_zero_to_positive; extension_updates_UI_only'),
'challenge':('roar_wave','challenge_action_started','owner_to_original_action_targets','confirmed_actual_enemy_action_start_only'),
'challenge_all':('roar_wave','challenge_action_started','owner_to_original_action_targets','per_eligible_actual_enemy_action; preserve_original_target'),
'absorption':('absorb','challenge_absorption_committed','initiating_owner_contact','actual_block_absorption_positive_only'),
'counter_thunder':('counter_release','counter_thunder_resolved','owner_to_attacking_entity','one_per_actual_enemy_attack_segment'),
'weak':('weakness','weakness_applied','resolved_target_status','positive_applied_delta_only'),
'weak_all':('weakness','weakness_applied','each_resolved_target_status','positive_applied_delta_only'),
'wound':('wound','vulnerable_applied','resolved_target_status','positive_applied_delta_only'),
'bite_mark':('mark_bite','bite_mark_added','resolved_target_status','key_by_owner_id_and_enemy_entity_id; retained_same_entity_revive'),
'draw':('card_draw','card_drawn','draw_pile_to_actual_hand_slot','only_actual_entered_hand; per_card_entity'),
'retrieve':('card_retrieve','selected_card_entered_hand','actual_source_pile_to_hand_slot','only_after_slot_reserved_and_move_committed'),
'discard':('card_discard','selected_card_discarded','actual_card_to_discard_pile','actual_selected_card_only'),
'scry':('card_retrieve','scry_selection_opened','actual_preview_cards','preview_highlight_only; no_hand_entry_or_simulated_shuffle'),
'exhaust':('card_exhaust','card_exhausted','actual_exhausted_card','same_card_entity; after_card_effects_unless_explicit_cost'),
'purify':('card_purify','card_purification_committed','actual_selected_card','purify_first_then_exhaust; U15_cost_other_card_before_play'),
'discount':('cost_reduce','card_cost_modifier_changed','actual_card_cost_anchor','actual_displayed_cost_or_pending_modifier_changed; unbound_next_card_buff_stays_owner_state; no_extra_energy_gain'),
'strength':('strength','strength_changed','owner_status','positive_actual_strength_delta_only; temporal_to_permanent_conversion_not_double_add'),
'dexterity':('armor_retain','dexterity_changed','owner_status','positive_actual_dexterity_delta_only'),
'charge':('charge','card_charge_changed','actual_selected_card','next_fixed_attack_segments_only; cleared_after_complete_resolution'),
'retain_card':('armor_retain','card_retain_added','actual_selected_card','retain_is_card_state_not_player_block'),
'enhance':('strength','card_enhancement_committed','actual_affected_card','new_persistent_card_enhancement_only'),
'replay':('card_replay','replay_granted_or_started','actual_affected_card','same_target_and_paid_X; replay_not_new_play_count_or_growth'),
'thunder_boost':('lightning_growth','thunder_modifier_changed','owner_status','actual_modifier_update; distinct_from_growth_counter'),
'energy':('energy_gain','energy_changed','owner_energy','actual_positive_energy_delta_only; once_caps_enforced_by_rules'),
'heal':('heal','health_recovered','owner_status','actual_positive_heal_after_cap'),
'lifesteal':('lifesteal','lifesteal_health_recovered','damaged_target_to_owner','only_actual_HP_loss_and_actual_heal_positive; fully_blocked_no_heal'),
'retain_armor':('armor_retain','retain_armor_applied','owner_status','read_actual_status; no_numeric_rule_in_VFX'),
'iron_armor':('armor_iron','iron_armor_applied','owner_status','actual_status_applied; visual_not_prevent_HP_damage'),
'thunder_armor':('thunder_armor','thunder_armor_block_committed','owner_front','one_per_complete_logical_thunder_event; group_not_per_enemy'),
'roar':('roar_wave','card_presentation_requested','owner_mouth','once_per_actual_play; cosmetic_only'),
'install':('cast_charge','power_instance_deployed','owner_status','one_per_new_deployed_instance; passives_use_result_events'),
'spirit_transfer':('feral_transfer','feral_target_confirmed','owner_to_actual_selected_card','positive_legal_selection_only; transfer_into_external_card'),
'transform':('feral_claw','feral_transformation_committed','actual_converted_card','attack_material_to_claw_other_material_to_body; emit_only_success')
}

DETAILS={
'C06':'攻击意图分支只展示实际获得的格挡；另一分支只展示实际抽牌。',
'C10':'先格挡，再实际迎战与吸收，最后根据已结算伤害显示反击；VFX不把吸收再加到伤害。',
'C14':'基础牌消耗、升级不消耗，读取实际card_exhausted事件；反雷是后续敌人攻击段结果。',
'C19':'留住的是所选攻击牌，不显示角色留甲状态。',
'C26':'共享返能限次由规则确认；不能每次看到雷光就返能。',
'U08':'强化读取出牌前咬痕；命中即登记，完全格挡/致死命中也可登记。',
'U10':'等待下一张攻击的强化可跨回合；不在回合结束取消其UI。',
'U11':'重演完整牌效；不追加一次出牌或成长。',
'U12':'本轮雷伤增幅不等于永久雷电成长，状态使用不同逻辑ID。',
'U13':'临时力量转正不显示重复的两次力量获得。',
'U14':'升级不消耗；按实际消耗事件播放。',
'U15':'所选另一张手牌先净化消耗作为费用，完成费用后才播放本牌抽牌。',
'U17':'查看、弃置、排序与抽牌均等玩家实际选择；不预播未选弃牌。',
'U19':'入场和每次实际迎战后各自读取抽牌、领域变化；领域延长不重复完整展开动画。',
'U21':'按部署实例，每回合实际阈值达成触发一次；入场已达标也由规则发事件。',
'U25':'此前目标计数与每回合首次条件由规则确认，抽到的攻击才显示减费。',
'U26':'第2张攻击的力量在其伤害前取得；只消费权威事件序列。',
'U28':'吸收增量归迎战发起者；只显示完成后实际全体雷伤。',
'U31':'X=0不播放伤害命中特效；实际支付X决定重复段，不从图集帧计数。',
'U34':'群体雷伤是一次完整逻辑雷伤，增甲不按受击敌人数重复。',
'U40':'此前至少2次雷伤读取出牌开始快照；返能共享限次，非当前动画闪电条数。',
'U41':'仅合法攻击材料成功转换后显示爪形，临时减费随同原实体保留。',
'U42':'非攻击材料转换成躯形（T02），不能误变爪形。',
'U43':'检索占用手牌位并完成取牌，再转换同一实体，之后显示减费。',
'R01':'永久领域无倒计时归零效果；死亡或战斗结束仍清理。',
'R02':'坚甲维持格挡，但溢出伤害仍可扣血；不以盾光屏蔽受伤/死亡动作。',
'R05':'直接格挡乘3的真实正增量驱动视觉；0变0不播增甲。',
'R08':'4次随机目标由规则逐段给出；VFX禁止自己抽签或复用首个目标。',
'R09':'所有敌人各按剩余行动机会迎战；原攻击目标不改，吸收归发起者。',
'R13':'领域内治疗、领域外展开是互斥分支；力量正常展示。',
'R14':'升级入场才抽牌；同一目标连锁减费只更新实际受影响的单体攻击牌。',
'R16':'升级入场格挡；之后力量/敏捷按完整牌效结果，非命中段重复。',
'R18':'入场、回合结束和本回合首次迎战后分别读取权威雷伤事件。',
'R23':'三次雷伤结算三次表现，不能把同一条雷的分叉数当作结算段。',
'R27':'允许选0张，0张不播放转换成功；逐实体读取爪形减费或躯形格挡。',
'R28':'入场/起手后的合法选择确认时先传递至外部卡牌，再以成功转换事件收尾；不把角色头部变形。',
'R29':'升级先完成回收，再固定手牌集合并逐张兽化；兽化后抽到的新牌不纳入本次集合。',
'R30':'首次爪形/躯形奖励分别独立，按权威格挡与能量事件表现。',
'R31':'目标破甲先于物理伤害；其他敌人的雷伤集合排除实际主目标。',
'T01':'形态继承材料升级/减费/保留；两次伤害后消耗，战后恢复原实体牌。',
'T02':'躯形增甲后全体雷伤再消耗；无角色永久体型替换。'
}

def main():
    source=ROOT/'source/cards_source.json';data=json.loads(source.read_text());old=json.loads((ROOT/'source/card_animation_bindings.json').read_text())
    oldmap={x['id']:x for x in old['cards']};cards=[];events=[]
    assert set(MAPPING)=={x['id'] for x in data['cards']},'Card coverage changed: explicitly review table.'
    for c in data['cards']:
        cues=[]
        for token in MAPPING[c['id']].split():
            effect,event,anchor,guard=VOCAB[token]
            item={'semantic_key':token,'event':event,'effect_id':effect,'anchor':anchor,'guard':guard,'audio_cue':'sfx.'+effect,'scope':'this_card_entity_or_its_actual_deployed_instance','order':'preserve_authoritative_event_order','blocks_gameplay':False,'dedup_key':['battle_id','owner_id','event_id','effect_id','target_entity_id']}
            if token=='transform':
                item['effect_by_result_form']={'claw':'feral_claw','body':'feral_body'}
                item['prelude_effect']='feral_transfer';item['prelude_event']='feral_target_confirmed'
                item['audio_cue_by_result_form']={'claw':'sfx.feral_claw','body':'sfx.feral_body'}
                item['do_not_duplicate_prelude']='R28 spirit_transfer uses same event_id; at most one transfer per selected entity.'
            if token=='domain':item['state_followups']={'positive_to_positive':'update_duration_UI_only','active':'domain_loop','positive_to_zero':'domain_exit'}
            if token=='thunder_all':item['group_visual_variant']='lightning_all only for an already-resolved group event; never in addition to per-target strike for the same packet'
            if token=='counter_thunder':item['target_contact_effect']='lightning_strike'
            if token in ('thunder','thunder_random'):
                item['optional_connector_effect']='lightning_chain'
                item['connector_policy']='same semantic result event; connect existing source/target anchors only; no extra damage, target, trigger count or additional audio cue'
            cues.append(item)
        cards.append({'id':c['id'],'asset_key':c['asset_key'],'name':c['name'],'type':c['type'],'cost':c['cost'],'base_effect_verbatim':c['base_effect'],'upgraded_effect_verbatim':c['upgraded_effect'],'primary_motion':oldmap[c['id']]['primary_motion'],'cues':cues,'special_cases':DETAILS.get(c['id'],'只消费实际成功结算事件；基础与升级使用同套特效，结果数量与数值由规则提供。')})
    common=[
        {'event':'thunder_growth_committed','effect_id':'lightning_growth','scope':'owner_status','guard':'each actual played Attack or ThunderSpell only; before its damage; replay excluded'},
        {'event':'domain_attack_bonus_thunder_resolved','effect_id':'lightning_strike','scope':'each_resolved_enemy','guard':'per actual ordinary-attack segment; group packet counts once for mechanics'},
        {'event':'domain_state_changed','effect_id':'domain_loop','scope':'owner_ground','guard':'one persistent owner instance while domain positive; restart only after actual death/revive re-entry'},
        {'event':'domain_suppression_applied','effect_id':'domain_suppress','scope':'affected_enemy','guard':'known eligible source actually suppressed; unknown source preserved; aggregate surviving owners'},
        {'event':'domain_purification_committed','effect_id':'card_purify','scope':'actual_drawn_status_or_curse','guard':'purify before exhaust then replacement draw; all from actual card events'},
        {'event':'incoming_attack_blocked','effect_id':'guard_hit','scope':'actual_defending_entity_contact','guard':'block_absorbed > 0; distinct incoming attack event'},
        {'event':'counter_thunder_resolved','effect_id':'counter_release','scope':'counter_owner_to_actual_attacker','guard':'actual enabled status; no recursive rules execution in VFX'},
        {'event':'feral_transformation_committed','effect_id':'feral_aura','scope':'owner_ground','guard':'one small owner accent per confirmed batch; no anatomy morph; actual cards remain same entities'},
        {'event':'bite_mark_removed','effect_id':None,'scope':'owner_enemy_entity_pair','guard':'remove persistent visual by entity identity; not on same-entity revive'},
        {'event':'owner_died_or_battle_ended','effect_id':None,'scope':'owner_local_domain_audio_on_death; all_battle_visuals_on_battle_end','guard':'reason=owner_death stops owner-local loops and pending presentation, not authoritative bite-mark data; reason=battle_end clears all visuals'},
    ]
    contract={
      'schema_version':1,'binding_kind':'portable_semantic_presentation_contract_not_native_game_api','card_count':len(cards),'card_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'mechanics_source': 'source/cards_source.json','primary_motion_source':'source/card_animation_bindings.json',
      'required_payload':['battle_id','owner_id','event_id','card_entity_id','target_entity_id_or_list','resolved_result','event_order'],
      'policy':{
       'dedup':'Deduplicate one presentation effect per semantic event and target. Global and per-card subscriptions route through the same key.',
       'no_rules':'No gameplay mutation, target selection, RNG draw, damage calculation, status duration update or awaiting VFX completion.',
       'multiplayer':'Owner/target stable entity IDs and authoritative event order. Local cosmetic variation uses event hash, never gameplay RNG.',
       'death':'Cancel pending target-bound VFX on freed nodes; owner death clears own domain and audio. Revive does not restore domain without fresh rules event. Same-enemy-entity revival rebinds bite-mark UI from its preserved authoritative state.',
       'selection_cancel':'Zero selection or cancelled invalid selection has no successful transfer/conversion cue. UI hover can use an uncommitted preview only.',
       'capacity':'Respect actual hand-entry/selection events; no fake cards when hand is full. Replayed effects use same paid X/target snapshot.',
       'layering':'Ground -20, rear ambient -10, character 0, front contact 20..30, status UI in its own CanvasLayer. Foreground near arm stays above braids independently.',
       'audio':'sfx IDs resolved by ../audio/manifest.json; persistent loops do not restart sound on each visual loop. Group/multihit cues are rate-limited cosmetics.',
       'speed':'Read presentation time scale; fast/skip mode may shorten or omit effects without changing rules. Never delay enemy action opportunity bookkeeping.',
       'flashes':'No full-screen flash, no additive overdraw requirement; native premultiplied imports must use correct alpha. Straight-alpha PNG is authoritative.',
       'unsupported_unknown_source':'Preserve unknown enemy behavior under domain; record unsupported source separately, never suppress because its VFX looks similar.'
      },'global_rule_cues':common,'cards':cards}
    atomic_text(ROOT/'card_vfx_bindings.json',json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    atomic_text(ROOT/'card_bindings_data.js','window.VOLIBEAR_CARD_VFX='+json.dumps(contract,ensure_ascii=False,separators=(',',':'))+';\n')
    lines=['# 89张卡牌的特效绑定','', '这是逐卡的表现层契约。事件名是本包定义的可移植语义名，**不是声称已存在的 STS2 API**。游戏逻辑发出真实结果，播放器只播放对应素材。基础、升级、条件分支和能力后续触发均保留原卡表。','', '| ID | 卡牌 | 特效文件ID | 重点时序/条件 |','|---|---|---|---|']
    for c in cards:
        fx=[]
        for x in c['cues']:
            for f in [x['effect_id'],*x.get('effect_by_result_form',{}).values(),x.get('prelude_effect')]:
                if f and f not in fx:fx.append(f)
        lines.append(f"| {c['id']} | {c['name']} | {', '.join(fx)} | {c['special_cases']} |")
    atomic_text(ROOT/'CARD_BINDINGS.md','\n'.join(lines)+'\n')
    print(json.dumps({'cards':len(cards),'card_cues':sum(len(x['cues']) for x in cards),'global_cues':len(common)}))
if __name__=='__main__':main()
