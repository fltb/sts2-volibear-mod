#!/usr/bin/env python3
"""Compose actual Volibear actor and VFX resources for visual review.

Targets and the event schedule are explicit resource fixtures. This command is
not a game simulation, native combat timing check, or installation acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import build_assets
from tools.preview_combat_vfx import stage, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', default=os.environ.get('VOLIBEAR_GODOT'))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/combat-combo-preview')
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
        'config_version=5\n[application]\nconfig/name="Volibear combat composition preview"\n'
        '[display]\nwindow/size/viewport_width=1480\nwindow/size/viewport_height=1100\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'tools/preview_combat_combos.gd', project / 'preview_combat_combos.gd')
    if args.pack is None:
        stage(project)
        scenes = project / 'VolibearArt/scenes'
        shutil.copyfile(ROOT / 'src/Volibear/Presentation/actor.gd', scenes / 'actor.gd')
        base = json.loads((build_assets.ANIMATIONS / 'manifest.json').read_text())
        clips = [row for row in base['clips'] + base.get('variants', [])
                 if row['name'] in ('idle_loop', 'domain_idle')]
        clips += build_assets.read_combat_inputs()
        for clip in clips:
            target = project / 'VolibearArt/animations' / clip['atlas']['image']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(build_assets.animation_source(clip['atlas']['image']), target)
        (scenes / 'volibear_frames.tres').write_text(build_assets.sprite_frames(clips, {}), encoding='utf-8')
        (scenes / 'volibear_combat.tscn').write_text(build_assets.combat_scene(base['pivot_px']), encoding='utf-8')
        shutil.copyfile(build_assets.COMBAT_ANIMATIONS / 'manifest.json', project / 'VolibearArt/animations/combat/manifest.json')
    env = os.environ.copy()
    if env.get('DOTNET_ROOT'):
        env['PATH'] = env['DOTNET_ROOT'] + os.pathsep + env.get('PATH', '')
    env.update(XDG_DATA_HOME=str(output / 'profile/data'),
               XDG_CONFIG_HOME=str(output / 'profile/config'),
               DOTNET_CLI_HOME=str(output / 'profile/dotnet'))
    if args.pack is None:
        run([godot, '--headless', '--editor', '--path', str(project), '--import'], env, output, 'import.log', 180)
    command = [godot, '--path', str(project), '--rendering-method', 'gl_compatibility',
               '--audio-driver', 'Dummy', '--script', 'preview_combat_combos.gd']
    if sys.platform.startswith('linux'):
        command += ['--display-driver', 'x11']
    command += ['--', str(args.pack.resolve()) if args.pack else '-', str(output)]
    log = run(command, env, output, 'render.log', 180)
    if 'VOLIBEAR_COMBAT_COMPOSITION_PASS cases=6 frames=60' not in log:
        raise RuntimeError('Missing composition rendering sentinel')
    from PIL import Image
    frames = []
    for path in sorted((output / 'frames').glob('*.png')):
        with Image.open(path) as image:
            frames.append(image.convert('RGB'))
    if len(frames) != 60:
        raise RuntimeError(f'Expected 60 rendered frames, found {len(frames)}')
    durations = [round((i + 1) * 100 / 24) * 10 - round(i * 100 / 24) * 10 for i in range(len(frames))]
    frames[0].save(output / 'combat_combos.gif', save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=2, optimize=False)
    print(log.strip())
    print(output / 'combat_combos.png')
    print(output / 'combat_combos.gif')
    if ffmpeg := shutil.which('ffmpeg'):
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-framerate', '24', '-i', str(output / 'frames/%03d.png'),
                        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                        str(output / 'combat_combos.mp4')], check=True, timeout=120)
        print(output / 'combat_combos.mp4')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
