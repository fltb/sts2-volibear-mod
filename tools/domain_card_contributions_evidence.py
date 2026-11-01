"""Strict raw-native gate for four contribution adapters, not insertion or input acceptance."""
import argparse
import json
from pathlib import Path

MARKER = '[Volibear] DOMAIN_CARD_CONTRIBUTIONS_RESULT '
CASES = ('hex', 'tangled', 'smoggy', 'ringing')
SOURCES = dict(hex=('SpectralKnight', 'KnightsElite', 'HEX', 'HexPower', 'Hexed', 2),
    tangled=('VineShambler', 'VineShamblerNormal', 'GRASPING_VINES_MOVE', 'TangledPower', 'Entangled', 1),
    smoggy=('LivingFog', 'LivingFogNormal', 'ADVANCED_GAS_MOVE', 'SmoggyPower', 'Smog', 1),
    ringing=('CeremonialBeast', 'CeremonialBeastBoss', 'BEAST_CRY_MOVE', 'RingingPower', 'Ringing', 1))
BASE_PHASES = ['warm', 'off', 'on', 'other-source', 'other-removed', 'off-again', 'departed-on', 'departed-off', 'mixed-native']


def validate(payload, token, family):
    if not isinstance(payload, dict) or not token or family not in CASES:
        return ['object/current token/supported family required']
    errors = []
    def eq(got, want, path):
        if isinstance(want, dict):
            if not isinstance(got, dict): errors.append(path + ': object required'); return
            if set(got) != set(want): errors.append(path + ': exact fields required')
            for key, value in want.items(): eq(got.get(key), value, path + '.' + key)
            return
        if isinstance(want, list):
            if not isinstance(got, list): errors.append(path + ': array required'); return
            if len(got) != len(want): errors.append(path + ': exact receipt count required')
            for index, (actual, expected) in enumerate(zip(got, want)): eq(actual, expected, path + f'[{index}]')
            return
        numeric = type(got) in (int, float) and type(want) in (int, float)
        if not (type(got) is type(want) or numeric) or got != want:
            errors.append(f'{path}: expected {want!r}, got {got!r}')
    def require(ok, path):
        if not ok: errors.append(path)
    source, encounter, move, power, affliction, amount = SOURCES[family]
    meta = dict(schema=1, token=token, scenario='domain-card-contributions', family=family,
        acceptance='four-native-contributions-not-affliction-writes-or-ordinary-input', testMode=False,
        version='v0.107.1', commit='59260271', encounter=encounter, sourceType=source,
        nativeMoveCalls=2 if family == 'hex' else 1, directPowerCallbackCalls=0, warmupQueriesPerApi=16,
        mixedStackPolicy='detected-unsupported-native-contribution-preserved', insertionCoverage=False,
        afflictionWriteSuppression=False, hexCleanupKind='native-PowerCmd.Remove-after-escape' if family == 'hex' else None)
    for key, value in meta.items(): eq(payload.get(key), value, key)
    owner, enemy = payload.get('ownerId'), payload.get('sourceId')
    require(type(owner) is int and type(enemy) is int and owner >= 0 and enemy >= 0 and owner != enemy, 'distinct actual native creature identities')
    roster = payload.get('initialRoster')
    if not isinstance(roster, list): return errors + ['native initial roster missing']
    require(sum(isinstance(r, dict) and r.get('id') == enemy and r.get('type') == source for r in roster) == 1, 'actual source in native encounter')
    eq(payload.get('keeperAdded'), len(roster) == 1, 'keeperAdded')
    death = payload.get('deathSourceId')
    if family == 'hex': require(type(death) is int and death not in (owner, enemy), 'distinct real death-control source')
    else: eq(death, None, 'deathSourceId')
    moves = payload.get('moves')
    expected_moves = [dict(sourceId=enemy, type=source, move=move)]
    if family == 'hex': expected_moves.append(dict(sourceId=death, type=source, move=move))
    eq(moves, expected_moves, 'native move history')
    eq(payload.get('received'), [dict(type=power, amount=amount, applierId=enemy, targetId=owner)], 'native power-received history')
    il = payload.get('ilSites')
    kinds = {'keywords': 'MegaCrit.Sts2.Core.Hooks.Hook.ModifyKeywordsInCombat',
        'cost': 'MegaCrit.Sts2.Core.Hooks.Hook.ModifyEnergyCostInCombat', 'play': 'MegaCrit.Sts2.Core.Hooks.Hook.ShouldPlay',
        'apply': 'MegaCrit.Sts2.Core.Commands.PowerCmd+<Apply>d__2.MoveNext',
        'amount': 'MegaCrit.Sts2.Core.Commands.PowerCmd+<ModifyAmount>d__6.MoveNext'}
    if not isinstance(il, list): errors.append('missing actual native IL receipts')
    else:
        eq(len(il), 5, 'native IL site count')
        require(all(isinstance(row, dict) for row in il), 'native IL rows must be objects')
        valid_kinds = all(isinstance(row, dict) and isinstance(row.get('Kind'), str) for row in il)
        require(valid_kinds, 'native IL kinds must be strings')
        if valid_kinds:
            eq(sorted(row.get('Kind', '') for row in il), sorted(kinds), 'native IL kinds')
            for row in il:
                eq(row, dict(Method=kinds.get(row.get('Kind')), Kind=row.get('Kind'), NativeCalls=1, ReplacedCalls=1), 'native IL row')
    phases = BASE_PHASES + (['removed-cleanup'] if family == 'hex' else []) + ['native-next-turn']
    if family == 'hex': phases += ['death-before', 'death-after']
    phases += ['player-control']
    rows = payload.get('steps')
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows): return errors + ['raw native snapshots required']
    eq([row.get('phase') for row in rows], phases, 'exact ordered snapshots')
    if [row.get('phase') for row in rows] != phases: return errors
    snapshots = {row['phase']: row for row in rows}
    off = snapshots['off']; card_id = off.get('cardId'); card_ref = off.get('cardRef'); power_ref = off.get('powerRef'); aff_ref = off.get('afflictionRef')
    require(type(card_id) is int and card_id >= 0 and isinstance(card_ref, str) and card_ref and isinstance(power_ref, str) and power_ref and isinstance(aff_ref, str) and aff_ref, 'actual stable model/affliction identities')
    active_phases = {'on', 'other-source', 'other-removed', 'departed-on', 'mixed-native', 'removed-cleanup', 'death-before', 'death-after', 'player-control', 'native-next-turn'}
    for phase, row in snapshots.items():
        for key, value in dict(ownerId=owner, sourceId=enemy, cardId=card_id, cardRef=card_ref,
                cardType='StrikeIronclad' if family == 'tangled' else 'DefendIronclad', testMode=False).items(): eq(row.get(key), value, phase + '.' + key)
        if phase in active_phases: require(type(row.get('domain')) is int and row['domain'] > 0, phase + ': live domain required')
        elif phase != 'native-next-turn': eq(row.get('domain'), 0, phase + '.domain')
        if phase in BASE_PHASES:
            eq(row.get('round'), 1, phase + '.round'); eq(row.get('pile'), 'Hand', phase + '.pile')
        else: eq(row.get('round'), 1 if phase == 'removed-cleanup' else 2, phase + '.round')
        eq(row.get('sourceAttached'), phase in BASE_PHASES[:6], phase + '.sourceAttached')
    eq(snapshots['warm'].get('powerPresent'), False, 'warm baseline power')
    eq(snapshots['warm'].get('affliction'), None, 'warm baseline affliction')
    for phase in BASE_PHASES[1:]:
        row = snapshots[phase]
        for key, value in dict(power=power, powerRef=power_ref, powerPresent=True, affliction=affliction, afflictionRef=aff_ref,
                amount=amount + (phase == 'mixed-native'), applierIsPlayer=False).items(): eq(row.get(key), value, phase + '.' + key)
        origin = row.get('origin')
        if not isinstance(origin, dict): errors.append(phase + ': source receipt missing'); continue
        state = 'mixed' if phase == 'mixed-native' else 'enemy'
        eq(origin, dict(State=state, ExpectedAmount=row['amount'], ActualAmount=row['amount'], SameCombat=True, SameOwner=True,
            EnemyIds=[str(enemy)], UnsupportedReason='contributor-allocation-not-proven;native-contribution-preserved' if state == 'mixed' else ''), phase + '.origin')
    def effect(phase, suppressed=False, other=False, player=False):
        row = snapshots[phase]
        expected_cost = 1 + ((1 if player else amount + (phase == 'mixed-native')) if family == 'tangled' and not suppressed else 0)
        if other and family == 'tangled': expected_cost += 2
        eq(row.get('cost'), expected_cost, phase + '.cost')
        eq(row.get('ethereal'), family == 'hex' and (not suppressed or other), phase + '.ethereal')
        veto = family in ('smoggy', 'ringing') and (not suppressed or other)
        eq(row.get('canPlay'), not veto, phase + '.canPlay')
        eq(row.get('preventer'), 'SlothPower' if other and veto else power if veto else None, phase + '.preventer')
        eq(row.get('reason'), 'BlockedByHook' if veto else 'None', phase + '.reason')
    for phase in BASE_PHASES[1:]: effect(phase, phase in ('on', 'other-source', 'other-removed', 'departed-on'), phase == 'other-source')
    for phase in ('removed-cleanup', 'native-next-turn', 'death-after'):
        if phase not in snapshots: continue
        row = snapshots[phase]
        eq(row.get('affliction'), None, phase + '.affliction'); eq(row.get('afflictionRef'), None, phase + '.afflictionRef')
        eq(row.get('powerPresent'), family == 'smoggy', phase + '.powerPresent')
        if family == 'smoggy':
            eq(row.get('powerRef'), power_ref, 'smoggy persists with native turn cleanup')
            eq(row.get('power'), power, phase + '.power'); eq(row.get('amount'), amount + 1, phase + '.amount')
        else:
            for key, value in dict(power=None, powerRef=None, amount=0, origin=None, applierId=None, applierIsPlayer=None).items(): eq(row.get(key), value, phase + '.' + key)
        eq(row.get('cost'), 1, phase + '.cost'); eq(row.get('ethereal'), False, phase + '.ethereal')
        eq(row.get('canPlay'), True, phase + '.canPlay'); eq(row.get('preventer'), None, phase + '.preventer')
    if family == 'hex':
        row = snapshots['death-before']; require(row.get('powerRef') != power_ref, 'fresh native death-control instance')
        eq(row.get('applierId'), death, 'death control native applier'); eq(row.get('affliction'), 'Hexed', 'death control affliction')
        eq(row.get('origin'), dict(State='enemy', ExpectedAmount=2, ActualAmount=2, SameCombat=True, SameOwner=True, EnemyIds=[str(death)], UnsupportedReason=''), 'death control origin')
        effect('death-before', True)
    control = snapshots['player-control']; require(control.get('powerRef') != power_ref, 'fresh player-applied power instance')
    eq(control.get('power'), power, 'player control power'); eq(control.get('applierId'), owner, 'player control actual applier')
    eq(control.get('applierIsPlayer'), True, 'player control source'); eq(control.get('amount'), 1, 'player control amount')
    eq(control.get('origin'), dict(State='player', ExpectedAmount=1, ActualAmount=1, SameCombat=True, SameOwner=True, EnemyIds=[], UnsupportedReason=''), 'player control origin')
    effect('player-control', player=True)
    plays = payload.get('plays')
    expected_play_phases = ['activate-native-restriction', 'activate-other-native-veto', 'activate-player-control'] if family in ('smoggy', 'ringing') else []
    if not isinstance(plays, list) or not all(isinstance(row, dict) for row in plays): errors.append('native play history missing')
    else:
        eq([row.get('phase') for row in plays], expected_play_phases, 'exact native control plays')
        ids = [row.get('cardId') for row in plays]
        require(all(type(i) is int and i >= 0 and i != card_id for i in ids) and len(set(ids)) == len(ids), 'distinct actual control cards')
        for row in plays:
            eq(row.get('nativeStarts'), 1, 'real card start'); eq(row.get('isAutoPlay'), True, 'explicit autoplay scope'); eq(row.get('cardType'), 'DefendIronclad', 'native control card')
    return errors


def check_log(text, token, family):
    rows = []
    if '[Volibear] DOMAIN_CARD_CONTRIBUTIONS_ERROR ' in text: return ['native probe error']
    for line in text.splitlines():
        if MARKER not in line: continue
        try: row = json.loads(line.split(MARKER, 1)[1])
        except (ValueError, TypeError): return ['malformed native result']
        if isinstance(row, dict) and row.get('token') == token: rows.append(row)
    if len(rows) != 1: return ['exactly one current-token native result required']
    return validate(rows[0], token, family)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('log', type=Path); parser.add_argument('--token', required=True); parser.add_argument('--case', choices=CASES, required=True)
    args = parser.parse_args(); errors = check_log(args.log.read_text(encoding='utf-8'), args.token, args.case)
    if errors: raise SystemExit('\n'.join(errors))
    print('Four-contribution native evidence passed; no insertion/affliction-write/ordinary-input claim.')


if __name__ == '__main__': main()
