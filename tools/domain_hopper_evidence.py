"""Independent Hopper C/M/return oracle. Native controlled fixture, not ordinary play."""
import json
import math

PREFIX = '[Volibear] DOMAIN_HOPPER_RESULT '
VARIANTS = ('off', 'on', 'c-wait-open', 'master-hook-open', 'master-committed-open',
            'off-death', 'mounted-domain-death', 'escape')
POINTS = {
    'on': 'before-native-ThieveryMove',
    'c-wait-open': 'native-C-completed-0.6wait-pending',
    'master-hook-open': 'native-BeforeCardRemoved-completed-before-M-pile',
    'master-committed-open': 'native-Steal-completed-before-Swipe-mount',
    'mounted-domain-death': 'after-native-Swipe-mounted-before-death',
}
ACCEPTANCE = 'controlled-native-moves-and-domain-windows-not-ordinary-input'


def need(value, label):
    if not value:
        raise ValueError('Hopper evidence: ' + label)


def same(actual, expected, label):
    if type(expected) is dict:
        need(type(actual) is dict and actual.keys() == expected.keys(), label)
        for key, value in expected.items():
            same(actual[key], value, label + '.' + key)
    elif type(expected) is list:
        need(type(actual) is list and len(actual) == len(expected), label)
        for index, value in enumerate(expected):
            same(actual[index], value, label + '[' + str(index) + ']')
    elif isinstance(expected, bool):
        need(type(actual) is bool and actual is expected, label)
    elif type(expected) in (int, float):
        need(type(actual) in (int, float) and math.isfinite(actual) and actual == expected, label)
    else:
        need(type(actual) is type(expected) and actual == expected, label)


