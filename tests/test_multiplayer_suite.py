"""Two-process routing and adversarial evidence fixtures; no native game is simulated or run."""
from contextlib import ExitStack, redirect_stderr
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import multiplayer_evidence as gate
import multiplayer_suite as suite

STOCK = dict(successful=True, exit_code=0, timed_out=False, runtime_errors=[])


def payment(rows):
    plays = [dict(owner=owner, card=card, index=index, spent=spent, autoPlay=False)
             for index, (owner, card, spent) in enumerate(rows)]
    actions = [dict(owner=p['owner'], card=p['card'], index=p['index'], actionId=str(i + 1),
                    state='Finished', context='GameActionPlayerChoiceContext') for i, p in enumerate(plays)]
    return dict(plays=plays, actions=actions)


def fixture(folder):
    """Synthetic log vocabulary used only to challenge the parser's acceptance boundary."""
    pair = 'fixture-pair'
    tokens = {role: 'fixture-' + role for role in ('host', 'client')}
    roots = {role: folder / role for role in tokens}
    pids = dict(host=100, client=200)
    for root in roots.values(): root.mkdir()
    checkpoint = dict(num_reloads=0, save_time=100, acts=[dict(id='ACT.OVERGROWTH')], players=[dict(net_id=1), dict(net_id=2)])
    after = dict(checkpoint, num_reloads=1, save_time=200)
    path = roots['host'] / 'current_run_mp.save'
    path.write_text(json.dumps(after), encoding='utf-8')
    initial = dict(encounter='SLIMES_WEAK', round=1, side='Player',
                   players=[dict(netId=owner, character='VOLIBEAR_CHARACTER', energy=3, lightning=0, turn=1,
                                 deck=[dict(id='VOLIBEAR_B01')], relics=['VOLIBEAR_HUNTERS_HEART'],
                                 piles=[dict(pile=p, cards=[]) for p in ('Discard', 'Draw', 'Exhaust', 'Hand', 'Play')])
                            for owner in (1, 2)], enemies=[dict(id='LEAF_SLIME_S', hp=30)])
    b04 = payment([(1, 'VOLIBEAR_B04', 1), (2, 'VOLIBEAR_B04', 1)])
    beast = dict(paid=payment([(1, 'VOLIBEAR_R29', 3), (2, 'VOLIBEAR_R29', 3)]),
                 exhausted=4, generated=4, masterDeckUnchanged=True, conversions=[])
    for owner in (1, 2):
        materials = [dict(id='VOLIBEAR_B01', owner=owner, index=10, pile='Exhaust'),
                     dict(id='VOLIBEAR_B02', owner=owner, index=11, pile='Exhaust')]
        forms = [dict(id='VOLIBEAR_T01', owner=owner, index=12, pile='Hand', upgrade=1, cost=0, masterIndex=-1),
                 dict(id='VOLIBEAR_T02', owner=owner, index=13, pile='Hand', upgrade=0, cost=0, masterIndex=-1)]
        beast['conversions'].append(dict(owner=owner, materials=materials, forms=forms))
    metrics = [dict(nativeMapEntry=True, initialCheckpoint=True),
               dict(paid=b04, enemyMoves=1, starterDrawOwners=[1], consumed=True, opportunityEntries=1),
               dict(domain=payment([(1, 'VOLIBEAR_C05', 1)]), lightning=payment([(2, 'VOLIBEAR_B03', 1)]),
                    domainAmounts=[1, 0], lightningCounts=[1, 1]), beast,
               dict(roundBefore=1, roundAfter=2, duplicateEnemyMoves=0, availableAgain=True, domainExpired=True, lightningReset=True),
               dict(paid=b04, consumed=True),
               dict(originalStateRestored=True, originalPlayerIds=[1, 2], earlyEntries=0, naturalEntries=0,
                    recovery='native-room-checkpoint', arbitraryMidcombatSnapshot=False)]
    peer_records = {}
    for role in tokens:
        envelope = dict(schema=1, token=tokens[role], pair=pair, role=role, pid=pids[role])
        begin = dict(envelope, userRoot=str(roots[role]), gameVersion='v0.107.1', gameCommit='59260271',
                     testMode=False, assemblyMvid='00000000-0000-0000-0000-000000000001',
                     transport='native-ENet-loopback', osInput=False, simulatedClicks=False, processRestarts=0)
        stages = []
        for i, name in enumerate(gate.STAGES):
            state = copy.deepcopy(initial)
            energy, lightning = [(3, 0), (29, 0), (28, 1), (25, 1), (3, 0), (29, 0), (3, 0)][i]
            for player in state['players']:
                player.update(energy=energy, lightning=lightning)
            if name == 'normal-turn-boundary': state['round'] = 2
            if name == 'native-beast-identities':
                for player, row in zip(state['players'], beast['conversions']):
                    for pile in player['piles']:
                        if pile['pile'] == 'Hand': pile['cards'] = copy.deepcopy(row['forms'])
                        if pile['pile'] == 'Exhaust': pile['cards'] = copy.deepcopy(row['materials'])
            stages.append(dict(envelope, stage=name, state=state, metrics=copy.deepcopy(metrics[i]),
                               transport=dict(netId=1 if role == 'host' else 2, peerCount=1,
                                              service='NetHostGameService' if role == 'host' else 'NetClientGameService',
                                              transport='ENetHost' if role == 'host' else 'ENetClient',
                                              nativeChecksums=True, nativeReplay=True)))
        calls = ['NGame.StartNewMultiplayerRun', 'RunState.FromSerializable', 'RunManager.SetUpSavedMultiplayer',
                 'NGame.LoadRun', 'StartRunLobby.SetReady', 'LoadRunLobby.SetReady']
        calls += ['NetHostGameService.StartENetHost', 'SaveManager.LoadAndCanonicalizeMultiplayerRunSave'] if role == 'host' else ['JoinFlow.Begin', 'NetClientGameService.Disconnect']
        final = dict(envelope, completed=gate.STAGES[:], submitted=['simultaneous-engage:VOLIBEAR_B04',
                     'owner-domain:VOLIBEAR_C05' if role == 'host' else 'teammate-lightning:VOLIBEAR_B03',
                     'native-beast-identities:VOLIBEAR_R29', 'engage-before-disconnect:VOLIBEAR_B04'],
                     nativeCalls=calls, finished=True, osInput=False, simulatedClicks=False, processRestarts=0,
                     cleanup=copy.deepcopy(gate.CLEAN), checkpointPath=str(path) if role == 'host' else None,
                     checkpointSha256=hashlib.sha256(path.read_bytes()).hexdigest() if role == 'host' else None,
                     checkpointBeforeSha256='1' * 64 if role == 'host' else None,
                     checkpoint=copy.deepcopy(checkpoint) if role == 'host' else None,
                     afterLoad=copy.deepcopy(after) if role == 'host' else None,
                     canonicalizedAt=dict(before=200, after=201) if role == 'host' else None,
                     scope=gate.SCOPE, exclusions=gate.EXCLUSIONS[:])
        disconnected = dict(envelope, clientConnectionClosed=True, observedPeerCount=0, hadConsumedOpportunity=True)
        peer_records[role] = dict(begin=begin, stages=stages, disconnected=disconnected, final=final)
    return peer_records, pair, tokens, roots, pids


