"""Strict native command/receipt/bridge/stream gate. Never claims listening or full-card acceptance."""
import json
import math
import sys

ACCEPTANCE = 'native-receipt/bridge/stream-not-listening'
FIXTURE = 'native-PowerCmd-and-production-move-helpers-not-card-deployment'
POWERS = [('StandingPower', 'armor_retain'), ('ImmovableBodyPower', 'armor_iron'),
          ('ThunderArmorPower', 'thunder_armor'), ('NextAttackDiscount', 'cost_reduce'), ('StrengthPower', 'strength')]
# Thunder Armor's cue belongs to the positive block commit (V18), not to power deployment;
# its deployment rows must stay silent even though the mechanic is exercised here.
DEPLOYMENT_SILENT = {'ThunderArmorPower'}
OPERATIONS = [('new', 0, 2, True), ('increase', 2, 3, True), ('silent', 3, 4, False),
              ('zero', 4, 4, False), ('negative', 4, 3, False), ('silent-new', 0, 2, False)]
FILES = {'armor_retain': ('guard_gain', .63), 'armor_iron': ('guard_hit', .42),
         'thunder_armor': ('lightning_growth', .42), 'cost_reduce': ('energy_gain', .58),
         'strength': ('charge', 1.0), 'card_purify': ('card_purify', .7), 'card_retrieve': ('card_retrieve', .43)}


def expected_steps():
    for model, cue in POWERS:
        for op, before, after, emit in OPERATIONS:
            yield model + ':' + op, model, cue if emit and model not in DEPLOYMENT_SILENT else None, before, after
    yield 'nested-silent-strength', 'StrengthPower', None, 2, 3
    yield 'nested-existing-strength', 'StrengthPower', 'strength', 3, 4
    for name, cue in [('generic-exhaust', None), ('generic-draw', None),
                      ('retrieve-discard', 'card_retrieve'), ('retrieve-draw', 'card_retrieve'),
                      ('retrieve-no-candidate', None), ('purify', 'card_purify')]:
        yield name, None, cue, None, None


