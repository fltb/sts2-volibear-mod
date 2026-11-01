"""Synthetic protocol tests only; these are NOT native engine acceptance evidence."""
import copy
import json
import unittest

from tools.beast_evidence import beast_contract_evidence, validate_beast_result

TOKEN = 'current-independent-beast-run'
PREFIX = '[Volibear] BEAST_CONTRACT_RESULT '


def snapshot(name, native, kind, target, base, variables, *, cost=None, upgrade=False,
             retain=False, keywords=None, pile='Hand', master=None, xid=False, cost_ref=100):
    value = base if cost is None else cost
    return dict(cardRef=name, nativeType=native, modelId=native.upper(), ownerRef=901,
                masterRef=master, costObjectRef=cost_ref, shape='None', type=kind, target=target,
                upgrade=upgrade, canonicalCost=base, costsX=xid, localCost=value, allCost=value,
                amountToSpend=3 if xid else max(0, value), retain=retain, keywords=keywords or [],
                pile=pile, presence=1, vars=variables, title='原始牌名')


def form(original, shape, variables, *, cost=1, upgrade=False, retain=False,
         keywords=None, pile='Hand'):
    # Synthetic fixture construction does not import the comparator's expectation helpers.
    return dict(original, shape=shape, type='Attack' if shape == 'Claw' else 'Skill',
                target='AnyEnemy' if shape == 'Claw' else 'AllEnemies', canonicalCost=1,
                costsX=False, localCost=cost, allCost=cost, amountToSpend=cost, upgrade=upgrade,
                retain=retain, keywords=keywords or ['Exhaust'], pile=pile, vars=variables,
                title=('裂骨之爪' if shape == 'Claw' else '风暴之躯') + ('+' if upgrade else ''))


def play(after, hp, block, hits, count_before, count_after):
    return dict(beforeHp=[100, 100, 100], afterHp=hp, blockBefore=0, blockAfter=block,
                energyBefore=3, energyAfter=3, lightningBefore=count_before, lightningAfter=count_after,
                playerStrength=0, enemyVulnerable=[0, 0, 0], autoPlayCalls=1, after=after,
                playHistory=[dict(cardRef=after['cardRef'], index=0, count=1)],
                damageHistory=[dict(target=target, hpLost=amount, blocked=0, props=props,
                                    cardRef=after['cardRef']) for target, amount, props in hits])


def common(variant):
    deck = []
    native_cards = [('B01', {'Damage': 6})] * 4 + [('B02', {'Block': 5})] * 4 + [
        ('B03', {'Damage': 8, 'Lightning': 3}), ('B04', {'Damage': 6, 'Block': 8})]
    for index, (key, variables) in enumerate(native_cards):
        deck.append(dict(cardRef=f'master-{index}', modelId='VOLIBEAR_' + key,
                         nativeType='Volibear_' + key, upgrade=False, cost=1, shape='None', vars=variables))
    return dict(token=TOKEN, scenario='beast-contract', variant=variant, completed=True, testMode=False,
                acceptance='effect-only-not-payment', character='VolibearCharacter',
                gameVersion='v0.107.1', gameCommit='59260271',
                fixtureApi='CombatState.CreateCard;CardPileCmd.Add;CardCmd.Upgrade;CreatureCmd.SetMaxAndCurrentHp',
                api='BeastForms.Convert;CardCmd.AutoPlay;CardPileCmd.Draw;PlayerCmd.EndTurn',
                enemyIds=[10, 11, 12], enemyTypes=['LeafSlimeS', 'TwigSlimeS', 'LeafSlimeM'],
                deckBefore=deck, deckAfter=copy.deepcopy(deck), changes=[], data={})


