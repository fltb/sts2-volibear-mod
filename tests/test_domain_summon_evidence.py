"""Evidence parser/oracle unit tests, NOT gameplay execution or a fake engine."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('domain_summon_evidence', ROOT / 'tools/domain_summon_evidence.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
TOKEN = 'summon-unit-run'


def sample(variant):
    # Serialized evidence fixtures; these do not execute or substitute game behavior.
    family = variant.split('-')[0]
    on, expire = not variant.endswith('-off'), variant == 'infested-expire'
    domain = 2 if on else 0
    typ, encounter, slot, move = {
        'fabricator': ('Fabricator', 'FabricatorNormal', 'fabricator', 'FABRICATING_STRIKE_MOVE'),
        'ovicopter': ('Ovicopter', 'OvicopterNormal', 'ovicopter', 'LAY_EGGS_MOVE'),
        'infested': ('PhrogParasite', 'PhrogParasiteElite', 'phrog', 'INFECT_MOVE')}[family]
    parent = dict(id='1', type=typ, slot=slot, hp=100, maxHp=100, block=0, minion=0,
                  infested=4 if family == 'infested' else 0, hatch=0, nextMove=move, startStunned=None)
    before = dict(parentId='1', playerId='0', parentHp=100, parentMaxHp=100, parentAttached=True,
                  parentInfested=4 if family == 'infested' else 0, playerHp=80, playerBlock=0,
                  domain=domain, inProgress=True, isEnding=False, round=1, side='Player', enemies=[parent])
    after = copy.deepcopy(before)
    if family == 'fabricator': after['playerHp'] = 62
    if family == 'infested':
        after.update(parentHp=0, parentAttached=False, parentInfested=0, isEnding=on, enemies=[])
    if expire: after['domain'] = 0
    if not on:
        count = dict(fabricator=1, ovicopter=3, infested=4)[family]
        for i in range(count):
            child_type = dict(fabricator='Stabbot', ovicopter='ToughEgg', infested='Wriggler')[family]
            hp = dict(fabricator=20, ovicopter=16, infested=19)[family]
            child_slot = 'bot1' if family == 'fabricator' else f'egg{5-i}' if family == 'ovicopter' else f'wriggler{i+1}'
            after['enemies'].append(dict(id=str(2+i), type=child_type, slot=child_slot, hp=hp, maxHp=hp,
                block=0, minion=0 if family == 'infested' else 1, infested=0,
                hatch=1 if family == 'ovicopter' else 0,
                nextMove=dict(fabricator='STAB_MOVE', ovicopter='HATCH_MOVE', infested='SPAWNED_MOVE')[family],
                startStunned=True if family == 'infested' else None))
    damage = []
    if family in ('fabricator', 'infested'):
        damage = [dict(sourceId='1' if family == 'fabricator' else '0',
            receiverId='0' if family == 'fabricator' else '1', hpLost=18 if family == 'fabricator' else 100,
            blocked=0, overkill=0, cardSource=None)]
    data = dict(before=before, after=after, damage=damage)
    if family != 'infested':
        next_move = 'FABRICATE_MOVE' if family == 'fabricator' else 'SMASH_MOVE'
        data.update(api='MonsterModel.PerformMove+MonsterModel.RollMove', initialMove=move, selected=move,
            setup='forced-existing-legal-reachable-FABRICATING_STRIKE_MOVE' if family == 'fabricator' else 'native-initial-LAY_EGGS_MOVE',
            performingBefore=False, performingAfter=False, stateLogBefore=[move], stateLogAfter=[move, next_move],
            nextMove=next_move, moves=[dict(sourceId='1', move=move, targets=['0'])])
    else:
        data.update(api='CreatureCmd.Damage+native-Kill/AfterDeath+CombatManager.CheckWinCondition',
            setup='controlled-native-Died-domain-removal-not-natural-draw-expiry' if expire else 'native-PhrogParasite-InfestedPower',
            input=dict(amount=100, props=6, sourceId='0', targetId='1'),
            results=[dict(receiverId='1', hpLost=100, blocked=0, overkill=0)], moves=[],
            diedReceipts=[dict(targetId='1', sameParent=True, hp=0, domainBefore=domain,
                domainAfter=0 if expire else domain, removedByFixture=expire)],
            callbackReceipts=[dict(ownerId='1', targetId='1', prevented=False, ownerHp=0, attached=True,
                infested=4, domain=0 if expire else domain, isEnding=on, taskCompleted=on)],
            winResult=on, wonCount=1 if on else 0, endedCount=1 if on else 0,
            finalInProgress=not on, finalEnemies=copy.deepcopy(after['enemies']))
    return dict(schema=1, token=TOKEN, scenario='domain-summon-contract', variant=variant,
        acceptance='native-mechanism-probe-not-complete-enemy-coverage', testMode=False, version='v0.107.1',
        commit='59260271', encounter=encounter, parentType=typ, fixtureHp=100,
        fixtureApi='CreatureCmd.SetMaxAndCurrentHp', data=data)


def log(payload):
    return gate.MARKER + json.dumps(payload) + '\n[Volibear] SHUTDOWN_BEGIN ' + TOKEN


class DomainSummonEvidenceTests(unittest.TestCase):
    def test_all_seven_serialized_cases(self):
        for case in gate.VARIANTS:
            with self.subTest(case=case):
                self.assertEqual(gate.validate(sample(case), TOKEN, case), [])
                self.assertTrue(gate.check_log(log(sample(case)), TOKEN, case)['passed'])

    def test_unhit_or_reenabled_async_handlers_fail(self):
        for case in ('infested-on', 'infested-expire'):
            broken = sample(case)
            broken['data']['callbackReceipts'] = []
            self.assertTrue(gate.validate(broken, TOKEN, case))
            broken = sample(case)
            broken['data']['after']['enemies'] = sample('infested-off')['data']['after']['enemies']
            broken['passed'] = True
            self.assertFalse(gate.check_log(log(broken), TOKEN, case)['passed'])

    def test_committed_veto_not_just_zero_children(self):
        broken = sample('infested-on')
        broken['data']['callbackReceipts'][0]['isEnding'] = False
        self.assertTrue(gate.validate(broken, TOKEN, 'infested-on'))
        broken = sample('infested-on')
        broken['data']['callbackReceipts'][0]['attached'] = False
        self.assertTrue(gate.validate(broken, TOKEN, 'infested-on'))

    def test_expiry_must_observe_actual_zero_at_native_boundaries(self):
        for location in ('died', 'callback', 'after'):
            broken = sample('infested-expire')
            if location == 'died': broken['data']['diedReceipts'][0]['domainAfter'] = 2
            if location == 'callback': broken['data']['callbackReceipts'][0]['domain'] = 2
            if location == 'after': broken['data']['after']['domain'] = 2
            self.assertTrue(gate.validate(broken, TOKEN, 'infested-expire'))

    def test_combat_must_really_finish_after_suppressed_final_spawn(self):
        for field, value in [('winResult', False), ('wonCount', 0), ('endedCount', 0), ('finalInProgress', True)]:
            broken = sample('infested-on')
            broken['data'][field] = value
            self.assertTrue(gate.validate(broken, TOKEN, 'infested-on'))
        broken = sample('infested-expire')
        broken['data']['finalEnemies'] = sample('infested-off')['data']['finalEnemies']
        self.assertTrue(gate.validate(broken, TOKEN, 'infested-expire'))

    def test_baseline_must_actually_summon_native_children(self):
        for case in ('fabricator-off', 'ovicopter-off', 'infested-off'):
            broken = sample(case)
            broken['data']['after']['enemies'] = broken['data']['before']['enemies']
            self.assertTrue(gate.validate(broken, TOKEN, case))

    def test_preserve_mixed_attack_native_history_and_followup(self):
        for case in ('fabricator-off', 'fabricator-on'):
            for field, value in [('damage', []), ('moves', []), ('performingAfter', True),
                                 ('nextMove', 'DISINTEGRATE_MOVE'), ('stateLogAfter', [])]:
                broken = sample(case)
                broken['data'][field] = value
                self.assertTrue(gate.validate(broken, TOKEN, case))
        broken = sample('ovicopter-on')
        broken['data']['nextMove'] = 'LAY_EGGS_MOVE'
        self.assertTrue(gate.validate(broken, TOKEN, 'ovicopter-on'))

    def test_all_controlled_snapshot_values_checked(self):
        for case in gate.VARIANTS:
            original = sample(case)
            for phase in ('before', 'after'):
                for field, value in original['data'][phase].items():
                    if type(value) not in (bool, int): continue
                    broken = copy.deepcopy(original)
                    broken['data'][phase][field] = not value if type(value) is bool else value + 1
                    with self.subTest(case=case, phase=phase, field=field):
                        self.assertTrue(gate.validate(broken, TOKEN, case))

    def test_children_preserve_actual_configuration(self):
        for case in ('fabricator-off', 'ovicopter-off', 'infested-off'):
            original = sample(case)
            index = 0 if case.startswith('infested') else 1
            for field, value in [('id', '0'), ('type', 'FakeMonster'), ('minion', 9), ('hatch', 9),
                                 ('infested', 9), ('slot', 'not-native-slot'), ('hp', 100),
                                 ('maxHp', 100), ('nextMove', 'FAKE_MOVE'), ('startStunned', 'fake')]:
                broken = copy.deepcopy(original)
                broken['data']['after']['enemies'][index][field] = value
                with self.subTest(case=case, field=field): self.assertTrue(gate.validate(broken, TOKEN, case))

    def test_native_identity_and_lethal_inputs(self):
        for field, value in [('amount', 99), ('props', 8), ('sourceId', '1'), ('targetId', '0')]:
            broken = sample('infested-on')
            broken['data']['input'][field] = value
            self.assertTrue(gate.validate(broken, TOKEN, 'infested-on'))
        for field in ('sourceId', 'receiverId'):
            broken = sample('fabricator-on')
            broken['data']['damage'][0][field] = '999'
            self.assertTrue(gate.validate(broken, TOKEN, 'fabricator-on'))

    def test_metadata_passed_flags_and_malformed_logs(self):
        for field in ('schema', 'token', 'scenario', 'variant', 'acceptance', 'testMode', 'version',
                      'commit', 'encounter', 'parentType', 'fixtureHp', 'fixtureApi'):
            broken = sample('fabricator-on')
            broken[field] = 'wrong'
            broken['passed'] = True
            self.assertTrue(gate.validate(broken, TOKEN, 'fabricator-on'))
        good = log(sample('fabricator-on'))
        for text in ('', good + '\n' + good, gate.MARKER + 'null', gate.MARKER + 'not-json',
                     good + '\n[Volibear] DOMAIN_SUMMON_ERROR exception', good.split('\n')[0]):
            self.assertFalse(gate.check_log(text, TOKEN, 'fabricator-on')['passed'])

    def test_nested_bool_is_not_numeric_receipt(self):
        broken = sample('infested-on')
        broken['data']['results'][0]['blocked'] = False
        self.assertTrue(gate.validate(broken, TOKEN, 'infested-on'))
        broken = sample('fabricator-on')
        broken['data']['damage'][0]['overkill'] = False
        self.assertTrue(gate.validate(broken, TOKEN, 'fabricator-on'))


if __name__ == '__main__':
    unittest.main()
