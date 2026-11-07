#!/usr/bin/env python3
"""Local development commands. Never distributes game assemblies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .runtime_platform import PLATFORMS, platform_for
except ImportError:
    from runtime_platform import PLATFORMS, platform_for

ROOT = Path(__file__).resolve().parents[1]
MOD = 'Volibear'
GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')
DEPLOY_MARKERS = ROOT / '.local/deploy'
SOURCES = [ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll',
           ROOT / 'src/Volibear/Volibear.json']
DATA_DIRECTORIES = {key: adapter.data_name for key, adapter in PLATFORMS.items()}
GAME_EXECUTABLES = {key: adapter.executable_name for key, adapter in PLATFORMS.items()}


def config():
    path = ROOT / '.local/config.json'
    if not path.is_file():
        raise RuntimeError('Run python tools/local_delivery.py --game-dir GAME --godot GODOT --dotnet DOTNET first.')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def data_directory(game):
    if os.name not in DATA_DIRECTORIES:
        raise RuntimeError('Unsupported platform for the game assemblies: ' + os.name)
    return platform_for().data_directory(game)


def game_executable(game):
    if os.name not in GAME_EXECUTABLES:
        raise RuntimeError('Unsupported platform for the game executable: ' + os.name)
    return platform_for().executable(game)


def validate_game(game):
    release = game / 'release_info.json'
    if not release.is_file():
        raise RuntimeError('Missing installed-game release_info.json: ' + str(game))
    info = json.loads(release.read_text(encoding='utf-8-sig'))
    if (info.get('version'), info.get('commit')) != (GAME_VERSION, GAME_COMMIT):
        raise RuntimeError('Game version mismatch; deployment refused: ' + str(info))
    data = data_directory(game)
    for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
        if not (data / name).is_file():
            raise RuntimeError('Missing game assembly: ' + name)
    if not game_executable(game).is_file():
        raise RuntimeError('Missing game executable: ' + game_executable(game).name)
    return data


def call(args, *, env=None):
    env = dict(os.environ if env is None else env, DOTNET_CLI_TELEMETRY_OPTOUT='1')
    subprocess.run([str(x) for x in args], cwd=ROOT, env=env, check=True)


def build_mod(settings, *, fresh=False):
    try:
        from . import toolchain
    except ImportError:
        import toolchain
    game = Path(settings['game_dir']).expanduser().resolve()
    data = validate_game(game)
    sdk = toolchain.executable(settings['dotnet'], '.NET')
    project = ROOT / 'src/Volibear/Volibear.csproj'
    assets = ROOT / 'src/Volibear/obj/project.assets.json'
    command = [sdk, 'build', project, '-c', 'Release', '-p:Sts2DataDir=' + str(data)]
    if fresh:
        # Delivery compiles every current source before tests inspect the resulting DLL.
        command.append('--no-incremental')
    elif assets.is_file() and assets.stat().st_mtime >= project.stat().st_mtime:
        command.append('--no-restore')
    call(command, env=toolchain.dotnet_environment(sdk))
    return ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ownership_marker():
    # Outside the mod directory: the game scans every JSON file it finds there as a manifest.
    return DEPLOY_MARKERS / (MOD + '.json')


def owned_file(target, name):
    if name not in (MOD + '.dll', MOD + '.json', MOD + '.pck'):
        raise RuntimeError('Unexpected owned file name: ' + str(name))
    path = target / name
    if path.is_symlink() or is_junction(path) or path.resolve() != target.resolve() / name:
        raise RuntimeError('Unexpected owned file target: ' + name)
    return path


def deployment_record(target):
    """Ownership evidence for this installation, migrating a marker from the old layout."""
    marker = ownership_marker()
    if marker.is_file():
        record = json.loads(marker.read_text())
        if isinstance(record, dict) and record.get('target') == str(target):
            if not isinstance(record.get('files'), dict) or not record['files']:
                raise RuntimeError('Invalid deployment ownership record')
            return record
    legacy = target / '.volibear-dev-owned.json'
    if legacy.is_file():
        try:
            hashes = json.loads(legacy.read_text())
        except ValueError:
            return None
        if (isinstance(hashes, dict) and hashes
                and all(owned_file(target, name).is_file() and digest(target / name) == sha
                        for name, sha in hashes.items())):
            return {'target': str(target), 'files': hashes}
    return None


def deploy(game, sources=None):
    target = game / 'mods' / MOD
    expected = game.resolve() / 'mods' / MOD
    if target.is_symlink() or target.resolve() != expected:
        raise RuntimeError('Unexpected deployment target')
    production = sources is None
    sources = list(SOURCES if sources is None else sources)
    record = deployment_record(expected)
    if target.exists() and record is None and any(target.iterdir()):
        raise RuntimeError('Existing unowned mod directory; refusing overwrite')
    old = record['files'] if record else {}
    for name, sha in old.items():
        p = owned_file(target, name)
        if p.exists() and (not p.is_file() or digest(p) != sha):
            raise RuntimeError('Previously deployed file changed: ' + name)
    for src in sources:
        if not src.is_file():
            raise RuntimeError('Build first: ' + str(src))
    payload = {src.name: src for src in sources}
    manifest = json.loads(payload[MOD + '.json'].read_text(encoding='utf-8'))
    if production:
        pack = ROOT / '.local/packs/Volibear.pck'
        if pack.is_file():
            payload[MOD + '.pck'] = pack
    if manifest.get('has_pck') and MOD + '.pck' not in payload:
        raise RuntimeError('Manifest declares has_pck but required Volibear.pck is missing; build pack first')
    for name in payload:
        p = target / name
        if p.is_symlink() or is_junction(p) or (os.path.lexists(p) and name not in old):
            raise RuntimeError('Refusing to overwrite unowned deployment file: ' + name)
    # Preflight before writing files, including migration of the old development junction.
    validate_assets_junction(target, record)
    target.mkdir(parents=True, exist_ok=True)
    unlink_assets(target, record)
    for name, src in payload.items():
        (target / name).write_bytes(src.read_bytes())
    legacy = target / '.volibear-dev-owned.json'
    if legacy.is_file():
        legacy.unlink()
    marker = ownership_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({'target': str(expected),
                                 'files': {name: digest(p) for name, p in payload.items()}}, indent=2) + '\n')
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
        p = owned_file(target, name)
        if p.exists() and (not p.is_file() or digest(p) != sha):
            raise RuntimeError('Deployed file changed; refusing to remove: ' + name)
    validate_assets_junction(target, record)
    unlink_assets(target, record)
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


def is_junction(path):
    return hasattr(os.path, 'isjunction') and os.path.isjunction(path)


def validate_assets_junction(target, record):
    """Recognize only the old owned Windows junction, never an arbitrary assets entry."""
    link = target / 'assets'
    if not os.path.lexists(link):
        return False
    if (not record or record.get('target') != str(target.resolve())
            or not is_junction(link) or link.is_symlink()
            or link.resolve(strict=True) != (ROOT / 'assets').resolve(strict=True)):
        raise RuntimeError('Unowned assets entry; refusing to remove: ' + str(link))
    return True


def unlink_assets(target, record=None):
    # Revalidate immediately before removal. rmdir removes the junction itself, never its tree.
    if validate_assets_junction(target, record):
        os.rmdir(target / 'assets')


def doctor_resources(game, settings):
    pack = ROOT / '.local/packs/Volibear.pck'
    manifest = json.loads((ROOT / 'src/Volibear/Volibear.json').read_text(encoding='utf-8'))
    print('PCK:', 'present' if pack.is_file() else 'MISSING',
          '(required)' if manifest.get('has_pck') else '(not declared)', pack)
    godot = settings.get('godot')
    print('Godot resource builder:',
          ('configured executable present' if Path(godot).is_file() else 'configured executable MISSING')
          if godot else 'no explicit godot path configured',
          '; required 4.5.1; resource export/load not verified by file presence')
    dependency = game / 'mods/BaseLib'
    metadata = dependency / 'BaseLib.json'
    if metadata.is_file():
        info = json.loads(metadata.read_text(encoding='utf-8-sig'))
        print('BaseLib installed manifest:', info.get('version', 'version absent'),
              '; id:', info.get('id', 'id absent'))
        print('BaseLib DLL:', 'present' if (dependency / 'BaseLib.dll').is_file() else 'MISSING')
        if info.get('has_pck'):
            print('BaseLib PCK:', 'present' if (dependency / 'BaseLib.pck').is_file() else 'MISSING')
    else:
        print('BaseLib installed manifest: MISSING')
    print('BaseLib candidate pin: 3.4.7; compatibility/load with StS2 0.107.1 / 59260271 '
          'not verified by file presence')


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
        try:
            from . import toolchain
        except ImportError:
            import toolchain
        checked = toolchain.check(c['dotnet'], c.get('godot'))
        print('.NET SDK:', checked['dotnet_version'], '; Godot Mono:', checked['godot_version'])
        print('Game %s / %s and managed references: OK' % (GAME_VERSION, GAME_COMMIT))
        print('Platform:', os.name, 'executable:', game_executable(game).name)
        doctor_resources(game, c)
    elif args.command == 'build':
        build_mod(c)
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
