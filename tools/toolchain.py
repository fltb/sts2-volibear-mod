"""Pinned local tool checks shared by the resource builder and delivery entrypoint."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GODOT_VERSION = '4.5.1.stable.mono.'


def executable(value, label):
    if not value:
        raise ValueError(f'Missing {label} executable; supply its path or configure .local/config.json')
    candidate = Path(str(value)).expanduser()
    resolved = candidate.resolve() if candidate.is_file() else None
    if resolved is None:
        found = shutil.which(str(value))
        resolved = Path(found).resolve() if found else None
    if resolved is None or not resolved.is_file():
        raise ValueError(f'{label} executable does not exist: {value}')
    return resolved


def dotnet_environment(dotnet, base=None):
    env = dict(os.environ if base is None else base)
    directory = str(Path(dotnet).resolve().parent)
    env.update(DOTNET_ROOT=directory, DOTNET_CLI_TELEMETRY_OPTOUT='1',
               DOTNET_NOLOGO='1', VOLIBEAR_DOTNET=str(dotnet), PYTHONUTF8='1')
    env['PATH'] = directory + os.pathsep + env.get('PATH', '')
    return env


def version(command, env):
    result = subprocess.run([str(value) for value in command], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', timeout=60)
    if result.returncode:
        raise ValueError('Tool version check failed: ' + str(command[0]) + '\n' + result.stdout[-3000:])
    return result.stdout.strip()


def check(dotnet, godot):
    dotnet = executable(dotnet, '.NET')
    godot = executable(godot, 'Godot Mono')
    env = dotnet_environment(dotnet)
    pin = json.loads((ROOT / 'global.json').read_text(encoding='utf-8'))['sdk']['version']
    actual_sdk = version([dotnet, '--version'], env)
    if actual_sdk != pin or not actual_sdk.startswith('9.'):
        raise ValueError(f'Requires .NET SDK {pin} selected by global.json; found {actual_sdk}')
    actual_godot = version([godot, '--version'], env)
    if not actual_godot.startswith(GODOT_VERSION):
        raise ValueError(f'Requires ordinary Godot 4.5.1 stable Mono; found {actual_godot}')
    return {'dotnet': str(dotnet), 'godot': str(godot),
            'dotnet_version': actual_sdk, 'godot_version': actual_godot}


def validate_pack_header(path):
    with Path(path).open('rb') as stream:
        header = stream.read(20)
    if len(header) != 20 or struct.unpack('<4s4I', header) != (b'GDPC', 3, 4, 5, 1):
        raise ValueError('Expected Godot 4.5.1 PCK format 3 header: ' + str(path))
