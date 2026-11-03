"""Trusted CA configuration for temporary standalone Godot profiles."""
import json
import os
from pathlib import Path
import shutil


def isolated_tls_settings(directory, environment):
    """Stage trusted CAs in a fresh Windows profile; return project.godot settings."""
    if os.name != 'nt':
        return ''
    directory = Path(directory).resolve()
    appdata = Path(environment['APPDATA']).resolve()
    if not appdata.is_relative_to(directory):
        raise ValueError('Godot editor settings must stay inside the temporary directory')
    try:
        from pip._vendor import certifi
    except ImportError as error:
        raise ValueError('Windows isolated Godot requires pip bundled certifi') from error
    ca = directory / 'build-ca.pem'
    shutil.copyfile(certifi.where(), ca)
    editor_config = appdata / 'Godot/editor_settings-4.5.tres'
    editor_config.parent.mkdir(parents=True, exist_ok=True)
    with editor_config.open('x', encoding='utf-8') as stream:
        stream.write('[gd_resource type="EditorSettings" format=3]\n[resource]\n'
                     'network/tls/editor_tls_certificates=' + json.dumps(ca.as_posix()) + '\n')
    return '[network]\ntls/certificate_bundle_override=' + json.dumps(ca.as_posix()) + '\n'
