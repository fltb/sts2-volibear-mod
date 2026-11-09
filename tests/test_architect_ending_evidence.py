import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from architect_ending_evidence import MARKER, check_log, validate


def fixture():
    return dict(schema=1, token='unit-architect', scenario='architect-ending', fixture='isolated-architect-events-not-full-run',
        version='v0.107.1', commit='59260271', testMode=False, passed=True, cases=[
            dict(family='volibear', character='VolibearCharacter', optionsChosen=4,
                 before=dict(hp=37, wins=0, saved=True),
                 after=dict(hp=37, wins=1, saved=False, gameOver=True, victoryRoom=True, screen='NGameOverScreen', deaths=0, domainEntries=1),
                 records=dict(victoryCalls=1, lossCalls=0, originalSnapshot=True),
                 visual=dict(entered=True, shader=True, arcs=12, scaleRatio=1.22, animation='domain_idle')),
            dict(family='ironclad', character='Ironclad', optionsChosen=2,
                 before=dict(hp=80, wins=1, saved=True),
                 after=dict(hp=0, wins=2, saved=False, gameOver=True, victoryRoom=True, screen='NGameOverScreen', deaths=1, domainEntries=0),
                 records=dict(victoryCalls=1, lossCalls=1, originalSnapshot=False),
                 visual=dict(entered=False, shader=False, arcs=0, scaleRatio=1, animation=''))])


class ArchitectEndingEvidenceTests(unittest.TestCase):
    def test_independent_synthetic_shapes(self):
        self.assertEqual(validate(fixture(), 'unit-architect'), [])
        self.assertEqual(check_log(MARKER + json.dumps(fixture()), 'unit-architect'), dict(errors=[], passed=True, cases=2))

    def test_behavior_and_persistence_mutations(self):
        mutations = [
            (0, 'after', 'hp', 0), (0, 'after', 'deaths', 1), (0, 'after', 'domainEntries', 0),
            (0, 'after', 'gameOver', False), (0, 'after', 'victoryRoom', False),
            (0, 'after', 'screen', 'FakeScreen'), (0, 'after', 'wins', 0), (0, 'after', 'saved', True),
            (0, 'records', 'victoryCalls', 2), (0, 'records', 'lossCalls', 1), (0, 'records', 'originalSnapshot', False),
            (0, 'visual', 'shader', False), (0, 'visual', 'arcs', 11), (0, 'visual', 'scaleRatio', 1),
            (0, 'visual', 'animation', 'die'), (0, 'visual', 'entered', False), (0, 'before', 'saved', False),
            (1, 'after', 'hp', 80), (1, 'after', 'deaths', 0), (1, 'after', 'domainEntries', 1),
            (1, 'records', 'lossCalls', 0), (1, 'before', 'wins', 99), (1, 'visual', 'entered', True),
        ]
        for index, section, key, value in mutations:
            with self.subTest(index=index, section=section, key=key):
                p = fixture(); p['cases'][index][section][key] = value
                self.assertTrue(validate(p, 'unit-architect'))

    def test_scope_types_and_missing_control(self):
        for key, value in [('schema', True), ('token', 'old'), ('version', 'old'), ('commit', 'old'), ('testMode', True), ('fixture', 'full-run')]:
            p = fixture(); p[key] = value
            self.assertTrue(validate(p, 'unit-architect'))
        p = fixture(); p['cases'].pop(); self.assertTrue(validate(p, 'unit-architect'))
        for value in (True, float('nan'), float('inf')):
            p = fixture(); p['cases'][0]['visual']['scaleRatio'] = value
            self.assertTrue(validate(p, 'unit-architect'))
        p = fixture(); p['cases'][0]['after']['deaths'] = False
        self.assertTrue(validate(p, 'unit-architect'))

    def test_log_isolation_and_duplicates(self):
        line = MARKER + json.dumps(fixture())
        for text, token in [(line, 'old'), (line + '\n' + line, 'unit-architect'),
                (MARKER + '{', 'unit-architect'), (line + '\nARCHITECT_ENDING_ERROR fail', 'unit-architect'),
                (MARKER + '{"token":"unit-architect","token":"unit-architect"}', 'unit-architect')]:
            self.assertTrue(check_log(text, token)['errors'])
