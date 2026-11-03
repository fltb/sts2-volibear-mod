"""Native Python ancestry/ABI contracts; probes mocked, no game or package installs."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import native_python as bridge


class NativePythonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.host_root = self.root / 'host Python'
        self.host = self.host_root / 'python'
        self.prefix = self.root / 'isolated checks'
        self.checks = self.prefix / 'bin/python'
        self.purelib = self.prefix / 'lib/python3.12/site-packages'
        self.platlib = self.prefix / 'lib64/python3.12/site-packages'
        for path in (self.host, self.checks, self.purelib / 'PIL/Image.py', self.platlib / 'numpy/__init__.py'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture', encoding='utf-8')
        self.host_info = dict(prefix=str(self.host_root), base_prefix=str(self.host_root),
            base_executable=str(self.host), version='3.12.10 fixture build', implementation='cpython',
            cache_tag='cpython-312', soabi='cpython-312-platform', bits=64,
            purelib=str(self.host_root / 'site-packages'), platlib=str(self.host_root / 'site-packages'))
        self.check_info = dict(self.host_info, prefix=str(self.prefix),
                              purelib=str(self.purelib), platlib=str(self.platlib))
        self.loaded = {'PIL.Image': str(self.purelib / 'PIL/Image.py')}
        self.env = {'PATH': 'original PATH', 'PYTHONPATH': 'existing paths',
                    'HTTPS_PROXY': 'proxy', 'DOTNET_ROOT': 'sdk root'}
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(bridge.sys, 'executable', str(self.host)))
        stack.enter_context(patch.object(bridge.sys, 'prefix', str(self.host_root)))
        stack.enter_context(patch.object(bridge.sys, 'base_prefix', str(self.host_root)))
        stack.enter_context(patch.object(bridge.sys, '_base_executable', str(self.host)))

    def invoke(self, *, info=None, loaded=None, checks=None, modules=('PIL.Image',)):
        responses = [self.host_info]
        if checks != self.host:
            responses.append(self.check_info if info is None else info)
        responses.append(self.loaded if loaded is None else loaded)
        with patch.object(bridge, '_probe', side_effect=responses) as probe:
            result = bridge.native_runtime(self.checks if checks is None else checks, self.env, modules=modules)
        return result, probe

    def test_verified_venv_libraries_use_host_and_preserve_environment(self):
        before = dict(self.env)
        (host, env), probe = self.invoke()
        self.assertEqual(host, self.host)
        self.assertEqual(self.env, before)
        self.assertEqual(env['PYTHONPATH'], os.pathsep.join((str(self.purelib), str(self.platlib), 'existing paths')))
        for key in ('PATH', 'HTTPS_PROXY', 'DOTNET_ROOT'):
            self.assertEqual(env[key], before[key])
        self.assertEqual([call.args[0] for call in probe.call_args_list], [self.host, self.checks, self.host])
        self.assertTrue(probe.call_args_list[0].kwargs['isolated'])
        self.assertTrue(probe.call_args_list[1].kwargs['isolated'])
        self.assertEqual(probe.call_args_list[2].args[2], env)
        self.assertIn('importlib.import_module', probe.call_args_list[2].args[1])

    def test_host_with_dependencies_needs_no_venv_or_path_changes(self):
        (host, env), probe = self.invoke(checks=self.host)
        self.assertEqual(host, self.host)
        self.assertEqual(env, self.env)
        self.assertEqual(probe.call_count, 2)

    def test_venv_entry_recovers_its_original_base_executable(self):
        with patch.object(bridge.sys, 'executable', str(self.checks)), \
             patch.object(bridge.sys, 'prefix', str(self.prefix)):
            (host, _), _probe = self.invoke()
        self.assertEqual(host, self.host)

    def test_posix_symlink_resolution_does_not_collapse_venv_identity(self):
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            return self.host if path == self.checks else original(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve):
            (host, env), probe = self.invoke()
        self.assertEqual(host, self.host)
        self.assertEqual(probe.call_args_list[1].args[0], self.checks)
        self.assertIn(str(self.purelib), env['PYTHONPATH'])

    def test_each_build_or_base_identity_mismatch_is_rejected(self):
        for key in ('version', 'implementation', 'cache_tag', 'soabi', 'bits', 'base_prefix', 'base_executable'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'mismatch'):
                self.invoke(info=dict(self.check_info, **{key: 'different'}))

    def test_wrong_venv_prefix_and_escaped_library_are_rejected(self):
        for key, value in (('prefix', str(self.root)), ('purelib', str(self.host_root)),
                           ('platlib', str(self.root / 'missing'))):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'venv'):
                self.invoke(info=dict(self.check_info, **{key: value}))

    def test_redirected_library_outside_venv_is_rejected(self):
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            return self.host_root if path == self.purelib else original(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve), self.assertRaisesRegex(ValueError, 'escapes'):
            self.invoke()

    def test_identical_library_directories_are_not_duplicated(self):
        (_, env), _probe = self.invoke(info=dict(self.check_info, platlib=str(self.purelib)))
        self.assertEqual(env['PYTHONPATH'], os.pathsep.join((str(self.purelib), 'existing paths')))

    def test_missing_or_foreign_module_origins_are_rejected(self):
        for loaded in ({}, {'PIL.Image': None}, {'PIL.Image': str(self.host)},
                       {'PIL.Image': str(self.root / 'absent.py')}):
            with self.subTest(loaded=loaded), self.assertRaises(ValueError):
                self.invoke(loaded=loaded)

    def test_optional_numpy_uses_platform_library(self):
        loaded = dict(self.loaded, numpy=str(self.platlib / 'numpy/__init__.py'))
        (_host, _env), probe = self.invoke(loaded=loaded, modules=('PIL.Image', 'numpy'))
        self.assertIn("'numpy'", probe.call_args.args[1])

    def test_probe_failure_or_invalid_output_is_not_accepted(self):
        for result in (subprocess.CompletedProcess([], 1, '', 'extension load failed'),
                       subprocess.CompletedProcess([], 0, 'not json', ''),
                       subprocess.CompletedProcess([], 0, '[]', '')):
            with self.subTest(result=result), patch.object(bridge.subprocess, 'run', return_value=result), \
                 self.assertRaises(ValueError):
                bridge._probe(self.host, 'code', self.env)
        result = subprocess.CompletedProcess([], 0, json.dumps({'ok': True}), '')
        with patch.object(bridge.subprocess, 'run', return_value=result) as run:
            self.assertEqual(bridge._probe(self.checks, 'code', self.env, isolated=True), {'ok': True})
        self.assertEqual(run.call_args.args[0], [str(self.checks), '-I', '-c', 'code'])
        self.assertEqual(run.call_args.kwargs['timeout'], 30)


if __name__ == '__main__':
    unittest.main()
