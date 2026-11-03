"""Windows/Linux host differences; scenario logic and result oracles stay shared."""
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class RuntimePlatform:
    key: str
    data_name: str
    executable_name: str
    path_separator: str

    def data_directory(self, game):
        return Path(game) / self.data_name

    def executable(self, game):
        return Path(game) / self.executable_name

    def isolation_bindings(self):
        if self.key == 'nt':
            return [('HOME', 'home'), ('APPDATA', 'appdata'), ('LOCALAPPDATA', 'localappdata')]
        return [('HOME', 'home'), ('XDG_DATA_HOME', 'data'),
                ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache')]

    def isolated_environment(self, directory, base):
        env = dict(base)
        for key, child in self.isolation_bindings():
            path = Path(directory) / child
            path.mkdir(parents=True)
            env[key] = str(path)
        return env

    def window_arguments(self):
        return ['--windowed', '--resolution', '1280x720']


class WindowsRuntime(RuntimePlatform):
    def __init__(self):
        super().__init__('nt', 'data_sts2_windows_x86_64', 'SlayTheSpire2.exe', ';')


class LinuxRuntime(RuntimePlatform):
    def __init__(self):
        super().__init__('posix', 'data_sts2_linuxbsd_x86_64', 'SlayTheSpire2', ':')

    def window_arguments(self):
        return ['--display-driver', 'x11', '--rendering-method', 'gl_compatibility',
                *super().window_arguments()]


PLATFORMS = {'nt': WindowsRuntime(), 'posix': LinuxRuntime()}


def create_directory_redirect(link, target):
    """Create a real test-directory redirect without Windows symlink privileges.

    Callers own both temporary paths and their cleanup. This creates a junction on
    Windows and a directory symlink on POSIX; it does not emulate file symlinks.
    """
    link = Path(link).absolute()
    target = Path(target).resolve(strict=True)
    if not target.is_dir():
        raise ValueError('Directory redirect requires an existing directory target')
    if os.path.lexists(link):
        raise FileExistsError(link)
    if os.name == 'nt':
        subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(target)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    if not link.is_dir() or link.resolve(strict=True) != target:
        raise RuntimeError('Directory redirect did not resolve to its target')
    return link


def platform_for(key=None):
    key = os.name if key is None else key
    if key not in PLATFORMS:
        raise ValueError('Unsupported runtime platform: ' + str(key))
    return PLATFORMS[key]
