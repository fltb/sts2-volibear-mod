"""Independent two-peer receipt checks. Parser fixtures never count as game evidence."""
import hashlib
import json
from pathlib import Path
import re
import uuid

from card_lifecycle_evidence import same
from save_load_evidence import native_reload_expected
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

STAGES = [
    'native-checkpoint', 'simultaneous-engage', 'owner-scoped-domain-lightning',
    'native-beast-identities', 'normal-turn-boundary', 'engage-before-disconnect',
    'native-checkpoint-rejoin',
]
PREFIX = '[Volibear] MULTIPLAYER_'
SCOPE = 'native-two-peer-paid-actions-disconnect-checkpoint-rejoin'
EXCLUSIONS = ['arbitrary-midcombat-snapshot-rejoin', 'steam-transport',
              'remote-choice-ui', 'combat-replay-playback']
CLEAN = dict(RunNull=True, CombatNull=True, InProgress=False,
             QueueEmpty=True, ActionNull=True, HistoryVisible=0)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def integer(value, low=0):
    return type(value) is int and value >= low


def records(log, kind):
    marker = PREFIX + kind + ' '
    return [json.loads(line[len(marker):]) for line in log.splitlines() if line.startswith(marker)]


def one(log, kind):
    found = records(log, kind)
    need(len(found) == 1 and type(found[0]) is dict, 'exactly one ' + kind + ' receipt required')
    return found[0]


def paid(receipt, expected):
    """The real executed action AND non-autoplay payment history must identify each play."""
    actions, plays = receipt['actions'], receipt['plays']
    need(type(actions) is list and type(plays) is list and len(actions) == len(plays) == len(expected),
         'native action/payment count differs')
    expected = sorted(expected)
    observed = []
    for action, play in zip(actions, plays):
        need(integer(play['owner'], 1) and integer(play['index']) and integer(play['spent']), 'invalid native payment identity')
        same(play['autoPlay'], False, 'autoplay cannot establish paid multiplayer acceptance')
        same(action['owner'], play['owner'], 'native action owner')
        same(action['index'], play['index'], 'native combat card index')
        same(action['card'], play['card'], 'native action card')
        same(action['state'], 'Finished', 'executed native action must finish')
        same(action['context'], 'GameActionPlayerChoiceContext', 'native paid choice context')
        need(isinstance(action['actionId'], str) and bool(action['actionId']), 'missing native action identity')
        observed.append((play['owner'], play['card'], play['spent']))
    same(sorted(observed), expected, 'native paid play set')
    need(len({(a['owner'], a['actionId']) for a in actions}) == len(actions), 'duplicate executed native action')


