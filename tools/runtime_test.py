"""Capability-scoped runtime for shared fixtures on Windows and Linux.

SDK-only and Harmony-only fixtures do not acquire a game dependency. Resolution
never installs software, rewrites config, launches the game or weakens an oracle.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from tools.runtime_platform import PLATFORMS, RuntimePlatform, platform_for

ROOT = Path(__file__).resolve().parents[1]


class RuntimeUnavailable(RuntimeError):
    pass


def _path(value, root):
    if not value:
        return None
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _executable(value, root, env, fallback):
    value = value or shutil.which(fallback, path=env.get('PATH', ''))
    if not value:
        return None
    local = _path(value, root)
    if local.is_file():
        return local
    found = shutil.which(str(value), path=env.get('PATH', ''))
    # Explicit invalid configuration is preserved for a useful failure, not silently replaced.
    return Path(found).resolve() if found else local


@dataclass(frozen=True)
class RuntimeTestEnvironment:
    root: Path
    platform: RuntimePlatform
    dotnet: Path | None
    game: Path | None
    data: Path | None
    baselib: Path
    harmony: Path | None
    mod: Path
    godot: Path | None
    host: Path
    mod_assembly: Path

    def require(self, *capabilities):
        paths = {
            'sdk': [self.dotnet], 'harmony': [self.harmony], 'baselib': [self.baselib],
            'mod': [self.mod], 'host': [self.host], 'mod_assembly': [self.mod_assembly],
            'godot': [self.godot],
            'native': [self.data / name if self.data else None
                       for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll')],
            'game': [self.platform.executable(self.game) if self.game else None,
                     self.game / 'release_info.json' if self.game else None],
        }
        for capability in capabilities:
            if capability not in paths:
                raise ValueError('Unknown runtime capability: ' + capability)
            if (capability in ('native', 'game') and self.data
                    and self.data.name in {p.data_name for p in PLATFORMS.values()}
                    and self.data.name != self.platform.data_name):
                raise RuntimeUnavailable('Configured game data directory belongs to the other runtime platform')
            missing = [str(p) if p else '<not configured>' for p in paths[capability]
                       if p is None or not p.is_file()]
            if missing:
                raise RuntimeUnavailable(f'{capability} runtime unavailable: ' + ', '.join(missing))
            if capability == 'game':
                info = json.loads((self.game / 'release_info.json').read_text(encoding='utf-8-sig'))
                if (info.get('version'), info.get('commit')) != ('v0.107.1', '59260271'):
                    raise RuntimeUnavailable('Game runtime must be StS2 v0.107.1 / 59260271')
        return self

    def properties(self):
        return {name: str(value) for name, value in {
            'Sts2DataDir': self.data, 'BaseLibPath': self.baselib,
            'HarmonyPath': self.harmony, 'ModDll': self.mod,
            'HostAssembly': self.host, 'ModAssembly': self.mod_assembly,
        }.items() if value is not None}

    def environment(self, base=None):
        env = dict(os.environ if base is None else base)
        env.update(self.properties())
        env.update(DOTNET_NOLOGO='1', DOTNET_CLI_TELEMETRY_OPTOUT='1', PYTHONUTF8='1')
        # Test processes must not contend with a different launch identity's global
        # NuGet temporary locks. Preserve an explicit caller-owned scratch location.
        env.setdefault('NUGET_SCRATCH', str(self.root / 'artifacts/runtime/nuget-scratch'))
        temporary = _path(env.get('VOLIBEAR_RUNTIME_TEMP'), self.root) or self.root / 'artifacts/runtime/tmp'
        temporary.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        # Do not reuse compiler/MSBuild servers started by another test launcher.
        env.setdefault('UseSharedCompilation', 'false')
        env.setdefault('MSBUILDDISABLENODEREUSE', '1')
        env.setdefault('DOTNET_CLI_USE_MSBUILD_SERVER', '0')
        if self.dotnet:
            env.update(DOTNET_ROOT=str(self.dotnet.parent), VOLIBEAR_DOTNET=str(self.dotnet))
            env['PATH'] = str(self.dotnet.parent) + self.platform.path_separator + env.get('PATH', '')
        if self.harmony:
            env['VOLIBEAR_HARMONY'] = str(self.harmony)
        return env

    def isolated_environment(self, directory):
        return self.platform.isolated_environment(directory, self.environment())

    def run(self, project, *, requirements=(), args=(), timeout=180,
            configuration='Release', artifacts=None):
        self.require('sdk', *requirements)
        project = _path(project, self.root)
        command = [str(self.dotnet), 'run', '--project', str(project), '-c', configuration]
        command += ['-p:' + name + '=' + value for name, value in self.properties().items()]
        if artifacts is not None:
            command += ['--artifacts-path', str(_path(artifacts, self.root))]
        command += [str(arg) for arg in args]
        return subprocess.run(command, cwd=self.root, env=self.environment(),
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)


def get_runtime(root=ROOT, *, settings=None, environ=None, platform=None):
    root = Path(root).resolve()
    env = os.environ if environ is None else environ
    adapter = platform_for(platform)
    if settings is None:
        config = root / '.local/config.json'
        settings = json.loads(config.read_text(encoding='utf-8-sig')) if config.is_file() else {}
    if not isinstance(settings, dict):
        raise ValueError('Runtime configuration must be a JSON object')
    configured_dotnet = env.get('VOLIBEAR_DOTNET') or settings.get('dotnet')
    dotnet = _executable(configured_dotnet, root, env, 'dotnet')
    if not configured_dotnet and dotnet is None:
        local_sdk = root / '.local/dotnet' / ('dotnet.exe' if adapter.key == 'nt' else 'dotnet')
        if local_sdk.is_file():
            dotnet = local_sdk.resolve()
    godot = _executable(env.get('VOLIBEAR_GODOT') or settings.get('godot'), root, env, 'godot')
    game = _path(env.get('VOLIBEAR_GAME_DIR') or settings.get('game_dir'), root)
    # Accept a configured managed-data directory as well as the normal install root.
    configured_data = None
    if game and game.name in {p.data_name for p in PLATFORMS.values()}:
        configured_data = game
        game = game.parent
    data = _path(env.get('Sts2DataDir') or env.get('VOLIBEAR_STS2_DATA_DIR'), root)
    data = data or configured_data or (adapter.data_directory(game) if game else None)
    baselib = _path(env.get('BaseLibPath') or settings.get('baselib'), root)
    dependency_version = '3.4.8' if env.get('VOLIBEAR_CHANNEL') == 'pbe' else '3.4.7'
    baselib = baselib or root / '.local/dependencies' / f'BaseLib-{dependency_version}' / 'BaseLib.dll'
    harmony = _path(env.get('HarmonyPath') or env.get('VOLIBEAR_HARMONY'), root)
    if harmony is None:
        cached = root / '.local/dependencies/Harmony-2.4.2/0Harmony.dll'
        harmony = cached if cached.is_file() else data / '0Harmony.dll' if data else cached
    mod = _path(env.get('ModDll'), root) or root / 'src/Volibear/bin/Release/net9.0/Volibear.dll'
    host = _path(env.get('HostAssembly'), root) or mod
    mod_assembly = _path(env.get('ModAssembly'), root) or mod
    return RuntimeTestEnvironment(root, adapter, dotnet, game, data, baselib, harmony, mod, godot,
                                  host, mod_assembly)


def fixture_runtime(test_case, *requirements, root=ROOT):
    runtime = get_runtime(root)
    try:
        runtime.require(*requirements)
    except RuntimeUnavailable as error:
        if os.environ.get('VOLIBEAR_REQUIRE_NATIVE') == '1':
            raise AssertionError(str(error)) from error
        else:
            raise unittest.SkipTest(str(error)) from error
    return runtime
