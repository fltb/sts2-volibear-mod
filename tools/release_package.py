#!/usr/bin/env python3
"""Package existing frozen artifacts only; never build, download, install or run the game."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

try:
    from . import dependencies
except ImportError:
    import dependencies

ROOT = Path(__file__).resolve().parents[1]
GAME_VERSION = '0.107.1'
GAME_BUILD = '59260271'
PRODUCER = 'volibear-release-package-v1'
LICENSE_SHA256 = '1847e0e0698142ed4347c1441a9fa81c8fbddd44b1d8bbcd5e3647f991759d7f'
MOD_FILES = ('Volibear.dll', 'Volibear.pck', 'Volibear.json')
DISTRIBUTION_NOTICES = {
    'LICENSE': ROOT / 'LICENSE',
    'LICENSE-ASSETS': ROOT / 'LICENSE-ASSETS',
    'LICENSING.md': ROOT / 'LICENSING.md',
    'licenses/audio/CREDITS.md': ROOT / 'assets/animation/audio/CREDITS.md',
    'licenses/audio/sources.json': ROOT / 'assets/animation/audio/sources.json',
    'licenses/audio/source/kenney/License.txt': ROOT / 'assets/animation/audio/source/kenney/License.txt',
}
OUTPUT = ROOT / '.local/release/Volibear-0.1.0-StS2-0.107.1.zip'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_file(path):
    path = Path(path).absolute()
    dependencies.assert_unredirected(path)
    if not path.is_file():
        raise ValueError('Required package input missing: ' + path.name)
    return path.read_bytes()


def reject_local_paths(payload, name):
    # Distribution text/inventory only. Binary debug/provenance strings are not runtime dependencies.
    for data in (payload, payload.replace(b'\x00', b'')):
        # Godot/FMOD resource schemes and HTTPS are not drive paths, including in UTF-16 strings.
        data = re.sub(rb'(?:https?|res|event|uid|user|local)://?', b'URI/', data)
        if re.search(rb'[A-Za-z]:[\\/]|/(?:Users|home|tmp)/', data):
            raise ValueError('Absolute local path in package input: ' + name)


def manifest(data, expected_id, version=None):
    value = json.loads(data.decode('utf-8-sig'))
    if (not isinstance(value, dict) or value.get('id') != expected_id
            or value.get('min_game_version') != GAME_VERSION
            or value.get('has_dll') is not True or value.get('has_pck') is not True
            or not isinstance(value.get('version'), str) or not value['version']):
        raise ValueError('Manifest identity/game version/artifact declarations mismatch')
    if set(value) - {'id', 'name', 'author', 'description', 'version', 'min_game_version', 'has_dll', 'has_pck', 'dependencies', 'affects_gameplay'}:
        raise ValueError('Unexpected manifest fields; development configuration is not distributable')
    if version is not None and value['version'] != version:
        raise ValueError('Dependency manifest pin mismatch')
    if expected_id == 'Volibear' and value.get('dependencies') != [{'id': 'BaseLib', 'min_version': dependencies.VERSION}]:
        raise ValueError('Volibear dependency pin mismatch')
    return value


def dependency_files(archive, license_file):
    data = read_file(archive)
    if sha(data) != dependencies.SHA256 or dependencies.VERSION != '3.4.7':
        raise ValueError('BaseLib archive/version pin mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sorted(z.namelist()) != sorted(dependencies.FILES):
            raise ValueError('Unexpected/duplicate files in pinned BaseLib archive')
        selected = {f'mods/BaseLib/{name}': z.read(name) for name in dependencies.FILES}
    manifest(selected['mods/BaseLib/BaseLib.json'], 'BaseLib', 'v3.4.7')
    license_bytes = read_file(license_file)
    if sha(license_bytes) != LICENSE_SHA256:
        raise ValueError('Original BaseLib license pin mismatch')
    selected['licenses/BaseLib-LICENSE.txt'] = license_bytes
    return selected


def check_owned_output(path, expected_names):
    if not path.exists():
        return
    try:
        with zipfile.ZipFile(path) as z:
            if sorted(z.namelist()) != sorted(expected_names):
                raise ValueError('Unexpected package entries')
            record = json.loads(z.read('PACKAGE.json'))
            if record.get('producer') != PRODUCER or set(record['files']) != set(expected_names) - {'PACKAGE.json'}:
                raise ValueError('Missing ownership inventory')
            if any(sha(z.read(name)) != digest for name, digest in record['files'].items()):
                raise ValueError('Changed package payload')
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        raise ValueError('Refusing to overwrite unknown or modified output archive') from error


def package(dll, pck, mod_manifest, archive, license_file, instructions, output, *, audio_profile='open'):
    if audio_profile not in ('open', 'riot_en'):
        raise ValueError('Unknown audio profile: ' + str(audio_profile))
    if audio_profile == 'riot_en' and not Path(output).resolve().is_relative_to((ROOT / '.local').resolve()):
        raise ValueError('Private Riot package must remain beneath ignored .local/')
    if any(Path(path).name != name for name, path in zip(MOD_FILES, (dll, pck, mod_manifest))):
        raise ValueError('Input artifact filename mismatch; no renamed game/development files')
    payload = {f'mods/Volibear/{name}': read_file(path)
               for name, path in zip(MOD_FILES, (dll, pck, mod_manifest))}
    info = manifest(payload['mods/Volibear/Volibear.json'], 'Volibear')
    payload.update(dependency_files(archive, license_file))
    payload['INSTALL_ZH.md'] = read_file(instructions)
    # The DLL, artwork and open audio travel with their own terms and source credits;
    # BaseLib's MIT text does not cover this mod or its asset authors.
    payload.update({name: read_file(path) for name, path in DISTRIBUTION_NOTICES.items()})
    if audio_profile == 'riot_en':
        payload['licenses/audio/RIOT_AUDIO_CREDITS.md'] = read_file(ROOT / 'assets/animation/audio/official/CREDITS.md')
        payload['licenses/audio/riot_en.json'] = read_file(ROOT / 'assets/animation/audio/profiles/riot_en.json')
        payload['AUDIO_PROFILE.txt'] = (
            'Private local Riot English audio profile with the complete open fallback set.\n'
            'Riot recordings remain Riot property and are not GPL/CC licensed.\n'
            'Replace the single Volibear.pck to switch profiles; never install two competing packs.\n'
            'This package does not claim human listening or native gameplay acceptance.\n').encode('utf-8')
    for name, data in payload.items():
        # Preserve approved DLL/PCK bytes. Their debug/provenance text is not an installation address.
        # Runtime resource loading is covered by the existing resource/game gates, not a byte-grep oracle.
        if not name.endswith(('.dll', '.pck')):
            reject_local_paths(data, name)
        if name.endswith('.dll') and not data.startswith(b'MZ'):
            raise ValueError('DLL header mismatch: ' + name)
        if name.endswith('.pck') and not data.startswith(b'GDPC'):
            raise ValueError('PCK header mismatch: ' + name)
    record = {'producer': PRODUCER, 'status': 'packaged-build', 'mod_version': info['version'],
              'game_version': GAME_VERSION, 'game_build': GAME_BUILD,
              'audio_profile': audio_profile, 'private_audio': audio_profile == 'riot_en',
              'dependency': {'id': 'BaseLib', 'version': dependencies.VERSION, 'archive_sha256': dependencies.SHA256,
                             'official_url': dependencies.URL},
              'files': {name: sha(data) for name, data in sorted(payload.items())}}
    payload['PACKAGE.json'] = (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    target = Path(output).absolute()
    dependencies.assert_unredirected(target)
    if target.suffix.lower() != '.zip':
        raise ValueError('Output must be a zip archive')
    check_owned_output(target, payload)
    # Validate all inputs/output ownership before creating anything. Fixed ordering/timestamps allow byte-identical reruns.
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.volibear-package-', suffix='.tmp', delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(payload.items()):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                z.writestr(entry, data)
        dependencies.assert_unredirected(target)
        check_owned_output(target, payload)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, default=ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll')
    parser.add_argument('--pck', type=Path, default=ROOT / '.local/packs/Volibear.pck')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'src/Volibear/Volibear.json')
    parser.add_argument('--baselib-archive', type=Path, default=ROOT / '.local/dependencies/BaseLib.3.4.7.zip')
    parser.add_argument('--baselib-license', type=Path, default=ROOT / 'licenses/BaseLib-LICENSE.txt')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--audio-profile', choices=('open', 'riot_en'), default='open')
    args = parser.parse_args()
    if args.audio_profile == 'riot_en' and args.output == OUTPUT:
        args.output = OUTPUT.with_name(OUTPUT.stem + '-riot_en-private.zip')
    result = package(args.dll, args.pck, args.manifest, args.baselib_archive, args.baselib_license,
                     ROOT / 'docs/INSTALL_ZH.md', args.output, audio_profile=args.audio_profile)
    print('Portable mod archive created: ' + result.name)


if __name__ == '__main__':
    main()