def check_metrics(stages):
    first = stages['native-checkpoint']['metrics']
    same(first, dict(nativeMapEntry=True, initialCheckpoint=True), 'native checkpoint')
    shared = stages['simultaneous-engage']['metrics']
    paid(shared['paid'], [(1, 'VOLIBEAR_B04', 1), (2, 'VOLIBEAR_B04', 1)])
    same(shared['enemyMoves'], 1, 'one shared enemy opportunity')
    same(shared['consumed'], True, 'enemy opportunity consumed')
    same(shared['opportunityEntries'], 1, 'one early opportunity entry')
    same(shared['starterDrawOwners'], [shared['paid']['plays'][0]['owner']], 'reward only first successful initiator')
    scoped = stages['owner-scoped-domain-lightning']['metrics']
    paid(scoped['domain'], [(1, 'VOLIBEAR_C05', 1)])
    paid(scoped['lightning'], [(2, 'VOLIBEAR_B03', 1)])
    same(scoped['domainAmounts'], [1, 0], 'domain belongs to host owner')
    same(scoped['lightningCounts'], [1, 1], 'teammate does not inherit domain attack attachment')
    beast = stages['native-beast-identities']['metrics']
    paid(beast['paid'], [(1, 'VOLIBEAR_R29', 3), (2, 'VOLIBEAR_R29', 3)])
    same(beast['exhausted'], 4, 'four native material exhaust entries')
    same(beast['generated'], 4, 'four native generated beast entries')
    same(beast['masterDeckUnchanged'], True, 'master deck immutable')
    need(type(beast['conversions']) is list and len(beast['conversions']) == 2, 'both players need native conversions')
    for owner, conversion in zip((1, 2), beast['conversions']):
        same(conversion['owner'], owner, 'conversion owner')
        materials, forms = conversion['materials'], conversion['forms']
        need(len(materials) == len(forms) == 2, 'exactly two material/form identities per player')
        same([c['id'] for c in materials], ['VOLIBEAR_B01', 'VOLIBEAR_B02'], 'material identities')
        same([c['id'] for c in forms], ['VOLIBEAR_T01', 'VOLIBEAR_T02'], 'native beast models')
        same([c['upgrade'] for c in forms], [1, 0], 'beast upgrades')
        for card in materials + forms:
            same(card['owner'], owner, 'native card owner')
            need(integer(card['index']), 'missing native combat card index')
        need(len({c['index'] for c in materials + forms}) == 4, 'material/form native ids were reused')
        same([c['pile'] for c in materials], ['Exhaust', 'Exhaust'], 'native exhaust material pile')
        same([c['pile'] for c in forms], ['Hand', 'Hand'], 'native generated form pile')
        same([c['masterIndex'] for c in forms], [-1, -1], 'generated forms cannot replace master deck')
        same([c['cost'] for c in forms], [0, 0], 'shared next-play discount on the native forms')
    turn = stages['normal-turn-boundary']['metrics']
    need(integer(turn['roundBefore'], 1), 'invalid normal round')
    same(turn['roundAfter'], turn['roundBefore'] + 1, 'one normal round advanced')
    for name, value in dict(duplicateEnemyMoves=0, availableAgain=True, domainExpired=True, lightningReset=True).items():
        same(turn[name], value, 'normal turn ' + name)
    before = stages['engage-before-disconnect']['metrics']
    paid(before['paid'], [(1, 'VOLIBEAR_B04', 1), (2, 'VOLIBEAR_B04', 1)])
    same(before['consumed'], True, 'real opportunity consumed before disconnect')
    same(stages['native-checkpoint-rejoin']['metrics'],
         dict(originalStateRestored=True, originalPlayerIds=[1, 2], earlyEntries=0, naturalEntries=0,
              recovery='native-room-checkpoint', arbitraryMidcombatSnapshot=False), 'native rejoin recovery boundary')
    for stage, energy, lightning in [('simultaneous-engage', 29, 0),
                                     ('owner-scoped-domain-lightning', 28, 1),
                                     ('native-beast-identities', 25, 1),
                                     ('normal-turn-boundary', 3, 0)]:
        state = stages[stage]['state']
        same([p['energy'] for p in state['players']], [energy, energy], stage + ' actual energy snapshot')
        same([p['lightning'] for p in state['players']], [lightning, lightning], stage + ' actual per-owner lightning snapshot')
    for player, conversion in zip(stages['native-beast-identities']['state']['players'], beast['conversions']):
        piles = {pile['pile']: pile['cards'] for pile in player['piles']}
        same(piles['Hand'], conversion['forms'], 'actual native hand contains the independently indexed beast forms')
        for material in conversion['materials']:
            need(material in piles['Exhaust'], 'actual native exhaust pile lacks consumed material')
    same(stages['normal-turn-boundary']['state']['round'], turn['roundAfter'], 'actual native next round snapshot')
    for stage in STAGES:
        same([p['deck'] for p in stages[stage]['state']['players']],
             [p['deck'] for p in stages['native-checkpoint']['state']['players']], stage + ' persistent master decks')


