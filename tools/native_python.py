"""Keep native process ancestry on the host Python; borrow only verified venv libraries."""
import json
import os
from pathlib import Path
import subprocess
import sys


IDENTITY = '''import json, struct, sys, sysconfig
print(json.dumps(dict(prefix=sys.prefix, base_prefix=sys.base_prefix,
    base_executable=getattr(sys, "_base_executable", sys.executable),
    version=sys.version, implementation=sys.implementation.name,
    cache_tag=sys.implementation.cache_tag, soabi=sysconfig.get_config_var("SOABI"),
    bits=struct.calcsize("P") * 8, purelib=sysconfig.get_path("purelib"),
    platlib=sysconfig.get_path("platlib"))))'''


def lexical_path(value):
    # Resolving a POSIX venv's bin/python symlink loses its environment identity.
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def _probe(executable, code, env, *, isolated=False):
    command = [str(executable), *(['-I'] if isolated else []), '-c', code]
    result = subprocess.run(command, env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=30, check=False)
    if result.returncode:
        raise ValueError('Native Python probe failed: ' + str(executable) + '\n' + result.stderr)
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid native Python probe result: ' + str(executable)) from error
    if not isinstance(value, dict):
        raise ValueError('Native Python probe must return an object')
    return value


def _inside(path, directory):
    return (path.is_relative_to(directory) and
            path.resolve().is_relative_to(directory.resolve()))


def native_runtime(checks_python, env, *, modules=('PIL.Image',)):
    """Return (host executable, copied environment); never install or launch a game.

    The check interpreter may be a venv symlink. Only its libraries cross this
    boundary, after matching the host's full Python build and underlying runtime.
    """
    host = lexical_path(sys.executable if sys.prefix == sys.base_prefix else sys._base_executable)
    checks = lexical_path(checks_python)
    child_env = dict(env)
    host_info = _probe(host, IDENTITY, env, isolated=True)
    if lexical_path(host_info['prefix']) != lexical_path(host_info['base_prefix']):
        raise ValueError('Native Python must be the original non-venv host interpreter')
    libraries = []
    if checks != host:
        check_info = _probe(checks, IDENTITY, env, isolated=True)
        for key in ('version', 'implementation', 'cache_tag', 'soabi', 'bits'):
            if check_info[key] != host_info[key]:
                raise ValueError('Check Python ABI mismatch: ' + key)
        for key in ('base_prefix', 'base_executable'):
            if Path(check_info[key]).resolve() != Path(host_info[key]).resolve():
                raise ValueError('Check Python host mismatch: ' + key)
        prefix = lexical_path(check_info['prefix'])
        if prefix != checks.parent.parent or prefix == lexical_path(check_info['base_prefix']):
            raise ValueError('Check Python is not the expected isolated venv')
        for key in ('purelib', 'platlib'):
            library = lexical_path(check_info[key])
            if not library.is_dir() or not _inside(library, prefix):
                raise ValueError('Check Python dependency path escapes its venv: ' + key)
            if library not in libraries:
                libraries.append(library)
        paths = [str(path) for path in libraries]
        if child_env.get('PYTHONPATH'):
            paths.append(child_env['PYTHONPATH'])
        child_env['PYTHONPATH'] = os.pathsep.join(paths)
    # Import extensions with precisely the executable/environment used by runners.
    # find_spec in this parent would not observe the child-only PYTHONPATH.
    code = ('import importlib, json\nmodules = ' + repr(tuple(modules)) + '\n'
            'print(json.dumps({name: importlib.import_module(name).__file__ for name in modules}))')
    loaded = _probe(host, code, child_env)
    if set(loaded) != set(modules):
        raise ValueError('Native Python dependency probe omitted requested modules')
    for name, filename in loaded.items():
        if not filename or not Path(filename).is_file():
            raise ValueError('Native Python dependency has no file: ' + name)
        if libraries and not any(_inside(lexical_path(filename), path) for path in libraries):
            raise ValueError('Native Python imported dependency outside the verified venv: ' + name)
    return host, child_env
