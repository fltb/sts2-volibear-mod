"""Serialization/mutation tests for the evidence gate, NOT native gameplay tests."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('domain_passive_evidence', ROOT / 'tools/domain_passive_evidence.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
TOKEN = 'passive-gate-unit-run'


def sample(case):
    family, mode = case.split('-')
    e = gate.expectations(case)
    ids = dict(ownerId='0', targetId='1')
    result = dict(schema=1, token=TOKEN, scenario='domain-passive-contract', variant=case,
        acceptance='controlled-native-await-mechanism-not-full-enemy-coverage', testMode=False,
        version='v0.107.1', commit='59260271', targetType='LeafSlimeS', fixture='native-SlimesWeak+native-fixture-powers',
        api='PowerCmd+CreatureCmd+PlayerCmd.EndTurn+actual-command-MoveNext-await-boundary',
        directStrengthInput=4, directBlockInput=7, directStrengthResult=4, directBlockResult=7, armedAfter=False)
    for k in ('directBefore', 'directAfter', 'firstTurn', 'secondTurn'): result[k] = dict(e[k], **ids)
    receipt = {k: dict(e[k], **ids) for k in ('before', 'afterYield', 'afterToggle', 'afterNested')}
    receipt.update(stage='after' if mode == 'post' else 'before', amount=3 if family == 'ritual' else 4,
        nestedBlockInput=3, nestedStrengthInput=2, nestedBlockResult=3, nestedStrengthResult=e['afterNested']['strength'])
    result['receipts'] = [receipt]
    blocks = [3] if family == 'ritual' or mode in ('on', 'open') else [4, 3] if mode == 'post' else [3, 4]
    result['blockHistory'] = [dict(targetId='1', amount=x, props=4) for x in blocks]
    if family == 'ritual':
        offsets = [2] if mode in ('on', 'open') else [3, 2] if mode == 'post' else [2, 3]
        result['powerHistory'] = [dict(targetId='1', power='StrengthPower', amount=x, applierId='1') for x in offsets]
    else:
        result['powerHistory'] = [dict(targetId='1', power='PlatingPower', amount=-1, applierId=None),
                                  dict(targetId='1', power='StrengthPower', amount=2, applierId='1')]
    result['history'] = [dict(sourceId='1', type='LeafSlimeS', move='GOOP_MOVE'),
                         dict(sourceId='2', type='TwigSlimeS', move='TACKLE_MOVE'),
                         dict(sourceId='3', type='LeafSlimeM', move='TACKLE_MOVE')]
    return result


def log(p): return gate.MARKER + json.dumps(p) + '\n[Volibear] SHUTDOWN_BEGIN ' + TOKEN


class PassiveEvidenceTests(unittest.TestCase):
    def test_ten_supported_serialized_cases(self):
        for case in gate.VARIANTS:
            with self.subTest(case=case):
                self.assertEqual(gate.validate(sample(case), TOKEN, case), [])
                self.assertTrue(gate.check_log(log(sample(case)), TOKEN, case)['passed'])

    def test_independent_fixed_commit_expectations(self):
        self.assertEqual(gate.expectations('ritual-open')['secondTurn']['strength'], 6)
        self.assertEqual(gate.expectations('ritual-close')['secondTurn']['strength'], 9)
        self.assertEqual(gate.expectations('ritual-post')['before']['strength'], 7)
        self.assertEqual(gate.expectations('ritual-post')['secondTurn']['strength'], 9)
        self.assertEqual(gate.expectations('plating-open')['secondTurn']['block'], 3)
        self.assertEqual(gate.expectations('plating-close')['secondTurn']['block'], 7)
        self.assertEqual(gate.expectations('plating-post')['before']['block'], 4)
        self.assertEqual(gate.expectations('plating-post')['secondTurn']['block'], 7)

    def test_every_controlled_snapshot_field_is_asserted(self):
        for case in gate.VARIANTS:
            original = sample(case)
            locations = [(original, k) for k in ('directBefore', 'directAfter', 'firstTurn', 'secondTurn')]
            locations += [(original['receipts'][0], k) for k in ('before', 'afterYield', 'afterToggle', 'afterNested')]
            for container, key in locations:
                for field, value in list(container[key].items()):
                    container[key][field] = not value if type(value) is bool else value + 1 if type(value) is int else 'wrong'
                    with self.subTest(case=case, phase=key, field=field):
                        self.assertTrue(gate.validate(original, TOKEN, case))
                    container[key][field] = value

    def test_no_receipt_unhit_detour_and_pending_arm_fail(self):
        p = sample('ritual-open'); p['receipts'] = []
        self.assertTrue(gate.validate(p, TOKEN, 'ritual-open'))
        p = sample('plating-open'); p['armedAfter'] = True
        self.assertTrue(gate.validate(p, TOKEN, 'plating-open'))

    def test_nested_unowned_benefits_must_survive(self):
        for case in ('ritual-on', 'ritual-open', 'plating-on', 'plating-open'):
            p = sample(case); p['receipts'][0]['nestedBlockResult'] = 0
            self.assertTrue(gate.validate(p, TOKEN, case))
            p = sample(case); p['receipts'][0]['nestedStrengthResult'] = 4
            self.assertTrue(gate.validate(p, TOKEN, case))

    def test_no_half_commit_history_or_negative_cleanup_loss(self):
        for case in gate.VARIANTS:
            for field in ('blockHistory', 'powerHistory', 'history'):
                p = sample(case); p[field] = []
                self.assertTrue(gate.validate(p, TOKEN, case))
        p = sample('ritual-on')
        p['powerHistory'].append(dict(targetId='1', power='StrengthPower', amount=0, applierId='1'))
        self.assertTrue(gate.validate(p, TOKEN, 'ritual-on'))
        p = sample('plating-on'); p['powerHistory'][0]['amount'] = 0
        self.assertTrue(gate.validate(p, TOKEN, 'plating-on'))

    def test_unsupported_cases_are_not_accepted(self):
        for case in ('curlup-on', 'skittish-on', 'ritual-new-on', 'plating-initial-on'):
            self.assertTrue(gate.validate(sample('ritual-on'), TOKEN, case))

    def test_metadata_token_passed_bool_and_log_rejection(self):
        for field in ('schema', 'token', 'version', 'commit', 'testMode', 'acceptance', 'api', 'fixture'):
            p = sample('ritual-on'); p[field] = 'wrong'; p['passed'] = True
            self.assertFalse(gate.check_log(log(p), TOKEN, 'ritual-on')['passed'])
        good = log(sample('plating-on'))
        for text in ('', good + '\n' + good, good.split('\n')[0], good + '\n[Volibear] DOMAIN_PASSIVE_ERROR fail', gate.MARKER + 'null'):
            self.assertFalse(gate.check_log(text, TOKEN, 'plating-on')['passed'])

    def test_nested_numeric_bool_not_equal(self):
        p = sample('plating-on'); p['receipts'][0]['afterNested']['ritual'] = False
        self.assertTrue(gate.validate(p, TOKEN, 'plating-on'))


if __name__ == '__main__': unittest.main()
