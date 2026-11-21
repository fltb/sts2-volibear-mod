#!/usr/bin/env python3
"""Render the production combat actor and exact new atlases in pinned Godot.

This deliberately does not claim game acceptance. The scene, script, clip timing
and raw texture bytes are production inputs. Outputs stay in ignored local work.
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


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True, type=Path)
    parser.add_argument('--dotnet', required=True, type=Path)
    parser.add_argument('--display', default=os.environ.get('DISPLAY'))
    parser.add_argument('--output', type=Path, default=ROOT / '.local/combat-motion-godot')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.local'):
        parser.error('Use an ignored .local output directory')
    if output.exists():
        parser.error('Output already exists; use a new path to preserve prior captures')
    (output / 'frames').mkdir(parents=True)
    project = output / 'project'
    scenes = project / 'VolibearArt/scenes'
    scenes.mkdir(parents=True)
    base_manifest, base_clips, _ = build_assets.read_inputs()
    selected = [clip for clip in base_clips if clip['name'] in {
        'idle_loop', 'domain_idle', 'weak_loop', 'domain_weak_loop', 'hurt', 'die'}]
    combat_clips = build_assets.read_combat_inputs()
    clips = selected + combat_clips
    for clip in clips:
        path = clip['atlas']['image']
        copy(build_assets.animation_source(path), project / 'VolibearArt/animations' / path)
    copy(build_assets.COMBAT_ANIMATIONS / 'manifest.json', project / 'VolibearArt/animations/combat/manifest.json')
    copy(build_assets.PRESENTATION / 'actor.gd', scenes / 'actor.gd')
    (scenes / 'volibear_frames.tres').write_text(build_assets.sprite_frames(clips, {}), encoding='utf-8')
    (scenes / 'volibear_combat.tscn').write_text(build_assets.combat_scene(base_manifest['pivot_px']), encoding='utf-8')
    copy(ROOT / 'tools/preview_combat_motions.gd', project / 'preview.gd')
    (project / 'project.godot').write_text(
        'config_version=5\n[application]\nconfig/name="Volibear combat motion preview"\n'
        '[display]\nwindow/size/viewport_width=1440\nwindow/size/viewport_height=1080\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    env = os.environ.copy()
    env['DOTNET_ROOT'] = str(args.dotnet.resolve().parent)
    env['PATH'] = env['DOTNET_ROOT'] + os.pathsep + env.get('PATH', '')
    if args.display:
        env['DISPLAY'] = args.display
    for label, command in (
        ('import', [str(args.godot), '--headless', '--editor', '--path', str(project), '--import', '--quit']),
        ('render', [str(args.godot), '--display-driver', 'x11', '--rendering-method', 'gl_compatibility',
                    '--audio-driver', 'Dummy', '--path', str(project), '--script', 'preview.gd', '--', str(output)]),
    ):
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        log = result.stdout + '\n' + result.stderr
        (output / (label + '.log')).write_text(log, encoding='utf-8')
        if result.returncode or 'SCRIPT ERROR:' in log or '\nERROR:' in log:
            raise RuntimeError(f'{label} failed: {log[-6000:]}')
    if 'VOLIBEAR_COMBAT_MOTION_PASS clips=14 frames=358 lifecycle=PASS rendered=33' not in log:
        raise RuntimeError('Missing actual animation lifecycle completion')
    # Read every real capture back. Stable title/label pixels prove that a desktop
    # viewport resize has not silently cropped or shifted subsequent video frames.
    from PIL import Image
    regions = [(0, 0, 1440, 78)] + [
        (27 + (i % 4) * 357, 86 + (i // 4) * 246,
         312 + (i % 4) * 357, 110 + (i // 4) * 246) for i in range(14)]
    with Image.open(output / 'contact-sheet.png') as reference:
        if reference.size != (1440, 1080):
            raise RuntimeError('Incorrect production preview dimensions')
        reference_regions = [reference.crop(region).tobytes() for region in regions]
    frames = sorted((output / 'frames').glob('*.png'))
    if len(frames) != 32:
        raise RuntimeError('Incomplete rendered animation sequence')
    for frame in frames:
        with Image.open(frame) as picture:
            if picture.size != (1440, 1080):
                raise RuntimeError('Frame size changed: ' + frame.name)
            for index, region in enumerate(regions):
                if picture.crop(region).tobytes() != reference_regions[index]:
                    raise RuntimeError(f'Title/label region {index} shifted or was obscured: {frame.name}')
    if ffmpeg := shutil.which('ffmpeg'):
        result = subprocess.run([ffmpeg, '-v', 'error', '-framerate', '24', '-i', str(output / 'frames/%03d.png'),
                                 '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                                 str(output / 'combat-motions.mp4')], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr)
        if ffprobe := shutil.which('ffprobe'):
            probe = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                                    '-show_entries', 'stream=width,height,nb_frames', '-of', 'json',
                                    str(output / 'combat-motions.mp4')],
                                   capture_output=True, text=True, timeout=20, check=True)
            stream = json.loads(probe.stdout)['streams'][0]
            if (stream['width'], stream['height'], int(stream['nb_frames'])) != (1440, 1080, 32):
                raise RuntimeError('Encoded video dimensions/frame count do not match the full captures')
    (output / 'result.json').write_text(json.dumps(dict(status='PASS', clips=14, frames=358,
            scope='production-resource-playback-and-actor-lifecycle; not game acceptance',
            render_captures=33, fixed_viewport=[1440, 1080],
            title_and_14_labels_unchanged_in_all_frames=True), indent=2), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
