"""Synthetic comparator acceptance/rejection tests, NOT evidence that the game ran."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'tools/relic_evidence.py'
PROBE = ROOT / 'src/Volibear/RelicContractProbe.cs'
spec = importlib.util.spec_from_file_location('relic_evidence_under_test', MODULE)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def specimen(case, medium="TwigSlimeM"):
    upgrade, death = 'upgrade' in case, case.endswith('death')
    n = 2 if upgrade else 1
    models = ['VOLIBEAR_B01'] * 4 + ['VOLIBEAR_B02'] * 4 + ['VOLIBEAR_B03', 'VOLIBEAR_B04']
    cards = [dict(cardRef=i + 1, modelId=m, masterIndex=i, masterModelId=m, combatCardIndex=100+i, sameObject=True, ownerId=10) for i, m in enumerate(models)]
    def draws(refs, normal=False):
        return [dict(cardRef=i, modelId=models[i - 1], fromHandDraw=normal) for i in refs]
    def step(label, target, before, count, blocked, performed=True):
        after = copy.deepcopy(before)
        new = before['draw'][:count]
        after['hand'] += new; after['draw'] = before['draw'][count:]; after['block'] -= blocked
        return dict(label=label, target=target, before=copy.deepcopy(before), after=after,
                    result=dict(performed=performed, completed=performed, absorbed=blocked), draws=draws(new),
                    moves=[dict(enemy=target, move='TACKLE_MOVE')] if performed else [],
                    damage=[dict(target=10, playerTarget=True, hpLost=0, blocked=blocked, props=8)] if performed else [])
    before = dict(round=1, turn=1, hp=80, block=0 if death else 100, hand=[], draw=list(range(1, 11)), discard=[], play=[], exhaust=[])
    starter = [dict(type='HuntersHeart', modelId='VOLIBEAR_HUNTERS_HEART')]
    upgraded = [dict(type='ImmortalHeart', modelId='VOLIBEAR_IMMORTAL_HEART'), dict(type='TouchOfOrobas', modelId='TOUCH_OF_OROBAS')]
    r = dict(token='run-token', scenario='relic-contract', variant=case, completed=True,
             gameVersion='v0.107.1', gameCommit='59260271', testMode=False, acceptance=evidence.ACCEPTANCE,
             character='VolibearCharacter', enemyIds=[11, 12, 13], enemyTypes=['LeafSlimeS', 'TwigSlimeS', medium], playerId=10,
             cards=cards, generated=[], sourceCardRef=10, initialRelics=starter, upgrade=None, finalRelics=upgraded if upgrade else starter,
             steps=[], transition=None)
    if upgrade:
        r['upgrade'] = dict(setupSucceeded=True, selectedStarter='VOLIBEAR_HUNTERS_HEART', selectedUpgrade='VOLIBEAR_IMMORTAL_HEART',
                            originalStillOwned=False, inventory=upgraded)
    if death:
        r['steps'].append(step('invalid-target', 10, before, 0, 0, False))
        dead = step('receiver-death', 11, before, 0, 0)
        dead['after']['hp'] = 0
        dead['result']['completed'] = False
        dead['damage'][0]['hpLost'] = 80
        r['steps'].append(dead)
    else:
        r['steps'].append(step('first', 11, before, n, 3))
        r['steps'].append(step('duplicate', 11, r['steps'][-1]['after'], 0, 0, False))
        r['steps'].append(step('second-enemy', 12, r['steps'][-1]['after'], 0, 4))
        old = copy.deepcopy(r['steps'][-1]['after'])
        generated_refs = [11,12] if medium == 'LeafSlimeM' else [11]
        move = 'STICKY_SHOT' if medium == 'LeafSlimeM' else 'STICKY_SHOT_MOVE'
        r['generated'] = [dict(cardRef=c, modelId='SLIMED', type='Slimed', cardType='Status', combatCardIndex=100+c,
                               sameObject=True, ownerId=10, masterModelId=None, masterIndex=-1, sourceEnemy=13,
                               sourceType=medium, sourceMove=move, pile='Discard', creatorId=None, round=1, turn=1, side='Enemy') for c in generated_refs]
        after = dict(round=2, turn=2, hp=80, block=0, hand=old['draw'][:5], draw=old['draw'][5:],
                     discard=old['hand'] + generated_refs, play=[], exhaust=[])
        r['transition'] = dict(before=old, after=copy.deepcopy(after), draws=draws(after['hand'], True),
                               moves=[dict(enemy=13, move=move)], firstNextMove='GOOP_MOVE', damage=[],
                               generatedHistory=[dict(cardRef=c, modelId='SLIMED', creatorId=None) for c in generated_refs])
        after['hp'] = 80; after['block'] = 100
        r['steps'].append(step('next-turn-first', 11, after, n, 3))
    return r


class RelicEvidenceTests(unittest.TestCase):
    def test_all_four_synthetic_valid_cases(self):
        for case in evidence.RELIC_CASES:
            with self.subTest(case=case):
                self.assertTrue(evidence.validate_relic_result(specimen(case), 'run-token', case))

    def test_missing_wrong_provenance_and_self_report_rejected(self):
        for key, value in [('token', 'stale'), ('gameCommit', 'other'), ('testMode', True), ('completed', False),
                           ('acceptance', 'full-orobas-dialogue-accepted'), ('character', 'Ironclad')]:
            r = specimen('RH-upgrade-turns'); r[key] = value
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']), key)
        r = specimen('RH-upgrade-turns'); r['passed'] = True
        self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))
        for key in list(r):
            broken = copy.deepcopy(r); del broken[key]
            if key != 'passed': self.assertFalse(evidence.validate_relic_result(broken, 'run-token', 'RH-upgrade-turns'))

    def test_replace_chain_and_single_initial_relic_required(self):
        for key, value in [('setupSucceeded', False), ('selectedUpgrade', 'CIRCLET'), ('originalStillOwned', True)]:
            r = specimen('RH-upgrade-turns'); r['upgrade'][key] = value
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']), key)
        for location in ['initialRelics', 'finalRelics']:
            r = specimen('RH-upgrade-turns')
            r[location] = r[location] + [dict(type='HuntersHeart', modelId='VOLIBEAR_HUNTERS_HEART')]
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))

    def test_draw_count_identity_master_ids_and_history_required(self):
        changes = [lambda r: r['steps'][0]['draws'].pop(),
                   lambda r: r['steps'][0]['after']['hand'].reverse(),
                   lambda r: r['steps'][0]['draws'][0].update(fromHandDraw=True),
                   lambda r: r['steps'][0]['moves'].clear(),
                   lambda r: r['cards'][0].update(masterIndex=1),
                   lambda r: r['cards'][0].update(masterModelId='VOLIBEAR_B04'),
                   lambda r: r['steps'][0]['draws'][0].update(cardRef=True)]
        for mutate in changes:
            r = specimen('RH-upgrade-turns'); mutate(r)
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))

    def test_same_turn_second_enemy_duplicate_and_next_turn_reset(self):
        for index in [1, 2]:
            r = specimen('RH-starter-turns')
            r['steps'][index]['draws'] = copy.deepcopy(r['steps'][0]['draws'])
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))
        for mutate in [lambda r: r['steps'][3]['after']['hand'].pop(),
                       lambda r: r['steps'][3]['before'].update(turn=1),
                       lambda r: r['transition']['draws'].pop(),
                       lambda r: r['transition']['moves'].append(dict(enemy=11, move='GOOP_MOVE')),
                       lambda r: r['transition'].update(firstNextMove='TACKLE_MOVE')]:
            r = specimen('RH-upgrade-turns'); mutate(r)
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))

    def test_failed_and_lethal_native_actions_cannot_claim_completion(self):
        for case in ['RH-starter-death', 'RH-upgrade-death']:
            for mutate in [lambda r: r['steps'][0]['result'].update(completed=True),
                           lambda r: r['steps'][1]['result'].update(completed=True),
                           lambda r: r['steps'][1]['after'].update(hp=1),
                           lambda r: r['steps'][1]['moves'].clear(),
                           lambda r: r['steps'][1]['damage'][0].update(hpLost=0),
                           lambda r: r['steps'][1]['draws'].append(dict(cardRef=1, modelId='VOLIBEAR_B01', fromHandDraw=False))]:
                r = specimen(case); mutate(r)
                self.assertFalse(evidence.validate_relic_result(r, 'run-token', case))

    def test_log_parser_requires_exactly_one_matching_result(self):
        case = 'RH-upgrade-turns'
        line = evidence.PREFIX + json.dumps(specimen(case))
        self.assertTrue(evidence.relic_contract_evidence(line, 'run-token', case)[1])
        for log in ['', line + '\n' + line, evidence.PREFIX + '{', evidence.PREFIX + '{}']:
            self.assertFalse(evidence.relic_contract_evidence(log, 'run-token', case)[1])
        self.assertFalse(evidence.relic_contract_evidence(line, 'stale-token', case)[1])
        self.assertFalse(evidence.relic_contract_evidence(line, 'run-token', 'RH-starter-turns')[1])

    def test_native_medium_variants_have_exact_independent_status_counts(self):
        for medium, count in [('TwigSlimeM', 1), ('LeafSlimeM', 2)]:
            for case in evidence.RELIC_CASES:
                r = specimen(case, medium)
                self.assertEqual(len(r['generated']), 0 if case.endswith('death') else count)
                self.assertTrue(evidence.validate_relic_result(r, 'run-token', case))
        r = specimen('RH-upgrade-turns', 'LeafSlimeM')
        r['generated'].pop()
        self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))

    def test_generated_status_origin_native_identity_and_master_are_strict(self):
        for key, value in [('modelId', 'WOUND'), ('type', 'Wound'), ('cardType', 'Skill'), ('combatCardIndex', 100),
                           ('combatCardIndex', True), ('sameObject', False), ('ownerId', 99), ('masterIndex', 0),
                           ('masterModelId', 'SLIMED'), ('sourceEnemy', 11), ('sourceType', 'LeafSlimeS'),
                           ('sourceMove', 'TACKLE_MOVE'), ('pile', 'Hand'), ('creatorId', 10), ('round', 2),
                           ('turn', 2), ('side', 'Player')]:
            r = specimen('RH-upgrade-turns'); r['generated'][0][key] = value
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']), key)
        r = specimen('RH-upgrade-death'); r['generated'] = specimen('RH-upgrade-turns')['generated']
        self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))

    def test_missing_status_history_dropped_unknown_or_reassigned_pile_identity_rejected(self):
        for mutate in [lambda r: r['transition']['generatedHistory'].clear(),
                       lambda r: r['transition']['generatedHistory'][0].update(creatorId=10),
                       lambda r: r['transition']['moves'][0].update(move='TACKLE_MOVE'),
                       lambda r: r['transition']['after']['discard'].remove(11),
                       lambda r: r['transition']['after']['discard'].append(999),
                       lambda r: r['transition']['after']['play'].append(11),
                       lambda r: r['steps'][3]['after']['discard'].remove(11),
                       lambda r: r['cards'][1].update(combatCardIndex=100),
                       lambda r: r['transition']['draws'][0].update(cardRef=11, modelId='SLIMED')]:
            r = specimen('RH-upgrade-turns'); mutate(r)
            self.assertFalse(evidence.validate_relic_result(r, 'run-token', r['variant']))

    def test_probe_uses_native_acquisition_actions_and_history_not_responders(self):
        source = PROBE.read_text(encoding='utf-8')
        for required in ['touch.SetupForPlayer(player)', 'await RelicCmd.Obtain(touch, player)',
                         'await EngageCmd.Perform(choices, target, source)', 'PlayerCmd.EndTurn(player, canBackOut: false)',
                         'CardDrawnEntry', 'MonsterPerformedMoveEntry', 'DamageReceivedEntry',
                         'card.DeckVersion', 'move.PerformMove']:
            if required == 'move.PerformMove':
                self.assertNotIn(required, source)  # production Engage owns the native monster call.
            else:
                self.assertIn(required, source)
        self.assertNotIn('AfterEngageCompleted(', source)
        self.assertNotIn('GetUpgradeReplacement()', source)
        self.assertNotIn('SetUpForTests', source)
        self.assertNotIn('SetupForTests(', source)
        self.assertNotIn('passed =', source)
        self.assertEqual(source.count('[HarmonyPatch('), 1)
        self.assertIn('[HarmonyPatch(typeof(Hook), nameof(Hook.AfterCardGeneratedForCombat))]', source)
        self.assertIn('private static void Prefix(CardModel card, Player? creator) => Generated?.Invoke(card, creator);', source)
        self.assertIn('CardGeneratedEntry', source)
        self.assertIn('NetCombatCard.FromModel(card)', source)
        self.assertIn('IsPerformingMove: true', source)
        self.assertIn('card is not Slimed', source)
        self.assertIn('Unknown native card identity', source)
        self.assertNotIn('CreateCard<Slimed>', source)
        self.assertNotIn('AddToCombatAndPreview<Slimed>', source)


if __name__ == '__main__':
    unittest.main()