def logs(records):
    def row(kind, value): return gate.PREFIX + kind + ' ' + json.dumps(value)
    result = {}
    for role, peer in records.items():
        lines = [row('BEGIN', peer['begin'])]
        for stage in peer['stages']:
            lines.append(row('STAGE', stage))
            if stage['stage'] == 'engage-before-disconnect': lines.append(row('DISCONNECT', peer['disconnected']))
        lines += [row('RESULT', peer['final']), '[Volibear] SHUTDOWN_BEGIN ' + peer['begin']['token']]
        result[role] = '\n'.join(lines)
    return result


class PeerEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='volibear-peer-parser-')
        self.addCleanup(self.temp.cleanup)
        self.records, self.pair, self.tokens, self.roots, self.pids = fixture(Path(self.temp.name))

    def verdict(self, records=None, **kw):
        return gate.check_pair(logs(records or self.records), self.pair, self.tokens,
                               kw.get('roots', self.roots), kw.get('pids', self.pids))

    def test_complete_synthetic_vocabulary_is_accepted_only_by_parser(self):
        self.assertEqual(self.verdict()['errors'], [])
        self.assertEqual(self.verdict()['observed_processes'], 2)

    def test_each_required_stage_is_mandatory(self):
        for i in range(len(gate.STAGES)):
            with self.subTest(stage=gate.STAGES[i]):
                changed = copy.deepcopy(self.records); del changed['client']['stages'][i]
                self.assertTrue(self.verdict(changed)['errors'])

    def test_missing_duplicate_or_stale_process_receipt_fails(self):
        for role in ('host', 'client'):
            raw = logs(self.records); raw[role] = ''
            self.assertTrue(gate.check_pair(raw, self.pair, self.tokens, self.roots, self.pids)['errors'])
            raw = logs(self.records); raw[role] += '\n' + raw[role].splitlines()[0]
            self.assertTrue(gate.check_pair(raw, self.pair, self.tokens, self.roots, self.pids)['errors'])
        for pids in (dict(host=100, client=100), dict(host=100, client=201), dict(host=100, client=True)):
            self.assertTrue(self.verdict(pids=pids)['errors'])

    def test_native_payment_and_owner_identity_negative_controls(self):
        for mutation in ('autoplay', 'free', 'wrong-owner', 'unfinished', 'duplicate', 'boolean-index'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.records)
                paid = changed['client']['stages'][1]['metrics']['paid']
                if mutation == 'autoplay': paid['plays'][0]['autoPlay'] = True
                if mutation == 'free': paid['plays'][0]['spent'] = 0
                if mutation == 'wrong-owner': paid['actions'][0]['owner'] = 2
                if mutation == 'unfinished': paid['actions'][0]['state'] = 'Queued'
                if mutation == 'duplicate': paid['actions'][1] = paid['actions'][0]
                if mutation == 'boolean-index': paid['plays'][0]['index'] = False
                self.assertTrue(self.verdict(changed)['errors'])

    def test_shared_opportunity_domain_and_beast_semantic_failures(self):
        for index, field, bad in ((1, 'enemyMoves', 2), (1, 'starterDrawOwners', [1, 2]),
                                  (1, 'consumed', 1), (2, 'domainAmounts', [1, 1]),
                                  (2, 'lightningCounts', [1, 2]), (3, 'generated', 2),
                                  (4, 'duplicateEnemyMoves', 1), (6, 'earlyEntries', 1)):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.records)
                for peer in changed.values(): peer['stages'][index]['metrics'][field] = bad
                self.assertTrue(self.verdict(changed)['errors'])
        for role in self.records:
            changed = copy.deepcopy(self.records)
            changed[role]['stages'][3]['metrics']['conversions'][0]['forms'][0]['index'] = 10
            self.assertTrue(self.verdict(changed)['errors'])

    def test_equal_wrong_snapshots_do_not_override_independent_energy_oracles(self):
        changed = copy.deepcopy(self.records)
        for peer in changed.values(): peer['stages'][2]['state']['players'][1]['energy'] = 29
        self.assertTrue(self.verdict(changed)['errors'])

    def test_peer_state_and_candidate_drift_fail(self):
        changed = copy.deepcopy(self.records)
        changed['client']['stages'][1]['state']['enemies'][0]['hp'] = 29
        self.assertTrue(self.verdict(changed)['errors'])
        changed = copy.deepcopy(self.records)
        changed['client']['begin']['assemblyMvid'] = '00000000-0000-0000-0000-000000000002'
        self.assertTrue(self.verdict(changed)['errors'])

    def test_native_transport_and_recovery_gates_cannot_be_disabled(self):
        for field, value in (('nativeChecksums', False), ('nativeReplay', False), ('peerCount', 0), ('transport', 'MockNet')):
            changed = copy.deepcopy(self.records); changed['client']['stages'][0]['transport'][field] = value
            self.assertTrue(self.verdict(changed)['errors'])
        for field, value in (('clientConnectionClosed', False), ('observedPeerCount', 1)):
            changed = copy.deepcopy(self.records); changed['host']['disconnected'][field] = value
            self.assertTrue(self.verdict(changed)['errors'])
        changed = copy.deepcopy(self.records); changed['host']['final']['nativeCalls'].remove('RunManager.SetUpSavedMultiplayer')
        self.assertTrue(self.verdict(changed)['errors'])

    def test_disk_checkpoint_changes_and_wrong_file_are_rejected(self):
        path = Path(self.records['host']['final']['checkpointPath'])
        path.write_text('{"num_reloads":99}', encoding='utf-8')
        self.assertTrue(self.verdict()['errors'])
        changed = copy.deepcopy(self.records); changed['host']['final']['checkpointPath'] = str(path.with_name('current_run.save'))
        self.assertTrue(self.verdict(changed)['errors'])
        # Matching the new disk digest is insufficient: canonicalization may
        # refresh its observed timestamp and increment reloads exactly once,
        # but it must preserve every other persisted field.
        for mutation in ('early-clock', 'late-clock', 'bad-bounds', 'double-reload', 'changed-roster', 'extra-field'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.records)
                final = changed['host']['final']
                if mutation == 'early-clock': final['afterLoad']['save_time'] = 199
                if mutation == 'late-clock': final['afterLoad']['save_time'] = 202
                if mutation == 'bad-bounds': final['canonicalizedAt']['before'] = True
                if mutation == 'double-reload': final['afterLoad']['num_reloads'] = 2
                if mutation == 'changed-roster': final['afterLoad']['players'][1]['net_id'] = 3
                if mutation == 'extra-field': final['afterLoad']['unreviewed_mutation'] = True
                path.write_text(json.dumps(final['afterLoad']), encoding='utf-8')
                final['checkpointSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                errors = self.verdict(changed)['errors']
                self.assertTrue(errors)
                self.assertTrue(any('canonical' in error.lower() for error in errors), errors)

    def test_errors_and_claimed_hot_snapshot_rejoin_are_rejected(self):
        raw = logs(self.records); raw['client'] += '\n' + gate.PREFIX + 'ERROR {}'
        self.assertTrue(gate.check_pair(raw, self.pair, self.tokens, self.roots, self.pids)['errors'])
        changed = copy.deepcopy(self.records); changed['host']['stages'][-1]['metrics']['arbitraryMidcombatSnapshot'] = True
        self.assertTrue(self.verdict(changed)['errors'])


class PeerRunner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='volibear-peer-runner-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def patches(self, stack):
        stack.enter_context(mock.patch.object(suite.h, 'ROOT', self.folder))
        stack.enter_context(mock.patch.object(suite.h, 'IS_WINDOWS', True))
        stack.enter_context(mock.patch.object(suite.h, 'validate_game'))
        stack.enter_context(mock.patch.object(suite, 'deployed_hashes', return_value={'Volibear.dll': 'digest'}))
        stock = stack.enter_context(mock.patch.object(suite.h, 'stock_teardown', return_value=(set(), STOCK)))
        stack.enter_context(mock.patch.object(suite, 'free_loopback_port', return_value=31234))
        stack.enter_context(mock.patch.object(suite.h, 'repository_metadata', return_value={}))
        stack.enter_context(mock.patch.object(suite, 'check_pair', return_value=dict(errors=[], scope=gate.SCOPE)))
        return stock

    def test_one_stock_and_two_concurrent_owned_profiles_no_bootstrap(self):
        barrier = threading.Barrier(2)
        captured = {}
        def launch(game, directory, env, command, *_):
            role = env['VOLIBEAR_MULTIPLAYER_ROLE']; captured[role] = dict(env=env, command=command)
            barrier.wait(timeout=3)
            return dict(pid=100 if role == 'host' else 200, checks={'complete': True}), ''
        with ExitStack() as stack:
            stock = self.patches(stack)
            stack.enter_context(mock.patch.object(suite, 'launch_peer', side_effect=launch))
            report = suite.run_suite(self.folder, display='background')
        stock.assert_called_once(); self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['multiplayer_processes'], 2)
        self.assertNotEqual(captured['host']['env']['VOLIBEAR_TEST_DATA_ROOT'], captured['client']['env']['VOLIBEAR_TEST_DATA_ROOT'])
        self.assertTrue(Path(report['report']).is_file())
        for role, row in captured.items():
            self.assertNotIn('--bootstrap', row['command'])
            self.assertIn('--force-steam=off', row['command'])
            self.assertEqual(row['env']['VOLIBEAR_TEST_SCENARIO'], 'multiplayer-suite')
            self.assertEqual(row['env']['VOLIBEAR_TEST_PRIVATE_DESKTOP'], '1')

    def test_inherited_scenarios_and_old_peer_settings_are_removed(self):
        with mock.patch.object(suite.h, 'IS_WINDOWS', True):
            env = suite.peer_environment(dict(VOLIBEAR_TEST_TOKEN='new', VOLIBEAR_TEST_DATA_ROOT='private',
                VOLIBEAR_TEST_ENGAGE='1', VOLIBEAR_TEST_SCENARIO='baseline', VOLIBEAR_SAVE_PHASE='resume',
                VOLIBEAR_NATIVE_RUN_MODE='old', VOLIBEAR_MULTIPLAYER_OLD='stale'),
                pair='pair', role='host', control=self.folder, port=1)
        for name in ('VOLIBEAR_TEST_ENGAGE', 'VOLIBEAR_SAVE_PHASE', 'VOLIBEAR_NATIVE_RUN_MODE', 'VOLIBEAR_MULTIPLAYER_OLD'):
            self.assertNotIn(name, env)
        self.assertEqual(env['VOLIBEAR_TEST_TOKEN'], 'new')

    def test_invalid_options_and_failed_stock_prevent_peer_launch(self):
        for options in (dict(display='window'), dict(timeout=True), dict(timeout=2), dict(frames=False), dict(frames=10)):
            with mock.patch.object(suite.h, 'IS_WINDOWS', True), mock.patch.object(suite, 'launch_peer') as launch:
                with self.assertRaises(ValueError): suite.run_suite(self.folder, **options)
                launch.assert_not_called()
        with ExitStack() as stack:
            self.patches(stack)
            stack.enter_context(mock.patch.object(suite.h, 'stock_teardown', return_value=(set(), dict(STOCK, exit_code=False))))
            launch = stack.enter_context(mock.patch.object(suite, 'launch_peer'))
            with self.assertRaises(RuntimeError): suite.run_suite(self.folder)
            launch.assert_not_called()

    def test_one_missing_or_failed_peer_cannot_pass(self):
        for mode in ('launch-error', 'runtime-error', 'same-pid'):
            with self.subTest(mode=mode), ExitStack() as stack:
                self.patches(stack)
                def launch(game, directory, env, *args):
                    client = env['VOLIBEAR_MULTIPLAYER_ROLE'] == 'client'
                    if client and mode == 'launch-error': raise RuntimeError('native executable failed')
                    return dict(pid=100 if not client or mode == 'same-pid' else 200,
                                checks={'complete': not (client and mode == 'runtime-error')}), ''
                stack.enter_context(mock.patch.object(suite, 'launch_peer', side_effect=launch))
                self.assertEqual(suite.run_suite(self.folder)['status'], 'failed')

    def test_probe_uses_only_native_transport_actions_and_save_apis(self):
        for name in ('MultiplayerAcceptanceProbe', 'NativeMultiplayerSession', 'NativeLobbyApi'):
            source = (ROOT / 'src/Volibear' / (name + '.cs')).read_text(encoding='utf-8')
            for forbidden in ('PushInput(', 'ForceClick(', 'InputEvent', 'SendInput(', 'EmitSignal(', 'SetUpTest(', 'SetUpReplay('):
                self.assertNotIn(forbidden, source)
        source = (ROOT / 'src/Volibear/MultiplayerAcceptanceProbe.cs').read_text(encoding='utf-8')
        self.assertIn('RequestEnqueue(new PlayCardAction', source)
        self.assertIn('new EndPlayerTurnAction(Local, Local.PlayerCombatState!.TurnNumber)', source)
        self.assertNotIn('PlayerCmd.EndTurn(', source)
        self.assertNotIn('action.CompletionTask', source)
        self.assertIn('LoadAndCanonicalizeMultiplayerRunSave', source)
        self.assertIn('multiplayerRunSaveFileName', source)

    def test_cold_scene_budget_does_not_relax_network_handshakes(self):
        source = (ROOT / 'src/Volibear/NativeMultiplayerSession.cs').read_text(encoding='utf-8')
        self.assertIn('int timeoutSeconds = 90', source)
        self.assertIn('clock.Elapsed.TotalSeconds > timeoutSeconds', source)
        self.assertIn('stage is "native StartNewMultiplayerRun" or "native saved multiplayer load" ? 360 : 90', source)
        self.assertIn('await Until(() => task.IsCompleted, stage, timeout)', source)
        self.assertIn('Call(service!, "Disconnect", quit, false)', source)
        self.assertNotIn('Call(service!, "Disconnect", quit, true)', source)

    def test_cli_requires_both_explicit_native_flags(self):
        for flags in ([], ['--execute-native'], ['--use-deployed']):
            with redirect_stderr(io.StringIO()), mock.patch.object(suite, 'run_suite') as run:
                with self.assertRaises(SystemExit) as error: suite.main(flags)
                self.assertEqual(error.exception.code, 2); run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
