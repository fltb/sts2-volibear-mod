#!/usr/bin/env python3
"""Build both installable PBE ZIPs locally using the paths in .local/config.json."""
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


def build():
    if not CONFIG.is_file():
        raise ValueError('Copy tools/local_config.example.json to .local/config.json and set game_dir, godot and dotnet.')
    settings = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    game = Path(settings['game_dir']).expanduser().resolve()
    manifest = PROJECT / 'Volibear.pbe.json'
    metadata = json.loads(manifest.read_text(encoding='utf-8-sig'))
    mod = metadata['id']
    installed = json.loads((game / 'release_info.json').read_text(encoding='utf-8-sig'))
    game_version = installed['version'].removeprefix('v')
    data = dev.data_directory(game)
    baselib = Path(settings.get('baselib_dll', game / 'mods/BaseLib/BaseLib.dll')).expanduser().resolve()
    for reference in (data / 'sts2.dll', data / 'GodotSharp.dll', data / '0Harmony.dll', baselib):
        if not reference.is_file():
            raise FileNotFoundError(f'Missing build reference: {reference}')
    tools = toolchain.check(settings['dotnet'], settings['godot'])
    env = toolchain.dotnet_environment(tools['dotnet'])
    local_delivery.prepare_audio('riot_en', env)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stem = f"{mod}-{metadata['version']}-pbe-{game_version}"
    with tempfile.TemporaryDirectory(dir=OUTPUT, prefix='.build-') as temporary:
        stage = Path(temporary)
        subprocess.run([tools['dotnet'], 'build', str(PROJECT / 'Volibear.csproj'), '-c', 'Release',
                        '-p:GameChannel=beta', '-p:IncludeDevProbes=false', f'-p:Sts2DataDir={data}',
                        f'-p:BaseLibPath={baselib}', '-o', str(stage / 'bin'), '--nologo'],
                       cwd=ROOT, env=env, check=True)
        archives = []
        for profile, label in PROFILES.items():
            pack = ROOT / '.local/packs/pbe' / profile / f'{mod}.pck'
            build_assets.build(Path(tools['godot']), pack, audio_profile=profile, dotnet=Path(tools['dotnet']))
            archive = stage / f'{stem}-{label}.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as out:
                out.write(stage / 'bin' / f'{mod}.dll', f'{mod}/{mod}.dll')
                out.write(pack, f'{mod}/{mod}.pck')
                out.write(manifest, f'{mod}/{mod}.json')
            archives.append(archive)
        for archive in archives:
            target = OUTPUT / archive.name
            os.replace(archive, target)
            print(target, flush=True)


if __name__ == '__main__':
    try:
        build()
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f'PBE build failed: {error}')
