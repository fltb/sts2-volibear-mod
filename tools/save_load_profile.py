r"""Short runner-owned profiles; retain both processes' saves and shader cache.

Pinned Godot4.5.1 DirAccessWindows prefixes local paths with \\?\ and uses
SetCurrentDirectoryW. ShaderRD._initialize_cache treats failed chdir followed by
ERR_ALREADY_EXISTS as an error on a reused cache. Never mask that runtime error.
"""
from pathlib import Path
import stat
import uuid
import headless as h
ROOT=Path(__file__).resolve().parents[1]
# Longest native ShaderRD class directory observed in the pinned renderer. Its
# next component is a SHA256 group ID; cache filenames use FileAccess, not chdir.
PINNED_LONGEST_SHADER='Fsr2ReconstructPreviousDepthPassShaderRD'
WIN32_MAX_PATH=260


def shader_directory_budget(user_root):
    path=str(Path(user_root)/'shader_cache'/PINNED_LONGEST_SHADER/('0'*64)).replace('/','\\')
    if not path.startswith('\\\\'):path='\\\\?\\'+path
    # SetCurrentDirectoryW needs room for a possible trailing slash and the NUL.
    units=len(path.encode('utf-16-le'))//2+2
    return dict(directory=path,utf16_units_with_terminator=units,limit=WIN32_MAX_PATH)


def require_shader_directory_budget(user_root):
    budget=shader_directory_budget(user_root)
    if budget['utf16_units_with_terminator']>=WIN32_MAX_PATH:
        raise ValueError('Owned profile exceeds pinned Windows shader-directory budget: '+str(budget))
    return budget


def _checked_parent():
    root=ROOT.resolve(strict=True);base=root/'.local'/'p'
    for path in (root/'.local',base):
        try:info=path.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise ValueError('Owned profile parent cannot be a symlink/reparse point: '+str(path))
        if not stat.S_ISDIR(info.st_mode):raise ValueError('Owned profile parent is not a directory: '+str(path))
    if base.resolve()!=base:raise ValueError('Owned profile parent escaped its fixed location')
    return base


def create_owned_profile():
    """No arbitrary profile argument; atomic creation rejects collisions/reuse.

    Return the actual absolute owned path. Do not move old evidence, clear cache,
    change ACLs/registry, or automatically delete this profile.
    """
    base=_checked_parent();profile=base/uuid.uuid4().hex[:12]
    if h.IS_WINDOWS:require_shader_directory_budget(h.user_data_root(profile))
    base.mkdir(parents=True,exist_ok=True)
    if _checked_parent()!=base:raise ValueError('Owned profile parent changed during preparation')
    profile.mkdir(exist_ok=False)
    actual=profile.resolve(strict=True)
    if actual!=profile:raise ValueError('New owned profile was redirected: '+str(profile))
    return actual
