"""Source contracts for native lobby preconditions and character localization.
These do not replace rerunning the complete six-case native smoke after the fix.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExplorationSetupContractTests(unittest.TestCase):
    def test_each_direct_fresh_run_restores_only_native_selected_character_stats(self):
        source = (ROOT/'src/Volibear/EnemyExplorationProbe.cs').read_text(encoding='utf-8')
        start = source.index('private static async Task<object> RunCase(')
        end = source.index('private sealed class CaseFailedException', start)
        case = source[start:end]
        character = case.index('var character = ModelDb.Character<Content.VolibearCharacter>();')
        initialize = case.index('progress.GetOrCreateCharacterStats(character.Id);')
        launch = case.index('StartNewSingleplayerRun(character,')
        self.assertLess(character, initialize)
        self.assertLess(initialize, launch)
        self.assertIn('shouldSave: false', case[launch:])
        self.assertEqual(len(re.findall(r'\.GetOrCreateCharacterStats\s*\(', source)), 1)
        for forbidden in ('SaveProgressFile(', 'new CharacterStats', '.Badges.Add(', '.Badges.Clear(', '.Badges.Remove('):
            self.assertNotIn(forbidden, source)

    def test_fixture_preparation_is_declared_without_claiming_normal_lobby_defect(self):
        source = (ROOT/'src/Volibear/EnemyExplorationProbe.cs').read_text(encoding='utf-8')
        for text in ('source = "StartRunLobby.BeginRunLocally.GetOrCreateCharacterStats"',
                     'reason = "direct-run-api-bypasses-lobby-and-shouldSave-false-skips-end-run-progress"',
                     'statsExistedBefore = priorStats is not null', 'statsPresentAfter = ReferenceEquals(',
                     'badgeEntriesBefore = priorBadgeEntries', 'badgeEntriesAfter = characterStats.Badges.Count',
                     'fixtureExplicitProgressSaveRequested = false', 'outcome, error, fixturePreparation,'):
            self.assertIn(text, source)

    def test_loss_summary_and_terminal_failure_are_not_bypassed(self):
        source = (ROOT/'src/Volibear/EnemyExplorationProbe.cs').read_text(encoding='utf-8')
        start = source.index('private static async Task CloseLossUi(')
        end = source.index('private static async Task<object> RunCase(', start)
        cleanup = source[start:end]
        self.assertLess(cleanup.index('"%ContinueButton"'),cleanup.index('.ForceClick();'))
        self.assertLess(cleanup.index('.ForceClick();'),cleanup.index('"%MainMenuButton"'))
        self.assertLess(cleanup.index('"%MainMenuButton"'),cleanup.index('ReturnToMainMenuAfterRun();'))
        self.assertIn('"native loss summary settled", capture', cleanup)
        self.assertIn('else if (outcome == "LOSS") await CloseLossUi(capture);', source)
        self.assertIn('if (expectedMismatch is not null) throw new InvalidOperationException(expectedMismatch);', source)

    def test_native_character_title_object_and_all_four_pronoun_keys(self):
        source = (ROOT/'src/Volibear/Content/VolibearLoc.cs').read_text(encoding='utf-8')
        entries = dict(re.findall(r'\["VOLIBEAR_CHARACTER\.([^"\n]+)"\]\s*=\s*"([^"\n]*)"',source))
        self.assertEqual(entries['title'],'沃利贝尔')
        self.assertEqual(entries['titleObject'],'沃利贝尔')
        for key,value in dict(pronounSubject='他',pronounObject='他',pronounPossessive='他的',possessiveAdjective='他的').items():
            self.assertEqual(entries[key],value)
        for old_key in ('pronoun_subject','pronoun_object','pronoun_possessive','possessive_adjective'):
            self.assertNotIn(old_key,entries)


if __name__=='__main__': unittest.main()
