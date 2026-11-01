"""Adversarial synthetic oracle checks; these are NOT Hopper native acceptance runs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from domain_hopper_evidence import VARIANTS, PREFIX, ACCEPTANCE, domain_hopper_evidence, validate


def fixture(case):
    baseline = dict(cRef='C', mRef='M', cMasterRef='M', cOwnerRef='P', mOwnerRef='P',
                    cModel='Volibear_B01', mModel='Volibear_B01', cUpgrade=False, mUpgrade=False,
                    cPile='Draw', mPile='Deck', cRemoved=False, mRemoved=False, masterInDeck=1,
                    registryOccurrences=1, rewardMasterRefs=[], loot=0, cardsRemovedHistory=0,
                    listRefs=[], swipes=[], capturedSwipeRef='null', capturedStolenRef='null',
                    playerHp=80, playerBlock=0, domain=0, hopperHp=79, hopperAttached=True, guardAttached=True)
    c_only = dict(cPile='None', cRemoved=True, listRefs=['C'])
    stolen = dict(**c_only, mPile='None', mRemoved=True, masterInDeck=0, loot=1,
                  cardsRemovedHistory=1, capturedSwipeRef='S', capturedStolenRef='C')
    swipe = dict(swipeRef='S', stolenRef='C', targetRef='OWNER', ownerRef='HOPPER')
    after = deepcopy(baseline); after['playerHp'] = 63
    if case == 'on':
        after['domain'] = 5
    elif case == 'c-wait-open':
        after.update(c_only, domain=5)
    elif case == 'master-hook-open':
        after.update(c_only, domain=5, cardsRemovedHistory=1, capturedSwipeRef='S', capturedStolenRef='C')
    else:
        after.update(stolen, swipes=[swipe])
        if case == 'master-committed-open':
            after['domain'] = 5
    rows = [dict(point='baseline', state=baseline), dict(point='after-theft', state=after)]
    windows = []
    points = {
        'on': 'before-native-ThieveryMove',
        'c-wait-open': 'native-C-completed-0.6wait-pending',
        'master-hook-open': 'native-BeforeCardRemoved-completed-before-M-pile',
        'master-committed-open': 'native-Steal-completed-before-Swipe-mount',
        'mounted-domain-death': 'after-native-Swipe-mounted-before-death',
    }
    if case in points:
        before = deepcopy(baseline)
        if case != 'on':
            before.update(c_only)
        if case == 'master-hook-open':
            before['cardsRemovedHistory'] = 1
        if case in ('master-committed-open', 'mounted-domain-death'):
            before.update(stolen)
        if case == 'mounted-domain-death':
            before.update(playerHp=63, swipes=[swipe])
        end = deepcopy(before); end['domain'] = 5
        pending = True if case == 'c-wait-open' else (None if case in ('on', 'mounted-domain-death') else False)
        windows.append(dict(point=points[case], nativePending=pending, before=before, after=end))
    if case in ('off-death', 'mounted-domain-death'):
        death = deepcopy(after)
        death.update(domain=5 if case == 'mounted-domain-death' else 0, mRemoved=False,
                     loot=0, swipes=[], rewardMasterRefs=['M'], hopperHp=0, hopperAttached=False)
        rows.append(dict(point='after-death', state=death))
    elif case == 'escape':
        escape = deepcopy(after); escape.update(playerHp=28, hopperAttached=False, swipes=[])
        rows.append(dict(point='after-escape', state=escape))
    moves = ['THIEVERY_MOVE'] + (['FLUTTER_MOVE', 'HAT_TRICK_MOVE', 'NAB_MOVE', 'ESCAPE_MOVE'] if case == 'escape' else [])
    return dict(schema=1, token='run', scenario='domain-hopper', variant=case, completed=True,
                version='v0.107.1', commit='59260271', testMode=False, encounter='ThievingHopperWeak', ascension=0,
                acceptance=ACCEPTANCE, playerRef='P', ownerRef='OWNER', hopperRef='HOPPER', playerId='1', hopperId='2',
                snapshots=rows, windows=windows,
                deathCallbacks=[dict(swipeRef='S', targetRef='HOPPER', stolenRef='C', masterRef='M', nativeCompleted=True,
                                     hopperHp=0, domain=5 if case == 'mounted-domain-death' else 0)]
                               if case in ('off-death', 'mounted-domain-death') else [],
                moves=[dict(sourceId='2', move=move) for move in moves],
                damage=[dict(sourceId='2', receiverId='1', hpLost=n, blocked=0, overkill=0)
                        for n in ([17, 21, 14] if case == 'escape' else [17])])


class DomainHopperEvidenceTests(unittest.TestCase):
    def reject(self, value, case):
        result, valid = domain_hopper_evidence(PREFIX + json.dumps(value), 'run', case)
        self.assertFalse(valid, result)

    def test_all_eight_independent_expected_paths(self):
        for case in VARIANTS:
            with self.subTest(case=case):
                self.assertTrue(validate(fixture(case), 'run', case))
                self.assertTrue(domain_hopper_evidence(PREFIX + json.dumps(fixture(case)), 'run', case)[1])

    def test_all_required_top_fields_and_snapshot_fields(self):
        for case in VARIANTS:
            value = fixture(case)
            for key in value:
                bad = deepcopy(value); del bad[key]
                with self.subTest(case=case, field=key): self.reject(bad, case)
            for index, row in enumerate(value['snapshots']):
                for key in row['state']:
                    bad = deepcopy(value); del bad['snapshots'][index]['state'][key]
                    with self.subTest(case=case, snapshot=index, field=key): self.reject(bad, case)

    def test_actual_attack_cannot_disappear_or_change_source(self):
        for case in VARIANTS:
            for mutation in ('omit', 'source', 'damage', 'bool', 'extra'):
                value = fixture(case)
                if mutation == 'omit': value['damage'] = []
                elif mutation == 'source': value['damage'][0]['sourceId'] = 'guard'
                elif mutation == 'damage': value['damage'][0]['hpLost'] = 0
                elif mutation == 'bool': value['damage'][0]['blocked'] = False
                else: value['moves'].append(dict(sourceId='2', move='THIEVERY_MOVE'))
                with self.subTest(case=case, mutation=mutation): self.reject(value, case)

    def test_no_false_master_debt_swipe_or_loot_on_cancellation(self):
        for case in ('on', 'c-wait-open', 'master-hook-open'):
            for key, wrong in (('mRemoved', True), ('masterInDeck', 0), ('loot', 1),
                               ('swipes', [dict(swipeRef='S', stolenRef='C', targetRef='OWNER', ownerRef='HOPPER')]),
                               ('rewardMasterRefs', ['M'])):
                value = fixture(case); value['snapshots'][1]['state'][key] = wrong
                with self.subTest(case=case, field=key): self.reject(value, case)

    def test_post_hook_residual_history_and_combat_loss_not_erased(self):
        for key, wrong in (('cardsRemovedHistory', 0), ('cRemoved', False), ('cPile', 'Draw'), ('capturedStolenRef', 'null')):
            value = fixture('master-hook-open'); value['snapshots'][1]['state'][key] = wrong
            with self.subTest(field=key): self.reject(value, 'master-hook-open')

    def test_committed_death_returns_same_master_once_without_deck_duplication(self):
        for case in ('off-death', 'mounted-domain-death'):
            for key, wrong in (('rewardMasterRefs', ['clone']), ('rewardMasterRefs', ['M', 'M']),
                               ('masterInDeck', 1), ('registryOccurrences', 2), ('mRemoved', True),
                               ('loot', 1), ('hopperAttached', True), ('capturedSwipeRef', 'different')):
                value = fixture(case); value['snapshots'][-1]['state'][key] = wrong
                with self.subTest(case=case, field=key, wrong=wrong): self.reject(value, case)

    def test_native_death_callback_cannot_be_missing_or_replaced(self):
        for case in ('off-death', 'mounted-domain-death'):
            for key, wrong in (('masterRef', 'clone'), ('swipeRef', 'unrelated'), ('targetRef', 'guard'), ('nativeCompleted', False)):
                value = fixture(case); value['deathCallbacks'][0][key] = wrong
                with self.subTest(case=case, field=key): self.reject(value, case)
            value = fixture(case); value['deathCallbacks'] = []; self.reject(value, case)

    def test_escape_not_fake_death_or_return(self):
        for key, wrong in (('rewardMasterRefs', ['M']), ('mRemoved', False), ('loot', 0), ('hopperHp', 0), ('swipes', [dict()])):
            value = fixture('escape'); value['snapshots'][-1]['state'][key] = wrong
            with self.subTest(field=key): self.reject(value, 'escape')

    def test_precise_window_and_reference_identity_required(self):
        for case in ('on', 'c-wait-open', 'master-hook-open', 'master-committed-open', 'mounted-domain-death'):
            for field, wrong in (('point', 'wrong-boundary'), ('nativePending', 'false')):
                value = fixture(case); value['windows'][0][field] = wrong
                with self.subTest(case=case, field=field): self.reject(value, case)
            value = fixture(case); value['windows'][0]['before']['mRef'] = 'equal-but-other-master'
            self.reject(value, case)

    def test_duplicate_missing_wrong_run_and_fake_success_rejected(self):
        good = PREFIX + json.dumps(fixture('off'))
        for log in ('', good + '\n' + good, PREFIX + '{"passed":true}', PREFIX + 'not-json'):
            self.assertFalse(domain_hopper_evidence(log, 'run', 'off')[1])
        self.assertFalse(domain_hopper_evidence(good, 'other-run', 'off')[1])
        self.assertFalse(domain_hopper_evidence(good, 'run', 'on')[1])


if __name__ == '__main__': unittest.main()
