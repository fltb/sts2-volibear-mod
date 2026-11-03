"""Independent gate mutations and real observer IL emission; synthetic rows are NOT native evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
sys.path.insert(0, str(ROOT / 'tools'))
import audio_receipt_evidence as gate


def sample(muted=False):
    report = dict(schema=1, token='fresh', acceptance=gate.ACCEPTANCE, fixture=gate.FIXTURE,
                  testMode=False, forcedUnmute=False, heard=False, rows=[], runtimeBoundaries=[
                      dict(method=name, nativeSignals=2, closeBeforeSignals=True, mutationBoundaries=1,
                           audioCallsReturningTask=0, audioEntryPatches=0) for name in ('Apply', 'ModifyAmount')])
    refs = {name: 10 + i for i, (name, _) in enumerate(gate.POWERS)}
    for i, (name, model, cue, before, after) in enumerate(gate.expected_steps()):
        power = (70 if name.startswith('nested-') else refs[model] + (20 if name.endswith(':silent-new') else 0)) if model else 0
        row = dict(id=name, powerRef=power, cardRef=0 if model else (90 if name == 'generic-exhaust' else 92 if name == 'purify' else 91),
                   sourceRef=1, replacementRef=93 if name == 'purify' else 0, beforeAmount=before, afterAmount=after,
                   beforePile=None, afterPile=None, replacementAfter='Hand' if name == 'purify' else None,
                   beforeHp=80, afterHp=80, nativeTaskCompleted=True, receipts=[], dispatches=[], frames=[])
        ticket = 100 + i * 3
        if model:
            row['frames'] = [dict(power=model, powerRef=power, ticket=ticket,
                silent=name.endswith(':silent') or name.endswith(':silent-new'), sourceRef=1, sameOwner=True)]
            if name == 'nested-silent-strength':
                row['frames'][0]['silent'] = True
                row['frames'] = [dict(power='VolibearChargeStrengthPower', powerRef=71, ticket=None, silent=None, sourceRef=0, sameOwner=False)] + row['frames']
            elif name == 'nested-existing-strength':
                row['frames'] = [dict(power='StrengthPower', powerRef=power, ticket=ticket-1, silent=False, sourceRef=1, sameOwner=True)] + row['frames']
        else:
            row['beforePile'], row['afterPile'] = {'generic-exhaust': ('Hand', 'Exhaust'), 'generic-draw': ('Draw', 'Hand'),
                'retrieve-discard': ('Discard', 'Hand'), 'retrieve-draw': ('Draw', 'Hand'),
                'retrieve-no-candidate': ('Hand', 'Hand'), 'purify': ('Draw', 'Exhaust')}[name]
        if cue:
            receipt = dict(sequence=2*i+1, kind='power' if model else 'card', id=ticket, cue='sfx.'+cue, sameOwner=True, sameCombat=True)
            if model:
                receipt.update(powerRef=power, power=model, delta=after-before, amount=after, silent=False, sourceRef=1, sameApplier=True, registered=True)
            else:
                receipt.update(cardRef=row['cardRef'], sourceRef=99 if name == 'purify' else 1,
                    source='DomainPower' if name == 'purify' else 'Volibear_U39',
                    **{'from': 'Hand' if name == 'purify' else row['beforePile']}, pile=row['afterPile'],
                    replacementPile='Draw' if name == 'purify' else None)
            effective = 0 if muted else .6**2 * .5**2
            asset, duration = gate.FILES[cue]
            node = dict(nodeId=200+i, playing=True, inTree=True, streamType='AudioStreamOggVorbis', length=duration,
                bus='Master', busMuted=False, busVolumeDb=0, volumeLinear=effective*10**(-9/20), file='ogg/'+asset+'.ogg', cue='sfx.'+cue,
                category='Sfx', authoredDb=0, mixDb=-3, headroomDb=6, voiceDivisor=1)
            dispatch = dict(sequence=2*i+2, eventId=('power_transaction:' if model else 'card_receipt:')+str(ticket),
                cue='sfx.'+cue, accepted=True, master=.6, sfx=.5, ambience=.4, focused=not muted,
                muteInBackground=muted, effectiveSfx=effective, nodes=[node])
            row['receipts']=[receipt]; row['dispatches']=[dispatch]
        report['rows'].append(row)
    return report


class AudioReceiptEvidenceTests(unittest.TestCase):
    def test_synthetic_valid_and_background_muted_are_not_heard(self):
        for muted in (False, True):
            report = sample(muted)
            self.assertTrue(gate.validate_audio_receipts(report, 'fresh'))
            text = '[Volibear] AUDIO_RECEIPT_RESULT ' + json.dumps(report)
            self.assertTrue(gate.audio_receipt_evidence(text, 'fresh')[1])
            for malformed in ('', text + '\n' + text, text + '\nAUDIO_RECEIPT_FAILED fresh error',
                              'AUDIO_RECEIPT_RESULT {broken', text + ' trailing'):
                self.assertFalse(gate.audio_receipt_evidence(malformed, 'fresh')[1])
            self.assertFalse(gate.audio_receipt_evidence(text, 'stale')[1])

    def test_negative_rows_identity_volume_and_stream_claims(self):
        baseline = sample()
        for key, value in [('token', 'old'), ('schema', True), ('testMode', True), ('forcedUnmute', True),
                           ('heard', True), ('fixture', 'generic-draw-inferred'), ('acceptance', 'heard')]:
            bad = copy.deepcopy(baseline); bad[key] = value
            self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'), key)
        for i, row in enumerate(baseline['rows']):
            bad = copy.deepcopy(baseline); del bad['rows'][i]
            self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
            bad = copy.deepcopy(baseline); bad['rows'][i]['nativeTaskCompleted'] = False
            self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
            if not row['receipts']:
                bad = copy.deepcopy(baseline); bad['rows'][i]['receipts'] = copy.deepcopy(baseline['rows'][0]['receipts'])
                self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
                continue
            for container, field, value in [('receipts', 'id', True), ('receipts', 'sameOwner', False),
                    ('receipts', 'sameCombat', False), ('receipts', 'cue', 'sfx.feral_aura'),
                    ('dispatches', 'accepted', False), ('dispatches', 'eventId', 'invented'),
                    ('dispatches', 'cue', 'sfx.card_draw'), ('dispatches', 'effectiveSfx', float('nan')),
                    ('dispatches', 'effectiveSfx', 1), ('dispatches', 'master', True)]:
                bad = copy.deepcopy(baseline); bad['rows'][i][container][0][field] = value
                self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'), (i, container, field))
            for field, value in [('nodeId', True), ('playing', False), ('inTree', False), ('streamType', 'Missing'),
                    ('length', 0), ('file', 'ogg/wrong.ogg'), ('volumeLinear', 1), ('volumeLinear', False),
                    ('voiceDivisor', True), ('headroomDb', 0), ('authoredDb', 1), ('bus', 'Unmuted')]:
                bad = copy.deepcopy(baseline); bad['rows'][i]['dispatches'][0]['nodes'][0][field] = value
                self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'), (i, field))
            for container in ('receipts', 'dispatches'):
                bad = copy.deepcopy(baseline); bad['rows'][i][container] *= 2
                self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
        for name, field, value in [('nested-existing-strength', 'powerRef', 999), ('purify', 'replacementAfter', 'Draw'),
                                 ('retrieve-draw', 'cardRef', 999)]:
            bad = copy.deepcopy(baseline); next(r for r in bad['rows'] if r['id'] == name)[field] = value
            self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
        for field, value in [('from', 'Exhaust'), ('pile', 'Hand'), ('replacementPile', 'Hand'), ('source', 'StatusCard')]:
            bad = copy.deepcopy(baseline); bad['rows'][-1]['receipts'][0][field] = value
            self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
        bad = sample(True); bad['rows'][0]['dispatches'][0]['nodes'][0]['volumeLinear'] = .1
        self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
        bad = copy.deepcopy(baseline); bad['runtimeBoundaries'][0]['audioCallsReturningTask'] = 1
        self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))

    def test_nested_silent_and_independent_positive_transactions(self):
        baseline = sample()
        self.assertEqual(len(baseline['rows']), 38)
        self.assertEqual(sum(len(r['receipts']) for r in baseline['rows']), 14)
        silent_index = next(i for i, r in enumerate(baseline['rows']) if r['id'] == 'nested-silent-strength')
        positive_index = silent_index + 1
        bad = copy.deepcopy(baseline); del bad['rows'][positive_index]
        self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))  # Never accept a 37-step replacement.
        bad = copy.deepcopy(baseline); bad['rows'][silent_index]['frames'][1]['silent'] = False
        self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
        bad = copy.deepcopy(baseline); bad['rows'][silent_index]['receipts'] = copy.deepcopy(bad['rows'][positive_index]['receipts'])
        self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'))
        for mutation in ('same-ticket', 'outer-receipt', 'borrowed-ticket', 'foreign-source', 'cloned-power'):
            bad = copy.deepcopy(baseline); row = bad['rows'][positive_index]
            if mutation == 'same-ticket': row['frames'][0]['ticket'] = row['frames'][1]['ticket']
            elif mutation == 'outer-receipt':
                row['receipts'][0]['id'] = row['frames'][0]['ticket']
                row['dispatches'][0]['eventId'] = 'power_transaction:' + str(row['frames'][0]['ticket'])
            elif mutation == 'borrowed-ticket': row['frames'][0]['ticket'] = bad['rows'][0]['frames'][0]['ticket']
            elif mutation == 'foreign-source': row['frames'][0]['sourceRef'] = 999
            else:
                row['powerRef'] = row['receipts'][0]['powerRef'] = 999
                for frame in row['frames']: frame['powerRef'] = 999
            self.assertFalse(gate.validate_audio_receipts(bad, 'fresh'), mutation)
        old = ROOT / 'artifacts/headless/20261031T234629Z-80d187bb/report.json'
        if old.is_file():
            report = json.loads(old.read_text(encoding='utf-8'))
            self.assertFalse(gate.validate_audio_receipts(report['combat_tests'], report['run_id']))

    def test_actual_probe_observer_emission_not_gameplay(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run('tests/audio_receipt_probe/AudioReceiptProbe.csproj',
                             args=('-p:RepositoryRoot=' + str(ROOT),), timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('AUDIO_RECEIPT_PROBE_EMISSION_OK checks=20;', result.stdout)
        self.assertIn('native_fixture=NOT_RUN; playback=NOT_RUN; heard=false', result.stdout)


if __name__ == '__main__': unittest.main()
