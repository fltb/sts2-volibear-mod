import copy
import json
from pathlib import Path
import sys
import unittest

# Works both in this isolated staging directory and after publication under tests/.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / 'domain_card_contributions_evidence.py').exists() else HERE.parent / 'tools'))
import domain_card_contributions_evidence as gate


def fixture(family):
    # Synthetic validator unit fixture, NEVER engine evidence.
    defs = {'hex': ('SpectralKnight', 'KnightsElite', 'HEX', 'HexPower', 'Hexed', 2),
        'tangled': ('VineShambler', 'VineShamblerNormal', 'GRASPING_VINES_MOVE', 'TangledPower', 'Entangled', 1),
        'smoggy': ('LivingFog', 'LivingFogNormal', 'ADVANCED_GAS_MOVE', 'SmoggyPower', 'Smog', 1),
        'ringing': ('CeremonialBeast', 'CeremonialBeastBoss', 'BEAST_CRY_MOVE', 'RingingPower', 'Ringing', 1)}
    source, encounter, move, power, affliction, amount = defs[family]
    p = dict(schema=1, token='unit-token', scenario='domain-card-contributions', family=family,
        acceptance='four-native-contributions-not-affliction-writes-or-ordinary-input', testMode=False,
        version='v0.107.1', commit='59260271', encounter=encounter, sourceType=source, sourceId=1, ownerId=0,
        initialRoster=[dict(id=1, type=source)], keeperAdded=True, nativeMoveCalls=2 if family == 'hex' else 1,
        deathSourceId=3 if family == 'hex' else None, directPowerCallbackCalls=0, warmupQueriesPerApi=16,
        moves=[dict(sourceId=1, type=source, move=move)], received=[dict(type=power, amount=amount, applierId=1, targetId=0)],
        mixedStackPolicy='detected-unsupported-native-contribution-preserved', insertionCoverage=False,
        afflictionWriteSuppression=False, hexCleanupKind='native-PowerCmd.Remove-after-escape' if family == 'hex' else None)
    if family == 'hex': p['moves'].append(dict(sourceId=3, type=source, move=move))
    p['ilSites'] = [dict(Method=name, Kind=kind, NativeCalls=1, ReplacedCalls=1) for kind, name in [
        ('keywords', 'MegaCrit.Sts2.Core.Hooks.Hook.ModifyKeywordsInCombat'),
        ('cost', 'MegaCrit.Sts2.Core.Hooks.Hook.ModifyEnergyCostInCombat'),
        ('play', 'MegaCrit.Sts2.Core.Hooks.Hook.ShouldPlay'),
        ('apply', 'MegaCrit.Sts2.Core.Commands.PowerCmd+<Apply>d__2.MoveNext'),
        ('amount', 'MegaCrit.Sts2.Core.Commands.PowerCmd+<ModifyAmount>d__6.MoveNext')]]
    phases = ['warm', 'off', 'on', 'other-source', 'other-removed', 'off-again', 'departed-on', 'departed-off', 'mixed-native']
    if family == 'hex': phases += ['removed-cleanup']
    phases += ['native-next-turn']
    if family == 'hex': phases += ['death-before', 'death-after']
    phases += ['player-control']
    rows = []
    for phase in phases:
        active = phase not in ('warm', 'off', 'off-again', 'departed-off')
        native_power = phase != 'warm' and phase not in ('removed-cleanup', 'death-after') and (phase != 'native-next-turn' or family == 'smoggy')
        has_affliction = native_power and phase != 'native-next-turn'
        player = phase == 'player-control'; died = phase == 'death-before'; mixed = phase == 'mixed-native' or phase == 'native-next-turn'
        n = 1 if player else amount + (phase == 'mixed-native' or phase == 'native-next-turn' and family == 'smoggy')
        kind = 'player' if player else 'mixed' if mixed else 'enemy'
        origin = dict(State=kind, ExpectedAmount=n, ActualAmount=n, SameCombat=True, SameOwner=True,
            EnemyIds=[] if player else ['3'] if died else ['1'],
            UnsupportedReason='contributor-allocation-not-proven;native-contribution-preserved' if kind == 'mixed' else '') if native_power else None
        suppressed = phase in ('on', 'other-source', 'other-removed', 'departed-on', 'death-before')
        other = phase == 'other-source'
        veto = has_affliction and family in ('smoggy', 'ringing') and (not suppressed or other)
        cost = 1 + (n if has_affliction and family == 'tangled' and not suppressed else 0) + (2 if other and family == 'tangled' else 0)
        rows.append(dict(phase=phase, round=2 if phase in ('native-next-turn', 'death-before', 'death-after', 'player-control') else 1,
            domain=5 if active else 0, sourceAttached=phase in ('warm', 'off', 'on', 'other-source', 'other-removed', 'off-again'),
            sourceAlive=True, ownerId=0, sourceId=1, cardId=20, cardType='StrikeIronclad' if family == 'tangled' else 'DefendIronclad',
            cardRef='c1', pile='Hand', affliction=affliction if has_affliction else None,
            afflictionRef=('aplayer' if player else 'adeath' if died else 'a1') if has_affliction else None,
            power=power if native_power else None, powerRef=('pplayer' if player else 'pdeath' if died else 'p1') if native_power else None,
            amount=n if native_power else 0, applierId=(0 if player else 3 if died else 1) if native_power else None,
            applierIsPlayer=player if native_power else None, origin=origin,
            ethereal=has_affliction and family == 'hex' and (not suppressed or other), cost=cost,
            canPlay=not veto, reason='BlockedByHook' if veto else 'None', preventer='SlothPower' if other and veto else power if veto else None,
            powerPresent=native_power, testMode=False))
    p['steps'] = rows
    p['plays'] = [dict(phase=phase, cardId=30+i, cardType='DefendIronclad', nativeStarts=1, isAutoPlay=True) for i, phase in enumerate(
        ['activate-native-restriction', 'activate-other-native-veto', 'activate-player-control'] if family in ('smoggy', 'ringing') else [])]
    return p


