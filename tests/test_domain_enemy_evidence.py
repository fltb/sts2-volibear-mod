"""Evidence-gate unit tests, NOT execution of the native mechanism probe."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('domain_enemy_evidence', ROOT / 'tools/domain_enemy_evidence.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
TOKEN = 'domain-enemy-unit-run'


def sample(variant='flutter'):
    # Controlled serialization fixture for exercising the validator; no game claim.
    start = dict(enemyId='1', playerId='0', enemyHp=1000, enemyMaxHp=1000, enemyBlock=0,
                 enemyPower=0, enemyPowerDisplay=0, enemyWeak=0, enemyArtifact=0,
                 playerHp=80, playerMaxHp=80, playerBlock=0, playerPower=0, playerWeak=0,
                 playerArtifact=0, domain=0, round=1, turn=1, active=False,
                 enemyAttached=True, playerAttached=True, samePowerInstance=True)
    ids = dict(player='0', enemy='1')
    rows = []
    for expected in gate.expected_steps(variant):
        item = {key: expected[key] for key in ('id', 'api', 'amount', 'props')}
        item['sourceId'] = None if expected['source'] is None else ids[expected['source']]
        item['targetId'] = ids[expected['target']]
        for phase in ('before', 'after'):
            item[phase] = dict(expected[phase], enemyId='1', playerId='0')
        item['results'] = [] if expected['hit'] is None else [dict(expected['hit'], receiverId=ids[expected['target']])]
        rows.append(item)
    return dict(schema=1, token=TOKEN, scenario='domain-enemy-contract', variant=variant,
                acceptance='mechanism-probe-not-native-enemy-coverage', testMode=False,
                version='v0.107.1', commit='59260271', enemyType='LeafSlimeS',
                fixtureApi='native-PowerCmd+CreatureCmd;starting-LeafSlimeS;no-replaced-actions',
                start=start, steps=rows)


def log(payload):
    return gate.MARKER + json.dumps(payload) + '\n[Volibear] SHUTDOWN_BEGIN ' + TOKEN


class DomainEnemyEvidenceTests(unittest.TestCase):
    def test_all_explicit_variants_accept_well_formed_serialization(self):
        for variant in gate.VARIANTS:
            with self.subTest(variant=variant):
                self.assertEqual(gate.validate(sample(variant), TOKEN, variant), [])
                self.assertTrue(gate.check_log(log(sample(variant)), TOKEN, variant)['passed'])

    def test_known_inputs_and_outcomes_are_fixed(self):
        flutter = sample('flutter')['steps']
        self.assertEqual([r['after']['enemyHp'] for r in flutter], [996, 988])
        self.assertEqual([r['after']['enemyPower'] for r in flutter], [4, 3])
        intangible = sample('intangible')['steps']
        self.assertEqual([r['results'][0]['blocked'] for r in intangible[:2]], [1, 5])
        self.assertEqual([r['results'][0]['hpLost'] for r in intangible[:4]], [0, 5, 1, 10])
        shell = sample('shell')['steps']
        self.assertEqual([r['after']['enemyHp'] for r in shell], [995, 987, 987, 987, 982])
        artifact = sample('artifact')['steps']
        self.assertEqual([r['after']['enemyArtifact'] for r in artifact], [2, 2, 2, 1])
        self.assertEqual([r['after']['enemyWeak'] for r in artifact], [0, 2, 2, 0])
        reflect = sample('reflect')['steps']
        self.assertEqual([r['after']['playerHp'] for r in reflect], [75, 75, 75, 70])
        self.assertEqual(reflect[2]['after']['enemyPower'], 2)
        heal = sample('heal')['steps']
        self.assertEqual(heal[2]['after']['enemyHp'], 507)
        self.assertEqual(heal[3]['after']['playerHp'], 54)

    def test_every_snapshot_numeric_and_boolean_field_is_asserted(self):
        for variant in gate.VARIANTS:
            original = sample(variant)
            for index, row in enumerate(original['steps']):
                for phase in ('before', 'after'):
                    for field, value in row[phase].items():
                        if type(value) not in (bool, int):
                            continue
                        broken = copy.deepcopy(original)
                        broken['steps'][index][phase][field] = not value if type(value) is bool else value + 1
                        with self.subTest(variant=variant, step=index, phase=phase, field=field):
                            self.assertTrue(gate.validate(broken, TOKEN, variant))

    def test_each_native_hit_field_is_asserted(self):
        for variant in gate.VARIANTS:
            original = sample(variant)
            for index, row in enumerate(original['steps']):
                for result in row['results']:
                    for field in result:
                        broken = copy.deepcopy(original)
                        broken['steps'][index]['results'][0][field] = '999' if field == 'receiverId' else result[field] + 1
                        with self.subTest(variant=variant, step=index, field=field):
                            self.assertTrue(gate.validate(broken, TOKEN, variant))

    def test_metadata_and_version_cannot_be_faked_by_passed_flag(self):
        for field in ('schema', 'token', 'scenario', 'variant', 'acceptance', 'testMode',
                      'version', 'commit', 'enemyType', 'fixtureApi'):
            broken = sample()
            broken[field] = 'wrong'
            broken['passed'] = True
            with self.subTest(field=field):
                self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))

    def test_passed_flag_is_never_evidence(self):
        broken = sample()
        broken['passed'] = True
        broken['steps'][1]['after']['enemyHp'] = 992  # incorrect reduction retained inside domain
        self.assertFalse(gate.check_log(log(broken), TOKEN, 'flutter')['passed'])
        correct = sample()
        correct['passed'] = False
        self.assertEqual(gate.validate(correct, TOKEN, 'flutter'), [])

    def test_native_identity_and_source_are_checked(self):
        for field in ('sourceId', 'targetId'):
            broken = sample()
            broken['steps'][0][field] = '999'
            self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))
        for phase in ('before', 'after'):
            for identity in ('enemyId', 'playerId'):
                broken = sample()
                broken['steps'][0][phase][identity] = '999'
                self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))
        broken = sample()
        broken['start']['enemyId'] = '0'
        self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))

    def test_expiry_and_shell_reset_are_not_skippable(self):
        for variant in ('intangible', 'reflect', 'shell'):
            broken = sample(variant)
            broken['steps'] = [r for r in broken['steps'] if r['id'] != 'next-turn']
            self.assertTrue(gate.validate(broken, TOKEN, variant))
        broken = sample('shell')
        broken['steps'][2]['results'][0]['hpLost'] = -8
        self.assertTrue(gate.validate(broken, TOKEN, 'shell'))

    def test_missing_duplicate_and_reordered_steps_fail(self):
        for change in ('missing', 'duplicate', 'reorder'):
            broken = sample()
            if change == 'missing': broken['steps'].pop()
            if change == 'duplicate': broken['steps'].append(broken['steps'][0])
            if change == 'reorder': broken['steps'].reverse()
            self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))

    def test_no_damage_result_or_extra_results_fail(self):
        broken = sample()
        broken['steps'][0]['results'] = []
        self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))
        broken = sample('artifact')
        broken['steps'][0]['results'] = [dict(receiverId='1', hpLost=0, blocked=0, overkill=0)]
        self.assertTrue(gate.validate(broken, TOKEN, 'artifact'))

    def test_bool_is_not_numeric_evidence(self):
        broken = sample()
        broken['steps'][0]['after']['enemyBlock'] = False
        self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))
        broken = sample()
        broken['schema'] = True
        self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))

    def test_malformed_payloads_fail_closed(self):
        for payload in (None, [], 'passed', {}, {'start': []}):
            self.assertTrue(gate.validate(payload, TOKEN, 'flutter'))
        for payload in ('not-json', '[]', 'null'):
            self.assertFalse(gate.check_log(gate.MARKER + payload, TOKEN, 'flutter')['passed'])
        self.assertTrue(gate.validate(sample(), '', 'flutter'))
        self.assertTrue(gate.validate(sample(), TOKEN, 'not-a-case'))

    def test_duplicate_result_and_wrong_shutdown_fail(self):
        text = log(sample())
        for broken in (text + '\n' + text, text.replace('SHUTDOWN_BEGIN ' + TOKEN, 'SHUTDOWN_BEGIN wrong'),
                       text + '\n[Volibear] DOMAIN_ENEMY_ERROR exception', '', text.split('\n')[0]):
            self.assertFalse(gate.check_log(broken, TOKEN, 'flutter')['passed'])

    def test_inputs_not_just_outcomes_checked(self):
        for field, value in [('amount', 9), ('props', 4), ('api', 'DirectPatchCall'), ('id', 'wrong')]:
            broken = sample()
            broken['steps'][0][field] = value
            self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))

    def test_same_power_identity_required_across_domain_toggle(self):
        broken = sample()
        broken['steps'][1]['before']['samePowerInstance'] = False
        self.assertTrue(gate.validate(broken, TOKEN, 'flutter'))


if __name__ == '__main__':
    unittest.main()