def peer(log, role, token, pair, user_root):
    need(not records(log, 'ERROR'), 'native probe reported an error')
    need(not re.search(r'checksum mismatch|state diverged|desync detected', log, re.I), 'native state divergence reported')
    begin, final, disconnected = one(log, 'BEGIN'), one(log, 'RESULT'), one(log, 'DISCONNECT')
    need(integer(begin['pid'], 1), 'invalid native process identity')
    for envelope in (begin, final, disconnected):
        for name, value in dict(schema=1, token=token, pair=pair, role=role, pid=begin['pid']).items():
            same(envelope[name], value, 'invocation ' + name)
    same(begin['gameVersion'], EXPECTED_GAME_VERSION, 'locked native game version')
    same(begin['gameCommit'], EXPECTED_GAME_COMMIT, 'locked native game commit')
    same(begin['userRoot'], str(user_root), 'isolated native profile')
    same(begin['testMode'], False, 'TestMode must not bypass native synchronization')
    same(begin['transport'], 'native-ENet-loopback', 'native transport')
    need(uuid.UUID(begin['assemblyMvid']).int != 0, 'missing candidate assembly MVID')
    for envelope in (begin, final):
        for name, value in dict(osInput=False, simulatedClicks=False, processRestarts=0).items():
            same(envelope[name], value, 'native process contract ' + name)
    same(final['completed'], STAGES, 'complete finite multiplayer stage sequence')
    same(final['finished'], True, 'native suite completion')
    same(final['cleanup'], CLEAN, 'native final cleanup')
    same(final['scope'], SCOPE, 'acceptance scope')
    same(final['exclusions'], EXCLUSIONS, 'honest acceptance boundaries')
    expected_submissions = ['simultaneous-engage:VOLIBEAR_B04',
                            'owner-domain:VOLIBEAR_C05' if role == 'host' else 'teammate-lightning:VOLIBEAR_B03',
                            'native-beast-identities:VOLIBEAR_R29', 'engage-before-disconnect:VOLIBEAR_B04']
    same(final['submitted'], expected_submissions, 'only local native inputs submitted')
    required_calls = {'NGame.StartNewMultiplayerRun', 'RunState.FromSerializable',
                      'RunManager.SetUpSavedMultiplayer', 'NGame.LoadRun',
                      'StartRunLobby.SetReady', 'LoadRunLobby.SetReady'}
    required_calls.update({'NetHostGameService.StartENetHost', 'SaveManager.LoadAndCanonicalizeMultiplayerRunSave'}
                          if role == 'host' else {'JoinFlow.Begin', 'NetClientGameService.Disconnect'})
    need(required_calls <= set(final['nativeCalls']), 'missing native lobby/new/load/disconnect API receipts')
    same(disconnected['clientConnectionClosed'], True, 'real connection closure')
    same(disconnected['observedPeerCount'], 0, 'real peer removal')
    same(disconnected['hadConsumedOpportunity'], True, 'disconnect state fixture')
    receipts = records(log, 'STAGE')
    same([r['stage'] for r in receipts], STAGES, 'exactly one ordered receipt per stage')
    stages = {}
    for record in receipts:
        for name, value in dict(schema=1, token=token, pair=pair, role=role, pid=begin['pid']).items():
            same(record[name], value, 'stage envelope ' + name)
        same(record['transport'], dict(netId=1 if role == 'host' else 2, peerCount=1,
                                      service='NetHostGameService' if role == 'host' else 'NetClientGameService',
                                      transport='ENetHost' if role == 'host' else 'ENetClient',
                                      nativeChecksums=True, nativeReplay=True), 'actual native connected transport')
        state = record['state']
        same([p['netId'] for p in state['players']], [1, 2], 'both original native players')
        for player in state['players']:
            same(player['character'], 'VOLIBEAR_CHARACTER', 'both native mod characters')
            same(player['relics'], ['VOLIBEAR_HUNTERS_HEART'], 'both native starter relics')
            need(integer(player['energy']) and integer(player['lightning']) and integer(player['turn'], 1), 'invalid player counters')
            same(sorted(p['pile'] for p in player['piles']), ['Discard', 'Draw', 'Exhaust', 'Hand', 'Play'], 'all native combat piles')
        need(type(state['enemies']) is list and bool(state['enemies']), 'native enemy snapshot missing')
        stages[record['stage']] = record
    same(stages['native-checkpoint-rejoin']['state'], stages['native-checkpoint']['state'], 'full checkpoint state restored')
    check_metrics(stages)
    shutdown = '[Volibear] SHUTDOWN_BEGIN ' + token
    need(log.count(shutdown) == 1, 'exactly one native shutdown required')
    # Whitespace-independent stage positions also allow readable negative-control fixtures.
    lines = log.splitlines()
    stage_positions = {json.loads(line[len(PREFIX + 'STAGE '):])['stage']: i
                       for i, line in enumerate(lines) if line.startswith(PREFIX + 'STAGE ')}
    position = lambda marker: next(i for i, line in enumerate(lines) if line.startswith(marker))
    need(position(PREFIX + 'BEGIN ') < stage_positions[STAGES[0]] < stage_positions['engage-before-disconnect']
         < position(PREFIX + 'DISCONNECT ') < stage_positions['native-checkpoint-rejoin']
         < position(PREFIX + 'RESULT ') < position(shutdown), 'native lifecycle receipts out of order')
    return dict(begin=begin, final=final, stages=stages, disconnect=disconnected)


