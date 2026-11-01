"""Synthetic positive/negative controls for native run receipts, never game evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import native_product_flow_evidence as gate


def fixture(token='suite-test', pid=100):
    current = dict(character='VOLIBEAR_CHARACTER', seed='VOLIBEAR-PRODUCT-FLOW', hp=80, maxHp=80, gold=99,
        floor=0, act=0, room='MapRoom', energy=None, shouldSave=False,
        deck=[dict(id='VOLIBEAR_'+name, upgrade=0) for name in ['B01']*4+['B02']*4+['B03','B04']],
        relics=['VOLIBEAR_HUNTERS_HEART'])
    events = []
    def add(kind, data):
        events.append(dict(seq=len(events), kind=kind, data=deepcopy(data)))
    add('run-start', current)
    for room in range(5):
        add('map-choice', dict(act=0, fromRow=room-1 if room else None, fromCol=0 if room else None,
            row=room, col=0, type='Monster' if room < 3 else 'Shop' if room == 3 else 'RestSite',
            legal=[dict(row=room, col=0)]))
        current.update(floor=room+1, room='CombatRoom' if room < 3 else 'MerchantRoom' if room == 3 else 'RestSiteRoom')
        add('map-arrived', dict(row=room, col=0, act=0, state=current))
        add('room', current)
        if room < 3:
            current['energy'] = 3
            before = deepcopy(current)
            current['energy'] = 2
            add('paid-action', dict(id='VOLIBEAR_B01', actionId=room+1, type='PlayCardAction', state='Finished',
                context='GameActionPlayerChoiceContext', exception=None, target=1, costBefore=1,
                before=before, after=current, history=dict(plays=[dict(id='VOLIBEAR_B01', autoPlay=False,
                    spent=1, index=0, count=1)], energy=[1])))
            current.update(energy=None, hp=current['hp']-3)
            add('battle-win', dict(number=room+1, encounter='SLIMES_WEAK', state=current))
            if room == 0:
                add('card-reward-choice', dict(available=['VOLIBEAR_C01', 'VOLIBEAR_C02'], selected='VOLIBEAR_C01'))
                before = deepcopy(current)
                current['deck'].append(dict(id='VOLIBEAR_C01', upgrade=0))
                add('reward', dict(type='CardReward', selected=True, nativeSelected=True, before=before, after=current))
        elif room == 3:
            before = deepcopy(current)
            current['gold'] -= 49
            current['deck'].append(dict(id='VOLIBEAR_C02', upgrade=0))
            add('shop', dict(type='MerchantCardEntry', cost=49, stockedBefore=True, bought=True, before=before, after=current))
        else:
            before = deepcopy(current)
            current['hp'] = 80
            add('rest', dict(option='HEAL', index=0, available=[0,1], ok=True, before=before, after=current))
    return dict(schema=1, token=token, pid=pid, gameVersion='0.107.1', gameCommit='59260271',
                scope=gate.SCOPE, osInput=False, simulatedClicks=False, stateFixtures=False, testMode=False,
                rewardDecisionBoundary='NCardRewardSelectionScreen.OptionSelected',
                outcome='completed', error=None, events=events)


class NativeProductFlowOracle(unittest.TestCase):
    def setUp(self):
        self.raw = fixture()

    def data(self, kind):
        return next(e['data'] for e in self.raw['events'] if e['kind'] == kind)

    def evaluate(self, raw=None):
        return gate.check_log(gate.PREFIX+json.dumps(self.raw if raw is None else raw), 'suite-test', 100)

    def test_complete_synthetic_flow_and_coverage(self):
        result = self.evaluate()
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['counts']['battle-win'], 3)
        self.assertEqual(result['counts']['map-arrived'], 5)

    def test_identity_build_scope_no_input_and_outcome_are_strict(self):
        changes = [('schema', True), ('pid', True), ('pid', 101), ('token', 'stale'),
                   ('gameVersion', '0.108.0'), ('gameCommit', 'other'), ('scope', 'fixtures'),
                   ('osInput', True), ('simulatedClicks', True), ('stateFixtures', True), ('testMode', True),
                   ('rewardDecisionBoundary', 'CardSelectCmd.Selector-only'),
                   ('outcome', 'failed'), ('error', 'died')]
        for key, value in changes:
            raw = deepcopy(self.raw); raw[key] = value
            with self.subTest(key=key): self.assertTrue(self.evaluate(raw)['errors'])

    def test_missing_any_required_coverage_fails_even_with_completed_outcome(self):
        for kind in ('run-start', 'paid-action', 'battle-win', 'card-reward-choice', 'reward', 'rest', 'shop', 'map-arrived'):
            raw = deepcopy(self.raw)
            raw['events'] = [e for e in raw['events'] if e['kind'] != kind]
            for i, event in enumerate(raw['events']): event['seq'] = i
            with self.subTest(kind=kind): self.assertTrue(self.evaluate(raw)['errors'])

    def test_paid_action_requires_native_source_history_payment_and_context(self):
        data = self.data('paid-action')
        for key, value in [('state', 'Canceled'), ('type', 'AutoPlayCardAction'),
                           ('context', 'ThrowingPlayerChoiceContext'), ('exception', 'native-error')]:
            previous = data[key]; data[key] = value
            self.assertTrue(self.evaluate()['errors']); data[key] = previous
        data['history']['plays'][0]['autoPlay'] = True
        self.assertTrue(self.evaluate()['errors'])
        data['history']['plays'][0]['autoPlay'] = False
        data['history']['energy'] = []
        self.assertTrue(self.evaluate()['errors'])

    def test_true_free_and_repeated_paid_card_history_are_allowed(self):
        data = self.data('paid-action')
        data['history']['plays'][0].update(count=2)
        second = deepcopy(data['history']['plays'][0]); second['index'] = 1
        data['history']['plays'].append(second)
        self.assertEqual(self.evaluate()['errors'], [])
        for play in data['history']['plays']: play['spent'] = 0
        data['history']['energy'] = []
        self.assertEqual(self.evaluate()['errors'], [])

    def test_reward_card_must_belong_to_offer_and_reach_master_deck(self):
        self.data('card-reward-choice')['selected'] = 'INVENTED_CARD'
        self.assertTrue(self.evaluate()['errors'])
        self.raw = fixture()
        self.data('reward')['after']['deck'] = deepcopy(self.data('reward')['before']['deck'])
        self.assertTrue(self.evaluate()['errors'])
        self.raw = fixture(); self.data('reward')['nativeSelected'] = False
        self.assertTrue(self.evaluate()['errors'])

    def test_shop_success_flag_alone_cannot_replace_gold_and_deck_changes(self):
        self.data('shop')['cost'] += 1
        self.assertTrue(self.evaluate()['errors'])
        self.raw = fixture(); self.data('shop')['after']['deck'] = deepcopy(self.data('shop')['before']['deck'])
        self.assertTrue(self.evaluate()['errors'])

    def test_rest_heal_or_upgrade_must_actually_change_native_state(self):
        data = self.data('rest'); data['after']['hp'] = data['before']['hp']
        self.assertTrue(self.evaluate()['errors'])
        data['option'] = 'SMITH'
        self.assertTrue(self.evaluate()['errors'])
        data['after']['deck'][0]['upgrade'] = 1
        self.assertEqual(self.evaluate()['errors'], [])
        data['index'] = 99
        self.assertTrue(self.evaluate()['errors'])

    def test_illegal_map_vote_and_wrong_arrival_fail(self):
        self.data('map-choice')['legal'] = []
        self.assertTrue(self.evaluate()['errors'])
        self.raw = fixture(); self.data('map-arrived')['col'] = 4
        self.assertTrue(self.evaluate()['errors'])

    def test_starter_deck_hp_relic_and_gold_are_not_fixture_shortcuts(self):
        for field, value in [('hp', 9999), ('gold', 999), ('deck', []), ('relics', ['DEBUG_RELIC']), ('shouldSave', True)]:
            raw = deepcopy(self.raw); raw['events'][0]['data'][field] = value
            with self.subTest(field=field): self.assertTrue(self.evaluate(raw)['errors'])

    def test_broken_json_missing_duplicate_receipt_and_unknown_events_fail(self):
        for log in ('', gate.PREFIX+'{', (gate.PREFIX+json.dumps(self.raw)+'\n')*2):
            self.assertTrue(gate.check_log(log, 'suite-test', 100)['errors'])
        self.raw['events'][1]['kind'] = 'force-victory'
        self.assertTrue(self.evaluate()['errors'])


if __name__ == '__main__': unittest.main()
