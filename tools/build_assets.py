#!/usr/bin/env python3
"""Build the production Volibear PCK with Godot 4.5.1, without building C# or deploying.

python tools/build_assets.py --godot /path/to/Godot_4.5.1_mono
All generated inputs, imports, logs and output remain beneath ignored .local/.
Approved exports are copied byte-for-byte; no art exporter is invoked.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / 'src/Volibear/Presentation'
ANIMATIONS = ROOT / 'assets/animation/animations/clean'
CARDS = ROOT / 'assets/cards'
UI = ROOT / 'assets/animation/ui'
VFX = ROOT / 'assets/animation/vfx'
AUDIO = ROOT / 'assets/animation/audio'
ICON_EXPORTS = {
    'relics/lightning_heart.svg': ('lightning_heart.svg', 64),
    'relics/big/lightning_heart.svg': ('lightning_heart.svg', 256),
    'relics/outline/lightning_heart.svg': ('lightning_heart_outline.svg', 64),
    'relics/storm_crown.svg': ('storm_crown.svg', 64),
    'relics/big/storm_crown.svg': ('storm_crown.svg', 256),
    'relics/outline/storm_crown.svg': ('storm_crown_outline.svg', 64),
    'powers/thunder_force.svg': ('thunder_force.svg', 64),
    'powers/big/thunder_force.svg': ('thunder_force.svg', 256),
    'powers/domain.svg': ('domain.svg', 64),
    'powers/big/domain.svg': ('domain.svg', 256),
}
NATIVE_RESOURCES = (
    'volibear_icon.tscn', 'volibear_energy.tscn', 'volibear_rest.tscn',
    'volibear_merchant.tscn', 'volibear_trail.tscn',
    'volibear_transition.tres', 'volibear_transition.gdshader',
    'volibear_effects.tscn', 'effects.gd',
)
PACK = ROOT / '.local/packs/Volibear.pck'
ALIASES = {
    'idle': 'idle_loop', 'Idle': 'idle_loop', 'IdleLoop': 'idle_loop',
    'Attack': 'attack', 'Cast': 'cast', 'Hit': 'hurt', 'hit': 'hurt', 'Hurt': 'hurt',
    'Die': 'die', 'Dead': 'die', 'dead': 'die', 'Death': 'die', 'death': 'die',
    'Relaxed': 'relaxed_loop', 'relaxed': 'relaxed_loop', 'revive': 'idle_loop',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_source(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Invalid asset path: {relative}')
    return path


def read_inputs():
    manifest = json.loads((ANIMATIONS / 'manifest.json').read_text(encoding='utf-8'))
    clips = manifest['clips'] + manifest.get('variants', [])
    if (not manifest['render_complete'] or len(clips) != 26
            or sum(c['frame_count'] for c in clips) != 940):
        raise ValueError('Expected the approved complete 26-sequence / 940-frame clean atlas set')
    for clip in clips:
        if len(clip['frames']) != clip['frame_count'] or clip['fps'] <= 0:
            raise ValueError(f'Invalid animation frames: {clip["name"]}')
        for key, digest in [('image', 'atlas_sha256'), ('json', 'atlas_json_sha256')]:
            if sha(safe_source(ANIMATIONS, clip['atlas'][key])) != clip[digest]:
                raise ValueError(f'Approved atlas hash mismatch: {clip["name"]} {key}')
    cards = json.loads((CARDS / 'data/asset_manifest.json').read_text(encoding='utf-8'))['cards']
    if len(cards) != 89:
        raise ValueError('Expected 89 approved card portraits')
    portraits = []
    for card in cards.values():
        exports = [e for e in card['exports'] if e['profile'] in ('sts2_small', 'sts2_big')]
        if {e['profile'] for e in exports} != {'sts2_small', 'sts2_big'} or len(exports) != 2:
            raise ValueError(f'Missing small/big portrait: {card["id"]}')
        for export in exports:
            source = safe_source(CARDS, export['path'])
            if sha(source) != export['sha256']:
                raise ValueError(f'Approved portrait hash mismatch: {source}')
            portraits.append(export)
    return manifest, clips, portraits


def read_ui_inputs():
    rows = json.loads((UI / 'manifest.json').read_text(encoding='utf-8'))['assets']
    for row in rows:
        if sha(safe_source(UI, row['file'])) != row['sha256']:
            raise ValueError(f'Approved UI hash mismatch: {row["id"]}')
    return rows


def read_effect_inputs():
    visual = json.loads((VFX / 'manifest.json').read_text(encoding='utf-8'))
    audio = json.loads((AUDIO / 'manifest.json').read_text(encoding='utf-8'))
    effects = visual['effects']
    if len(effects) != 40 or len(audio['cues']) != 54 or len(audio['assets']) != 47:
        raise ValueError('Expected approved 40 VFX / 54 cues / 47 sound assets')
    for effect in effects:
        if sha(safe_source(VFX, effect['atlas']['image'])) != effect['atlas']['sha256']:
            raise ValueError(f'Approved VFX hash mismatch: {effect["id"]}')
        if len(effect['frames']) != effect['frame_count'] or effect['fps'] <= 0:
            raise ValueError('Invalid VFX frame metadata')
    sounds = {row['file']: row for row in audio['assets']}
    for row in sounds.values():
        if sha(safe_source(AUDIO, row['file'])) != row['ogg_sha256']:
            raise ValueError(f'Approved audio hash mismatch: {row["id"]}')
    cue_ids = {cue['id'] for cue in audio['cues']}
    if len(cue_ids) != 54 or len(sounds) != 47:
        raise ValueError('Duplicate sound or cue identity')
    for cue in audio['cues']:
        if cue['file'] not in sounds or cue['max_voices'] < 1:
            raise ValueError('Invalid audio cue target/polyphony')
    for effect in effects:
        if effect['audio_cue'] not in cue_ids:
            raise ValueError('VFX references unknown audio cue')
    return effects, audio


def effect_clips(effects):
    return [{**e, 'name': e['id'],
             'frames': [{**f, 'duration_ms': 1000 / e['fps']} for f in e['frames']]}
            for e in effects]


def stage_icons(art):
    for path, (source, size) in ICON_EXPORTS.items():
        svg = (PRESENTATION / 'icons' / source).read_text(encoding='utf-8')
        if 'width="256" height="256"' not in svg:
            raise ValueError('Original rune master must be 256px square')
        svg = svg.replace('width="256" height="256"', f'width="{size}" height="{size}"', 1)
        destination = art / 'icons' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(svg, encoding='utf-8')


def output_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / '.local').resolve()) or path.suffix != '.pck':
        raise ValueError('Resource output must be a .pck beneath ignored .local/')
    return path


def sprite_frames(clips, aliases=None, texture_root='res://VolibearArt/animations'):
    """Use manifest rectangles, not guessed atlas grid positions or cropped/re-encoded art."""
    lines = ['[gd_resource type="SpriteFrames" format=3]', '']
    for i, clip in enumerate(clips):
        lines.append(f'[ext_resource type="Texture2D" path="{texture_root}/{clip["atlas"]["image"]}" id="atlas_{i}"]')
    entries = {}
    for i, clip in enumerate(clips):
        frames = []
        for j, frame in enumerate(clip['frames']):
            ident = f'frame_{i}_{j}'
            rect = ', '.join(str(n) for n in frame['rect'])
            lines += ['', f'[sub_resource type="AtlasTexture" id="{ident}"]',
                      f'atlas = ExtResource("atlas_{i}")', f'region = Rect2({rect})',
                      'filter_clip = true']
            duration = frame['duration_ms'] * clip['fps'] / 1000
            frames.append(f'{{"duration": {duration:.9f}, "texture": SubResource("{ident}")}}')
        entries[clip['name']] = (clip, frames)
    for alias, source in (ALIASES if aliases is None else aliases).items():
        entries[alias] = entries[source]
    animations = []
    for name, (clip, frames) in entries.items():
        animations.append('{"frames": [' + ', '.join(frames) + '], "loop": '
                          + str(clip['loop']).lower() + ', "name": &"' + name
                          + '", "speed": ' + str(clip['fps']) + '}')
    lines += ['', '[resource]', 'animations = [' + ',\n'.join(animations) + ']', '']
    return '\n'.join(lines)


def combat_scene(pivot):
    return f'''[gd_scene load_steps=3 format=3]
[ext_resource type="SpriteFrames" path="res://VolibearArt/scenes/volibear_frames.tres" id="frames"]
[ext_resource type="Script" path="res://VolibearArt/scenes/actor.gd" id="actor"]
[node name="Volibear" type="Node2D"]
[node name="Visuals" type="Node2D" parent="."]
unique_name_in_owner = true
[node name="AnimatedSprite2D" type="AnimatedSprite2D" parent="Visuals"]
position = Vector2({-pivot[0]}, {-pivot[1]})
centered = false
sprite_frames = ExtResource("frames")
animation = &"idle_loop"
autoplay = "idle_loop"
script = ExtResource("actor")
[node name="PhobiaModeVisuals" type="Node2D" parent="."]
unique_name_in_owner = true
visible = false
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -150.0
offset_top = -370.0
offset_right = 160.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(0, -185)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(0, -440)
[node name="TalkPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(110, -350)
[node name="OrbPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-170, -240)
[node name="FormVfx" type="Control" parent="."]
unique_name_in_owner = true
mouse_filter = 2
'''


SELECTION_SCENE = '''[gd_scene load_steps=3 format=3]
[ext_resource type="SpriteFrames" path="res://VolibearArt/scenes/volibear_frames.tres" id="frames"]
[ext_resource type="Script" path="res://VolibearArt/scenes/actor.gd" id="actor"]
[node name="VolibearSelection" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="ActorAnchor" type="Control" parent="."]
layout_mode = 0
anchor_left = 0.69
anchor_right = 0.69
anchor_top = 0.86
anchor_bottom = 0.86
mouse_filter = 2
[node name="AnimatedSprite2D" type="AnimatedSprite2D" parent="ActorAnchor"]
position = Vector2(-375, -663)
scale = Vector2(1.5, 1.5)
centered = false
sprite_frames = ExtResource("frames")
animation = &"relaxed_loop"
autoplay = "relaxed_loop"
script = ExtResource("actor")
return_animation = &"relaxed_loop"
'''


def run(godot_args, work, label, env):
    log = work / (label + '.log')
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([str(x) for x in godot_args], cwd=ROOT, env=env,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    text = log.read_text(encoding='utf-8', errors='replace')
    if result.returncode or 'SCRIPT ERROR:' in text or 'ERROR:' in text:
        raise RuntimeError(f'{label} failed ({result.returncode}); {log}\n{text[-6000:]}')
    print(f'{label}: OK ({log})', flush=True)
    return text


def build(godot, output=PACK):
    output = output_path(output)
    godot = godot.resolve()
    if not godot.is_file():
        raise ValueError('Godot executable does not exist')
    manifest, clips, portraits = read_inputs()
    ui = read_ui_inputs()
    effects, audio = read_effect_inputs()
    snapshots = {p: sha(p) for p in [ANIMATIONS / 'manifest.json', CARDS / 'data/asset_manifest.json',
                                    UI / 'manifest.json', VFX / 'manifest.json', AUDIO / 'manifest.json']}
    work = ROOT / '.local/asset-build' / uuid.uuid4().hex
    project = work / 'project'
    art = project / 'VolibearArt'
    project.mkdir(parents=True)
    env = dict(os.environ, PYTHONUTF8='1')
    # The Mono editor needs hostfxr even though this pack contains no C# scripts.
    # Prefer the repository's pinned SDK; do not replace any system installation.
    config_path = ROOT / '.local/config.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {}
    dotnet = config.get('dotnet') or shutil.which('dotnet')
    if not dotnet or not Path(dotnet).is_file():
        raise ValueError('Godot Mono requires dotnet: configure .local/config.json dotnet or PATH')
    env['DOTNET_ROOT'] = str(Path(dotnet).resolve().parent)
    env['PATH'] = env['DOTNET_ROOT'] + os.pathsep + env.get('PATH', '')
    env['DOTNET_CLI_TELEMETRY_OPTOUT'] = '1'
    for variable in ['APPDATA', 'LOCALAPPDATA', 'HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME']:
        folder = work / 'profile' / variable
        folder.mkdir(parents=True)
        env[variable] = str(folder)
    version = run([godot, '--version'], work, 'version', env).strip()
    if not version.startswith('4.5.1.stable.mono.'):
        raise ValueError(f'Requires Godot 4.5.1 stable mono; found {version}')
    # Reuse the existing runtime-only asset selection, never the legacy build output.
    run([sys.executable, ROOT / 'assets/animation/integration_sts2_v5/stage_assets.py',
         '--output', art], work, 'stage', env)
    for export in portraits:
        destination = art / 'cards' / export['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CARDS / export['path'], destination)
        if sha(destination) != export['sha256']:
            raise ValueError(f'Portrait changed during copy: {destination}')
    scenes = art / 'scenes'
    scenes.mkdir()
    (scenes / 'volibear_frames.tres').write_text(sprite_frames(clips), encoding='utf-8')
    (scenes / 'volibear_combat.tscn').write_text(combat_scene(manifest['pivot_px']), encoding='utf-8')
    (scenes / 'volibear_selection.tscn').write_text(SELECTION_SCENE, encoding='utf-8')
    social_aliases = {**ALIASES, 'idle': 'relaxed_loop', 'Idle': 'relaxed_loop', 'IdleLoop': 'relaxed_loop'}
    (scenes / 'volibear_social_frames.tres').write_text(sprite_frames(clips, social_aliases), encoding='utf-8')
    shutil.copyfile(PRESENTATION / 'actor.gd', scenes / 'actor.gd')
    for name in NATIVE_RESOURCES:
        shutil.copyfile(PRESENTATION / name, scenes / name)
    (scenes / 'volibear_effect_frames.tres').write_text(
        sprite_frames(effect_clips(effects), {}, 'res://VolibearArt/vfx'), encoding='utf-8')
    stage_icons(art)
    project_text = ('config_version=5\n[application]\nconfig/name="Volibear asset build"\n'
                    '[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    verify_project_text = project_text
    # Confined Windows hosts may not expose the system certificate store. This build never
    # uses networking; an explicit CA bundle avoids that host dependency without waiving errors.
    # The CA bundle is outside VolibearArt and never enters the exported resource list.
    if os.name == 'nt':
        try:
            from pip._vendor import certifi
        except ImportError as error:
            raise ValueError('Windows isolated Godot build requires pip bundled certifi') from error
        ca = work / 'build-ca.pem'
        shutil.copyfile(certifi.where(), ca)
        verify_project_text += '[network]\ntls/certificate_bundle_override=' + json.dumps(ca.as_posix()) + '\n'
        editor_config = Path(env['APPDATA']) / 'Godot/editor_settings-4.5.tres'
        editor_config.parent.mkdir(parents=True, exist_ok=True)
        editor_config.write_text('[gd_resource type="EditorSettings" format=3]\n[resource]\n'
                                 'network/tls/editor_tls_certificates=' + json.dumps(ca.as_posix()) + '\n',
                                 encoding='utf-8')
    (project / 'project.godot').write_text(project_text, encoding='utf-8')
    resources = sorted('res://' + p.relative_to(project).as_posix() for p in art.rglob('*')
                       if p.suffix in {'.png', '.ogg', '.svg', '.tscn', '.tres', '.gd', '.gdshader'})
    preset = (ROOT / 'assets/animation/integration_sts2_v5/export_presets.cfg').read_text(encoding='utf-8')
    preset = preset.replace('export_filter="all_resources"', 'export_filter="resources"\nexport_files=PackedStringArray('
                            + ', '.join(json.dumps(p) for p in resources) + ')')
    # Keep GDScript as source: the pack is consumed by the pinned MegaDot host, not this editor.
    preset = preset.replace('script_export_mode=1', 'script_export_mode=0')
    (project / 'export_presets.cfg').write_text(preset, encoding='utf-8')
    run([godot, '--headless', '--editor', '--path', project, '--import'], work, 'import', env)
    temporary_pack = work / 'Volibear.pck'
    run([godot, '--headless', '--path', project, '--export-pack', 'AssetPack', temporary_pack], work, 'export', env)
    verify = work / 'verify'
    verify.mkdir()
    (verify / 'project.godot').write_text(verify_project_text, encoding='utf-8')
    shutil.copyfile(PRESENTATION / 'verify_pack.gd', verify / 'verify_pack.gd')
    shutil.copyfile(PRESENTATION / 'verify_effects.gd', verify / 'verify_effects.gd')
    # Independent expectations travel outside the pack, so a missing resource cannot erase its test.
    expected = {'clips': {c['name']: {'frames': c['frame_count'], 'loop': c['loop']} for c in clips},
                'portraits': ['res://VolibearArt/cards/' + e['path'] for e in portraits],
                'effects': {e['id']: {'frames': e['frame_count'], 'loop': e['loop'], 'tile': e['atlas']['tile_size']}
                            for e in effects},
                'audio': [{'path': 'res://VolibearArt/audio/' + row['file'], 'seconds': row['duration_seconds']}
                          for row in audio['assets']],
                'icons': {'res://VolibearArt/icons/' + path: size for path, (_, size) in ICON_EXPORTS.items()}}
    expected_path = work / 'expected.json'
    expected_path.write_text(json.dumps(expected), encoding='utf-8')
    result = run([godot, '--headless', '--path', verify, '--script', 'verify_pack.gd', '--',
                  temporary_pack, expected_path], work, 'verify', env)
    if ('VOLIBEAR_RESOURCE_PASS clips=26 frames=940 portraits=178' not in result
            or 'VOLIBEAR_UI_RESOURCE_PASS scenes=5 transition=1' not in result):
        raise RuntimeError('Missing resource verification completion sentinel')
    effect_result = run([godot, '--headless', '--path', verify, '--script', 'verify_effects.gd', '--',
                         temporary_pack, expected_path], work, 'verify-effects', env)
    if 'VOLIBEAR_EFFECTS_PASS vfx=40 audio=47 cues=54 icons=10 lifecycle=PASS' not in effect_result:
        raise RuntimeError('Missing production effects lifecycle verification completion sentinel')
    for source, digest in snapshots.items():
        if sha(source) != digest:
            raise ValueError(f'Input manifest changed during build: {source}')
    # Recheck approved source and staged atlas hashes before publishing the candidate pack.
    read_inputs()
    for clip in clips:
        if sha(art / 'animations' / clip['atlas']['image']) != clip['atlas_sha256']:
            raise ValueError('Staged atlas changed during build')
    read_ui_inputs()
    for row in ui:
        if sha(art / 'ui' / row['file']) != row['sha256']:
            raise ValueError('Staged approved UI bytes changed during build')
    read_effect_inputs()
    for effect in effects:
        if sha(art / 'vfx' / effect['atlas']['image']) != effect['atlas']['sha256']:
            raise ValueError('Staged approved VFX bytes changed during build')
    for row in audio['assets']:
        if sha(art / 'audio' / row['file']) != row['ogg_sha256']:
            raise ValueError('Staged approved audio bytes changed during build')
    output.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temporary_pack, output)
    print(f'RESOURCE BUILD ONLY: {output} ({output.stat().st_size} bytes); no game acceptance or deployment')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=PACK,
                        help='Candidate .pck beneath .local; defaults to .local/packs/Volibear.pck')
    args = parser.parse_args()
    build(args.godot, args.output)


if __name__ == '__main__':
    main()
