"""Production asset inputs and native resource contracts; no game-acceptance claims."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_assets', ROOT / 'tools/build_assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.clips, cls.portraits = assets.read_inputs()

    def test_approved_inputs_and_exact_portrait_coverage(self):
        self.assertEqual(26, len(self.clips))
        self.assertEqual(940, sum(c['frame_count'] for c in self.clips))
        self.assertEqual(178, len(self.portraits))
        self.assertEqual(89, sum(e['profile'] == 'sts2_small' for e in self.portraits))
        self.assertEqual(89, sum(e['profile'] == 'sts2_big' for e in self.portraits))

    def test_frames_use_authored_rects_and_non_looping_death(self):
        text = assets.sprite_frames(self.clips)
        self.assertEqual(940, text.count('[sub_resource type="AtlasTexture"'))
        self.assertIn('region = Rect2(3584, 0, 512, 512)', text)
        self.assertIn('"loop": false, "name": &"Die"', text)
        self.assertIn('"loop": true, "name": &"idle"', text)
        self.assertIn('"name": &"domain_storm_leap"', text)
        for alias in ('Attack', 'Cast', 'Hit', 'Hurt', 'Dead', 'Die', 'Idle'):
            self.assertIn(f'"name": &"{alias}"', text)

    def test_combat_scene_has_native_contract_and_ground_pivot(self):
        scene = assets.combat_scene(self.manifest['pivot_px'])
        self.assertIn('position = Vector2(-250, -442)', scene)
        self.assertIn('centered = false', scene)
        for node in ('Visuals', 'PhobiaModeVisuals', 'Bounds', 'CenterPos', 'IntentPos', 'OrbPos', 'TalkPos', 'FormVfx'):
            self.assertIn(f'[node name="{node}"', scene)
        self.assertEqual(8, scene.count('unique_name_in_owner = true'))
        self.assertNotIn('ironclad', scene.lower())

    def test_rejects_modified_approved_atlas(self):
        with patch.object(assets, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'Approved atlas hash mismatch'):
                assets.read_inputs()

    def test_source_paths_cannot_escape_approved_root(self):
        with self.assertRaises(ValueError):
            assets.safe_source(ROOT / 'assets', '../README.md')

    def test_all_output_paths_are_ignored_local_staging(self):
        self.assertTrue(assets.PACK.is_relative_to(ROOT / '.local'))
        self.assertEqual('Volibear.pck', assets.PACK.name)
        self.assertEqual(assets.PACK, assets.output_path(assets.PACK))
        with self.assertRaises(ValueError):
            assets.output_path(ROOT / 'assets/unsafe.pck')
        with self.assertRaises(ValueError):
            assets.output_path(ROOT / '.local/packs/unsafe.zip')

    def test_approved_ui_inputs_are_unchanged(self):
        rows = assets.read_ui_inputs()
        names = {r['id'] for r in rows}
        self.assertTrue({'character_icon_volibear', 'energy_master', 'character_select_transition'} <= names)
        with patch.object(assets, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'Approved UI hash mismatch'):
                assets.read_ui_inputs()

    def test_ui_scenes_use_native_types_and_no_borrowed_character(self):
        expected = {'volibear_icon.tscn', 'volibear_energy.tscn', 'volibear_rest.tscn',
                    'volibear_merchant.tscn', 'volibear_trail.tscn', 'volibear_transition.tres',
                    'volibear_transition.gdshader', 'volibear_effects.tscn', 'effects.gd'}
        self.assertEqual(expected, set(assets.NATIVE_RESOURCES))
        for name in expected:
            text = (assets.PRESENTATION / name).read_text(encoding='utf-8')
            self.assertNotIn('ironclad', text.lower())
            self.assertNotIn('res://src/', text)
        energy = (assets.PRESENTATION / 'volibear_energy.tscn').read_text(encoding='utf-8')
        for name in ('Label', 'Layers', 'RotationLayers', 'EnergyVfxBack', 'EnergyVfxFront', 'StarAnchor'):
            self.assertIn(f'[node name="{name}"', energy)
        rest = (assets.PRESENTATION / 'volibear_rest.tscn').read_text(encoding='utf-8')
        for name in ('ControlRoot', 'Hitbox', 'ThoughtBubbleLeft', 'ThoughtBubbleRight'):
            self.assertIn(f'[node name="{name}"', rest)
        self.assertNotIn('[node name="SelectionReticle"', rest)

    def test_social_aliases_preserve_relaxed_loop_reuse(self):
        text = assets.sprite_frames(self.clips, {**assets.ALIASES, 'idle': 'relaxed_loop'})
        alias_row = next(line for line in text.splitlines() if '"name": &"idle"' in line)
        self.assertIn('SubResource("frame_1_0")', alias_row)
        self.assertNotIn('SubResource("frame_0_0")', alias_row)

    def test_transition_and_trail_native_contracts(self):
        shader = (assets.PRESENTATION / 'volibear_transition.gdshader').read_text(encoding='utf-8')
        self.assertIn('uniform float threshold', shader)
        material = (assets.PRESENTATION / 'volibear_transition.tres').read_text(encoding='utf-8')
        self.assertIn('shader_parameter/threshold = 0.0', material)
        self.assertIn('character_select_transition.png', material)
        trail = (assets.PRESENTATION / 'volibear_trail.tscn').read_text(encoding='utf-8')
        self.assertIn('[node name="Sprites" type="Node2D" parent="."]', trail)
        self.assertIn('type="CPUParticles2D" parent="Sprites"', trail)

    def test_complete_approved_effect_and_audio_inputs(self):
        effects, audio = assets.read_effect_inputs()
        self.assertEqual(40, len(effects))
        self.assertEqual(54, len(audio['cues']))
        self.assertEqual(47, len(audio['assets']))
        text = assets.sprite_frames(assets.effect_clips(effects), {}, 'res://VolibearArt/vfx')
        self.assertEqual(sum(e['frame_count'] for e in effects), text.count('[sub_resource type="AtlasTexture"'))
        self.assertIn('res://VolibearArt/vfx/atlases/lightning_chain.png', text)
        self.assertIn('"loop": true, "name": &"domain_loop"', text)
        self.assertNotIn('"name": &"Attack"', text)

    def test_effect_integrity_rejects_changed_atlas_and_audio(self):
        with patch.object(assets, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'Approved VFX hash mismatch'):
                assets.read_effect_inputs()
        original_sha = assets.sha
        with patch.object(assets, 'sha', side_effect=lambda p: '0' * 64 if p.suffix == '.ogg' else original_sha(p)):
            with self.assertRaisesRegex(ValueError, 'Approved audio hash mismatch'):
                assets.read_effect_inputs()

    def test_original_rune_icons_have_no_embedded_external_art(self):
        self.assertEqual(10, len(assets.ICON_EXPORTS))
        for destination, (source, size) in assets.ICON_EXPORTS.items():
            self.assertIn(size, (64, 256))
            svg = ET.fromstring((assets.PRESENTATION / 'icons' / source).read_text(encoding='utf-8'))
            self.assertEqual('256', svg.attrib['width'])
            self.assertEqual('256', svg.attrib['height'])
            self.assertEqual('0 0 256 256', svg.attrib['viewBox'])
            self.assertTrue(all(element.tag.rsplit('}', 1)[-1] in {'svg', 'path', 'circle'} for element in svg.iter()))
            self.assertFalse(destination.startswith('/'))


if __name__ == '__main__':
    unittest.main()
