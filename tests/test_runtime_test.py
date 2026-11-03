"""Shared runtime contracts: both platform adapters, capability isolation and execution."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.runtime_platform import platform_for
from tools.runtime_test import get_runtime, fixture_runtime, RuntimeUnavailable


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.sdk = self.touch('sdk/dotnet.exe')

    def touch(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
        return path

    def runtime(self, **kwargs):
        kwargs.setdefault('settings', {'dotnet': str(self.sdk)})
        kwargs.setdefault('environ', {})
        return get_runtime(self.root, **kwargs)

    def test_windows_and_linux_paths_and_window_arguments(self):
        for key, data, executable in [('nt', 'data_sts2_windows_x86_64', 'SlayTheSpire2.exe'),
                                       ('posix', 'data_sts2_linuxbsd_x86_64', 'SlayTheSpire2')]:
            with self.subTest(platform=key):
                runtime = self.runtime(platform=key, settings={'dotnet': str(self.sdk), 'game_dir': 'game'})
                self.assertEqual(runtime.data, self.root / 'game' / data)
                self.assertEqual(runtime.platform.executable(runtime.game), self.root / 'game' / executable)
                args = runtime.platform.window_arguments()
                self.assertEqual(args[-3:], ['--windowed', '--resolution', '1280x720'])
                self.assertEqual('--display-driver' in args, key == 'posix')
        with self.assertRaises(ValueError):
            platform_for('unknown')

    def test_sdk_only_does_not_require_game_or_harmony(self):
        runtime = self.runtime()
        self.assertIs(runtime.require('sdk'), runtime)
        self.assertIsNone(runtime.game)
        for capability in ('native', 'harmony', 'baselib', 'mod', 'godot', 'game'):
            with self.subTest(capability=capability), self.assertRaises(RuntimeUnavailable):
                runtime.require(capability)
        with self.assertRaises(ValueError):
            runtime.require('made-up')

    def test_harmony_only_does_not_require_native_references(self):
        harmony = self.touch('harmony/0Harmony.dll')
        runtime = self.runtime(environ={'VOLIBEAR_HARMONY': str(harmony)})
        runtime.require('sdk', 'harmony')
        self.assertIsNone(runtime.data)
        with self.assertRaises(RuntimeUnavailable):
            runtime.require('native')

    def test_native_requires_each_real_reference(self):
        for key in ('nt', 'posix'):
            runtime = self.runtime(platform=key, settings={'game_dir': 'game'})
            for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
                with self.assertRaises(RuntimeUnavailable):
                    runtime.require('native')
                self.touch(str(runtime.data.relative_to(self.root) / name))
            runtime.require('native')
            self.assertEqual(runtime.harmony, runtime.data / '0Harmony.dll')

    def test_explicit_overrides_win_without_invalid_fallback(self):
        other = self.touch('other/dotnet.exe')
        runtime = self.runtime(environ={'VOLIBEAR_DOTNET': str(other), 'Sts2DataDir': str(self.root / 'refs'),
                                      'BaseLibPath': str(self.root / 'base.dll'),
                                      'HarmonyPath': str(self.root / 'harmony.dll'), 'ModDll': str(self.root / 'mod.dll')})
        self.assertEqual(runtime.dotnet, other)
        self.assertEqual(runtime.data, self.root / 'refs')
        self.assertEqual(runtime.baselib, self.root / 'base.dll')
        self.assertEqual(runtime.harmony, self.root / 'harmony.dll')
        self.assertEqual(runtime.mod, self.root / 'mod.dll')
        with self.assertRaises(RuntimeUnavailable):
            self.runtime(environ={'VOLIBEAR_DOTNET': str(self.root / 'absent.exe')}).require('sdk')

    def test_config_bom_and_data_directory_normalization(self):
        config = self.root / '.local/config.json'
        config.parent.mkdir()
        config.write_text(json.dumps({'dotnet': str(self.sdk), 'game_dir': 'game/data_sts2_windows_x86_64'}), encoding='utf-8-sig')
        runtime = get_runtime(self.root, platform='nt', environ={})
        self.assertEqual(runtime.game, self.root / 'game')
        self.assertEqual(runtime.dotnet, self.sdk)
        foreign = get_runtime(self.root, platform='posix', environ={})
        foreign.require('sdk')
        for capability in ('native', 'game'):
            with self.assertRaisesRegex(RuntimeUnavailable, 'other runtime platform'):
                foreign.require(capability)
        with self.assertRaises(ValueError):
            self.runtime(settings=[])

    def test_environment_is_scoped_and_preserves_existing_settings(self):
        for key, separator in [('nt', ';'), ('posix', ':')]:
            runtime = self.runtime(platform=key)
            original = {'PATH': 'existing', 'NUGET_PACKAGES': 'private-cache', 'DOTNET_CLI_HOME': 'private-home'}
            env = runtime.environment(original)
            self.assertEqual(original['PATH'], 'existing')
            self.assertEqual(env['PATH'], str(self.sdk.parent) + separator + 'existing')
            self.assertEqual(env['DOTNET_ROOT'], str(self.sdk.parent))
            self.assertEqual(env['NUGET_PACKAGES'], 'private-cache')
            self.assertEqual(env['DOTNET_CLI_HOME'], 'private-home')
            self.assertEqual(env['BaseLibPath'], str(runtime.baselib))
            self.assertEqual(env['NUGET_SCRATCH'], str(self.root / 'artifacts/runtime/nuget-scratch'))
            self.assertEqual(runtime.environment({'NUGET_SCRATCH': 'caller-owned'})['NUGET_SCRATCH'], 'caller-owned')
            self.assertNotIn('Sts2DataDir', env)
            self.assertEqual(env['TEMP'], str(self.root / 'artifacts/runtime/tmp'))
            self.assertEqual(env['TMP'], env['TEMP'])
            self.assertEqual(env['TMPDIR'], env['TEMP'])
            self.assertTrue(Path(env['TEMP']).is_dir())
            self.assertEqual(env['UseSharedCompilation'], 'false')
            self.assertEqual(env['MSBUILDDISABLENODEREUSE'], '1')
            self.assertEqual(env['DOTNET_CLI_USE_MSBUILD_SERVER'], '0')
            custom = self.root / 'custom-temp'
            self.assertEqual(runtime.environment({'VOLIBEAR_RUNTIME_TEMP': str(custom)})['TMP'], str(custom))

    def test_run_preserves_failure_and_explicit_project_options(self):
        runtime = self.runtime()
        failed = mock.Mock(returncode=1, stdout='compiler failed', stderr='details')
        with mock.patch('tools.runtime_test.subprocess.run', return_value=failed) as execute:
            self.assertIs(runtime.run('tests/project.csproj', timeout=17,
                                      artifacts='artifacts/fixture', args=('-p:Special=true',)), failed)
        command = execute.call_args.args[0]
        self.assertEqual(command[0], str(self.sdk))
        self.assertIn(str(self.root / 'tests/project.csproj'), command)
        self.assertEqual(command[-1], '-p:Special=true')
        self.assertIn('--artifacts-path', command)
        self.assertEqual(execute.call_args.kwargs['timeout'], 17)
        self.assertEqual(execute.call_args.kwargs['encoding'], 'utf-8')
        self.assertEqual(execute.call_args.kwargs['cwd'], self.root)

    def test_missing_capability_never_starts_process(self):
        with mock.patch('tools.runtime_test.subprocess.run') as execute:
            with self.assertRaises(RuntimeUnavailable):
                self.runtime().run('fixture.csproj', requirements=('native',))
        execute.assert_not_called()

    def test_optional_and_strict_unavailability_for_instance_and_class(self):
        runtime = self.runtime()
        for case in (self, type(self)):
            for strict, error in [('0', unittest.SkipTest), ('1', AssertionError)]:
                with mock.patch('tools.runtime_test.get_runtime', return_value=runtime), \
                     mock.patch.dict(os.environ, {'VOLIBEAR_REQUIRE_NATIVE': strict}), self.assertRaises(error):
                    fixture_runtime(case, 'native', root=self.root)

    def test_local_sdk_fallback_is_platform_specific_and_last_resort(self):
        for key, executable in (('nt', 'dotnet.exe'), ('posix', 'dotnet')):
            local = self.touch('.local/dotnet/' + executable)
            with self.subTest(platform=key), mock.patch('tools.runtime_test.shutil.which', return_value=None):
                runtime = self.runtime(platform=key, settings={})
                self.assertEqual(runtime.dotnet, local)
                runtime.require('sdk')
                for settings, env in (({'dotnet': 'missing-sdk'}, {}),
                                      ({}, {'VOLIBEAR_DOTNET': 'missing-sdk'})):
                    explicit = self.runtime(platform=key, settings=settings, environ=env)
                    self.assertEqual(explicit.dotnet, self.root / 'missing-sdk')
                    with self.assertRaises(RuntimeUnavailable):
                        explicit.require('sdk')
            with mock.patch('tools.runtime_test.shutil.which',
                            side_effect=lambda name, **kwargs: str(self.sdk) if name == 'dotnet' else None):
                self.assertEqual(self.runtime(platform=key, settings={}).dotnet, self.sdk)

    def test_foreign_data_is_scoped_to_native_and_explicit_data_wins(self):
        harmony = self.touch('harmony/0Harmony.dll')
        for key, other in (('nt', 'posix'), ('posix', 'nt')):
            settings = {'dotnet': str(self.sdk), 'game_dir': 'game/' + platform_for(other).data_name}
            env = {'HarmonyPath': str(harmony)}
            runtime = self.runtime(platform=key, settings=settings, environ=env)
            runtime.require('sdk', 'harmony')
            for capability in ('native', 'game'):
                with self.assertRaisesRegex(RuntimeUnavailable, 'other runtime platform'):
                    runtime.require(capability)
            refs = self.root / 'refs' / platform_for(key).data_name
            for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
                self.touch(str(refs.relative_to(self.root) / name))
            for override in ('Sts2DataDir', 'VOLIBEAR_STS2_DATA_DIR'):
                selected = self.runtime(platform=key, settings=settings, environ={**env, override: str(refs)})
                self.assertEqual(selected.data, refs)
                selected.require('sdk', 'native')

    def test_assembly_alias_capabilities_match_environment_and_command(self):
        host = self.touch('custom/host.dll')
        assembly = self.touch('custom/assembly.dll')
        runtime = self.runtime(environ={'HostAssembly': str(host), 'ModAssembly': str(assembly)})
        runtime.require('host', 'mod_assembly')
        with self.assertRaises(RuntimeUnavailable):
            runtime.require('mod')
        self.assertEqual(runtime.environment({})['HostAssembly'], str(host))
        self.assertEqual(runtime.environment({})['ModAssembly'], str(assembly))
        with mock.patch('tools.runtime_test.subprocess.run') as execute:
            runtime.run('fixture.csproj', requirements=('host', 'mod_assembly'))
        command = execute.call_args.args[0]
        self.assertIn('-p:HostAssembly=' + str(host), command)
        self.assertIn('-p:ModAssembly=' + str(assembly), command)
        default = self.runtime(environ={'ModDll': str(host)})
        default.require('mod', 'host', 'mod_assembly')
        self.assertEqual(default.host, host)
        self.assertEqual(default.mod_assembly, host)
        for attribute, capability in (('HostAssembly', 'host'), ('ModAssembly', 'mod_assembly')):
            broken = self.runtime(environ={'ModDll': str(host), attribute: 'missing.dll'})
            broken.require('mod')
            with self.assertRaises(RuntimeUnavailable):
                broken.require(capability)
        env = runtime.environment({'ProductionAssembly': 'special-fixture.dll'})
        self.assertEqual(env['ProductionAssembly'], 'special-fixture.dll')
        self.assertNotIn('ProductionAssembly', runtime.properties())

    def test_both_platform_profiles_preserve_base_and_reject_reuse(self):
        bindings = {
            'nt': {'HOME': 'home', 'APPDATA': 'appdata', 'LOCALAPPDATA': 'localappdata'},
            'posix': {'HOME': 'home', 'XDG_DATA_HOME': 'data',
                      'XDG_CONFIG_HOME': 'config', 'XDG_CACHE_HOME': 'cache'},
        }
        for key, expected in bindings.items():
            with self.subTest(platform=key):
                runtime = self.runtime(platform=key)
                profile = self.root / ('profile-' + key)
                base = {'HOME': 'ordinary-profile', 'KEEP': 'unchanged'}
                before = dict(base)
                with mock.patch.object(type(runtime), 'environment', return_value=base):
                    env = runtime.isolated_environment(profile)
                    self.assertEqual(base, before)
                    self.assertEqual(env['KEEP'], 'unchanged')
                    self.assertEqual(set(env) - {'KEEP'}, set(expected))
                    for variable, child in expected.items():
                        self.assertEqual(env[variable], str(profile / child))
                        self.assertTrue((profile / child).is_dir())
                    marker = profile / 'home' / 'existing-save'
                    marker.write_text('preserve')
                    with self.assertRaises(FileExistsError):
                        runtime.isolated_environment(profile)
                    self.assertEqual(marker.read_text(), 'preserve')

    def test_game_version_is_checked_separately_from_reference_capability(self):
        runtime = self.runtime(platform='nt', settings={'game_dir': 'game'})
        self.touch('game/SlayTheSpire2.exe')
        release = self.touch('game/release_info.json')
        release.write_text(json.dumps({'version': 'wrong', 'commit': '59260271'}))
        with self.assertRaises(RuntimeUnavailable):
            runtime.require('game')
        release.write_text(json.dumps({'version': 'v0.107.1', 'commit': '59260271'}))
        runtime.require('game')
