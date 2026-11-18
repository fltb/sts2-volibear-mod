#!/usr/bin/env python3
"""Render and verify production combat VFX in isolated geometry scenes.

This does not launch StS2 or claim game acceptance. Without --pack, the harness
stages the actual source controller, manifests and existing atlas textures. With
--pack it loads the exported production PCK. Outputs stay under ignored .local.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_assets import effect_clips, sprite_frames


def stage(project: Path) -> None:
    scenes = project / 'VolibearArt/scenes'
    scenes.mkdir(parents=True, exist_ok=True)
    for name in ('effects.gd', 'combat_vfx.gd', 'audio_profile.gd', 'volibear_effects.tscn'):
        shutil.copyfile(ROOT / 'src/Volibear/Presentation' / name, scenes / name)
    for directory in ('vfx', 'audio'):
        source = ROOT / 'assets/animation' / directory
        destination = project / 'VolibearArt' / directory
        destination.mkdir(exist_ok=True)
        shutil.copyfile(source / 'manifest.json', destination / 'manifest.json')
    audio_source = ROOT / 'assets/animation/audio'
    audio_manifest = json.loads((audio_source / 'manifest.json').read_text())
    for asset in audio_manifest['assets']:
        destination = project / 'VolibearArt/audio' / asset['file']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio_source / asset['file'], destination)
    # Only legacy textures are referenced by the controller's shared SpriteFrames;
    # procedural geometry itself contains no generated or substitute image assets.
    atlas_source = ROOT / 'assets/animation/vfx/atlases'
    atlas_target = project / 'VolibearArt/vfx/atlases'
    # Godot writes .import sidecars beside images. A symlink would leak these
    # generated files into the source tree, so keep staging physically isolated.
    if atlas_target.is_symlink():
        atlas_target.unlink()
    atlas_target.mkdir(exist_ok=True)
    for image in atlas_source.glob('*.png'):
        shutil.copy2(image, atlas_target / image.name)
    manifest = json.loads((ROOT / 'assets/animation/vfx/manifest.json').read_text())
    (scenes / 'volibear_effect_frames.tres').write_text(
        sprite_frames(effect_clips(manifest['effects']), {}, 'res://VolibearArt/vfx'), encoding='utf-8')


def run(command: list[str], env: dict[str, str], output: Path, name: str, timeout: int = 120) -> str:
    process = subprocess.run(command, env=env, cwd=ROOT, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=timeout)
    (output / name).write_text(process.stdout, encoding='utf-8')
    if process.returncode or re.search(r'(?m)^(?:SCRIPT ERROR|ERROR):', process.stdout):
        raise RuntimeError(f'{name} failed ({process.returncode}):\n{process.stdout[-8000:]}')
    return process.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', default=os.environ.get('VOLIBEAR_GODOT'))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/combat-vfx-preview')
    parser.add_argument('--headless', action='store_true', help='Run behavior checks without capture')
    args = parser.parse_args()
    godot = shutil.which(args.godot or '') or args.godot
    if not godot or not Path(godot).is_file():
        parser.error('Provide --godot or VOLIBEAR_GODOT')
    output = args.output.resolve()
    if not any(output.is_relative_to(ROOT / part) for part in ('.local', 'artifacts')):
        parser.error('Output must be beneath this repository .local/ or artifacts/')
    output.mkdir(parents=True, exist_ok=True)
    project = output / 'project'
    project.mkdir(exist_ok=True)
    (output / 'frames').mkdir(exist_ok=True)
    (project / 'project.godot').write_text(
        'config_version=5\n[application]\nconfig/name="Combat VFX resource verification"\n'
        '[display]\nwindow/size/viewport_width=1404\nwindow/size/viewport_height=928\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'tools/preview_combat_vfx.gd', project / 'preview_combat_vfx.gd')
    if args.pack is None:
        stage(project)
    env = os.environ.copy()
    if env.get('DOTNET_ROOT'):
        env['PATH'] = env['DOTNET_ROOT'] + os.pathsep + env.get('PATH', '')
    env['XDG_DATA_HOME'] = str(output / 'profile/data')
    env['XDG_CONFIG_HOME'] = str(output / 'profile/config')
    env['DOTNET_CLI_HOME'] = str(output / 'profile/dotnet')
    if args.pack is None:
        run([godot, '--headless', '--editor', '--path', str(project), '--import'], env, output, 'import.log')
    command = [godot, '--path', str(project), '--rendering-method', 'gl_compatibility',
               '--audio-driver', 'Dummy', '--script', 'preview_combat_vfx.gd']
    command += ['--headless'] if args.headless else ['--display-driver', 'x11'] if sys.platform.startswith('linux') else []
    command += ['--', str(args.pack.resolve()) if args.pack else '-', '' if args.headless else str(output)]
    log = run(command, env, output, 'verify.log')
    if 'VOLIBEAR_COMBAT_VFX_PASS styles=29' not in log:
        raise RuntimeError('Missing production controller verification sentinel')
    print(log.strip())
    if not args.headless:
        from PIL import Image
        frames = []
        for path in sorted((output / 'frames').glob('*.png')):
            with Image.open(path) as image:
                frames.append(image.convert('RGB'))
        if len(frames) != 32:
            raise RuntimeError(f'Expected 32 rendered frames, found {len(frames)}')
        frames[0].save(output / 'combat_vfx.gif', save_all=True, append_images=frames[1:],
                       duration=65, loop=0, disposal=2, optimize=False)
        for name in ('physical.png', 'thunder.png', 'defense_synergy.png', 'target_geometry.png', 'combat_vfx.gif'):
            print(output / name)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
