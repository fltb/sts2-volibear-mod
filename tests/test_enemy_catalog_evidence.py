"""Synthetic catalog-validator tests. No native enemies or actions execute here."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enemy_catalog_evidence as evidence


def manifest():
    acts = [dict(id='ACT.' + name.upper(), type='MegaCrit.Sts2.Core.Models.Acts.' + name,
                 encounters=[], events=[], ancients=[])
            for name in ('Overgrowth', 'Underdocks', 'Hive', 'Glory')]
    events = [dict(id='EVENT.EVENT_' + str(i), type='MegaCrit.Sts2.Core.Models.Events.Example' + str(i),
                   registrationSources=['ModelDb.AllSharedEvents'], references=[]) for i in range(5)]
    encounters = []
    for i in range(85):
        eid = 'ENCOUNTER.ENCOUNTER_' + str(i)
        if i < 80:
            act = acts[i % 4]
            act['encounters'].append(eid)
            origin = dict(kind='act', sourceId=act['id'], member='ActModel.AllEncounters', ilOffset=None)
        else:
            event = events[i - 80]
            origin = dict(kind='registered-event-il-reference', sourceId=event['id'],
                          member='Example.MoveNext@0x06000001 -> EventModel.EnterCombatWithoutExitingEvent', ilOffset=10)
            event['references'].append(dict(encounterId=eid, origin=copy.deepcopy(origin)))
        mids = ['MONSTER.MONSTER_' + str(i)]
        if i == 0:
            mids += ['MONSTER.MONSTER_' + str(j) for j in range(85, 107)]
        encounters.append(dict(id=eid, type='MegaCrit.Sts2.Core.Models.Encounters.Example' + str(i),
            registered=True, isDebug=False, included=True, exclusionReason=None, roomType='Monster',
            origins=[origin], monsterIds=mids, executionStatus='NOT_RUN',
            bootstrapMode='ACT_ENCOUNTER' if i < 80 else 'EVENT_SETUP_REQUIRED'))
    monsters = [dict(id='MONSTER.MONSTER_' + str(i), type='MegaCrit.Sts2.Core.Models.Monsters.Example' + str(i),
        registered=True, encounterIds=['ENCOUNTER.ENCOUNTER_' + str(i if i < 85 else 0)],
        liveInstanceIds=[1] if i == 0 else [], stateDiscovery='OBSERVED_NATIVE_INSTANCE' if i == 0 else 'UNKNOWN',
        executionStatus='NOT_RUN', effectBranches='UNKNOWN', passiveCoverage='NOT_RUN') for i in range(107)]
    state = dict(id='TACKLE_MOVE', type='MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState',
        isMove=True, configuredFollowUp='TACKLE_MOVE', mustPerformOnce=False, actionMethod='Example.Tackle',
        intentTypes=['AttackIntent'], guard='UNKNOWN_NOT_EVALUATED', executionStatus='NOT_RUN')
    return dict(schema=1, token='current', scenario='enemy-catalog', testMode=False,
        acceptance='native-source-discovery-only', executionStatus='NOT_RUN', gameVersion='v0.107.1', gameCommit='59260271',
        gameAssemblyMvid='12345678-1234-1234-1234-123456789abc', modAssemblyMvid='abcdef12-1234-1234-1234-123456789abc',
        baseLibAssemblyVersion='3.4.7.0', baseLibInformationalVersion='3.4.7', godotVersion='4.5.1.stable.mono',
        seed='VOLIBEARTEST', numericSeed=123, ascension=0, act='ACT.OVERGROWTH', actIndex=0,
        fixtureEncounter='ENCOUNTER.ENCOUNTER_0', round=1, sourcePolicy=evidence.POLICY,
        discoveryLimitations=['guards unknown', 'indirect references need review', 'not action coverage'],
        acts=acts, events=events, sharedEventIds=[event['id'] for event in events], sharedAncientIds=[],
        encounters=encounters, monsters=monsters,
        liveInstances=[dict(combatId=1, modelId=monsters[0]['id'], type=monsters[0]['type'], hp=12, block=0,
            initialState='TACKLE_MOVE', currentState='TACKLE_MOVE', nextMove='TACKLE_MOVE', states=[state],
            stateDiscovery='OBSERVED_NATIVE_INSTANCE', powers=[], executionStatus='NOT_RUN',
            transitionsComplete=False, branchesComplete=False)],
        unreachedCandidates=[dict(id='MONSTER.MOCK', type='MegaCrit.Sts2.Core.Models.Monsters.Mock', category='monster',
            registered=False, status='REACHABILITY_UNRESOLVED',
            reason='not-reached-by-enumerated-native-registration-sources;not-an-automatic-exemption')],
        counts=dict(acts=4, events=5, actEncounters=80, eventOnlyEncounters=5, encounters=85, monsters=107,
                    liveInstances=1, executedActions=0, verifiedTransitions=0, verifiedBranches=0))


class EnemyCatalogEvidenceTests(unittest.TestCase):
    def check(self, data):
        return evidence.validate_manifest(data, run_id='current', expected_seed='VOLIBEARTEST')

    def test_consistent_synthetic_graph_is_discovery_only(self):
        data = manifest()
        self.assertEqual(self.check(data), [])
        self.assertEqual(data['counts']['executedActions'], 0)
        self.assertEqual(data['executionStatus'], 'NOT_RUN')

    def test_missing_root_nodes_models_and_event_only_encounters_fail(self):
        for collection in ('acts', 'events', 'encounters', 'monsters', 'liveInstances'):
            data = manifest()
            data[collection].pop()
            self.assertTrue(self.check(data), collection)
        data = manifest()
        data['events'][0]['references'].clear()
        self.assertTrue(self.check(data))
        data = manifest()
        data['encounters'][-1]['origins'][0]['sourceId'] = 'EVENT.UNREGISTERED'
        self.assertTrue(self.check(data))

    def test_gameplay_pass_claims_and_guessed_states_are_rejected(self):
        for mutate in (lambda d: d.__setitem__('executionStatus', 'PASS'),
                       lambda d: d['monsters'][0].__setitem__('executionStatus', 'PASS'),
                       lambda d: d['monsters'][1].__setitem__('stateDiscovery', 'OBSERVED_NATIVE_INSTANCE'),
                       lambda d: d['counts'].__setitem__('executedActions', 1),
                       lambda d: d['liveInstances'][0].__setitem__('branchesComplete', True),
                       lambda d: d['liveInstances'][0]['states'][0].__setitem__('executionStatus', 'PASS'),
                       lambda d: d['liveInstances'][0]['states'][0].__setitem__('guard', 'always'),
                       lambda d: d['unreachedCandidates'][0].__setitem__('status', 'NOT_APPLICABLE')):
            data = manifest()
            mutate(data)
            self.assertTrue(self.check(data))

    def test_version_seed_token_provenance_and_counts_are_bound(self):
        for key, value in dict(token='stale', gameVersion='v0.107.2', gameCommit='wrong', seed='OTHER',
                               testMode=True, sourcePolicy='namespace-class-count', godotVersion='4.6').items():
            data = manifest()
            data[key] = value
            self.assertTrue(self.check(data), key)
        data = manifest()
        data['events'][0]['registrationSources'] = ['invented']
        self.assertTrue(self.check(data))
        data = manifest()
        data['counts']['verifiedBranches'] = False
        self.assertTrue(self.check(data))

    def test_new_native_discovery_expands_not_caps_denominator(self):
        data = manifest()
        data['encounters'][0]['monsterIds'].append('MONSTER.NEW_DISCOVERY')
        new = copy.deepcopy(data['monsters'][-1])
        new.update(id='MONSTER.NEW_DISCOVERY', type='MegaCrit.Sts2.Core.Models.Monsters.NewDiscovery')
        data['monsters'].append(new)
        data['counts']['monsters'] = 108
        self.assertEqual(self.check(data), [])

    def test_malformed_nested_payloads_fail_closed(self):
        for key in manifest():
            data = manifest()
            data[key] = None
            if key == 'baseLibInformationalVersion':
                continue  # Assembly informational metadata can legitimately be absent.
            self.assertTrue(self.check(data), key)
        data = manifest()
        data['encounters'][0]['origins'][0]['sourceId'] = []
        self.assertTrue(self.check(data))

    def test_single_artifact_hash_token_and_summary_must_agree(self):
        data = manifest()
        raw = (json.dumps(data) + '\n').encode()
        summary = dict(token='current', scenario='enemy-catalog', acceptance='native-source-discovery-only',
            executionStatus='NOT_RUN', manifest='enemy-catalog.json', sha256=hashlib.sha256(raw).hexdigest(),
            bytes=len(raw), counts=data['counts'], gameVersion='v0.107.1', gameCommit='59260271')
        line = evidence.PREFIX + json.dumps(summary)
        with mock.patch.object(Path, 'is_file', return_value=True), mock.patch.object(Path, 'read_bytes', return_value=raw):
            result, valid = evidence.catalog_evidence(line, 'current', Path.cwd(), expected_seed='VOLIBEARTEST')
            self.assertTrue(valid, result)
            self.assertEqual(result['g4ActionCoverage'], 'NOT_RUN')
            self.assertFalse(evidence.catalog_evidence(line, 'stale', Path.cwd())[1])
            self.assertFalse(evidence.catalog_evidence(line + '\n' + line, 'current', Path.cwd())[1])
            summary['sha256'] = '0' * 64
            self.assertFalse(evidence.catalog_evidence(evidence.PREFIX + json.dumps(summary), 'current', Path.cwd())[1])
        summary['manifest'] = '../enemy-catalog.json'
        self.assertFalse(evidence.catalog_evidence(evidence.PREFIX + json.dumps(summary), 'current', Path.cwd())[1])


if __name__ == '__main__':
    unittest.main()
