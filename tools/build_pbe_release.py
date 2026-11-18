#!/usr/bin/env python3
"""Build installable ZIPs for one game channel using local game and tool paths."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import build_assets
import dev
import local_delivery
import toolchain

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'src/Volibear'
CONFIG = ROOT / '.local/config.json'
OUTPUT = ROOT / '.local/release/pbe'
PROFILES = {'open': 'opensound', 'riot_en': 'riot-sound'}


def build(channel='pbe', game_dir=None):
    if not CONFIG.is_file():
        raise ValueError('Copy tools/local_config.example.json to .local/config.json and set game_dir, godot and dotnet.')
    settings = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    game_key = 'stable_game_dir' if channel == 'stable' else 'game_dir'
    game_path = game_dir or settings.get(game_key)
    if not game_path:
        raise ValueError(f'Set {game_key} in .local/config.json or pass --game-dir.')
    game = Path(game_path).expanduser().resolve()
    manifest = PROJECT / f'Volibear.{channel}.json'
    metadata = json.loads(manifest.read_text(encoding='utf-8-sig'))
    mod = metadata['id']
    installed = json.loads((game / 'release_info.json').read_text(encoding='utf-8-sig'))
    game_version = installed['version'].removeprefix('v')
    target_series = metadata['min_game_version'].rsplit('.', 1)[0]
    if (channel == 'stable' and game_version != metadata['min_game_version']
            or channel == 'pbe' and not game_version.startswith(target_series + '.')):
        raise ValueError(f'The {channel} target cannot be built from StS2 {game_version}.')
    data = dev.data_directory(game)
    baselib_key = 'stable_baselib_dll' if channel == 'stable' else 'baselib_dll'
    baselib = Path(settings.get(baselib_key, game / 'mods/BaseLib/BaseLib.dll')).expanduser().resolve()
    for reference in (data / 'sts2.dll', data / 'GodotSharp.dll', data / '0Harmony.dll', baselib):
        if not reference.is_file():
            raise FileNotFoundError(f'Missing build reference: {reference}')
    tools = toolchain.check(settings['dotnet'], settings['godot'])
    env = toolchain.dotnet_environment(tools['dotnet'])
    local_delivery.prepare_audio('riot_en', env)
    output = OUTPUT if channel == 'pbe' else OUTPUT.parent / channel
    output.mkdir(parents=True, exist_ok=True)
    stem = f"{mod}-{metadata['version']}-{channel}-{game_version}"
    game_channel = 'beta' if channel == 'pbe' else 'stable'
    with tempfile.TemporaryDirectory(dir=output, prefix='.build-') as temporary:
        stage = Path(temporary)
        subprocess.run([tools['dotnet'], 'build', str(PROJECT / 'Volibear.csproj'), '-c', 'Release',
                        f'-p:GameChannel={game_channel}', '-p:IncludeDevProbes=false', f'-p:Sts2DataDir={data}',
                        f'-p:BaseLibPath={baselib}', '-o', str(stage / 'bin'),
                        '--artifacts-path', str(stage / 'compile'), '--nologo'],
                       cwd=ROOT, env=env, check=True)
        archives = []
        for profile, label in PROFILES.items():
            pack = ROOT / '.local/packs' / channel / profile / f'{mod}.pck'
            build_assets.build(Path(tools['godot']), pack, audio_profile=profile, dotnet=Path(tools['dotnet']))
            archive = stage / f'{stem}-{label}.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as out:
                out.write(stage / 'bin' / f'{mod}.dll', f'{mod}/{mod}.dll')
                out.write(pack, f'{mod}/{mod}.pck')
                out.write(manifest, f'{mod}/{mod}.json')
            archives.append(archive)
        for archive in archives:
            target = output / archive.name
            os.replace(archive, target)
            print(target, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel', choices=('stable', 'pbe'), default='pbe')
    parser.add_argument('--game-dir', type=Path, help='Override the configured local game directory')
    args = parser.parse_args()
    try:
        build(args.channel, args.game_dir)
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f'{args.channel} build failed: {error}')