def validate_audio_receipts(report, token):
    def need(value):
        if not value: raise ValueError('native audio receipt contract mismatch at line ' + str(sys._getframe(1).f_lineno))
    def integer(v, minimum=1):
        return type(v) is int and v >= minimum
    def number(v):
        return type(v) in (int, float) and math.isfinite(v)
    try:
        need(isinstance(report, dict) and type(report['schema']) is int and report['schema'] == 1)
        need(bool(token) and report['token'] == token and report['acceptance'] == ACCEPTANCE and report['fixture'] == FIXTURE)
        need(report['testMode'] is False and report['forcedUnmute'] is False and report['heard'] is False)
        boundaries = report['runtimeBoundaries']
        need(type(boundaries) is list and [b['method'] for b in boundaries] == ['Apply', 'ModifyAmount'])
        for b in boundaries:
            need(type(b['nativeSignals']) is int and b['nativeSignals'] == 2 and b['closeBeforeSignals'] is True)
            need(type(b['mutationBoundaries']) is int and b['mutationBoundaries'] == 1)
            need(type(b['audioCallsReturningTask']) is int and b['audioCallsReturningTask'] == 0)
            need(type(b['audioEntryPatches']) is int and b['audioEntryPatches'] == 0)
        rows = report['rows']; expected = list(expected_steps())
        need(type(rows) is list and len(rows) == len(expected) == 38)
        seen = set(); nodes = set(); sequences = set(); source = rows[0]['sourceRef']; need(integer(source))
        power_refs = {}; tickets = set(); nested_ref = None; last_sequence = 0
        for row, (name, model, cue, before, after) in zip(rows, expected):
            need(row['id'] == name and row['nativeTaskCompleted'] is True and row['sourceRef'] == source)
            for key in ('powerRef', 'cardRef', 'sourceRef', 'replacementRef'): need(integer(row[key], 0))
            need(number(row['beforeHp']) and number(row['afterHp']) and row['beforeHp'] == row['afterHp'] and row['beforeHp'] > 0)
            need(row['beforeAmount'] == before and row['afterAmount'] == after)
            need(type(row['receipts']) is list and type(row['dispatches']) is list and type(row['frames']) is list)
            if model:
                need(integer(row['powerRef']) and row['cardRef'] == 0 and row['beforePile'] is None and row['afterPile'] is None)
                need(type(row['beforeAmount']) is int and type(row['afterAmount']) is int)
                if name.endswith(':new'): power_refs[model] = row['powerRef']
                elif name.endswith(':silent-new'): need(row['powerRef'] != power_refs[model])
                elif not name.startswith('nested-'): need(row['powerRef'] == power_refs[model])
                frames = row['frames']
                if name == 'nested-silent-strength':
                    # Native generic Apply<T> directly forwards the existing instance AND silent.
                    need([f['power'] for f in frames] == ['VolibearChargeStrengthPower', 'StrengthPower'])
                    need(frames[0]['ticket'] is None and frames[0]['sourceRef'] == 0 and type(frames[0]['sourceRef']) is int and frames[0]['silent'] is None and frames[0]['sameOwner'] is False)
                    need(frames[1]['silent'] is True)
                    nested_ref = row['powerRef']
                    active_frames = frames[1:]
                elif name == 'nested-existing-strength':
                    # Non-generic Apply and inner Modify are separate exact command frames.
                    need(row['powerRef'] == nested_ref)
                    need([f['power'] for f in frames] == ['StrengthPower', 'StrengthPower'])
                    need(all(f['silent'] is False and f['powerRef'] == nested_ref for f in frames))
                    need(frames[0]['ticket'] != frames[1]['ticket'])
                    active_frames = frames
                else:
                    need(len(frames) == 1 and frames[0]['power'] == model)
                    if model in DEPLOYMENT_SILENT:
                        # No cue means no audio ticket; only the native frame identity is required.
                        need(frames[0]['ticket'] is None and frames[0]['silent'] is None)
                        active_frames = []
                    else:
                        need(frames[0]['silent'] is (name.endswith(':silent') or name.endswith(':silent-new')))
                        active_frames = frames
                for frame in active_frames:
                    need(integer(frame['ticket']) and integer(frame['powerRef']) and integer(frame['sourceRef']) and frame['sourceRef'] == source and frame['sameOwner'] is True)
                    need(frame['ticket'] not in tickets); tickets.add(frame['ticket'])
                if active_frames: need(active_frames[-1]['powerRef'] == row['powerRef'])
            else:
                need(row['powerRef'] == 0 and integer(row['cardRef']) and not row['frames'])
                piles = {'generic-exhaust': ('Hand', 'Exhaust'), 'generic-draw': ('Draw', 'Hand'),
                         'retrieve-discard': ('Discard', 'Hand'), 'retrieve-draw': ('Draw', 'Hand'),
                         'retrieve-no-candidate': ('Hand', 'Hand'), 'purify': ('Draw', 'Exhaust')}
                need((row['beforePile'], row['afterPile']) == piles[name])
            if cue is None:
                need(row['receipts'] == [] and row['dispatches'] == [])
                continue
            need(len(row['receipts']) == len(row['dispatches']) == 1)
            receipt, dispatch = row['receipts'][0], row['dispatches'][0]
            need(integer(receipt['id']) and integer(receipt['sourceRef']) and receipt['cue'] == dispatch['cue'] == 'sfx.' + cue)
            need(integer(receipt['powerRef'] if model else receipt['cardRef']))
            kind = 'power' if model else 'card'; need(receipt['kind'] == kind)
            identity = (kind, receipt['id']); need(identity not in seen); seen.add(identity)
            need(receipt['sameOwner'] is True and receipt['sameCombat'] is True)
            need(integer(receipt['sequence']) and integer(dispatch['sequence']))
            need(last_sequence < receipt['sequence'] < dispatch['sequence']); last_sequence = dispatch['sequence']
            for seq in (receipt['sequence'], dispatch['sequence']): need(seq not in sequences); sequences.add(seq)
            if model:
                need(receipt['id'] == row['frames'][-1]['ticket'] and receipt['powerRef'] == row['powerRef'])
                need(receipt['power'] == model and receipt['delta'] == after - before and type(receipt['delta']) is int)
                need(receipt['amount'] == after and type(receipt['amount']) is int and receipt['sourceRef'] == source)
                need(receipt['silent'] is False and receipt['sameApplier'] is True and receipt['registered'] is True)
            else:
                need(receipt['cardRef'] == row['cardRef'] and receipt['pile'] == row['afterPile'])
                if name == 'purify':
                    need(receipt['source'] == 'DomainPower' and integer(receipt['sourceRef']) and receipt['sourceRef'] != source)
                    need(receipt['from'] == 'Hand' and receipt['replacementPile'] == 'Draw')
                    need(integer(row['replacementRef']) and row['replacementRef'] != row['cardRef'] and row['replacementAfter'] == 'Hand')
                else:
                    need(receipt['source'] == 'Volibear_U39' and receipt['sourceRef'] == source)
                    need(receipt['from'] == row['beforePile'] and receipt['replacementPile'] is None)
            prefix = 'power_transaction:' if model else 'card_receipt:'
            need(dispatch['eventId'] == prefix + str(receipt['id']) and dispatch['accepted'] is True)
            for key in ('master', 'sfx', 'ambience', 'effectiveSfx'):
                need(number(dispatch[key]) and 0 <= dispatch[key] <= 1)
            need(type(dispatch['focused']) is bool and type(dispatch['muteInBackground']) is bool)
            master = 0 if not dispatch['focused'] and dispatch['muteInBackground'] else dispatch['master']
            effective = master ** 2 * dispatch['sfx'] ** 2
            need(math.isclose(dispatch['effectiveSfx'], effective, abs_tol=1e-6))
            need(type(dispatch['nodes']) is list and len(dispatch['nodes']) == 1)
            node = dispatch['nodes'][0]
            need(integer(node['nodeId']) and node['nodeId'] not in nodes); nodes.add(node['nodeId'])
            need(node['playing'] is True and node['inTree'] is True and node['streamType'] == 'AudioStreamOggVorbis')
            need(node['cue'] == dispatch['cue'] and node['category'] == 'Sfx' and node['bus'] == 'Master')
            need(type(node['busMuted']) is bool and number(node['busVolumeDb']))
            asset, length = FILES[cue]
            need(node['file'] == 'ogg/' + asset + '.ogg' and number(node['length']) and abs(node['length'] - length) < .05)
            need(node['authoredDb'] == 0 and number(node['authoredDb']) and node['mixDb'] == -3 and number(node['mixDb']))
            need(node['headroomDb'] == 6 and number(node['headroomDb']) and integer(node['voiceDivisor']))
            gain = effective * 10 ** (-9 / 20) / node['voiceDivisor']
            need(number(node['volumeLinear']) and math.isclose(node['volumeLinear'], gain, rel_tol=1e-5, abs_tol=1e-7))
        need(len(seen) == len(nodes) == 12)
        # Search/recovery must return the very same entity, not a replacement clone.
        by_id = {r['id']: r for r in rows}
        need(len({by_id[n]['cardRef'] for n in ('generic-draw', 'retrieve-discard', 'retrieve-draw', 'retrieve-no-candidate')}) == 1)
        return True
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return False


def audio_receipt_evidence(log, token):
    if 'AUDIO_RECEIPT_FAILED' in log: return None, False
    lines = [line.split('AUDIO_RECEIPT_RESULT ', 1)[1] for line in log.splitlines() if 'AUDIO_RECEIPT_RESULT ' in line]
    if len(lines) != 1: return None, False
    try: report = json.loads(lines[0])
    except (ValueError, TypeError): return None, False
    return report, validate_audio_receipts(report, token)

