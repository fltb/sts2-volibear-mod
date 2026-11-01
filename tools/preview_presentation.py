#!/usr/bin/env python3
"""Render the production PCK in an isolated Godot window; never launch the game.

Outputs are ignored local resource previews. VFX are created by effects.emit_effect;
the contact sheets seek their authored poster frames only after production dispatch.
The energy GIF drives the native scene's Label to demonstrate its cosmetic reactions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FPS = 12
SENTINEL = 'VOLIBEAR_PREVIEW_PASS vfx=40 energy_states=4 relics=2'


def render(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    # Xvfb and Godot belong to one private process group. A renderer timeout must not
    # leave an invisible graphics process running after the wrapper exits.
    process = subprocess.Popen(command, env=env, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
    try:
        stdout, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise RuntimeError('Resource rendering timed out; the owned renderer/display were stopped')
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def executable(value: str | None, names: tuple[str, ...]) -> Path | None:
    if value:
        result = shutil.which(value) or value
        return Path(result).resolve() if Path(result).is_file() else None
    for name in names:
        if result := shutil.which(name):
            return Path(result).resolve()
    return None


def create_gif(output: Path) -> None:
    from PIL import Image

    paths = sorted((output / 'energy_frames').glob('*.png'))
    if len(paths) != FPS * 4:
        raise RuntimeError(f'Expected {FPS * 4} real energy frames; found {len(paths)}')
    images = []
    for path in paths:
        with Image.open(path) as source:
            images.append(source.convert('RGB'))
    palette = images[0].quantize(colors=128)
    frames = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    # GIF uses 10 ms units. Distribute rounding instead of shortening every frame.
    durations = [round((i + 1) * 100 / FPS) * 10 - round(i * 100 / FPS) * 10
                 for i in range(len(frames))]
    frames[0].save(output / 'energy.gif', save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=False, disposal=2)
    sheets = []
    for path in sorted(output.glob('vfx_group_*.png')):
        with Image.open(path) as source:
            sheets.append(source.convert('RGB'))
    if len(sheets) != 5:
        raise RuntimeError('Expected five rendered VFX groups')
    contact = Image.new('RGB', (max(image.width for image in sheets), sum(image.height for image in sheets)))
    top = 0
    for sheet in sheets:
        contact.paste(sheet, (0, top))
        top += sheet.height
    contact.save(output / 'vfx_contact_sheet.png', optimize=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', default=os.environ.get('VOLIBEAR_GODOT'), help='Godot 4.5.1 Mono executable')
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/packs/Volibear.pck')
    parser.add_argument('--output', type=Path, help='New output directory inside .local or artifacts')
    args = parser.parse_args(argv)
    config_path = ROOT / '.local/config.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {}
    godot = executable(args.godot or config.get('godot'), ('godot-mono', 'godot4-mono', 'godot4', 'godot'))
    if godot is None:
        parser.error('Supply --godot or VOLIBEAR_GODOT with the Godot 4.5.1 Mono executable')
    pack = args.pack.resolve()
    if not pack.is_file() or pack.suffix.lower() != '.pck':
        parser.error('The production PCK must already exist; this tool does not build or deploy it')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (args.output or ROOT / '.local/presentation-preview' / stamp).resolve()
    if not any(output.is_relative_to(ROOT / folder) for folder in ('.local', 'artifacts')):
        parser.error('Preview outputs must stay inside this repository\'s ignored .local or artifacts directory')
    if output.exists() and any(output.iterdir()):
        parser.error('Output directory is not empty; choose a new directory to preserve the previous capture')
    dotnet = executable(os.environ.get('VOLIBEAR_DOTNET') or config.get('dotnet'), ('dotnet',))
    if dotnet is None:
        fallback = ROOT / '.local/dotnet' / ('dotnet.exe' if os.name == 'nt' else 'dotnet')
        dotnet = fallback if fallback.is_file() else None
    if dotnet is None:
        parser.error('Godot Mono needs .NET; set VOLIBEAR_DOTNET or put dotnet on PATH')
    output.mkdir(parents=True, exist_ok=True)
    project = output / 'project'
    project.mkdir()
    (output / 'energy_frames').mkdir()
    shutil.copyfile(ROOT / 'tools/preview_presentation.gd', project / 'preview_presentation.gd')
    (project / 'project.godot').write_text(
        'config_version=5\n[application]\nconfig/name="Volibear resource preview"\n'
        '[display]\nwindow/size/viewport_width=1920\nwindow/size/viewport_height=1080\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    env = os.environ.copy()
    env['DOTNET_ROOT'] = str(dotnet.resolve().parent)
    env['PATH'] = env['DOTNET_ROOT'] + os.pathsep + env.get('PATH', '')
    env['DOTNET_CLI_HOME'] = str(output / 'profile/dotnet')
    env['XDG_DATA_HOME'] = str(output / 'profile/data')
    env['XDG_CONFIG_HOME'] = str(output / 'profile/config')
    if os.name == 'nt':
        env['APPDATA'] = str(output / 'profile/appdata')
        env['LOCALAPPDATA'] = str(output / 'profile/localappdata')
    version = subprocess.run([str(godot), '--version'], env=env, text=True,
                             capture_output=True, check=True, timeout=20).stdout.strip()
    if not version.startswith('4.5.1.stable.mono.'):
        raise ValueError(f'Requires the pinned Godot 4.5.1 Mono; found {version}')
    command = [str(godot), '--path', str(project), '--rendering-method', 'gl_compatibility',
               '--audio-driver', 'Dummy', '--script', 'preview_presentation.gd', '--', str(pack), str(output)]
    if sys.platform.startswith('linux'):
        xvfb = shutil.which('xvfb-run')
        if xvfb is None:
            raise RuntimeError('Linux preview needs xvfb-run for an isolated display; --headless uses a dummy renderer and is not supported')
        command = [xvfb, '-a', '-s', '-screen 0 1920x1080x24'] + command[:1] + ['--display-driver', 'x11'] + command[1:]
    result = render(command, env)
    log = result.stdout + '\n' + result.stderr
    (output / 'godot.log').write_text(log, encoding='utf-8')
    if result.returncode or SENTINEL not in log or re.search(r'(?m)^(?:ERROR|SCRIPT ERROR):', log):
        raise RuntimeError(f'Resource rendering failed (exit {result.returncode}); see {output / "godot.log"}\n{log[-6000:]}')
    create_gif(output)
    print('Rendered production resources, not a game acceptance run:')
    for name in ('overview.png', 'energy.gif', 'energy_3.png', 'energy_2.png', 'energy_0.png',
                 'energy_4.png', 'vfx_contact_sheet.png', 'vfx_contrast.png'):
        print(output / name)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