def row(p, phase): return next(r for r in p['steps'] if r['phase'] == phase)


class EvidenceTests(unittest.TestCase):
    def test_all_four_synthetic_contract_fixtures(self):
        for family in gate.CASES:
            with self.subTest(family=family): self.assertEqual(gate.validate(fixture(family), 'unit-token', family), [])

    def test_token_version_and_scope_are_bound(self):
        for key, value in [('token', 'old'), ('version', 'v0.107.0'), ('commit', 'old'), ('testMode', True),
                ('afflictionWriteSuppression', True), ('insertionCoverage', True), ('directPowerCallbackCalls', 1), ('warmupQueriesPerApi', 0)]:
            with self.subTest(key=key):
                p = fixture('hex'); p[key] = value; self.assertTrue(gate.validate(p, 'unit-token', 'hex'))

    def test_all_family_contribution_regressions(self):
        for family, key, value in [('hex', 'ethereal', True), ('tangled', 'cost', 2), ('smoggy', 'canPlay', False), ('ringing', 'canPlay', False)]:
            with self.subTest(family=family):
                p = fixture(family); row(p, 'on')[key] = value; self.assertTrue(gate.validate(p, 'unit-token', family))

    def test_other_source_cannot_be_erased(self):
        for family, key, value in [('hex', 'ethereal', False), ('tangled', 'cost', 1), ('smoggy', 'canPlay', True), ('ringing', 'preventer', None)]:
            with self.subTest(family=family):
                p = fixture(family); row(p, 'other-source')[key] = value; self.assertTrue(gate.validate(p, 'unit-token', family))

    def test_player_source_cannot_be_suppressed(self):
        for family, key, value in [('hex', 'ethereal', False), ('tangled', 'cost', 1), ('smoggy', 'canPlay', True), ('ringing', 'canPlay', True)]:
            with self.subTest(family=family):
                p = fixture(family); row(p, 'player-control')[key] = value; self.assertTrue(gate.validate(p, 'unit-token', family))

    def test_mixed_source_is_not_old_applier_inference(self):
        for family in gate.CASES:
            p = fixture(family); row(p, 'mixed-native')['origin']['State'] = 'enemy'
            with self.subTest(family=family): self.assertTrue(gate.validate(p, 'unit-token', family))

    def test_departure_cannot_drop_provenance(self):
        for family in gate.CASES:
            p = fixture(family); row(p, 'departed-on')['origin']['SameCombat'] = False
            with self.subTest(family=family): self.assertTrue(gate.validate(p, 'unit-token', family))

    def test_no_fake_affliction_replacement_or_cleanup(self):
        for phase, key, value in [('on', 'afflictionRef', 'fake'), ('departed-on', 'affliction', None),
                ('native-next-turn', 'affliction', 'Ringing'), ('native-next-turn', 'amount', 2)]:
            p = fixture('ringing'); row(p, phase)[key] = value
            with self.subTest(phase=phase, key=key): self.assertTrue(gate.validate(p, 'unit-token', 'ringing'))

    def test_native_moves_and_real_commits_required(self):
        for key, value in [('moves', []), ('received', []), ('sourceId', 0), ('initialRoster', [])]:
            p = fixture('tangled'); p[key] = value
            with self.subTest(key=key): self.assertTrue(gate.validate(p, 'unit-token', 'tangled'))

    def test_duplicate_or_missing_rows_rejected(self):
        p = fixture('hex'); p['steps'].append(copy.deepcopy(p['steps'][0])); self.assertTrue(gate.validate(p, 'unit-token', 'hex'))
        p = fixture('hex'); p['steps'].pop(); self.assertTrue(gate.validate(p, 'unit-token', 'hex'))

    def test_il_actual_callsite_and_strict_numeric_types(self):
        for value in (0, 2, True, '1'):
            p = fixture('hex'); p['ilSites'][0]['NativeCalls'] = value
            with self.subTest(value=value): self.assertTrue(gate.validate(p, 'unit-token', 'hex'))
        p = fixture('hex'); p['ilSites'][0]['Method'] = 'HexPower.TryModifyKeywordsInCombat'
        self.assertTrue(gate.validate(p, 'unit-token', 'hex'))

    def test_hex_actual_death_cleanup_required(self):
        p = fixture('hex'); row(p, 'death-after')['affliction'] = 'Hexed'; self.assertTrue(gate.validate(p, 'unit-token', 'hex'))
        p = fixture('hex'); p['deathSourceId'] = 1; self.assertTrue(gate.validate(p, 'unit-token', 'hex'))

    def test_native_autoplay_history_must_not_claim_ordinary_input(self):
        p = fixture('smoggy'); p['plays'][0]['isAutoPlay'] = False; self.assertTrue(gate.validate(p, 'unit-token', 'smoggy'))
        p = fixture('smoggy'); p['plays'][0]['nativeStarts'] = 0; self.assertTrue(gate.validate(p, 'unit-token', 'smoggy'))

    def test_log_current_token_and_duplicates(self):
        line = gate.MARKER + json.dumps(fixture('hex'))
        self.assertEqual(gate.check_log(line, 'unit-token', 'hex'), [])
        self.assertTrue(gate.check_log(line, 'other', 'hex'))
        self.assertTrue(gate.check_log(line + '\n' + line, 'unit-token', 'hex'))
        self.assertTrue(gate.check_log(gate.MARKER + '{', 'unit-token', 'hex'))
        self.assertTrue(gate.check_log('[Volibear] DOMAIN_CARD_CONTRIBUTIONS_ERROR bad\n' + line, 'unit-token', 'hex'))


if __name__ == '__main__': unittest.main()
