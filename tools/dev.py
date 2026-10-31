#!/usr/bin/env python3
"""Local development commands. Never distributes game assemblies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MOD = 'Volibear'


def config():
    path = ROOT / '.local/config.json'
    if not path.is_file():
        raise RuntimeError('Create .local/config.json with game_dir and dotnet paths.')
    return json.loads(path.read_text())


def validate_game(game):
    info = json.loads((game / 'release_info.json').read_text())
    if (info.get('version'), info.get('commit')) != ('v0.107.1', '59260271'):
        raise RuntimeError('Game version mismatch; deployment refused: ' + str(info))
    data = game / 'data_sts2_linuxbsd_x86_64'
    for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
        if not (data / name).is_file():
            raise RuntimeError('Missing game assembly: ' + name)
    return data


def call(args):
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1')
    subprocess.run([str(x) for x in args], cwd=ROOT, env=env, check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deploy(game):
    target = game / 'mods' / MOD
    expected = game.resolve() / 'mods' / MOD
    if target.is_symlink() or target.resolve() != expected:
        raise RuntimeError('Unexpected deployment target')
    sources = [ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll',
               ROOT / 'src/Volibear/Volibear.json']
    marker = target / '.volibear-dev-owned.json'
    old = json.loads(marker.read_text()) if marker.is_file() else {}
    if target.exists() and not marker.is_file() and any(target.iterdir()):
        raise RuntimeError('Existing unowned mod directory; refusing overwrite')
    for name, sha in old.items():
        p = target / name
        if p.name != name or (p.exists() and digest(p) != sha):
            raise RuntimeError('Previously deployed file changed: ' + name)
    for src in sources:
        if not src.is_file():
            raise RuntimeError('Build first: ' + str(src))
    target.mkdir(parents=True, exist_ok=True)
    for src in sources:
        (target / src.name).write_bytes(src.read_bytes())
    marker.write_text(json.dumps({p.name: digest(p) for p in sources}, indent=2) + '\n')
    print('Deployed owned files only:', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'build', 'test', 'deploy', 'run', 'logs'])
    args = parser.parse_args()
    if args.command == 'test':
        call([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        return
    c = config()
    game = Path(c['game_dir']).expanduser().resolve()
    data = validate_game(game)
    if args.command == 'doctor':
        call([c['dotnet'], '--version'])
        print('Game 0.107.1 / 59260271 and managed references: OK')
        print('PCK/Godot and RitsuLib: not yet configured; DLL-only probe supported')
    elif args.command == 'build':
        call([c['dotnet'], 'build', 'src/Volibear/Volibear.csproj', '-c', 'Release',
              '-p:Sts2DataDir=' + str(data)])
    elif args.command == 'deploy':
        deploy(game)
    elif args.command == 'run':
        # Steam selects its own app ID from this installation's appmanifest.
        manifests = list(game.parent.parent.glob('appmanifest_*.acf'))
        matches = [p for p in manifests if '"Slay the Spire 2"' in p.read_text()]
        if len(matches) != 1:
            raise RuntimeError('Could not uniquely resolve Steam appmanifest')
        app_id = matches[0].stem.split('_')[1]
        call(['flatpak', 'run', 'com.valvesoftware.Steam', 'steam://rungameid/' + app_id])
    elif args.command == 'logs':
        print('Inspect Godot app_userdata/Slay the Spire 2/logs under host and Steam Flatpak user data.')
        print('Successful initialization must include: [Volibear] LOAD_OK')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
