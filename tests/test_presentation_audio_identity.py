"""Profile source identity negatives; not a playback or listening test."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import audio_profiles
import presentation_acceptance_evidence as gate


class ProfileSourceIdentity(unittest.TestCase):
    def setUp(self):
        self.authored = audio_profiles.read_json(audio_profiles.AUDIO / 'manifest.json')
        # Match the shipped stage_assets runtime manifest, not authoring masters.
        for row in self.authored['cues']:
            row.pop('wav', None)
        self.open = {'schema_version': 1, 'profile': 'open', 'overrides': []}
        profile = audio_profiles.profile_data('riot_en')
        self.runtime = {'schema_version': 1, 'profile': 'riot_en', 'fallback': 'open',
                        'overrides': [{'cue': r['cue'], 'file': 'profiles/riot_en/' + r['source'] + '.ogg',
                                       'duration_seconds': 1.25, 'gain_db': 0}
                                      for r in profile['overrides']]}

    def resolve(self, runtime):
        with patch.object(audio_profiles, 'verify_prepared', return_value=self.runtime) as verify:
            files = gate._effective_audio_files(self.authored, runtime)
            if runtime.get('profile') == 'riot_en':
                verify.assert_called_once_with(full_decode=False)
            else:
                verify.assert_not_called()
        return files

    def voice(self, cue, file):
        return {'cue': cue, 'file': file, 'playing': True, 'volume': 0.5}

    def test_runtime_rejects_unstaged_authoring_cues(self):
        source = audio_profiles.read_json(audio_profiles.AUDIO / 'manifest.json')
        with self.assertRaisesRegex(ValueError, 'authored audio cue inventory'):
            gate._effective_audio_files(source, self.open)

    def test_open_exact_authored_paths(self):
        files = self.resolve(self.open)
        self.assertEqual(len(files), 54)
        self.assertFalse(gate._source_audio_errors([self.voice(c['id'], c['file'])
                                                  for c in self.authored['cues']], files))

    def test_riot_overrides_and_open_fallbacks(self):
        files = self.resolve(self.runtime)
        overrides = {r['cue']: r['file'] for r in self.runtime['overrides']}
        self.assertEqual(len(overrides), 11)
        for cue in self.authored['cues']:
            expected = overrides.get(cue['id'], cue['file'])
            self.assertEqual(files[cue['id']], expected)
            self.assertFalse(gate._source_audio_errors([self.voice(cue['id'], expected)], files))

    def test_wrong_override_or_fallback_rejected(self):
        files = self.resolve(self.runtime)
        overridden = self.runtime['overrides'][0]
        original = next(c for c in self.authored['cues'] if c['id'] == overridden['cue'])
        fallback = next(c for c in self.authored['cues'] if c['id'] not in {r['cue'] for r in self.runtime['overrides']})
        for cue, file in [(original['id'], original['file']),
                          (fallback['id'], overridden['file']),
                          (original['id'], '../arbitrary.ogg'),
                          ('unknown', original['file'])]:
            with self.subTest(cue=cue, file=file):
                self.assertTrue(gate._source_audio_errors([self.voice(cue, file)], files))
        self.assertTrue(gate._source_audio_errors(
            [self.voice(overridden['cue'], overridden['file'])], self.resolve(self.open)))

    def test_profile_cannot_authorize_arbitrary_mapping(self):
        for field, value in [('file', '../arbitrary.ogg'), ('cue', 'unknown'),
                             ('duration_seconds', 999), ('gain_db', 12)]:
            runtime = deepcopy(self.runtime)
            runtime['overrides'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.resolve(runtime)
        runtime = deepcopy(self.runtime)
        runtime['overrides'].pop()
        with self.assertRaises(ValueError):
            self.resolve(runtime)
        for runtime in ({'profile': 'anything'}, dict(self.open, overrides=self.runtime['overrides'])):
            with self.assertRaises(ValueError):
                self.resolve(runtime)

    def test_authored_inventory_cannot_authorize_arbitrary_path(self):
        self.authored['cues'][0]['file'] = 'arbitrary.ogg'
        with self.assertRaises(ValueError):
            self.resolve(self.open)

    def test_playback_and_gain_still_required(self):
        files = self.resolve(self.runtime)
        cue, file = next(iter(files.items()))
        for field, value in [('playing', False), ('playing', 1), ('volume', 0),
                             ('volume', -1), ('volume', float('nan')), ('volume', True)]:
            voice = self.voice(cue, file)
            voice[field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(gate._source_audio_errors([voice], files))

    def test_capture_observes_production_emissions_and_waits_for_cleanup(self):
        # Source wiring guard only; the installed-game run supplies playback evidence.
        source = (ROOT / 'src/Volibear/PresentationAcceptanceProbe.cs').read_text()
        self.assertIn('audioProfile=Manifest("res://VolibearArt/audio/profiles/runtime.json")', source)
        self.assertIn('nameof(VolibearEffects.Emit),nameof(VolibearEffects.PlaySound)', source)
        self.assertIn('postfix:new HarmonyMethod(typeof(PresentationAcceptanceProbe),nameof(ObserveEmission))', source)
        self.assertIn('row.playing |= player.Playing;', source)
        self.assertNotIn('row.playing = true', source)
        self.assertIn('await Until(()=>Effects(owner) is null', source)
        kill = source.index('await CreatureCmd.Kill(enemy,force:true)')
        victory = source.index('Need(await CombatManager.Instance.CheckWinCondition()')
        cleanup = source.index('await Until(()=>Effects(owner) is null')
        self.assertLess(kill, victory)
        self.assertLess(victory, cleanup)
        finalizer = source[source.rindex('finally'):]
        self.assertIn('UnpatchAll("Volibear.PresentationAcceptance.AudioObserver")', finalizer)

    def test_domain_animation_observation_is_bounded_and_requires_real_change(self):
        source = (ROOT / 'src/Volibear/PresentationAcceptanceProbe.cs').read_text()
        capture = source.split('private static async Task CaptureDomainSpirit', 1)[1].split('private static Node? EffectRoot', 1)[0]
        self.assertIn('var before=arc.Points.ToArray()', capture)
        self.assertIn('observedFrames<180', capture)
        self.assertIn('Time.GetTicksMsec()-observationStart<5000', capture)
        self.assertIn('await Frame();observedFrames++', capture)
        self.assertIn('Need(!before.SequenceEqual(arc.Points)', capture)
        self.assertNotIn('DomainStormRing.Animate', capture)
        self.assertNotIn('await Pause(.25)', capture)

    def test_audio_environment_is_checked_before_long_native_batches(self):
        probe = (ROOT / 'src/Volibear/PresentationAcceptanceProbe.cs').read_text()
        suite = (ROOT / 'src/Volibear/NativeVerificationSuite.cs').read_text()
        self.assertLess(suite.index('PresentationAcceptanceProbe.ValidateAudioEnvironment();'),
                        suite.index('CardFaceAcceptanceProbe.RunBatch'))
        self.assertLess(probe.index('            ValidateAudioEnvironment();'),
                        probe.index('phase="catalog"'))
        self.assertIn('windowFocused=focused,muteInBackground,busMuted', probe)
        self.assertIn('Need(focused||!muteInBackground', probe)
        self.assertNotIn('MuteInBackground = false', probe)
        self.assertNotIn('DisplayServer.WindowMoveToForeground', probe)

    def test_local_prepared_runtime_against_pinned_authority(self):
        path = audio_profiles.WORK / 'prepared/riot_en/runtime.json'
        if not path.is_file():
            self.skipTest('private prepared profile unavailable; exact local verification not run')
        runtime = json.loads(path.read_text())
        files = gate._effective_audio_files(self.authored, runtime)
        self.assertEqual(len(files), 54)
        self.assertEqual(sum(path.startswith('profiles/riot_en/') for path in files.values()), 11)
