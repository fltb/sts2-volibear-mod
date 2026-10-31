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
GAME_VERSION = 'v0.107.1'
GAME_COMMIT = '59260271'
DEPLOY_MARKERS = ROOT / '.local/deploy'
SOURCES = [ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll',
           ROOT / 'src/Volibear/Volibear.json']
DATA_DIRECTORIES = {'nt': 'data_sts2_windows_x86_64', 'posix': 'data_sts2_linuxbsd_x86_64'}
GAME_EXECUTABLES = {'nt': 'SlayTheSpire2.exe', 'posix': 'SlayTheSpire2'}


def config():
    path = ROOT / '.local/config.json'
    if not path.is_file():
        raise RuntimeError('Create .local/config.json with game_dir and dotnet paths.')
    return json.loads(path.read_text())


def data_directory(game):
    if os.name not in DATA_DIRECTORIES:
        raise RuntimeError('Unsupported platform for the game assemblies: ' + os.name)
    return game / DATA_DIRECTORIES[os.name]


def game_executable(game):
    if os.name not in GAME_EXECUTABLES:
        raise RuntimeError('Unsupported platform for the game executable: ' + os.name)
    return game / GAME_EXECUTABLES[os.name]


def validate_game(game):
    info = json.loads((game / 'release_info.json').read_text())
    if (info.get('version'), info.get('commit')) != (GAME_VERSION, GAME_COMMIT):
        raise RuntimeError('Game version mismatch; deployment refused: ' + str(info))
    data = data_directory(game)
    for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
        if not (data / name).is_file():
            raise RuntimeError('Missing game assembly: ' + name)
    if not game_executable(game).is_file():
        raise RuntimeError('Missing game executable: ' + game_executable(game).name)
    return data


def call(args):
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1')
    subprocess.run([str(x) for x in args], cwd=ROOT, env=env, check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ownership_marker():
    # Outside the mod directory: the game scans every JSON file it finds there as a manifest.
    return DEPLOY_MARKERS / (MOD + '.json')


def deployment_record(target):
    """Ownership evidence for this installation, migrating a marker from the old layout."""
    marker = ownership_marker()
    if marker.is_file():
        record = json.loads(marker.read_text())
        if isinstance(record, dict) and record.get('target') == str(target):
            return record
    legacy = target / '.volibear-dev-owned.json'
    if legacy.is_file():
        try:
            hashes = json.loads(legacy.read_text())
        except ValueError:
            return None
        if (isinstance(hashes, dict) and hashes
                and all((target / name).is_file() and digest(target / name) == sha
                        for name, sha in hashes.items())):
            return {'target': str(target), 'files': hashes}
    return None


def deploy(game, sources=None):
    target = game / 'mods' / MOD
    expected = game.resolve() / 'mods' / MOD
    if target.is_symlink() or target.resolve() != expected:
        raise RuntimeError('Unexpected deployment target')
    sources = SOURCES if sources is None else sources
    record = deployment_record(expected)
    if target.exists() and record is None and any(target.iterdir()):
        raise RuntimeError('Existing unowned mod directory; refusing overwrite')
    old = record['files'] if record else {}
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
    legacy = target / '.volibear-dev-owned.json'
    if legacy.is_file():
        legacy.unlink()
    marker = ownership_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({'target': str(expected),
                                 'files': {p.name: digest(p) for p in sources}}, indent=2) + '\n')
    print('Deployed owned files only:', target)


def steam_app_id(game):
    """Steam selects its own app ID from this installation's appmanifest."""
    manifests = list(game.parent.parent.glob('appmanifest_*.acf'))
    matches = [p for p in manifests if '"Slay the Spire 2"' in p.read_text()]
    if len(matches) != 1:
        raise RuntimeError('Could not uniquely resolve Steam appmanifest')
    return matches[0].stem.split('_')[1]


def undeploy(game):
    target = game / 'mods' / MOD
    expected = game.resolve() / 'mods' / MOD
    if target.is_symlink() or target.resolve() != expected:
        raise RuntimeError('Unexpected deployment target')
    record = deployment_record(expected)
    if record is None:
        raise RuntimeError('No owned deployment to remove: ' + str(target))
    for name, sha in record['files'].items():
        p = target / name
        if p.is_file() and digest(p) != sha:
            raise RuntimeError('Deployed file changed; refusing to remove: ' + name)
    for name in [*record['files'], '.volibear-dev-owned.json']:
        p = target / name
        if p.is_file():
            p.unlink()
    if target.is_dir() and not any(target.iterdir()):
        target.rmdir()
    marker = ownership_marker()
    if marker.is_file():
        marker.unlink()
    print('Removed owned files only:', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'build', 'test', 'deploy', 'undeploy',
                                            'run', 'logs'])
    args = parser.parse_args()
    if args.command == 'test':
        call([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        return
    c = config()
    game = Path(c['game_dir']).expanduser().resolve()
    data = validate_game(game)
    if args.command == 'doctor':
        call([c['dotnet'], '--version'])
        print('Game %s / %s and managed references: OK' % (GAME_VERSION, GAME_COMMIT))
        print('Platform:', os.name, 'executable:', game_executable(game).name)
        print('PCK/Godot and RitsuLib: not yet configured; DLL-only probe supported')
    elif args.command == 'build':
        call([c['dotnet'], 'build', 'src/Volibear/Volibear.csproj', '-c', 'Release',
              '-p:Sts2DataDir=' + str(data)])
    elif args.command == 'deploy':
        deploy(game)
    elif args.command == 'undeploy':
        undeploy(game)
    elif args.command == 'run':
        app_id = steam_app_id(game)
        if os.name == 'nt':
            # The steam:// handler resolves the installation through the appmanifest.
            os.startfile('steam://rungameid/' + app_id)
        else:
            call(['flatpak', 'run', 'com.valvesoftware.Steam', 'steam://rungameid/' + app_id])
    elif args.command == 'logs':
        print('Inspect app_userdata/Slay the Spire 2/logs under the host and Steam user data.')
        print('Windows: %APPDATA%\\SlayTheSpire2; Linux: $XDG_DATA_HOME/SlayTheSpire2')
        print('Successful initialization must include: [Volibear] LOAD_OK')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