def check_pair(logs, pair, tokens, roots, pids):
    errors, peers = [], {}
    for role in ('host', 'client'):
        try:
            row = peer(logs[role], role, tokens[role], pair, roots[role])
            need(integer(pids[role], 1), 'real owned native process id missing')
            same(row['begin']['pid'], pids[role], 'receipt must belong to the actual launched native process')
            peers[role] = row
        except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration, AttributeError) as error:
            errors.append(role + ': ' + str(error))
    if len(peers) == 2:
        try:
            host, client = peers['host'], peers['client']
            need(host['begin']['pid'] != client['begin']['pid'], 'two distinct native processes required')
            need(Path(roots['host']).resolve() != Path(roots['client']).resolve(), 'distinct isolated peer profiles required')
            same(host['begin']['assemblyMvid'], client['begin']['assemblyMvid'], 'both peers run identical candidate DLL')
            for name in STAGES:
                same(host['stages'][name]['state'], client['stages'][name]['state'], name + ' complete peer state agreement')
                same(host['stages'][name]['metrics'], client['stages'][name]['metrics'], name + ' native action/history agreement')
            final = host['final']
            checkpoint = Path(final['checkpointPath'])
            resolved = checkpoint.resolve(strict=True)
            need(checkpoint.is_absolute() and resolved == checkpoint.absolute()
                 and resolved.is_relative_to(Path(roots['host']).resolve(strict=True)), 'checkpoint escaped isolated host profile')
            need(checkpoint.name == 'current_run_mp.save', 'must inspect the native multiplayer checkpoint')
            need(re.fullmatch(r'[0-9a-f]{64}', final['checkpointSha256'] or '') is not None, 'invalid checkpoint digest')
            same(hashlib.sha256(resolved.read_bytes()).hexdigest(), final['checkpointSha256'], 'actual native disk checkpoint hash')
            disk = json.loads(resolved.read_text(encoding='utf-8-sig'))
            need(type(disk) is dict and type(final['checkpoint']) is dict, 'native checkpoint is not JSON object')
            same(disk, final['afterLoad'], 'actual native multiplayer disk checkpoint')
            expected, _ = native_reload_expected(final['checkpoint'])
            bounds = final['canonicalizedAt']
            need(type(bounds) is dict and set(bounds) == {'before', 'after'}
                 and integer(bounds['before'], 1) and integer(bounds['after'], bounds['before']), 'canonicalization clock bounds')
            saved_time = final['afterLoad']['save_time']
            need(integer(saved_time, final['checkpoint']['save_time'])
                 and bounds['before'] <= saved_time <= bounds['after'], 'native CanonicalizeSave save time outside observed call')
            # Pinned RunManager.CanonicalizeSave creates a fresh save timestamp;
            # SetUpSavedMultiplayer increments reloads. Other fields stay strict.
            expected['save_time'] = saved_time
            same(final['afterLoad'], expected, 'only native canonical time/reload count/map defaults may change checkpoint')
            need(re.fullmatch(r'[0-9a-f]{64}', final['checkpointBeforeSha256'] or '') is not None, 'original checkpoint digest missing')
            same(client['final']['checkpointPath'], None, 'client must restore host checkpoint over native join')
            same(client['final']['checkpointSha256'], None, 'client cannot substitute a separate local checkpoint')
            for name in ('checkpointBeforeSha256', 'checkpoint', 'afterLoad', 'canonicalizedAt'):
                same(client['final'][name], None, 'client native join payload, no independent local save ' + name)
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
            errors.append('pair: ' + str(error))
    return dict(errors=errors, peers=peers, scope=SCOPE, exclusions=EXCLUSIONS,
                observed_processes=len({p['begin']['pid'] for p in peers.values()}))