def f01_fixture():
    result = common('f01')
    rows = []
    # Damage/block/history constants deliberately independent of reported vars.
    inputs = [
        ('starter-claw', 'Volibear_B01', 'Attack', 'AnyEnemy', 1, {'Damage': 6}, 'Claw', {'Damage': 7, 'Hits': 2}, False, True, [], False, False, 'master-0', [86, 100, 100], 0, [(10, 7, 8)] * 2, 0, 0),
        ('native-bash', 'Bash', 'Attack', 'AnyEnemy', 2, {'Damage': 8, 'VulnerablePower': 2}, 'Claw', {'Damage': 7, 'Hits': 2}, False, False, [], False, False, None, [86, 100, 100], 0, [(10, 7, 8)] * 2, 0, 0),
        ('native-defend', 'DefendIronclad', 'Skill', 'Self', 1, {'Block': 5}, 'Body', {'Block': 9, 'Lightning': 2}, False, False, [], False, False, None, [98, 98, 98], 9, [(10, 2, 4), (11, 2, 4), (12, 2, 4)], 0, 1),
        ('native-power', 'Inflame', 'Power', 'Self', 1, {'StrengthPower': 3}, 'Body', {'Block': 12, 'Lightning': 3}, True, False, [], False, False, None, [97, 97, 97], 12, [(10, 3, 4), (11, 3, 4), (12, 3, 4)], 1, 2),
        ('native-status', 'Void', 'Status', 'None', -1, {'Energy': 1}, 'Body', {'Block': 9, 'Lightning': 2}, False, False, ['Ethereal', 'Unplayable'], True, False, None, [98, 98, 98], 9, [(10, 2, 4), (11, 2, 4), (12, 2, 4)], 2, 3),
        ('native-curse', 'Injury', 'Curse', 'None', -1, {}, 'Body', {'Block': 9, 'Lightning': 2}, False, False, ['Unplayable'], False, False, None, [98, 98, 98], 9, [(10, 2, 4), (11, 2, 4), (12, 2, 4)], 3, 4),
        ('native-x', 'Whirlwind', 'Attack', 'AllEnemies', 0, {'Damage': 5}, 'Claw', {'Damage': 7, 'Hits': 2}, False, False, [], False, True, None, [86, 100, 100], 0, [(10, 7, 8)] * 2, 4, 4),
    ]
    for index, item in enumerate(inputs):
        name, native, kind, target, base, variables, shape, beast_vars, upgraded, retained, keywords, draw, xid, master, hp, block, hits, cb, ca = item
        before = snapshot(name, native, kind, target, base, variables, upgrade=upgraded, retain=retained,
                          keywords=keywords, pile='Draw' if draw else 'Hand', master=master, xid=xid, cost_ref=100 + index)
        after = form(before, shape, beast_vars, upgrade=upgraded, retain=retained)
        rows.append(dict(name=name, before=before, returnedShape=shape,
                         afterConversion=dict(after, pile='Draw' if draw else 'Hand'),
                         drawCalls=int(draw), beforeDrawEnergy=3, afterDrawEnergy=3, afterDraw=after,
                         play=play(dict(after, pile='Exhaust'), hp, block, hits, cb, ca)))
        result['changes'].append(dict(cardRef=name, shape=shape, ownerRef=901, sameCombat=True))
    result['data'] = dict(rows=rows, voidControl=dict(beforeEnergy=3, afterEnergy=2, restoredEnergy=3, drawCalls=1,
        snapshot=snapshot('native-void-control', 'Void', 'Status', 'None', -1, {'Energy': 1},
                          keywords=['Ethereal', 'Unplayable'], cost_ref=200)))
    return result


def f02_fixture():
    result = common('f02')
    original = snapshot('native-bludgeon', 'Bludgeon', 'Attack', 'AnyEnemy', 3, {'Damage': 32},
                        cost=2, retain=True, keywords=['Retain'])
    base = form(original, 'Claw', {'Damage': 7, 'Hits': 2}, retain=True, keywords=['Exhaust', 'Retain'])
    upgraded = form(original, 'Claw', {'Damage': 11, 'Hits': 2}, upgrade=True, retain=True,
                    keywords=['Exhaust', 'Retain'])
    zero = dict(base, localCost=0, allCost=0, amountToSpend=0)
    upgraded_zero = dict(upgraded, localCost=0, allCost=0, amountToSpend=0)
    result['data'] = dict(before=original, firstShape='Claw', afterConversion=zero, secondShape='Claw',
        afterRepeat=copy.deepcopy(zero), afterNewSet=base,
        firstPlay=play(dict(base, pile='Exhaust'), [86, 100, 100], 0, [(10, 7, 8)] * 2, 0, 0),
        recycled=copy.deepcopy(base), afterUpgrade=upgraded, afterZero=upgraded_zero,
        upgradedPlay=play(dict(upgraded, pile='Exhaust'), [78, 100, 100], 0, [(10, 11, 8)] * 2, 0, 0),
        beforeTurn=copy.deepcopy(upgraded_zero), afterTurn=copy.deepcopy(upgraded),
        roundBefore=1, turnBefore=1, roundAfter=2, turnAfter=2, energyAfterTurn=3, hpAfterTurn=80)
    result['changes'] = [dict(cardRef='native-bludgeon', shape='Claw', ownerRef=901, sameCombat=True)]
    return result


