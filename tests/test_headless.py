import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import headless


class HeadlessRunnerTests(unittest.TestCase):
    def test_caught_probe_exceptions_are_runtime_errors_not_clean_exit(self):
        for marker in ('DOMAIN_REVIVAL_PROBE_ERROR', 'PREPARED_CHOICE_ERROR',
                       'DOMAIN_SUMMON_D17_ERROR', 'ENEMY_EXPLORATION_ERROR',
                       'AUDIO_RECEIPT_FAILED'):
            line = '[Volibear] ' + marker + ' System.NullReferenceException: fixture failure'
            with self.subTest(marker=marker):
                self.assertEqual(headless.error_lines(line), [line])
                self.assertFalse(headless.evaluate(0, False, line)['no_runtime_errors'])
        # A serialized expected rejection observation is not a failure marker.
        self.assertEqual(headless.error_lines('[Volibear] RESULT {"expectedException":"InvalidOperationException"}'), [])

    def contract_record(self, variant='e01'):
        absorbed = 5 if variant == 'e01' else 8
        hp = 77 if variant == 'e01' else 80
        block = 2 if variant == 'e02' else 0
        hand_after = 5 if variant == 'b04' else 6
        receipt = lambda amount: dict(Performed=True, Completed=True, Absorbed=amount)
        return dict(token='current', scenario='engage-contract', variant=variant, passed=True,
                    testMode=False, acceptance='effect-only-not-payment',
                    api='CardCmd.AutoPlay:Volibear_B04' if variant == 'b04' else 'Core.EngageCmd.Perform',
                    enemy='LeafSlimeS', nativeMove='TACKLE_MOVE', strength=5, fixtureEnemyHp=50,
                    hpBefore=80, blockBefore={'e01': 5, 'e02': 10, 'b04': 0}[variant],
                    hpAfter=hp, blockAfter=block, enemyHpBefore=50,
                    enemyHpAfter=44 if variant == 'b04' else 50,
                    handBefore=5, handAfter=hand_after, firstHandDraw=1, first=receipt(absorbed),
                    firstBlockReceipts=[absorbed], movesAfter=1,
                    duplicate=dict(Performed=False, Completed=False, Absorbed=0),
                    duplicateHp=hp, duplicateBlock=block, duplicateHand=hand_after,
                    duplicateMoves=1, duplicateDamageReceipts=0,
                    secondResult=receipt(4), secondHandBefore=hand_after, secondHandAfter=hand_after,
                    roundBefore=1, roundAfter=2, turnBefore=1, turnAfter=2,
                    phaseMonsters=['LeafSlimeS', 'LeafSlimeM', 'TwigSlimeS'], phaseMoveCounts=[1, 1, 1],
                    nextNativeMove='GOOP_MOVE', next=receipt(8), nextHandBefore=5, nextHandAfter=6,
                    nextHp=80, nextBlock=2, nextMoves=2)

    def test_production_engage_cases_require_distinct_exact_measurements(self):
        for variant in ('e01', 'e02', 'b04'):
            record = self.contract_record(variant)
            line = '[Volibear] ENGAGE_CONTRACT_RESULT ' + json.dumps(record)
            with self.subTest(variant=variant):
                self.assertTrue(headless.engage_contract_evidence(line, 'current', variant)[1])
                self.assertFalse(headless.engage_contract_evidence(line, 'stale', variant)[1])
                for missing in record:
                    bad = dict(record)
                    del bad[missing]
                    self.assertFalse(headless.engage_contract_evidence(
                        '[Volibear] ENGAGE_CONTRACT_RESULT ' + json.dumps(bad), 'current', variant)[1], missing)
        e01 = '[Volibear] ENGAGE_CONTRACT_RESULT ' + json.dumps(self.contract_record())
        for log in ('', e01 + '\n' + e01, '[Volibear] ENGAGE_CONTRACT_RESULT []',
                    '[Volibear] ENGAGE_CONTRACT_RESULT null', '[Volibear] ENGAGE_CONTRACT_RESULT invalid'):
            self.assertFalse(headless.engage_contract_evidence(log, 'current', 'e01')[1])
        self.assertFalse(headless.engage_contract_evidence(e01, 'current', 'e02')[1])

    def test_production_engage_rejects_forged_receipts_draws_and_phase(self):
        import copy
        mutations = dict(scenario='content', api='simulated', enemy='Dummy', nativeMove='fake', strength=0,
                         testMode=True, passed=False, acceptance='ordinary-payment',
                         fixtureEnemyHp=49, hpBefore=79, blockBefore=4, hpAfter=80, blockAfter=1,
                         enemyHpBefore=49, enemyHpAfter=44, handBefore=4, handAfter=5, firstHandDraw=0,
                         firstBlockReceipts=[3], movesAfter=2, duplicateHp=76, duplicateBlock=1,
                         duplicateHand=7, duplicateMoves=2, duplicateDamageReceipts=1,
                         secondHandBefore=5, secondHandAfter=7, roundBefore=0, roundAfter=1,
                         turnBefore=0, turnAfter=1, phaseMoveCounts=[2, 1, 1],
                         phaseMonsters=['LeafSlimeS', 'LeafSlimeM', 'Dummy'], nextNativeMove='TACKLE_MOVE',
                         nextHandBefore=4, nextHandAfter=5, nextHp=79, nextBlock=1, nextMoves=3)
        for field, value in mutations.items():
            bad = self.contract_record()
            bad[field] = value
            with self.subTest(field=field):
                self.assertFalse(headless.engage_contract_evidence(
                    '[Volibear] ENGAGE_CONTRACT_RESULT ' + json.dumps(bad), 'current', 'e01')[1])
        for receipt in ('first', 'duplicate', 'secondResult', 'next'):
            for field in ('Performed', 'Completed', 'Absorbed'):
                bad = copy.deepcopy(self.contract_record())
                bad[receipt][field] = 99
                self.assertFalse(headless.engage_contract_evidence(
                    '[Volibear] ENGAGE_CONTRACT_RESULT ' + json.dumps(bad), 'current', 'e01')[1])
        for field, value in [('movesAfter', True), ('phaseMoveCounts', [True, 1, 1]),
                             ('firstBlockReceipts', [True]), ('strength', True)]:
            bad = self.contract_record()
            bad[field] = value
            self.assertFalse(headless.engage_contract_evidence(
                '[Volibear] ENGAGE_CONTRACT_RESULT ' + json.dumps(bad), 'current', 'e01')[1])

    def test_shader_teardown_needs_matching_category_and_does_not_hide_runtime_error(self):
        canvas = 'ERROR: 3 shaders of type CanvasShaderRD were never freed'
        particles = 'ERROR: 2 shaders of type ParticlesShaderRD were never freed'
        stock = headless.teardown_categories([canvas])
        self.assertTrue(headless.is_teardown(canvas))
        self.assertTrue(headless.evaluate(0, False, canvas, stock)['teardown_matches_stock'])
        self.assertFalse(headless.evaluate(0, False, particles, stock)['teardown_matches_stock'])
        self.assertFalse(headless.evaluate(0, False, canvas, set())['teardown_matches_stock'])
        self.assertFalse(headless.evaluate(0, False, canvas + '\nERROR: gameplay broke', stock)['no_runtime_errors'])
        self.assertFalse(headless.is_teardown('ERROR: shaders failed compiling CanvasShaderRD'))

    def test_opengl_teardown_is_category_matched_not_blanket_ignored(self):
        canvas = 'ERROR: 5 shaders of type CanvasShaderGLES3 were never freed'
        texture = 'ERROR: Texture with GL ID of 15: leaked 20 bytes.'
        stock = headless.teardown_categories([canvas, texture])
        log = canvas + '\nERROR: Texture with GL ID of 260: leaked 1020 bytes.'
        self.assertTrue(headless.evaluate(0, False, log, stock)['no_runtime_errors'])
        self.assertTrue(headless.evaluate(0, False, log, stock)['teardown_matches_stock'])
        self.assertFalse(headless.evaluate(0, False, log, set())['teardown_matches_stock'])
        particles = 'ERROR: 1 shaders of type ParticlesShaderGLES3 were never freed'
        self.assertFalse(headless.evaluate(0, False, particles, stock)['teardown_matches_stock'])
        for error in ('ERROR: Texture upload failed', 'ERROR: shaders failed compiling CanvasShaderGLES3',
                      'ERROR: Texture with GL ID of 15: corrupted data.'):
            self.assertFalse(headless.is_teardown(error))
            self.assertFalse(headless.evaluate(0, False, log + '\n' + error, stock)['no_runtime_errors'])

    def test_stock_control_timeout_never_supplies_accepted_categories(self):
        leak = 'Steam initialization skipped\nSTOCK_CONTROLLER_READY_NATIVE_QUIT\nERROR: 3 shaders of type CanvasShaderRD were never freed'
        with mock.patch.object(headless, 'prepare_run', return_value=(Path('fixture'), {}, ['game'])) as prepare, \
                mock.patch.object(headless, 'launch', return_value=(0, True)), \
                mock.patch.object(headless, 'combined_log', return_value=leak):
            categories, evidence = headless.stock_teardown(Path('game'), 180, 3600, 'window')
            self.assertEqual(prepare.call_args.args[2], 0)
            self.assertFalse(evidence['successful'])
            self.assertEqual(categories, set())
        with mock.patch.object(headless, 'prepare_run', return_value=(Path('fixture'), {}, ['game'])), \
                mock.patch.object(headless, 'launch', return_value=(0, False)), \
                mock.patch.object(headless, 'combined_log', return_value=leak):
            categories, evidence = headless.stock_teardown(Path('game'), 180, 100, 'window')
            self.assertTrue(evidence['successful'])
            self.assertEqual(evidence['frames'], 0)
            self.assertEqual(categories, headless.teardown_categories(headless.error_lines(leak)))

    def test_stock_requires_readiness_and_native_quit_marker(self):
        for marker in ('', 'STOCK_CONTROLLER_ERROR readiness timeout',
                       'STOCK_CONTROLLER_READY_NATIVE_QUIT\nSTOCK_CONTROLLER_READY_NATIVE_QUIT'):
            with mock.patch.object(headless, 'prepare_run', return_value=(Path('fixture'), {}, ['game'])), \
                 mock.patch.object(headless, 'launch', return_value=(0, False)) as launch, \
                 mock.patch.object(headless, 'combined_log', return_value='Steam initialization skipped\n' + marker):
                categories, evidence = headless.stock_teardown(Path('game'), 300, 600, 'window')
                self.assertFalse(evidence['successful'])
                self.assertEqual(categories, set())
                command = launch.call_args.args[3]
                self.assertIn('--nomods', command)
                self.assertIn('--script', command)

    def content_record(self):
        return dict(token='current', scenario='content', passed=True, testMode=False,
                    api='CardCmd.AutoPlay', acceptance='effect-only-not-payment',
                    cards=['Volibear_B01', 'Volibear_B02', 'Volibear_B03'],
                    character='VolibearCharacter', startingHp=80, deckSize=10, played=3,
                    attackBefore=50, attackAfter=44, attackDelta=6,
                    blockBefore=0, blockAfter=5, blockGain=5, enemyCount=2,
                    fixtureEnemyHp=50, originalEnemyHp=[15, 16],
                    fixtureApi='CreatureCmd.SetMaxAndCurrentHp;CardPileCmd.Add',
                    enemyBefore=[50, 44], enemyAfter=[39, 41], enemyDeltas=[11, 3])

    def test_content_requires_current_unique_structured_evidence(self):
        line = '[Volibear] CONTENT_RESULT ' + json.dumps(self.content_record())
        self.assertTrue(headless.content_evidence(line, 'current')[1])
        self.assertFalse(headless.content_evidence(line, 'stale')[1])
        self.assertFalse(headless.content_evidence(line, 'current', 'baseline')[1])
        for log in ('', line + '\n' + line, '[Volibear] CONTENT_RESULT []',
                    '[Volibear] CONTENT_RESULT null', '[Volibear] CONTENT_RESULT broken'):
            with self.subTest(log=log):
                self.assertFalse(headless.content_evidence(log, 'current')[1])

    def test_content_rejects_forged_pass_and_each_bad_measurement(self):
        mutations = dict(token='other', scenario='baseline', passed=False, testMode=True,
                         api='OnPlay', acceptance='ordinary-input', cards=['B01'],
                         character='Ironclad', startingHp=79, deckSize=9, played=2,
                         attackBefore=16, attackAfter=8, attackDelta=5,
                         blockBefore=1, blockAfter=4, blockGain=4, enemyCount=3,
                         enemyBefore=[14, 9], enemyAfter=[3, 6], enemyDeltas=[10, 3])
        for field, value in mutations.items():
            with self.subTest(field=field):
                record = self.content_record()
                record[field] = value
                self.assertFalse(headless.content_evidence(
                    '[Volibear] CONTENT_RESULT ' + json.dumps(record), 'current')[1])
        for field in self.content_record():
            record = self.content_record()
            del record[field]
            with self.subTest(missing=field):
                self.assertFalse(headless.content_evidence(
                    '[Volibear] CONTENT_RESULT ' + json.dumps(record), 'current')[1])
        for field, value in [('played', True), ('attackDelta', 6.0), ('enemyDeltas', [11, 3.0]),
                             ('enemyBefore', None), ('enemyAfter', [0, 6])]:
            record = self.content_record()
            record[field] = value
            self.assertFalse(headless.content_evidence(
                '[Volibear] CONTENT_RESULT ' + json.dumps(record), 'current')[1])

    def test_display_command_keeps_headless_default_and_posix_options(self):
        command = ['game', '--headless', '--audio-driver', 'Dummy', '--force-steam=off']
        self.assertEqual(headless.display_command(command, 'headless'), command)
        with mock.patch.object(headless, 'IS_WINDOWS', False):
            virtual = headless.display_command(command, 'xvfb')
            self.assertEqual(virtual[0], 'xvfb-run')
            self.assertIn('gl_compatibility', virtual)
            self.assertNotIn('--headless', virtual)
            self.assertIn('--force-steam=off', virtual)
            with mock.patch.dict(headless.os.environ, {'DISPLAY': ':77'}):
                window = headless.display_command(command, 'window')
                self.assertEqual(window, ['game', '--force-steam=off', '--display-driver', 'x11',
                                          '--rendering-method', 'gl_compatibility',
                                          '--windowed', '--resolution', '1280x720',
                                          '--script', str(headless.ROOT / 'tools/window_guard.gd')])
                self.assertNotIn('xvfb-run', window)
                self.assertNotIn('llvmpipe', window)
            with mock.patch.dict(headless.os.environ, {'DISPLAY': ''}):
                with self.assertRaisesRegex(RuntimeError, 'DISPLAY'):
                    headless.display_command(command, 'window')
            with self.assertRaisesRegex(RuntimeError, 'Windows'):
                headless.display_command(command, 'background')
        with mock.patch.object(headless, 'IS_WINDOWS', True):
            window = headless.display_command(command, 'window')
            self.assertEqual(window, ['game', '--force-steam=off', '--windowed', '--resolution', '1280x720'])
            with self.assertRaisesRegex(RuntimeError, 'POSIX'):
                headless.display_command(command, 'xvfb')

    @unittest.skipUnless(headless.IS_WINDOWS, 'Windows native window fixtures')
    def test_window_preparation_preserves_offline_profile_and_token(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(headless, 'ROOT', Path(tmp)):
            directory, env, command = headless.prepare_run(Path(tmp) / 'game', 'token', 300, 'window')
            self.assertNotIn('--headless', command)
            self.assertNotIn('--audio-driver', command)
            self.assertNotIn('Dummy', command)
            self.assertIn('--force-steam=off', command)
            self.assertIn('--quit-after', command)
            self.assertEqual(env['VOLIBEAR_TEST_TOKEN'], 'token')
            self.assertEqual(env['VOLIBEAR_TEST_FAST_MODE'], 'Fast')
            self.assertEqual(env['VOLIBEAR_TEST_DATA_ROOT'], str(headless.user_data_root(directory)))
            for key, _ in headless.ISOLATION_BINDINGS:
                self.assertTrue(Path(env[key]).is_relative_to(directory))
            settings = json.loads((headless.user_data_root(directory) / 'default/1/settings.save').read_text())
            self.assertTrue(settings['mod_settings']['mods_enabled'])
            self.assertFalse(settings['fullscreen'])
            self.assertFalse(settings['limit_fps_in_background'])

    @unittest.skipUnless(headless.IS_WINDOWS, 'Windows private-desktop native renderer')
    def test_background_native_renderer_owns_unselected_desktop(self):
        command = headless.display_command(['game', '--headless', '--audio-driver', 'Dummy', '--force-steam=off'], 'background')
        self.assertEqual(command, ['game', '--force-steam=off', '--windowed', '--resolution', '1280x720', '--audio-driver', 'Dummy'])
        with mock.patch.object(headless, '_create_job', return_value='owned-job'), \
             mock.patch.object(headless, '_create_private_desktop', return_value=(None, 678, 'fixture-desktop')), \
             mock.patch.object(headless, '_assert_isolated_desktop'), \
             mock.patch.object(headless, '_assign_job', return_value=True), \
             mock.patch.object(headless.subprocess, 'Popen') as spawn, \
             mock.patch.object(headless._kernel32, 'CloseHandle'), \
             mock.patch.object(headless._user32, 'CloseDesktop') as close:
            headless.spawn_owned(command, 'cwd', {'VOLIBEAR_TEST_PRIVATE_DESKTOP':'1'}, None, window=True)
            self.assertEqual(spawn.call_args.kwargs['startupinfo'].lpDesktop, 'fixture-desktop')
            self.assertEqual(spawn.call_args.kwargs['creationflags'], 0)
            headless.close_owned('owned-job')
            close.assert_called_once_with(678)
        self.assertNotIn('owned-job', headless._desktops_by_job)

    @unittest.skipUnless(headless.IS_WINDOWS, 'Windows private-desktop launch failure')
    def test_private_desktop_launch_failure_releases_owned_handles(self):
        with mock.patch.object(headless, '_create_job', return_value='failed-job'), \
             mock.patch.object(headless, '_create_private_desktop', return_value=(None, 679, 'fixture-desktop')), \
             mock.patch.object(headless, '_assert_isolated_desktop'), \
             mock.patch.object(headless.subprocess, 'Popen', side_effect=OSError('launch failed')), \
             mock.patch.object(headless._kernel32, 'CloseHandle') as close_job, \
             mock.patch.object(headless._user32, 'CloseDesktop') as close_desktop:
            with self.assertRaisesRegex(OSError, 'launch failed'):
                headless.spawn_owned(['game'], 'cwd', {'VOLIBEAR_TEST_PRIVATE_DESKTOP':'1'}, None, window=True)
            close_job.assert_called_once_with('failed-job')
            close_desktop.assert_called_once_with(679)
        self.assertNotIn('failed-job', headless._desktops_by_job)

    @unittest.skipUnless(headless.IS_WINDOWS, 'Windows owned process flags')
    def test_window_process_uses_same_job_ownership_without_hidden_flag(self):
        with mock.patch.object(headless, '_create_job', return_value='owned-job'), \
                mock.patch.object(headless, '_assign_job', return_value=True) as assign, \
                mock.patch.object(headless.subprocess, 'Popen') as spawn:
            process, job = headless.spawn_owned(['game'], 'cwd', {}, None, window=True)
            self.assertEqual(job, 'owned-job')
            assign.assert_called_once_with(job, process)
            self.assertEqual(spawn.call_args.kwargs['creationflags'], 0)

    def test_stock_control_uses_requested_display(self):
        directory = Path('fixture')
        with mock.patch.object(headless, 'prepare_run', return_value=(directory, {}, ['game'])) as prepare, \
                mock.patch.object(headless, 'launch', return_value=(0, False)) as launch, \
                mock.patch.object(headless, 'combined_log', return_value=''):
            headless.stock_teardown(Path('game'), 30, 300, 'window')
            self.assertEqual(prepare.call_args.args[-1], 'window')
            self.assertIn('--nomods', launch.call_args.args[3])

    def test_exit_zero_alone_not_success(self):
        self.assertFalse(all(headless.evaluate(0, False, '').values()))

    def test_engine_error_rejects_load_marker(self):
        checks = headless.evaluate(0, False,
            'Steam initialization skipped\n[Volibear] LOAD_OK\nSCRIPT ERROR: failed')
        self.assertFalse(checks['no_runtime_errors'])

    def test_engine_teardown_leaks_are_not_runtime_errors(self):
        leak = ("ERROR: 27 RID allocations of type 'PN13RendererDummy14TextureStorage"
                "12DummyTextureE' were leaked at exit.")
        log = 'Steam initialization skipped\n[Volibear] LOAD_OK\n' + leak
        checks = headless.evaluate(0, False, log)
        self.assertTrue(checks['no_runtime_errors'])
        stock = headless.teardown_categories([leak])
        self.assertTrue(headless.evaluate(0, False, log, stock)['teardown_matches_stock'])

    def test_teardown_category_not_in_stock_control_fails(self):
        stock = headless.teardown_categories(
            ["ERROR: 27 RID allocations of type 'A' were leaked at exit."])
        novel = "ERROR: 3 RID allocations of type 'SomethingNew' were leaked at exit."
        self.assertFalse(headless.evaluate(0, False, novel, stock)['teardown_matches_stock'])
        # Counts differ per run; only the category may be compared.
        same = headless.teardown_categories(
            ["ERROR: 99 RID allocations of type 'A' were leaked at exit."])
        self.assertTrue(headless.evaluate(0, False, novel.replace('SomethingNew', 'A'), stock)['teardown_matches_stock'])
        self.assertEqual(same, stock)

    def test_timeout_always_fails(self):
        self.assertFalse(headless.evaluate(0, True,
            'Steam initialization skipped\n[Volibear] LOAD_OK')['exited_zero'])

    def test_cloud_backend_rejected(self):
        self.assertFalse(headless.evaluate(0, False,
            'Steam initialization skipped\nwrite saves to steam storage')['no_cloud_backend'])

    def test_scenario_evidence_rejects_stale_missing_and_malformed(self):
        record = dict(scenario='baseline', token='current', passed=True,
                      before=80, after=74, resultCount=1, roundBefore=1, roundAfter=2,
                      api='DamageCmd.Attack', testMode=False,
                      cardApi='CardCmd.AutoPlay:StrikeIronclad',
                      cardTargetBefore=15, cardTargetAfter=9)
        line = '[Volibear] BASELINE_RESULT ' + json.dumps(record)
        self.assertTrue(headless.scenario_evidence(line, 'current', 'baseline')[1])
        for log in ('', line + '\n' + line, '[Volibear] BASELINE_RESULT []',
                    '[Volibear] BASELINE_RESULT broken'):
            self.assertFalse(headless.scenario_evidence(log, 'current', 'baseline')[1])
        self.assertFalse(headless.scenario_evidence(line, 'stale', 'baseline')[1])
        record['after'] = 15
        self.assertFalse(headless.scenario_evidence('[Volibear] BASELINE_RESULT ' +
            json.dumps(record), 'current', 'baseline')[1])

    def test_engage_evidence_requires_exact_variant_and_absorption(self):
        import copy
        record = dict(engageEnabled=True, skippedActions=1,
                      responseCount=1, responseBlockBefore=27, responseBlockAfter=30, followupDamage=1,
                      engageOrder=['pre-effect-finished', 'enemy-action-finished',
                                   'completion-response', 'duplicate-rejected', 'remaining-card-effect'],
                      engage=dict(Performed=True, Absorbed=3, Completed=True),
                      duplicate=dict(Performed=False, Absorbed=0, Completed=False))
        self.assertTrue(headless.engage_evidence(record, True))
        self.assertFalse(headless.engage_evidence(record, False))
        self.assertFalse(headless.engage_evidence(None, True))
        for key, value in [('engageEnabled', False), ('skippedActions', 0),
                           ('engage', None), ('duplicate', {}), ('responseCount', 2),
                           ('responseBlockAfter', 27), ('followupDamage', 0), ('engageOrder', [])]:
            bad = copy.deepcopy(record)
            bad[key] = value
            self.assertFalse(headless.engage_evidence(bad, True))
        for field, value in [('Absorbed', 0), ('Completed', False), ('Performed', False)]:
            bad = copy.deepcopy(record)
            bad['engage'][field] = value
            self.assertFalse(headless.engage_evidence(bad, True))
        self.assertTrue(headless.engage_evidence(dict(engageEnabled=False,
            engage=None, duplicate=None, skippedActions=0), False))

    def _spawn(self, directory, command):
        output = (directory / 'stdout.log').open('w')
        try:
            process, job = headless.spawn_owned(command, str(directory), os.environ.copy(), output)
        finally:
            # The child owns its duplicated handle; Windows cannot delete an open file.
            output.close()
        self.addCleanup(headless.close_owned, job)
        return process, job

    def test_owned_process_timeout(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            directory = Path(tmp)
            process, job = self._spawn(directory, [sys.executable, '-c', 'import time; time.sleep(60)'])
            code, timed_out = headless.wait_owned_process(process, 0.05, job)
            self.assertTrue(timed_out)
            self.assertNotEqual(code, 0)
            self.assertIsNotNone(process.poll())

    def test_wrapper_exit_still_cleans_group(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            directory = Path(tmp)
            pidfile = directory / 'child.pid'
            script = ('import subprocess,sys; from pathlib import Path; '
                      'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                      'Path(sys.argv[1]).write_text(str(p.pid))')
            process, job = self._spawn(directory, [sys.executable, '-c', script, str(pidfile)])
            code, timed_out = headless.wait_owned_process(process, 5, job)
            self.assertEqual(code, 0)
            self.assertFalse(timed_out)
            pid = int(pidfile.read_text())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if not headless.process_alive(pid):
                    break
                time.sleep(0.01)
            else:
                self.fail('Owned child survived wrapper cleanup')

    def test_environment_isolated(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            directory = Path(tmp)
            env = headless.isolated_env(directory)
            for key, _ in headless.ISOLATION_BINDINGS:
                self.assertTrue(Path(env[key]).is_relative_to(directory))
                self.assertTrue(Path(env[key]).is_dir())
            self.assertTrue(headless.user_data_root(directory).is_relative_to(directory))

    def test_engine_log_preferred_over_redirected_stdout(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            directory = Path(tmp)
            (directory / 'stdout.log').write_text('')
            (directory / 'game.log').write_text('[Volibear] LOAD_OK\n')
            self.assertIn('LOAD_OK', headless.combined_log(directory))


class DomainEvidenceTests(unittest.TestCase):
    """Synthetic validator self-tests, not engine execution or card acceptance."""
    def record(self, variant='d01'):
        refs = ['starting-0', 'starting-1'] if variant == 'd01' else [] if variant == 'l02' else ['native-twin-strike']
        force = {'d01': 2, 'd02': 0, 'd03': 0, 'l02': 3}.get(variant, 2)
        replay = 1 if variant == 'd03' else 0
        hp = {'d01': [76, 88, 88], 'd02': [86, 96, 96], 'd03': [76, 96, 96], 'l02': [100, 100, 100]}.get(variant)
        r = dict(token='current', scenario='domain-contract', variant=variant, completed=True, testMode=False,
                 acceptance='effect-only-not-payment', character='VolibearCharacter',
                 fixtureApi='CreatureCmd.SetMaxAndCurrentHp;CardPileCmd.Add;PowerCmd;CardCmd.AutoPlay',
                 api='LightningCmd+CreatureCmd.Damage' if variant == 'l02' else 'CardPileCmd.Draw+PlayerCmd.EndTurn'
                     if variant == 'draw-expiry' else 'CardCmd.AutoPlay',
                 proxy='native-TwinStrike-not-C02-acceptance' if variant in ('d02', 'd03') else 'none',
                 enemyIds=[10, 11, 12], enemyTypes=['LeafSlimeS', 'LeafSlimeM', 'TwigSlimeS'], batches=[])
        if variant == 'draw-expiry':
            refs = ['starting-0', 'starting-1', 'starting-2']
            d = lambda ref, hand: dict(cardRef=ref, fromHandDraw=hand)
            r['data'] = dict(inputs=dict(domainRounds=1, storm=2, directDrawCount=1, normalDrawCount=5,
                outsideDrawCount=1, energy=3, replacementRefs=refs, statusType='Void'), roundBefore=1, turnBefore=1,
                direct=dict(energy=3, domain=1, handCount=1, voidPile='Exhaust', replacementPile='Hand',
                    sameVoid=True, sameReplacement=True, drawn=[d('direct-void', False), d(refs[0], False)]),
                boundary=dict(round=2, turn=2, domainAfterFullDraw=[1], domainAfterEarlyHook=0, storm=2,
                    count=0, energy=3, handCount=5, voidPile='Exhaust', replacementPile='Hand', sameVoid=True,
                    sameReplacement=True, drawn=[d('boundary-void', True), d(refs[1], False),
                        d(refs[2], True), d('starting-3', True), d('starting-4', True), d('starting-5', True)]),
                outside=dict(energyBefore=3, energyAfter=2, handBefore=4, handAfter=5, voidPile='Hand',
                    replacementPile='Draw', sameVoid=True, drawn=[d('outside-void', False)]))
            return r
        count = 2 if variant == 'd01' else 1
        r['data'] = dict(inputs=dict(domainRounds=0 if variant == 'l02' else 1, storm=force,
            fixtureEnemyHp=100, fixtureEnemyBlock=10 if variant == 'l02' else 0,
            explicitLightningBase=0 if variant == 'l02' else None, unrelatedUnpowered=1 if variant == 'l02' else 0,
            cards=[dict(cardRef=ref, type='Volibear_B01' if variant == 'd01' else 'TwinStrike',
                        upgrade=False, replay=replay) for ref in refs]),
            beforeHp=[100] * 3, beforeBlock=[10 if variant == 'l02' else 0] * 3,
            afterHp=hp, afterBlock=[7 if variant == 'l02' else 0] * 3, finalHp=hp,
            finalBlock=[6 if variant == 'l02' else 0] * 3, countBefore=0, countAfter=count, countFinal=count,
            domainAmount=0 if variant == 'l02' else 1, stormAmount=force,
            energyBefore=3, energyAfter=3, actualAutoPlayCalls=len(refs),
            cardPiles=[dict(cardRef=ref, pile='Discard', sameIdentity=True) for ref in refs],
            playHistory=[dict(cardRef=ref, index=i, count=replay + 1) for ref in refs for i in range(replay + 1)])
        damage = lambda target, hp, block, props, ref: dict(target=target, hpLost=hp, blocked=block, props=props, cardRef=ref)
        history = []
        if variant == 'l02':
            history = [damage(i, 0, 3, 4, None) for i in r['enemyIds']] + [damage(i, 0, 1, 4, None) for i in r['enemyIds']]
        else:
            for ref in refs:
                history.append(damage(10, 6 if variant == 'd01' else 5, 0, 8, ref))
                history.extend(damage(i, 6 if variant == 'd01' else 4, 0, 4, ref) for i in r['enemyIds'])
                history.extend(damage(10, 5, 0, 8, ref) for _ in range(0 if variant == 'd01' else 3 if variant == 'd03' else 1))
        r['data']['damageHistory'] = history
        for i in range(count):
            r['batches'].append(dict(id=i + 1, round=1, turn=1, baseDamage=0 if variant == 'l02' else 4,
                storm=force, amount=3 if variant == 'l02' else 6 if variant == 'd01' else 4, count=i + 1,
                cardRef=None if variant == 'l02' else refs[i if variant == 'd01' else 0],
                playId=None if variant == 'l02' else i + 100, targets=r['enemyIds'],
                hits=[dict(target=t, hpLost=0 if variant == 'l02' else 6 if variant == 'd01' else 4,
                           blocked=3 if variant == 'l02' else 0, overkill=0) for t in r['enemyIds']]))
        return r

    def check_record(self, record, variant=None):
        return headless.domain_contract_evidence('[Volibear] DOMAIN_CONTRACT_RESULT ' + json.dumps(record),
                                                 'current', variant or record['variant'])[1]

    def test_domain_all_five_synthetic_valid_shapes(self):
        for variant in headless.DOMAIN_CASES:
            with self.subTest(variant=variant):
                self.assertTrue(self.check_record(self.record(variant)))

    def test_domain_rejects_missing_duplicate_cross_run_and_completed_only(self):
        for variant in headless.DOMAIN_CASES:
            record = self.record(variant)
            for field in record:
                bad = dict(record)
                del bad[field]
                self.assertFalse(self.check_record(bad, variant), field)
            line = '[Volibear] DOMAIN_CONTRACT_RESULT ' + json.dumps(record)
            self.assertFalse(headless.domain_contract_evidence(line, 'stale', variant)[1])
            self.assertFalse(headless.domain_contract_evidence(line + '\n' + line, 'current', variant)[1])
        for payload in ('[]', 'null', 'broken', '{"completed":true}'):
            self.assertFalse(headless.domain_contract_evidence('[Volibear] DOMAIN_CONTRACT_RESULT ' + payload, 'current', 'd01')[1])

    def test_domain_rejects_wrong_history_batches_and_identity_despite_completion(self):
        import copy
        mutations = [lambda r: r['data'].__setitem__('afterHp', [82, 94, 94]),
                     lambda r: r['data'].__setitem__('countAfter', 1),
                     lambda r: r['data'].__setitem__('countAfter', True),
                     lambda r: r['data']['damageHistory'].reverse(),
                     lambda r: r['data']['playHistory'].pop(),
                     lambda r: r['batches'].pop(),
                     lambda r: r['batches'][1].__setitem__('playId', r['batches'][0]['playId']),
                     lambda r: r['batches'][1].__setitem__('id', r['batches'][0]['id']),
                     lambda r: r['batches'][0].__setitem__('baseDamage', 8),
                     lambda r: r['batches'][0]['hits'][1].__setitem__('hpLost', 0),
                     lambda r: r['data']['cardPiles'][0].__setitem__('sameIdentity', False),
                     lambda r: r['data']['inputs']['cards'][0].__setitem__('upgrade', True),
                     lambda r: r.__setitem__('proxy', 'C02-card-acceptance')]
        for mutate in mutations:
            record = copy.deepcopy(self.record())
            mutate(record)
            self.assertFalse(self.check_record(record))

    def test_domain_replay_and_multihit_are_distinct_native_histories(self):
        replay = self.record('d03')
        self.assertFalse(self.check_record(replay, 'd02'))
        replay['data']['playHistory'][1]['index'] = 0
        self.assertFalse(self.check_record(replay))
        replay = self.record('d03')
        replay['data']['actualAutoPlayCalls'] = 2
        self.assertFalse(self.check_record(replay))
        replay = self.record('d03')
        replay['batches'].append(replay['batches'][0])
        self.assertFalse(self.check_record(replay))

    def test_domain_zero_base_fully_blocked_and_unrelated_damage_not_counted(self):
        import copy
        for path, value in [(('data', 'countAfter'), 0), (('data', 'countFinal'), 2),
                            (('data', 'afterBlock'), [10, 10, 10]), (('data', 'afterHp'), [97, 97, 97]),
                            (('data', 'finalBlock'), [7, 7, 7])]:
            record = copy.deepcopy(self.record('l02'))
            record[path[0]][path[1]] = value
            self.assertFalse(self.check_record(record))
        record = self.record('l02')
        record['batches'][0]['amount'] = 0
        self.assertFalse(self.check_record(record))

    def test_domain_draw_purge_expiry_and_outside_control_each_required(self):
        import copy
        mutations = [('direct', 'energy', 2), ('direct', 'voidPile', 'Hand'),
                     ('direct', 'sameVoid', False), ('direct', 'handCount', 2),
                     ('boundary', 'domainAfterFullDraw', [0]), ('boundary', 'domainAfterEarlyHook', 1),
                     ('boundary', 'storm', 0), ('boundary', 'voidPile', 'Hand'),
                     ('boundary', 'sameReplacement', False), ('boundary', 'handCount', 6),
                     ('outside', 'energyAfter', 3), ('outside', 'voidPile', 'Exhaust'),
                     ('outside', 'replacementPile', 'Hand')]
        for section, field, value in mutations:
            record = copy.deepcopy(self.record('draw-expiry'))
            record['data'][section][field] = value
            self.assertFalse(self.check_record(record), (section, field))
        record = self.record('draw-expiry')
        record['data']['boundary']['drawn'][1]['fromHandDraw'] = True
        self.assertFalse(self.check_record(record))

    def test_domain_malformed_nested_fields_fail_closed(self):
        import copy
        for variant in headless.DOMAIN_CASES:
            original = self.record(variant)
            for key in original['data']:
                record = copy.deepcopy(original)
                record['data'][key] = None
                self.assertFalse(self.check_record(record), (variant, key))
        for value in (None, [], [None], [True, 11, 12], [10, 10, 12]):
            record = self.record()
            record['enemyIds'] = value
            self.assertFalse(self.check_record(record))

    def test_domain_run_once_routes_exact_case_and_retains_external_gate(self):
        record = self.record('d03')
        log = ('Steam initialization skipped\n[Volibear] LOAD_OK\n'
               '[Volibear] ISOLATION_OK steam=false\n[Volibear] DOMAIN_CONTRACT_RESULT ' + json.dumps(record))
        env, command = {}, ['game']
        with mock.patch.object(headless, 'new_run_id', return_value='current'), \
             mock.patch.object(headless, 'prepare_run', return_value=(Path('synthetic'), env, command)), \
             mock.patch.object(headless, 'launch', return_value=(0, False)), \
             mock.patch.object(headless, 'combined_log', return_value=log), \
             mock.patch.object(headless, 'IS_WINDOWS', True), \
             mock.patch.dict(os.environ, {'VOLIBEAR_TEST_AUDIO_ADAPTER': '0'}), \
             mock.patch.object(headless.subprocess, 'check_output', side_effect=['commit', '']), \
             mock.patch.object(Path, 'write_text'), mock.patch('builtins.print'):
            report = headless.run_once(Path('game'), 180, 5000, scenario='domain-contract',
                stock=set(), stock_evidence=dict(successful=True, exit_code=0, timed_out=False), domain_case='d03')
        self.assertEqual(env['VOLIBEAR_TEST_DOMAIN_CASE'], 'd03')
        self.assertEqual(env['VOLIBEAR_TEST_CHARACTER'], 'volibear')
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], 'domain-contract')
        self.assertIn('--bootstrap', command)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['checks']['domain_contract_assertions'])

    def test_card_face_routes_case_but_missing_native_receipt_fails(self):
        env, command = {}, ['game']
        log = 'Steam initialization skipped\n[Volibear] LOAD_OK\n[Volibear] ISOLATION_OK steam=false\n'
        with mock.patch.object(headless, 'new_run_id', return_value='current'), \
             mock.patch.object(headless, 'prepare_run', return_value=(Path('synthetic'), env, command)), \
             mock.patch.object(headless, 'launch', return_value=(0, False)), \
             mock.patch.object(headless, 'combined_log', return_value=log), \
             mock.patch.object(headless, 'IS_WINDOWS', True), \
             mock.patch.dict(os.environ, {'VOLIBEAR_TEST_AUDIO_ADAPTER': '0'}), \
             mock.patch.object(headless.subprocess, 'check_output', side_effect=['commit', '']), \
             mock.patch.object(Path, 'write_text'), mock.patch('builtins.print'):
            report = headless.run_once(Path('game'), 180, 5000, scenario='card-face-acceptance',
                stock=set(), stock_evidence=dict(successful=True, exit_code=0, timed_out=False),
                card_face_case='B01-base-plain')
        self.assertEqual(env['VOLIBEAR_TEST_CARD_FACE_CASE'], 'B01-base-plain')
        self.assertEqual(env['VOLIBEAR_TEST_CHARACTER'], 'volibear')
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], 'card-face-acceptance')
        self.assertIn('--bootstrap', command)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['checks']['card_face_assertions'])

    def test_domain_longer_stock_control_does_not_waive_native_texture_error(self):
        with mock.patch.object(headless, 'prepare_run', return_value=(Path('synthetic'), {}, ['game'])) as prepare, \
             mock.patch.object(headless, 'launch', return_value=(0, False)), \
             mock.patch.object(headless, 'combined_log', return_value='Steam initialization skipped\nERROR: Parameter t is null'):
            categories, evidence = headless.stock_teardown(Path('game'), 180, 5000, 'window')
        self.assertEqual(prepare.call_args.args[2], 0)
        self.assertEqual(categories, set())
        self.assertFalse(evidence['successful'])
        self.assertEqual(evidence['runtime_errors'], ['ERROR: Parameter t is null'])


if __name__ == '__main__':
    unittest.main()