def validate(result, token, variant):
    need(variant in VARIANTS, 'unknown requested case')
    for field, expected in dict(schema=1, token=token, scenario='domain-hopper', variant=variant,
                                completed=True, version='v0.107.1', commit='59260271', testMode=False,
                                encounter='ThievingHopperWeak', ascension=0, acceptance=ACCEPTANCE).items():
        same(result[field], expected, field)
    identity = [result[key] for key in ('playerRef', 'ownerRef', 'hopperRef', 'playerId', 'hopperId')]
    need(all(type(value) is str and value and value != 'null' for value in identity), 'native identities absent')
    need(len(set(identity[:3])) == 3 and result['playerId'] != result['hopperId'], 'source/player identity alias')
    expected_points = ['baseline', 'after-theft']
    if variant in ('off-death', 'mounted-domain-death'):
        expected_points += ['after-death']
    elif variant == 'escape':
        expected_points += ['after-escape']
    snapshots = result['snapshots']
    need(type(snapshots) is list and [row['point'] for row in snapshots] == expected_points, 'snapshot sequence')
    baseline = snapshots[0]['state']
    c, m = baseline['cRef'], baseline['mRef']
    need(type(c) is str and type(m) is str and c != m and c != 'null' and m != 'null', 'actual distinct combat/master')
    need(baseline['cPile'] in ('Draw', 'Discard'), 'eligible initial combat pile')
    need(type(baseline['cModel']) is str and baseline['cModel'].startswith('Volibear_'), 'actual player card model')
    same(baseline['mModel'], baseline['cModel'], 'master model')
    same(baseline['cUpgrade'], False, 'fresh combat card upgrade')
    same(baseline['mUpgrade'], False, 'fresh master upgrade')

    def state(row, *, stage, domain, hp, c_removed, m_removed, master_deck, loot,
              removed_history, listed, mounted, rewards=0, attached=True, hopper_hp=79):
        for field, expected in dict(cRef=c, mRef=m, cMasterRef=m, cOwnerRef=result['playerRef'],
                                    mOwnerRef=result['playerRef'], cModel=baseline['cModel'], mModel=baseline['mModel'],
                                    cUpgrade=False, mUpgrade=False, cRemoved=c_removed, mRemoved=m_removed,
                                    cPile='None' if c_removed else baseline['cPile'],
                                    mPile='Deck' if master_deck else 'None', masterInDeck=master_deck,
                                    registryOccurrences=1, loot=loot, cardsRemovedHistory=removed_history,
                                    playerHp=hp, playerBlock=0, domain=domain, hopperHp=hopper_hp,
                                    hopperAttached=attached, guardAttached=True).items():
            same(row[field], expected, stage + '.' + field)
        need(type(row['capturedSwipeRef']) is str and row['capturedSwipeRef'] not in (c, m, result['playerRef']), stage + '.captured Swipe reference')
        same(row['capturedStolenRef'], 'null' if row['capturedSwipeRef'] == 'null' else c, stage + '.captured theft identity')
        same(row['listRefs'], [c] if listed else [], stage + '.native selected list')
        same(row['rewardMasterRefs'], [m] if rewards else [], stage + '.same master reward')
        need(type(row['swipes']) is list and len(row['swipes']) == mounted, stage + '.Swipe count')
        if mounted:
            swipe = row['swipes'][0]
            need(type(swipe['swipeRef']) is str and swipe['swipeRef'] not in ('null', c, m), stage + '.Swipe identity')
            for field, expected in dict(stolenRef=c, targetRef=result['ownerRef'], ownerRef=result['hopperRef']).items():
                same(swipe[field], expected, stage + '.Swipe.' + field)
            same(row['capturedSwipeRef'], swipe['swipeRef'], stage + '.captured actual mounted Swipe')
            same(row['capturedStolenRef'], c, stage + '.captured actual stolen card')

    state(baseline, stage='baseline', domain=0, hp=80, c_removed=False, m_removed=False,
          master_deck=1, loot=0, removed_history=0, listed=False, mounted=0)
    blocked = variant in ('on', 'c-wait-open', 'master-hook-open')
    domain_after = 5 if variant in POINTS and variant != 'mounted-domain-death' else 0
    after = snapshots[1]['state']
    state(after, stage='after-theft', domain=domain_after, hp=63, c_removed=variant != 'on',
          m_removed=not blocked, master_deck=int(blocked), loot=int(not blocked),
          removed_history=int(not blocked or variant == 'master-hook-open'), listed=variant != 'on', mounted=int(not blocked))
    if variant in ('on', 'c-wait-open'):
        same(after['capturedSwipeRef'], 'null', 'cancelled before Steal does not start Swipe')
        same(after['capturedStolenRef'], 'null', 'no borrowed stolen card')
    if variant == 'master-hook-open':
        need(after['capturedSwipeRef'] != 'null', 'native Steal actually reached posthook gate')
        same(after['capturedStolenRef'], c, 'unmounted native prehook property is residual, not fake cleaned')

    windows = result['windows']
    need(type(windows) is list and len(windows) == int(variant in POINTS), 'domain input count')
    if windows:
        window = windows[0]
        same(window['point'], POINTS[variant], 'precise native window')
        same(window['nativePending'], True if variant == 'c-wait-open' else (None if variant in ('on', 'mounted-domain-death') else False), 'native wait completion state')
        before_c = variant != 'on'
        master_done = variant in ('master-committed-open', 'mounted-domain-death')
        history_done = variant in ('master-hook-open', 'master-committed-open', 'mounted-domain-death')
        mounted = int(variant == 'mounted-domain-death')
        window_hp = 63 if mounted else 80
        for label, amount in (('before', 0), ('after', 5)):
            state(window[label], stage='window.' + label, domain=amount, hp=window_hp,
                  c_removed=before_c, m_removed=master_done, master_deck=int(not master_done),
                  loot=int(master_done), removed_history=int(history_done), listed=before_c, mounted=mounted)

    if len(snapshots) == 3:
        same(snapshots[2]['state']['capturedSwipeRef'], after['capturedSwipeRef'], 'terminal exact original Swipe')
    if variant in ('off-death', 'mounted-domain-death'):
        state(snapshots[2]['state'], stage='after-death', domain=5 if variant == 'mounted-domain-death' else 0,
              hp=63, c_removed=True, m_removed=False, master_deck=0, loot=0, removed_history=1,
              listed=True, mounted=0, rewards=1, attached=False, hopper_hp=0)
    elif variant == 'escape':
        state(snapshots[2]['state'], stage='after-escape', domain=0, hp=28, c_removed=True,
              m_removed=True, master_deck=0, loot=1, removed_history=1, listed=True, mounted=0, attached=False)
    callbacks = []
    if variant in ('off-death', 'mounted-domain-death'):
        callbacks = [dict(swipeRef=after['capturedSwipeRef'], targetRef=result['hopperRef'], stolenRef=c,
                          masterRef=m, nativeCompleted=True, hopperHp=0,
                          domain=5 if variant == 'mounted-domain-death' else 0)]
    same(result['deathCallbacks'], callbacks, 'actual original Swipe.BeforeDeath callback')
    move_ids = ['THIEVERY_MOVE'] + (['FLUTTER_MOVE', 'HAT_TRICK_MOVE', 'NAB_MOVE', 'ESCAPE_MOVE'] if variant == 'escape' else [])
    same(result['moves'], [dict(sourceId=result['hopperId'], move=move) for move in move_ids], 'actual native move history')
    damage = [dict(sourceId=result['hopperId'], receiverId=result['playerId'], hpLost=value, blocked=0, overkill=0)
              for value in ([17, 21, 14] if variant == 'escape' else [17])]
    same(result['damage'], damage, 'actual native attack damage preserved')
    return True


def domain_hopper_evidence(log, token, variant):
    lines = [line.split(PREFIX, 1)[1] for line in log.splitlines() if PREFIX in line]
    if len(lines) != 1:
        return {'error': 'missing/duplicate Hopper result'}, False
    try:
        result = json.loads(lines[0])
        validate(result, token, variant)
        return result, True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        return {'error': str(error)}, False


check_log = domain_hopper_evidence
