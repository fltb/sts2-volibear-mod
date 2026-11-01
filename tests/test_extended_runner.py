"""Routing tests only; synthetic outcomes never stand in for game evidence."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless


class ExtendedRunnerTests(unittest.TestCase):
    def run_case(self, scenario, case, accepted):
        env, command = {}, ['game.exe']
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(headless, 'prepare_run', return_value=(Path(temp), env, command)))
            stack.enter_context(patch.object(headless, 'new_run_id', return_value='fixture-token'))
            stack.enter_context(patch.object(headless, 'launch', return_value=(0, False)))
            stack.enter_context(patch.object(headless, 'combined_log', return_value='raw-native-evidence'))
            stack.enter_context(patch.object(headless, 'evaluate', return_value={'no_runtime_errors': True}))
            stack.enter_context(patch.object(headless.subprocess, 'check_output', return_value='fixture'))
            stack.enter_context(patch.dict(headless.os.environ, {'VOLIBEAR_TEST_AUDIO_ADAPTER': '0'}))
            if scenario == 'beast-contract':
                gate = stack.enter_context(patch.object(headless, 'beast_contract_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'beast_case': case}
                key, check = 'VOLIBEAR_TEST_BEAST_CASE', 'beast_contract_assertions'
            elif scenario == 'domain-passive-contract':
                gate_name = ('new_apply_evidence' if case.startswith('newapply-') else
                             'suck_evidence' if case.startswith('suck-') else
                             'initial_plating_evidence' if case.startswith('plating-initial-') else
                             'card_passive_evidence' if case.startswith(('curlup-', 'skittish-')) else
                             'domain_passive_evidence')
                gate = stack.enter_context(patch.object(headless, gate_name,
                                                         return_value={'passed': accepted, 'errors': []}))
                options = {'domain_passive_case': case}
                key, check = 'VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE', 'domain_passive_contract_assertions'
            elif scenario == 'enemy-exploration':
                gate = stack.enter_context(patch.object(headless, 'exploration_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                frozen = Path(temp) / 'frozen-selection.json'
                catalog = {'native': 'catalog'}
                prepare = stack.enter_context(patch.object(headless, 'prepare_exploration_inputs',
                    return_value=({'VOLIBEAR_TEST_MATRIX_SELECTION': str(frozen)}, frozen, catalog, None)))
                env['VOLIBEAR_TEST_EXPLORATION_APPROVED'] = 'stale-inherited-approval'
                options = {'matrix_selection': 'selection-input', 'matrix_catalog': 'catalog-input'}
                key, check = None, 'enemy_exploration_assertions'
            elif scenario == 'primal-contract':
                gate = stack.enter_context(patch.object(headless, 'primal_contract_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'primal_case': case}
                key, check = 'VOLIBEAR_TEST_PRIMAL_CASE', 'primal_contract_assertions'
            elif scenario == 'coupon-contract':
                gate = stack.enter_context(patch.object(headless, 'coupon_contract_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'coupon_case': case}
                key, check = 'VOLIBEAR_TEST_COUPON_CASE', 'coupon_contract_assertions'
            elif scenario == 'domain-steam':
                gate = stack.enter_context(patch.object(headless, 'domain_steam_evidence',
                                                         return_value={'errors': [] if accepted else ['fixture failure']}))
                options = {'steam_case': case}
                key, check = 'VOLIBEAR_TEST_VARIANT', 'domain_steam_assertions'
            elif scenario == 'standing-extra-turn':
                gate = stack.enter_context(patch.object(headless, 'standing_extra_turn_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'standing_case': case}
                key, check = 'VOLIBEAR_TEST_STANDING_EXTRA_TURN_CASE', 'standing_extra_turn_assertions'
            elif scenario == 'domain-dampen-transactions':
                gate = stack.enter_context(patch.object(headless, 'domain_dampen_evidence',
                                                         return_value=[] if accepted else ['fixture failure']))
                options = {'dampen_case': case}
                key, check = 'VOLIBEAR_TEST_DAMPEN_CASE', 'domain_dampen_assertions'
            elif scenario == 'domain-card-contributions':
                gate = stack.enter_context(patch.object(headless, 'domain_card_evidence',
                                                         return_value=[] if accepted else ['fixture failure']))
                options = {'domain_card_case': case}
                key, check = 'VOLIBEAR_TEST_DOMAIN_CARD_CASE', 'domain_card_contribution_assertions'
            elif scenario == 'domain-revival':
                gate = stack.enter_context(patch.object(headless, 'domain_revival_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'revival_case': case}
                key, check = 'VOLIBEAR_TEST_VARIANT', 'domain_revival_assertions'
            elif scenario == 'prepared-choice':
                gate = stack.enter_context(patch.object(headless, 'prepared_choice_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'prepared_choice_case': case}
                key, check = 'VOLIBEAR_TEST_PREPARED_CHOICE_CASE', 'prepared_choice_assertions'
            elif scenario == 'power-presentation':
                gate = stack.enter_context(patch.object(headless, 'power_presentation_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {}
                key, check = None, 'power_presentation_assertions'
            elif scenario == 'prepared-contract':
                gate = stack.enter_context(patch.object(headless, 'prepared_contract_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'prepared_case': case}
                key, check = 'VOLIBEAR_TEST_PREPARED_CASE', 'prepared_contract_assertions'
            elif scenario == 'enemy-matrix-mvp':
                gate = stack.enter_context(patch.object(headless, 'matrix_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {}
                key, check = None, 'enemy_matrix_assertions'
            elif scenario == 'relic-contract':
                gate = stack.enter_context(patch.object(headless, 'relic_contract_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'relic_case': case}
                key, check = 'VOLIBEAR_TEST_RELIC_CASE', 'relic_contract_assertions'
            elif scenario == 'domain-summon-contract':
                summon_gate = 'summon_d17_evidence' if case in headless.SUMMON_D17_CASES else 'domain_summon_evidence'
                gate = stack.enter_context(patch.object(headless, summon_gate,
                                                         return_value={'passed': accepted, 'errors': []}))
                options = {'domain_summon_case': case}
                key, check = 'VOLIBEAR_TEST_DOMAIN_SUMMON_CASE', 'domain_summon_contract_assertions'
            elif scenario == 'enemy-catalog':
                gate = stack.enter_context(patch.object(headless, 'enemy_catalog_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {}
                key, check = None, 'enemy_catalog_assertions'
            elif scenario == 'audio-receipts':
                gate = stack.enter_context(patch.object(headless, 'audio_receipt_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {}
                key, check = None, 'audio_receipt_assertions'
            elif scenario == 'persistent-contract':
                gate = stack.enter_context(patch.object(headless, 'persistent_contract_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {'persistent_case': case}
                key, check = 'VOLIBEAR_TEST_PERSISTENT_CASE', 'persistent_contract_assertions'
            elif scenario == 'catalog':
                gate = stack.enter_context(patch.object(headless, 'catalog_evidence',
                                                         return_value=({'observation': 1}, accepted)))
                options = {}
                key, check = None, 'catalog_assertions'
            else:
                gate = stack.enter_context(patch.object(headless, 'domain_enemy_evidence',
                                                         return_value={'passed': accepted, 'errors': []}))
                options = {'domain_enemy_case': case}
                key, check = 'VOLIBEAR_TEST_DOMAIN_ENEMY_CASE', 'domain_enemy_contract_assertions'
            with contextlib.redirect_stdout(io.StringIO()):
                result = headless.run_once(Path(temp), 45, 300, scenario, 'window', set(),
                    {'successful': True, 'exit_code': 0, 'timed_out': False}, **options)
            if scenario == 'power-presentation':
                self.assertEqual(env['VOLIBEAR_TEST_POWER_PRESENTATION'], '1')
            if scenario == 'audio-receipts':
                self.assertEqual(env['VOLIBEAR_TEST_AUDIO_RECEIPTS'], '1')
            if scenario == 'enemy-exploration':
                prepare.assert_called_once_with(Path(temp), 'selection-input', 'catalog-input', None)
                self.assertNotIn('VOLIBEAR_TEST_EXPLORATION_APPROVED', env)
                self.assertEqual(env['VOLIBEAR_TEST_MATRIX_SELECTION'], str(frozen))
                gate.assert_called_once_with('raw-native-evidence', 'fixture-token', Path(temp),
                                             selection_path=frozen, catalog=catalog, prerequisite=None)
            elif scenario == 'enemy-matrix-mvp':
                gate.assert_called_once_with('raw-native-evidence', 'fixture-token', Path(temp))
            elif scenario == 'enemy-catalog':
                gate.assert_called_once_with('raw-native-evidence', 'fixture-token', Path(temp), expected_seed='VOLIBEARTEST')
            elif scenario in ('catalog', 'power-presentation', 'audio-receipts'):
                gate.assert_called_once_with('raw-native-evidence', 'fixture-token')
            else:
                gate.assert_called_once_with('raw-native-evidence', 'fixture-token', case)
                self.assertEqual(env[key], case)
            self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], scenario)
            self.assertEqual(env['VOLIBEAR_TEST_CHARACTER'], 'volibear')
            self.assertIn('--bootstrap', command)
            self.assertIs(result['checks'][check], accepted)
            self.assertEqual(result['status'], 'passed' if accepted else 'failed')

    def test_beast_routes_both_variants_and_cannot_waive_gate_failure(self):
        for case in headless.BEAST_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('beast-contract', case, accepted)

    def test_enemy_routes_all_variants_and_cannot_waive_gate_failure(self):
        for case in headless.DOMAIN_ENEMY_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-enemy-contract', case, accepted)

    def test_persistent_routes_all_implemented_variants_and_preserves_failure(self):
        for case in headless.PERSISTENT_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('persistent-contract', case, accepted)

    def test_catalog_routes_exact_token_and_preserves_failure(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                self.run_case('catalog', None, accepted)

    def test_passive_routes_both_native_probe_families(self):
        for case in headless.DOMAIN_PASSIVE_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-passive-contract', case, accepted)

    def test_exploration_binds_frozen_inputs_and_clears_inherited_approval(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                self.run_case('enemy-exploration', None, accepted)

    def test_audio_receipts_enable_probe_and_require_strict_gate(self):
        for accepted in (False, True):
            self.run_case('audio-receipts', None, accepted)

    def test_primal_routes_both_exact_turn_variants(self):
        for case in headless.PRIMAL_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('primal-contract', case, accepted)

    def test_coupon_routes_all_native_payment_variants(self):
        for case in headless.COUPON_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('coupon-contract', case, accepted)

    def test_steam_routes_all_thirty_eight_variants_and_preserves_failure(self):
        self.assertEqual(len(headless.STEAM_CASES), 38)
        self.assertEqual(set(headless.STEAM_CASES), headless.STEAM_VARIANTS)
        for case in headless.STEAM_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-steam', case, accepted)

    def test_standing_routes_both_variants_and_preserves_failure(self):
        for case in headless.STANDING_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('standing-extra-turn', case, accepted)

    def test_dampen_routes_all_seven_variants_and_preserves_failure(self):
        for case in headless.DAMPEN_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-dampen-transactions', case, accepted)

    def test_domain_card_routes_exact_contribution_families(self):
        for case in headless.DOMAIN_CARD_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-card-contributions', case, accepted)

    def test_revival_routes_exact_requested_variant(self):
        for case in headless.REVIVAL_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-revival', case, accepted)

    def test_prepared_choice_routes_all_variants(self):
        for case in headless.PREPARED_CHOICE_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('prepared-choice', case, accepted)

    def test_power_presentation_routes_flag_and_gate(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                self.run_case('power-presentation', None, accepted)

    def test_prepared_routes_all_native_payment_variants(self):
        for case in headless.PREPARED_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('prepared-contract', case, accepted)

    def test_enemy_matrix_binds_native_artifact_directory(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                self.run_case('enemy-matrix-mvp', None, accepted)

    def test_relic_routes_all_variants_and_preserves_failure(self):
        for case in headless.RELIC_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('relic-contract', case, accepted)

    def test_summon_routes_all_variants_and_preserves_failure(self):
        for case in headless.DOMAIN_SUMMON_CASES:
            for accepted in (False, True):
                with self.subTest(case=case, accepted=accepted):
                    self.run_case('domain-summon-contract', case, accepted)

    def test_enemy_catalog_binds_artifact_directory_and_seed(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                self.run_case('enemy-catalog', None, accepted)

    def test_exploration_missing_or_invalid_inputs_never_launch(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(headless, 'prepare_run', return_value=(Path(temp), {}, ['game.exe'])), \
             patch.object(headless, 'launch') as launch, \
             patch.object(headless, 'prepare_exploration_inputs', side_effect=ValueError('invalid prerequisite')):
            with self.assertRaises(RuntimeError):
                headless.run_once(Path(temp), 45, 300, 'enemy-exploration', 'window')
            with self.assertRaises(ValueError):
                headless.run_once(Path(temp), 45, 300, 'enemy-exploration', 'window',
                                  matrix_selection='selection', matrix_catalog='catalog')
            launch.assert_not_called()

    def test_unknown_variant_never_launches(self):
        for scenario, option in [('beast-contract', 'beast_case'),
                                 ('domain-enemy-contract', 'domain_enemy_case'),
                                 ('persistent-contract', 'persistent_case'),
                                 ('domain-summon-contract', 'domain_summon_case'),
                                 ('relic-contract', 'relic_case'),
                                 ('domain-passive-contract', 'domain_passive_case'),
                                 ('prepared-contract', 'prepared_case'),
                                 ('domain-revival', 'revival_case'),
                                 ('prepared-choice', 'prepared_choice_case'),
                                 ('coupon-contract', 'coupon_case'),
                                 ('domain-card-contributions', 'domain_card_case'),
                                 ('primal-contract', 'primal_case'),
                                 ('domain-dampen-transactions', 'dampen_case'),
                                 ('standing-extra-turn', 'standing_case'),
                                 ('domain-steam', 'steam_case')]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                with patch.object(headless, 'prepare_run', return_value=(Path(temp), {}, ['game.exe'])), \
                     patch.object(headless, 'launch') as launch, \
                     patch.dict(headless.os.environ, {'VOLIBEAR_TEST_AUDIO_ADAPTER': '0'}):
                    with self.assertRaises(RuntimeError):
                        headless.run_once(Path(temp), 45, 300, scenario, 'window', **{option: 'unknown'})
                    launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
