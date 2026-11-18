"""Startup evidence parsing, not a game or multi-mod execution fixture."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.compat_report import report

ROOT = Path(__file__).resolve().parents[1]
CLEAN = '''[Volibear] BUILD_GATE build=verified channel=pbe target=0.113.0/16ac0fe3
[Volibear] CONTENT_OK cards=89 character=VolibearCharacter
[Volibear] COMPAT_SUMMARY failures=0
[Volibear] LOAD_OK version=0.1.1
[Volibear] COMPAT_SCAN {"scanned_targets":10,"own_targets":5,"shared_targets":0,"status":"metadata_only"}
'''


class CompatibilityReportTests(unittest.TestCase):
    def test_success_is_only_initialization_evidence(self):
        result = report(CLEAN)
        self.assertTrue(result['passed'])
        self.assertEqual('initialization_passed', result['support_status'])
        self.assertIn('not evaluated', result['scope'])
        self.assertEqual([], result['failure_details'])

    def test_shared_target_or_mod_presence_is_not_a_failure(self):
        text = CLEAN + ('[OtherFramework] Patch application complete: 6 applied, 2 ignored, 0 failed, 8 total\n'
                        '[OtherFramework] [Optional] attack_listener - Success ✓\n'
                        '[OtherFramework] 0 patches failed\n'
                        '[OtherFramework] no critical patches failed\n'
                        '[OtherFramework] 0 of 42 patches failed\n'
                        'Field of view changed to 75\n'
                        'Card state changed: true; shared target AttackCommand.Execute\n'
                        'Enabled mods: BaseLib, RitsuLib, Volibear\n')
        self.assertTrue(report(text)['passed'])

    def test_own_failure_preserves_target_owners_and_cause(self):
        detail = ('[Volibear] COMPAT_FAIL Core.CardResolutionHooks :: InvalidOperationException: '
                  'Volibear transpiler installation failed: target=void Attack.MoveNext(); '
                  'owner=Volibear.CardResolution; existing_transpilers=[Other.Attack(priority=400)]. '
                  '<- InvalidOperationException: Expected one native Damage callsite; found 0.')
        result = report(CLEAN + 'ERROR: ' + detail + '\n' + detail)
        self.assertFalse(result['passed'])
        self.assertEqual('unsupported', result['support_status'])
        self.assertEqual(1, result['failure_count'])
        failure = result['failure_details'][0]
        self.assertEqual('void Attack.MoveNext()', failure['target_method'])
        self.assertEqual('Volibear.CardResolution', failure['patch_owner'])
        self.assertEqual('Other.Attack(priority=400)', failure['existing_transpilers'])
        self.assertIn('found 0', failure['details'])

    def test_late_optional_foreign_failure_is_not_hidden_by_load_ok(self):
        # Generic framework log shape: the parser must not know the owner's name.
        late = '''[UnrelatedLibrary] [Optional] per_hit_dispatch - Failed ✗
[UnrelatedLibrary]   Description: Redirect the native per-hit damage call
[UnrelatedLibrary]   Error: Expected one awaited Damage producer; found 0
[UnrelatedLibrary]   Exception: System.InvalidOperationException: native anchor missing
   at Example.Rewrite()
[UnrelatedLibrary] Patch application complete: 9 applied, 0 ignored, 1 failed, 10 total
'''
        result = report(CLEAN + late)
        self.assertTrue(result['initialized'])
        self.assertFalse(result['passed'])
        self.assertEqual('unsupported', result['support_status'])
        self.assertIn('found 0', result['failure_details'][0]['details'])
        self.assertIn('Example.Rewrite()', result['failure_details'][0]['details'])

    def test_foreign_patch_failure_before_our_init_is_also_retained(self):
        result = report('ERROR: Failed to apply patch External.Attack: missing callsite\n' + CLEAN)
        self.assertFalse(result['passed'])
        self.assertIn('External.Attack', result['reasons'][0])

    def test_generic_multiline_failure_keeps_owner_target_and_reason(self):
        result = report(CLEAN + 'Failed to apply patch\n Owner: Example.Feature\n'
                        ' Target: Game.Card.Play\n Reason: anchor is missing\n')
        self.assertEqual('unsupported', result['support_status'])
        self.assertEqual(1, result['failure_count'])
        detail = result['failure_details'][0]
        self.assertEqual('Example.Feature', detail['patch_owner'])
        self.assertEqual('Game.Card.Play', detail['target_method'])
        self.assertIn('anchor is missing', detail['details'])

    def test_dependency_or_api_failure_does_not_need_our_markers(self):
        for message in ('Example depends on mods which have not been loaded',
                        'Exception thrown while loading mod Example: FileLoadException',
                        'System.TypeLoadException: missing required game interface'):
            with self.subTest(message=message):
                result = report(message)
                self.assertEqual('unsupported', result['support_status'])
                self.assertFalse(result['passed'])

    def test_missing_and_truncated_evidence_is_inconclusive(self):
        for text in ('', '[Volibear] LOAD_OK version=0.1.1',
                     CLEAN.split('[Volibear] COMPAT_SCAN', 1)[0],
                     CLEAN.replace('[Volibear] COMPAT_SUMMARY failures=0\n', '')):
            with self.subTest(text=text):
                result = report(text)
                self.assertFalse(result['passed'])
                self.assertEqual('inconclusive', result['support_status'])
                self.assertTrue(result['missing_evidence'])

    def test_nonzero_summary_without_details_still_explains_failure(self):
        result = report(CLEAN.replace('failures=0', 'failures=3'))
        self.assertFalse(result['passed'])
        self.assertEqual(3, result['failure_count'])
        self.assertIn('detailed cause is missing', result['reasons'][0])

    def test_ansi_colored_failure_and_later_details(self):
        result = report(CLEAN + '\x1b[31m[Library] [Critical] apply_damage - Failed ✗\x1b[0m\n'
                        '[Library] Error: no awaited producer\n')
        self.assertFalse(result['passed'])
        self.assertIn('no awaited producer', result['failure_details'][0]['details'])
        self.assertNotIn('\x1b', result['failure_details'][0]['details'])

    def test_full_failure_count_survives_display_limit(self):
        result = report(CLEAN + '\n'.join('Failed to apply patch P' + str(i) for i in range(30)))
        self.assertEqual(30, result['failure_count'])
        self.assertEqual(24, len(result['failure_details']))
        self.assertTrue(result['failures_truncated'])

    def test_shared_metadata_is_evidence_not_a_conflict_verdict(self):
        shared = {'target': 'Attack.MoveNext()', 'status': 'shared_unverified',
                  'patches': [{'owner': 'Volibear.CardResolution'}, {'owner': 'External.Observer'}]}
        scan = {'status': 'metadata_only', 'scanned_targets': 10, 'own_targets': 5, 'shared_targets': 1}
        result = report(CLEAN + '[Volibear] COMPAT_SHARED ' + json.dumps(shared) + '\n'
                        '[Volibear] COMPAT_SCAN ' + json.dumps(scan))
        self.assertTrue(result['passed'])
        self.assertEqual('initialization_passed', result['support_status'])
        self.assertEqual([shared], result['shared_targets'])
        self.assertEqual(scan, result['patch_snapshot'])

    def test_failed_or_truncated_metadata_is_inconclusive(self):
        for extra in ('[Volibear] COMPAT_SCAN_ERROR cannot read patch metadata',
                      '[Volibear] COMPAT_SCAN_ERROR System.MissingMethodException: snapshot API changed\n'
                      ' ---> System.TypeLoadException: metadata cannot be resolved\n   at Snapshot.Capture()\n',
                      '[Volibear] COMPAT_SHARED {"target":', '[Volibear] COMPAT_SCAN null',
                      '[Volibear] COMPAT_SCAN {"anything":1}',
                      '[Volibear] COMPAT_SCAN {"status":"metadata_only","scanned_targets":10,"own_targets":5,"shared_targets":1}',
                      '[Volibear] COMPAT_SHARED {"target":"Card.Play","status":"shared_unverified"}'):
            with self.subTest(extra=extra):
                result = report(CLEAN + extra)
                self.assertFalse(result['passed'])
                self.assertEqual('inconclusive', result['support_status'])
                self.assertTrue(result['metadata_errors'])
                self.assertEqual(0, result['failure_count'])

    def test_reporting_error_does_not_hide_a_later_real_failure(self):
        result = report(CLEAN + '[Volibear] COMPAT_SCAN_ERROR System.MissingMethodException: reporting only\n'
                        '   at Snapshot.Capture()\nFailed to apply patch External.Attack: missing callsite\n')
        self.assertEqual('unsupported', result['support_status'])
        self.assertEqual(1, result['failure_count'])
        self.assertIn('External.Attack', result['reasons'][0])

    def test_earlier_success_cannot_complete_a_new_boot(self):
        partial = '[Volibear] BUILD_GATE build=verified channel=pbe target=0.113.0\n'
        without_boundary = report(CLEAN + partial)
        self.assertEqual('inconclusive', without_boundary['support_status'])
        self.assertIn('Multiple Volibear startups', without_boundary['reasons'][0])
        with_boundary = report('Godot Engine v4.5.1\n' + CLEAN + 'Godot Engine v4.5.1\n' + partial)
        self.assertEqual('inconclusive', with_boundary['support_status'])
        self.assertFalse(with_boundary['initialized'])
        self.assertEqual(1, with_boundary['discarded_previous_boots'])

    def test_previous_boot_failure_is_not_assigned_to_current_boot(self):
        result = report('Godot Engine v4.5.1\nFailed to apply patch Old.Install\n'
                        'Godot Engine v4.5.1\n' + CLEAN)
        self.assertTrue(result['passed'])
        self.assertEqual(0, result['failure_count'])
        self.assertEqual(1, result['discarded_previous_boots'])

    def test_read_only_log_cli_needs_no_game_or_local_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'game.log'
            output = Path(directory) / 'compat.json'
            for text, exit_code in ((CLEAN, 0), (CLEAN + 'Failed to apply patch SomeOwner', 1), ('', 1)):
                with self.subTest(text=text):
                    source.write_text(text, encoding='utf-8')
                    result = subprocess.run([sys.executable, str(ROOT / 'tools/compat_report.py'),
                                             '--log', str(source), '--json', str(output)],
                                            cwd=directory, capture_output=True, text=True, timeout=10)
                    self.assertEqual(exit_code, result.returncode, result.stderr)
                    parsed = json.loads(result.stdout)
                    self.assertEqual(parsed, json.loads(output.read_text()))
                    self.assertIsNone(parsed['game_dir'])
                    self.assertEqual(str(source.resolve()), parsed['log_file'])


if __name__ == '__main__':
    unittest.main()
