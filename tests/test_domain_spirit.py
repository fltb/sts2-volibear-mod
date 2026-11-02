"""Focused contracts for runtime domain spirit rendering and lifecycle wiring."""
import json
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPIRIT = ROOT / 'src/Volibear/Presentation/VolibearPresentationBridge.DomainSpirit.cs'
BRIDGE = ROOT / 'src/Volibear/Presentation/VolibearPresentationBridge.cs'


class DomainSpiritTests(unittest.TestCase):
    def test_approved_frames_are_treated_at_foot_origin(self):
        source = SPIRIT.read_text()
        self.assertIn('GetNodeOrNull<Node2D>("Visuals")', source)
        self.assertIn('visuals.Scale = _spiritScale * 1.22f', source)
        self.assertIn('sprite!.Material', source)
        self.assertNotIn('SpriteFrames =', source)
        self.assertIn('tex.a * 0.72', source)
        self.assertIn('vertex_tint = COLOR', source)
        self.assertIn('DomainStormRing.Populate(_stormRing)', source)

    def test_ring_is_wide_volumetric_and_below_native_status_ui(self):
        source = SPIRIT.read_text()
        ending = (ROOT / 'src/Volibear/Presentation/VolibearArchitectDomainVisual.cs').read_text()
        ring = (ROOT / 'src/Volibear/Presentation/DomainStormRing.cs').read_text()
        for text in (source, ending):
            self.assertNotIn('ZIndex = -1', text)
            self.assertNotIn('ZIndex = 2', text)
            self.assertIn('DomainStormRing.Populate(', text)
            self.assertIn('DomainStormRing.Animate(', text)
        self.assertIn('MoveChild(_stormRing, 0)', source)
        self.assertIn('MoveChild(view, 0)', ending)
        self.assertIn('root.ZIndex = 0', ring)
        self.assertIn('Radius = 300f', ring)
        self.assertIn('Name = "StormWall"', ring)
        self.assertIn('Name = "StormBolts"', ring)
        self.assertIn('VertexColors =', ring)
        self.assertIn('Animate(root, Time.GetTicksMsec()', ring)
        self.assertIn('CanvasItemMaterial.BlendModeEnum.Add', ring)
        self.assertIn('CanvasItemMaterial.LightModeEnum.Unshaded', ring)

    def test_ending_initializes_and_ticks_without_mod_node_virtual_callbacks(self):
        ending = (ROOT / 'src/Volibear/Presentation/VolibearArchitectDomainVisual.cs').read_text()
        self.assertNotIn('override void _Ready', ending)
        self.assertLess(ending.index('DomainStormRing.Populate(view)'), ending.index('AddChild(view)'))
        self.assertIn('ProcessFrame += Tick', ending)
        self.assertIn('ProcessFrame -= Tick', ending)
        self.assertIn('TreeEntered += view.Attach', ending)
        self.assertIn('TreeExiting += view.Detach', ending)
        self.assertNotIn('Entered = false', ending)
        self.assertNotIn('body.Scale = originalScale', ending)

    def test_every_terminal_lifecycle_releases_spirit(self):
        source = BRIDGE.read_text()
        for name in ('private void Died(', 'internal void SuspendEnding()', 'internal void StopCombat()'):
            section = source.split(name, 1)[1].split('\n        }', 1)[0]
            self.assertIn('ReleaseSpiritForm();', section, name)
        self.assertIn('UpdateSpiritForm(active);', source)
        self.assertIn('TickSpiritForm();', source)
        release = SPIRIT.read_text().split('private void ReleaseSpiritForm()', 1)[1]
        self.assertIn('_spiritVisuals!.Scale = _spiritScale', release)
        self.assertIn('_spiritSprite!.Material = _spiritMaterial', release)
        self.assertIn('_stormRing!.QueueFree()', release)

    def test_native_acceptance_observes_enlargement_animation_and_cleanup(self):
        source = (ROOT / 'src/Volibear/PresentationAcceptanceProbe.cs').read_text()
        self.assertIn('await CaptureDomainSpirit(owner);', source)
        self.assertIn('!before.SequenceEqual(arc.Points)', source)
        self.assertIn('spiritSprite.Material==spiritOriginalMaterial', source)
        self.assertIn('spiritVisuals.Scale.IsEqualApprox(spiritOriginalScale)', source)

    def test_godot_parses_exact_production_shader(self):
        config = ROOT / '.local/config.json'
        if not config.exists():
            self.skipTest('local Godot path not configured')
        godot = json.loads(config.read_text()).get('godot')
        if not godot or not pathlib.Path(godot).is_file():
            self.skipTest('configured Godot is not installed')
        shader = re.search(r'SpiritShader = """\n(.*?)\n\s*""";', SPIRIT.read_text(), re.S).group(1)
        shader = '\n'.join(line.strip() for line in shader.splitlines())
        with tempfile.TemporaryDirectory(prefix='domain-spirit-') as folder:
            path = pathlib.Path(folder)
            (path / 'project.godot').write_text('[application]\nconfig/name="Domain shader validation"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
            (path / 'spirit.gdshader').write_text(shader)
            (path / 'check.gd').write_text('extends SceneTree\nfunc _initialize():\n\tvar shader = Shader.new()\n\tshader.code = FileAccess.get_file_as_string("res://spirit.gdshader")\n\tshader.get_shader_uniform_list()\n\tprint("DOMAIN_SHADER_PARSED")\n\tquit(0)\n')
            result = subprocess.run([godot, '--headless', '--path', folder, '--script', 'check.gd'], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('DOMAIN_SHADER_PARSED', result.stdout)
            self.assertNotIn('SHADER ERROR', result.stdout + result.stderr)
            self.assertNotIn('SCRIPT ERROR', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