class BeastEvidenceTests(unittest.TestCase):
    def test_independent_positive_f01(self):
        report = f01_fixture()
        self.assertTrue(validate_beast_result(report, TOKEN, 'f01'))
        parsed, passed = beast_contract_evidence(PREFIX + json.dumps(report), TOKEN, 'f01')
        self.assertTrue(passed)
        self.assertEqual(parsed, report)

    def test_independent_positive_f02(self):
        self.assertTrue(validate_beast_result(f02_fixture(), TOKEN, 'f02'))

    def test_parser_rejects_missing_duplicate_malformed_scalar_or_stale(self):
        text = PREFIX + json.dumps(f01_fixture())
        for log, token, case in [('', TOKEN, 'f01'), (text + '\n' + text, TOKEN, 'f01'),
                                 (PREFIX + '{', TOKEN, 'f01'), (PREFIX + 'null', TOKEN, 'f01'),
                                 (text, 'stale', 'f01'), (text, TOKEN, 'f03'), (text, TOKEN, 'f02')]:
            with self.subTest(log=log[:40], token=token, case=case):
                self.assertFalse(beast_contract_evidence(log, token, case)[1])

    def test_f01_rejects_each_mutated_observation(self):
        mutations = [
            (('completed',), False), (('completed',), 1), (('testMode',), True),
            (('gameVersion',), 'v0.108.0'), (('gameCommit',), 'other'),
            (('acceptance',), 'manual-payment-accepted'), (('changes',), []),
            (('enemyIds',), [10, 10, 12]), (('deckAfter', 0, 'vars', 'Damage'), 7),
            (('data', 'rows', 0, 'before', 'masterRef'), None),
            (('data', 'rows', 0, 'afterConversion', 'cardRef'), 'replacement-token'),
            (('data', 'rows', 0, 'afterConversion', 'modelId'), 'VOLIBEAR_T01'),
            (('data', 'rows', 0, 'afterConversion', 'ownerRef'), 902),
            (('data', 'rows', 0, 'afterConversion', 'costObjectRef'), 999),
            (('data', 'rows', 0, 'afterConversion', 'masterRef'), 'master-1'),
            (('data', 'rows', 0, 'afterConversion', 'retain'), False),
            (('data', 'rows', 0, 'afterConversion', 'presence'), 0),
            (('data', 'rows', 0, 'afterConversion', 'vars', 'Damage'), 6),
            (('data', 'rows', 0, 'play', 'afterHp'), [88, 100, 100]),
            (('data', 'rows', 0, 'play', 'damageHistory'), []),
            (('data', 'rows', 0, 'play', 'playHistory', 0, 'count'), 2),
            (('data', 'rows', 0, 'play', 'after', 'pile'), 'Discard'),
            (('data', 'rows', 0, 'play', 'energyAfter'), 2),
            (('data', 'rows', 1, 'play', 'enemyVulnerable'), [2, 0, 0]),
            (('data', 'rows', 2, 'play', 'blockAfter'), 5),
            (('data', 'rows', 3, 'play', 'playerStrength'), 3),
            (('data', 'rows', 3, 'afterConversion', 'upgrade'), False),
            (('data', 'rows', 4, 'afterConversion', 'keywords'), ['Exhaust', 'Unplayable']),
            (('data', 'rows', 4, 'afterDrawEnergy'), 2),
            (('data', 'rows', 4, 'drawCalls'), 0),
            (('data', 'rows', 5, 'afterConversion', 'type'), 'Curse'),
            (('data', 'rows', 6, 'afterConversion', 'costsX'), True),
            (('data', 'rows', 6, 'afterConversion', 'amountToSpend'), 3),
            (('data', 'voidControl', 'afterEnergy'), 3),
            (('data', 'voidControl', 'restoredEnergy'), 4),
        ]
        for path, value in mutations:
            with self.subTest(path=path):
                report = copy.deepcopy(f01_fixture())
                target = report
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertFalse(validate_beast_result(report, TOKEN, 'f01'))

    def test_f02_rejects_each_mutated_observation(self):
        mutations = [
            (('data', 'before', 'localCost'), 3),
            (('data', 'afterConversion', 'localCost'), 1),
            (('data', 'afterRepeat', 'costObjectRef'), 999),
            (('data', 'afterNewSet', 'localCost'), 0),
            (('data', 'firstPlay', 'after', 'localCost'), 0),
            (('data', 'recycled', 'cardRef'), 'new-entity'),
            (('data', 'recycled', 'pile'), 'Exhaust'),
            (('data', 'afterUpgrade', 'vars', 'Damage'), 17),
            (('data', 'afterUpgrade', 'upgrade'), False),
            (('data', 'afterZero', 'localCost'), 1),
            (('data', 'upgradedPlay', 'afterHp'), [16, 100, 100]),
            (('data', 'beforeTurn', 'localCost'), 1),
            (('data', 'afterTurn', 'localCost'), 0),
            (('data', 'afterTurn', 'retain'), False),
            (('data', 'roundAfter'), 1),
            (('data', 'turnAfter'), 1),
        ]
        for path, value in mutations:
            with self.subTest(path=path):
                report = copy.deepcopy(f02_fixture())
                target = report
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertFalse(validate_beast_result(report, TOKEN, 'f02'))
        report = f02_fixture()
        report['changes'] *= 2
        self.assertFalse(validate_beast_result(report, TOKEN, 'f02'))

    def test_missing_or_forged_data_never_passes(self):
        for variant, factory in [('f01', f01_fixture), ('f02', f02_fixture)]:
            for bad in [None, [], {}, True, {'passed': True}]:
                report = factory()
                report['data'] = bad
                self.assertFalse(validate_beast_result(report, TOKEN, variant))


if __name__ == '__main__':
    unittest.main()
