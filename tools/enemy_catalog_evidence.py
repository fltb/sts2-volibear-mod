"""Validate native discovery artifacts, NEVER promote them to enemy action coverage.

The prior locked-source 80-act/85-total/107-monster inventory is a lower-bound
cross-check, not a cap. New discoveries expand the denominator and need review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PREFIX = '[Volibear] ENEMY_CATALOG_RESULT '
POLICY = 'native-registered-acts-plus-registered-event-encounter-references'
ACT_TYPES = {'MegaCrit.Sts2.Core.Models.Acts.' + name
             for name in ('Overgrowth', 'Underdocks', 'Hive', 'Glory')}
MINIMUM_COUNTS = dict(actEncounters=80, eventOnlyEncounters=5, encounters=85, monsters=107)
ID = re.compile(r'^[A-Z_]+\.[A-Z0-9_]+$')


def validate_manifest(data, *, run_id, expected_seed=None):
    try:
        return _validate_manifest(data, run_id=run_id, expected_seed=expected_seed)
    except (TypeError, KeyError, AttributeError, ValueError) as error:
        return ['malformed manifest shape: ' + type(error).__name__]


def _validate_manifest(data, *, run_id, expected_seed=None):
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
        return condition
    if not isinstance(data, dict):
        return ['manifest must be an object']
    for key, expected in dict(schema=1, token=run_id, scenario='enemy-catalog', testMode=False,
                              acceptance='native-source-discovery-only', executionStatus='NOT_RUN',
                              gameVersion='v0.107.1', gameCommit='59260271', sourcePolicy=POLICY).items():
        require(type(data.get(key)) is type(expected) and data.get(key) == expected, key + ' mismatch')
    require(isinstance(data.get('seed'), str) and bool(data.get('seed')), 'missing actual seed')
    if expected_seed is not None:
        require(data.get('seed') == expected_seed, 'seed mismatch')
    for key in ('numericSeed', 'ascension', 'actIndex', 'round'):
        require(type(data.get(key)) is int and data[key] >= 0, 'invalid ' + key)
    for key in ('gameAssemblyMvid', 'modAssemblyMvid'):
        require(isinstance(data.get(key), str) and re.fullmatch(r'[a-fA-F0-9-]{36}', data[key]) is not None,
                'missing loaded assembly identity: ' + key)
    require(isinstance(data.get('baseLibAssemblyVersion'), str) and bool(data['baseLibAssemblyVersion']), 'missing BaseLib version')
    require(isinstance(data.get('godotVersion'), str) and data['godotVersion'].startswith('4.5.1'), 'wrong Godot version')
    require(isinstance(data.get('discoveryLimitations'), list) and len(data['discoveryLimitations']) >= 3,
            'discovery limitations must remain explicit')

    def records(key):
        value = data.get(key)
        if not require(isinstance(value, list) and all(isinstance(row, dict) for row in value), key + ' must be object array'):
            return []
        return value
    acts, events, encounters, monsters, live, unreached = [records(key) for key in
        ('acts', 'events', 'encounters', 'monsters', 'liveInstances', 'unreachedCandidates')]
    def index(rows, name):
        result = {}
        for row in rows:
            identity = row.get('id')
            if not require(isinstance(identity, str) and ID.fullmatch(identity) is not None, name + ': invalid ID'):
                continue
            require(identity not in result, name + ': duplicate ID ' + identity)
            require(isinstance(row.get('type'), str) and row['type'].startswith('MegaCrit.Sts2.Core.Models.'),
                    name + ': non-native type ' + identity)
            result[identity] = row
        return result
    act_map, event_map, enc_map, monster_map = (index(rows, key) for rows, key in
        ((acts, 'acts'), (events, 'events'), (encounters, 'encounters'), (monsters, 'monsters')))
    require({row.get('type') for row in acts} == ACT_TYPES, 'locked native Act registrations mismatch')
    require(data.get('act') in act_map, 'actual fixture Act missing from native registered roots')
    def id_list(value, name):
        if not require(isinstance(value, list) and all(isinstance(item, str) and ID.fullmatch(item) for item in value),
                       name + ': invalid ID list'):
            return set()
        require(len(value) == len(set(value)), name + ': duplicate references')
        return set(value)
    reached_events = id_list(data.get('sharedEventIds'), 'sharedEventIds') | id_list(data.get('sharedAncientIds'), 'sharedAncientIds')
    reached_encounters = set()
    for act in acts:
        reached_encounters |= id_list(act.get('encounters'), 'act.encounters')
        reached_events |= id_list(act.get('events'), 'act.events') | id_list(act.get('ancients'), 'act.ancients')
    require(reached_events == set(event_map), 'registered event roots and event records differ')
    for event in events:
        roots = event.get('registrationSources')
        expected_roots = set()
        if event.get('id') in data.get('sharedEventIds', []):
            expected_roots.add('ModelDb.AllSharedEvents')
        if event.get('id') in data.get('sharedAncientIds', []):
            expected_roots.add('ModelDb.AllSharedAncients')
        for act in acts:
            for field, member in (('events', '.AllEvents'), ('ancients', '.AllAncients')):
                if event.get('id') in act.get(field, []):
                    expected_roots.add(act['id'] + member)
        require(isinstance(roots, list) and bool(roots) and all(isinstance(s, str) for s in roots)
                and set(roots) == expected_roots, 'event lacks exact registration provenance')
        refs = event.get('references')
        if not require(isinstance(refs, list), 'event references missing'):
            continue
        for ref in refs:
            if not require(isinstance(ref, dict), 'invalid event reference'):
                continue
            target, origin = ref.get('encounterId'), ref.get('origin')
            if isinstance(target, str):
                reached_encounters.add(target)
            require(target in enc_map if isinstance(target, str) else False, 'event references absent encounter')
            require(isinstance(origin, dict) and origin.get('sourceId') == event.get('id'), 'event reference has wrong source')
            if isinstance(target, str) and target in enc_map:
                require(origin in enc_map[target].get('origins', []), 'event reference lacks matching encounter provenance')
    require(reached_encounters == set(enc_map), 'source-root encounter closure differs from records')
    formal, act_encounters, model_union = set(), set(), set()
    for encounter in encounters:
        eid = encounter.get('id')
        require(encounter.get('registered') is True, 'unregistered encounter cannot enter formal source graph')
        require(encounter.get('executionStatus') == 'NOT_RUN', 'catalog is not encounter execution evidence')
        debug = encounter.get('isDebug')
        require(type(debug) is bool and encounter.get('included') is (not debug), 'invalid debug exclusion')
        require(encounter.get('exclusionReason') == ('native-IsDebugEncounter=true' if debug else None), 'unproven exclusion reason')
        origins = encounter.get('origins')
        if not require(isinstance(origins, list) and bool(origins), 'encounter lacks source provenance'):
            origins = []
        has_act = False
        for origin in origins:
            if not require(isinstance(origin, dict), 'invalid source provenance'):
                continue
            kind, source, member, offset = (origin.get(k) for k in ('kind', 'sourceId', 'member', 'ilOffset'))
            if kind == 'act':
                has_act = True
                require(source in act_map and eid in act_map[source].get('encounters', []), 'invalid Act source edge')
                require(member == 'ActModel.AllEncounters' and offset is None, 'invalid Act source member')
            elif kind in ('registered-event-canonical', 'registered-event-il-reference'):
                require(source in event_map, 'unregistered event cannot justify encounter')
                if source in event_map:
                    require(any(ref.get('encounterId') == eid and ref.get('origin') == origin
                                for ref in event_map[source].get('references', []) if isinstance(ref, dict)),
                            'event provenance lacks reverse reference')
                if kind.endswith('canonical'):
                    require(member == 'EventModel.CanonicalEncounter' and offset is None, 'invalid canonical source')
                else:
                    require(isinstance(member, str) and '@0x' in member and ' -> ' in member
                            and type(offset) is int and offset >= 0, 'invalid native IL provenance')
            else:
                require(False, 'unsupported reachability proof: ' + str(kind))
        require(encounter.get('bootstrapMode') == ('ACT_ENCOUNTER' if has_act else 'EVENT_SETUP_REQUIRED'), 'wrong fixture setup classification')
        mids = id_list(encounter.get('monsterIds'), 'encounter.monsterIds')
        if not debug and isinstance(eid, str):
            formal.add(eid)
            if has_act:
                act_encounters.add(eid)
            model_union |= mids
    require(model_union == set(monster_map), 'formal encounter monster union differs from denominator')
    require(data.get('fixtureEncounter') in formal, 'live fixture is not a formal source encounter')
    live_ids = set()
    for instance in live:
        cid, mid = instance.get('combatId'), instance.get('modelId')
        require(type(cid) is int and cid >= 0 and cid not in live_ids, 'invalid/duplicate native instance identity')
        if type(cid) is int:
            live_ids.add(cid)
        require(isinstance(mid, str) and mid in monster_map, 'live monster missing from denominator')
        require(instance.get('executionStatus') == 'NOT_RUN' and instance.get('transitionsComplete') is False
                and instance.get('branchesComplete') is False, 'live inspection is not state/action coverage')
        states = instance.get('states')
        if instance.get('stateDiscovery') == 'UNKNOWN':
            require(states is None, 'unknown state discovery cannot invent states')
        else:
            require(instance.get('stateDiscovery') == 'OBSERVED_NATIVE_INSTANCE' and isinstance(states, list), 'invalid live state evidence')
            if isinstance(states, list):
                state_ids = set()
                for state in states:
                    if not require(isinstance(state, dict), 'invalid native state record'):
                        continue
                    sid = state.get('id')
                    require(isinstance(sid, str) and bool(sid) and sid not in state_ids, 'duplicate/invalid state ID')
                    if isinstance(sid, str):
                        state_ids.add(sid)
                    require(type(state.get('isMove')) is bool and state.get('executionStatus') == 'NOT_RUN'
                            and state.get('guard') == 'UNKNOWN_NOT_EVALUATED', 'state execution falsely claimed')
                require(instance.get('initialState') in state_ids and instance.get('currentState') in state_ids
                        and instance.get('nextMove') in state_ids, 'observed default/current move absent from state dictionary')
    for monster in monsters:
        mid = monster.get('id')
        require(monster.get('registered') is True and monster.get('executionStatus') == 'NOT_RUN'
                and monster.get('effectBranches') == 'UNKNOWN' and monster.get('passiveCoverage') == 'NOT_RUN',
                'model discovery must not assert G4 behavior coverage')
        expected_encounters = {eid for eid in formal if mid in enc_map[eid].get('monsterIds', [])}
        require(id_list(monster.get('encounterIds'), 'monster.encounterIds') == expected_encounters, 'monster encounter backlinks differ')
        actual = [item.get('combatId') for item in live if item.get('modelId') == mid]
        require(monster.get('liveInstanceIds') == actual, 'monster instance backlinks differ')
        require(monster.get('stateDiscovery') == ('OBSERVED_NATIVE_INSTANCE' if actual else 'UNKNOWN'), 'uninstantiated model invents state evidence')
    for candidate in unreached:
        require(candidate.get('status') == 'REACHABILITY_UNRESOLVED'
                and candidate.get('reason') == 'not-reached-by-enumerated-native-registration-sources;not-an-automatic-exemption',
                'unreached namespace type cannot silently become exempt')
        require(candidate.get('id') not in model_union | set(enc_map), 'included model also listed unreached')
    expected_counts = dict(acts=len(acts), events=len(events), actEncounters=len(act_encounters),
                           eventOnlyEncounters=len(formal - act_encounters), encounters=len(formal), monsters=len(monster_map),
                           liveInstances=len(live), executedActions=0, verifiedTransitions=0, verifiedBranches=0)
    counts = data.get('counts')
    require(isinstance(counts, dict) and counts == expected_counts and all(type(v) is int for v in counts.values()),
            'counts do not match raw graph (or behavior was falsely counted)')
    for key, minimum in MINIMUM_COUNTS.items():
        require(expected_counts[key] >= minimum, f'{key} below independent locked-source candidate floor {minimum}')
    return errors


def catalog_evidence(log, run_id, evidence_root, *, expected_seed=None):
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        return None, False
    try:
        summary = json.loads(lines[0])
        if not isinstance(summary, dict) or summary.get('manifest') != 'enemy-catalog.json':
            return None, False
        root = Path(evidence_root).resolve()
        path = (root / summary['manifest']).resolve()
        if path.parent != root or not path.is_file():
            return summary, False
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError, TypeError):
        return None, False
    errors = validate_manifest(data, run_id=run_id, expected_seed=expected_seed)
    if not isinstance(data, dict):
        summary['validationErrors'] = errors
        return summary, False
    for key, value in dict(token=run_id, scenario='enemy-catalog', acceptance='native-source-discovery-only',
                           executionStatus='NOT_RUN', gameVersion='v0.107.1', gameCommit='59260271',
                           bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), counts=data.get('counts')).items():
        if type(summary.get(key)) is not type(value) or summary.get(key) != value:
            errors.append('summary mismatch: ' + key)
    summary['validationErrors'] = errors
    summary['priorStaticCandidateCounts'] = MINIMUM_COUNTS
    summary['g4ActionCoverage'] = 'NOT_RUN'
    return summary, not errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--seed')
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        print(json.dumps({'discoveryValid': False, 'error': str(error)}))
        return 1
    errors = validate_manifest(data, run_id=args.run_id, expected_seed=args.seed)
    print(json.dumps({'discoveryValid': not errors, 'counts': data.get('counts') if isinstance(data, dict) else None,
                      'g4ActionCoverage': 'NOT_RUN', 'errors': errors}, ensure_ascii=False))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
