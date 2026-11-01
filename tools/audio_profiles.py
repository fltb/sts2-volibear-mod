#!/usr/bin/env python3
"""Fetch, verify and package the explicit open or private Riot English audio profile.

No Riot media is written outside ignored .local/. The default open profile is
complete offline. A private package replaces the single full Volibear.pck; it is
not a second pack whose load order can silently change the selected sounds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / 'assets/animation/audio'
PROFILES = AUDIO / 'profiles'
WORK = ROOT / '.local/audio-profiles'
HOSTS = {'static.wikia.nocookie.net', 'cmsassets.rgpub.io'}
PROCESSING_VERSION = 1


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def local_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / '.local').resolve()):
        raise ValueError('Private media/build output must remain beneath ignored .local/')
    return path


def write_json(path, data):
    path = local_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def source_url(url):
    parsed = urllib.parse.urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname not in HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('Unapproved public media URL: ' + url)
    return url


class PublicMediaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        source_url(new_url)
        return super().redirect_request(request, fp, code, msg, headers, new_url)


def profile_data(profile):
    if profile not in ('open', 'riot_en'):
        raise ValueError('Unknown audio profile: ' + str(profile))
    data = read_json(PROFILES / (profile + '.json'))
    if data.get('schema_version') != 1 or data.get('profile') != profile:
        raise ValueError('Invalid profile identity/schema')
    if profile == 'open':
        return data
    cues = {c['id']: c for c in read_json(AUDIO / 'manifest.json')['cues']}
    ids, filenames, bound = set(), set(), set()
    for row in data['sources']:
        if not re.fullmatch(r'[a-z0-9_]+', row['id']) or row['id'] in ids:
            raise ValueError('Unsafe/duplicate source identity')
        if (not re.fullmatch(r'[A-Za-z0-9_]+\.(ogg|mp3)', row['filename'])
                or row['filename'] in filenames):
            raise ValueError('Unsafe/duplicate source filename')
        if not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or not 0 < row['bytes'] <= 32 * 1024 * 1024:
            raise ValueError('Missing fixed source hash/size')
        source_url(row['download_url'])
        if row['license'] != 'LicenseRef-Riot-Proprietary' or row['language'] not in ('en_US', 'nonverbal'):
            raise ValueError('Private profile must preserve Riot rights and English/nonverbal scope')
        ids.add(row['id'])
        filenames.add(row['filename'])
    by_id = {s['id']: s for s in data['sources']}
    for row in data['overrides']:
        cue = cues.get(row['cue'])
        if cue is None or row['cue'] in bound or row['source'] not in ids or cue['loop']:
            raise ValueError('Unknown/duplicate/looping cue override')
        kind = by_id[row['source']]['kind']
        if (cue['bus'] == 'Voice') != (kind == 'voice'):
            raise ValueError('Voice and SFX must retain their existing mixing channels')
        bound.add(row['cue'])
    for row in data['fallbacks']:
        if row['cue'] not in cues or row['cue'] in bound:
            raise ValueError('Fallback overlaps an active override')
    return data


def decode(path):
    import numpy as np
    metadata = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,sample_rate,channels',
        '-of', 'json', str(path)]))
    seconds = float(metadata['format']['duration'])
    if not 0.02 <= seconds <= 60:
        raise ValueError('Unexpected individual clip duration: ' + str(path))
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', '48000', 'pipe:1'])
    pcm = np.frombuffer(raw, dtype='<f4').copy()
    if not len(pcm) or not np.isfinite(pcm).all() or float(np.sqrt(np.mean(pcm.astype(float) ** 2))) < 1e-5:
        raise ValueError('Silent or invalid decoded audio: ' + str(path))
    return pcm, metadata


def verify_open(*, full_decode=True):
    profile_data('open')
    manifest = read_json(AUDIO / 'manifest.json')
    if len(manifest['assets']) != 47 or len(manifest['cues']) != 54:
        raise ValueError('Expected all 47 open assets and 54 cues')
    files = {}
    for row in manifest['assets']:
        for key, hash_key in (('file', 'ogg_sha256'), ('wav', 'wav_sha256')):
            path = (AUDIO / row[key]).resolve()
            if not path.is_relative_to(AUDIO.resolve()) or digest(path) != row[hash_key]:
                raise ValueError('Open asset hash/path mismatch: ' + row['id'])
        if full_decode:
            pcm, meta = decode(AUDIO / row['file'])
            if (meta['streams'][0]['codec_name'] != 'vorbis' or max(abs(pcm)) >= .89
                    or abs(float(meta['format']['duration']) - row['duration_seconds']) > .001):
                raise ValueError('Open asset decode/level/duration mismatch: ' + row['id'])
        files[row['file']] = row
    for cue in manifest['cues']:
        if cue['file'] not in files or cue['asset_id'] != files[cue['file']]['id']:
            raise ValueError('Incomplete open cue fallback: ' + cue['id'])
    sources = read_json(AUDIO / 'sources.json')['recordings']
    for row in sources:
        if row['license'] != 'CC0-1.0' or digest(AUDIO / row['file']) != row['sha256']:
            raise ValueError('Open recording license/source hash mismatch')
    if 'CC0' not in (AUDIO / 'source/kenney/License.txt').read_text(encoding='utf-8'):
        raise ValueError('Missing original Kenney CC0 license')
    return {'profile': 'open', 'assets': 47, 'cues': 54, 'cc0_recordings': len(sources),
            'decoded': full_decode, 'listening_review': 'not_claimed'}


def original_path(row):
    return local_path(WORK / 'originals' / row['filename'])


def verify_original(row):
    path = original_path(row)
    if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
        raise ValueError('Missing/changed original; run fetch: ' + row['filename'])
    return path


def fetch_sources():
    data = profile_data('riot_en')
    opener = urllib.request.build_opener(PublicMediaRedirect())
    transferred = 0
    for row in data['sources']:
        destination = original_path(row)
        if destination.exists():
            verify_original(row)  # Never overwrite a different existing original.
            continue
        try:
            # Ordinary public GET: no credentials, cookies, challenge bypass or retries.
            with opener.open(source_url(row['download_url']), timeout=35) as response:
                source_url(response.url)
                raw = response.read(32 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Public download stopped at HTTP {error.code}; no retry: {row["download_url"]}') from error
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Public media changed from the pinned original: ' + row['filename'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.partial')
        temporary.write_bytes(raw)
        temporary.replace(destination)
        transferred += 1
        print('Fetched and SHA256 verified: ' + row['filename'], flush=True)
    return {'profile': 'riot_en', 'verified_originals': len(data['sources']), 'downloaded_now': transferred}


def prepare_profile(*, fetch=False):
    import numpy as np
    data = profile_data('riot_en')
    if fetch:
        fetch_sources()
    settings = data['processing']
    destination = local_path(WORK / 'prepared/riot_en')
    destination.mkdir(parents=True, exist_ok=True)
    processed = {}
    for source in data['sources']:
        original = verify_original(source)
        pcm, _ = decode(original)
        edit = data['edits'].get(source['id'], {})
        start = int(float(edit.get('start_seconds', 0)) * 48000)
        end = int(float(edit.get('end_seconds', len(pcm) / 48000)) * 48000)
        if not 0 <= start < end <= len(pcm):
            raise ValueError('Invalid authored excerpt: ' + source['id'])
        pcm = pcm[start:end]
        active = np.flatnonzero(abs(pcm) > 10 ** (settings['trim_edge_silence_db'] / 20))
        if not len(active):
            raise ValueError('No active samples in source: ' + source['id'])
        padding = int(settings['edge_padding_seconds'] * 48000)
        pcm = pcm[max(0, int(active[0]) - padding):min(len(pcm), int(active[-1]) + padding + 1)]
        pcm *= float(settings['target_peak']) / float(max(abs(pcm)))
        fade_in = min(len(pcm), int(settings['fade_in_seconds'] * 48000))
        fade_out = min(len(pcm), int(settings['fade_out_seconds'] * 48000))
        pcm[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)
        pcm[-fade_out:] *= np.linspace(1, 0, fade_out, dtype=np.float32)
        target = destination / (source['id'] + '.ogg')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', '48000', '-ac', '1',
                        '-i', 'pipe:0', '-map_metadata', '-1', '-c:a', 'libvorbis', '-q:a',
                        str(settings['vorbis_quality']), str(target)], input=pcm.astype('<f4').tobytes(), check=True)
        decoded, metadata = decode(target)
        if max(abs(decoded)) >= .89:
            raise ValueError('Processed sample peak exceeds the open mix headroom: ' + source['id'])
        processed[source['id']] = {'file': target.name, 'sha256': digest(target),
                                  'source_sha256': source['sha256'],
                                  'duration_seconds': float(metadata['format']['duration']),
                                  'peak': float(max(abs(decoded)))}
    overrides = [{'cue': row['cue'], 'file': 'profiles/riot_en/' + processed[row['source']]['file'],
                  'duration_seconds': processed[row['source']]['duration_seconds'], 'gain_db': 0}
                 for row in data['overrides']]
    runtime = {'schema_version': 1, 'profile': 'riot_en', 'fallback': 'open', 'overrides': overrides}
    write_json(destination / 'runtime.json', runtime)
    write_json(destination / 'build.json', {'processing_version': PROCESSING_VERSION,
               'profile_sha256': digest(PROFILES / 'riot_en.json'), 'processed': processed,
               'sources': data['sources'], 'listening_review': 'not_claimed'})
    return {'profile': 'riot_en', 'processed_assets': len(processed), 'overrides': len(overrides),
            'open_fallback_cues': 54 - len(overrides)}


def verify_prepared(*, full_decode=True):
    data = profile_data('riot_en')
    directory = local_path(WORK / 'prepared/riot_en')
    if not (directory / 'build.json').is_file() or not (directory / 'runtime.json').is_file():
        raise ValueError('Private profile is not prepared; run tools/audio_profiles.py prepare --profile riot_en')
    record = read_json(directory / 'build.json')
    runtime = read_json(directory / 'runtime.json')
    if (record.get('processing_version') != PROCESSING_VERSION
            or record['profile_sha256'] != digest(PROFILES / 'riot_en.json')):
        raise ValueError('Prepared profile is stale; run prepare again')
    if set(record['processed']) != {s['id'] for s in data['sources']}:
        raise ValueError('Prepared profile has a different source set')
    for source in data['sources']:
        verify_original(source)
        row = record['processed'][source['id']]
        expected_name = source['id'] + '.ogg'
        if row['file'] != expected_name or digest(directory / expected_name) != row['sha256']:
            raise ValueError('Prepared audio mismatch: ' + source['id'])
        if full_decode:
            pcm, _ = decode(directory / expected_name)
            if max(abs(pcm)) >= .89:
                raise ValueError('Prepared audio exceeds mix peak ceiling')
    expected = [{'cue': row['cue'], 'file': 'profiles/riot_en/' + record['processed'][row['source']]['file'],
                 'duration_seconds': record['processed'][row['source']]['duration_seconds'], 'gain_db': 0}
                for row in data['overrides']]
    if runtime != {'schema_version': 1, 'profile': 'riot_en', 'fallback': 'open', 'overrides': expected}:
        raise ValueError('Prepared runtime cue mapping changed')
    return runtime


def stage_profile(profile, audio_destination):
    """Called by build_assets after staging the complete approved open audio set."""
    profile_data(profile)
    destination = local_path(audio_destination) / 'profiles'
    destination.mkdir(parents=True, exist_ok=True)
    if profile == 'open':
        if (destination / 'riot_en').exists():
            raise ValueError('Open build requires a fresh stage without private Riot media')
        write_json(destination / 'runtime.json', {'schema_version': 1, 'profile': 'open', 'overrides': []})
        return
    runtime = verify_prepared(full_decode=False)
    target = destination / 'riot_en'
    target.mkdir(exist_ok=True)
    for row in read_json(WORK / 'prepared/riot_en/build.json')['processed'].values():
        shutil.copyfile(WORK / 'prepared/riot_en' / row['file'], target / row['file'])
        if digest(target / row['file']) != row['sha256']:
            raise ValueError('Private asset changed while staging')
    write_json(destination / 'runtime.json', runtime)


def package(profile, godot):
    # Import only for this command; verify/fetch do not depend on Godot or the game.
    try:
        from tools import build_assets
    except ModuleNotFoundError:
        import build_assets
    verify_open()
    if profile == 'riot_en':
        prepare_profile(fetch=True)
    directory = local_path(WORK / 'packages' / profile)
    directory.mkdir(parents=True, exist_ok=True)
    pack = build_assets.build(Path(godot), directory / 'Volibear.pck', audio_profile=profile)
    return archive_profile(profile, pack)


def archive_profile(profile, pack):
    """Wrap an already verified profile PCK with portable notices and exact hashes."""
    profile_data(profile)
    pack = local_path(pack)
    if pack.name != 'Volibear.pck' or pack.read_bytes()[:4] != b'GDPC':
        raise ValueError('Audio package requires the verified Volibear.pck')
    directory = local_path(WORK / 'packages' / profile)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ('Volibear-audio-' + profile + '.zip')
    notice = ('Audio resource replacement for the matching Volibear mod.\n'
              'Close the game and replace mods/Volibear/Volibear.pck with this single complete pack.\n'
              'The installed Volibear DLL/manifest and BaseLib are still required.\n'
              'Keep the previous PCK to switch back. AUDIO_PACKAGE.json records each supplied file hash.\n'
              'Profile: ' + profile + '. All open fallback sounds remain included.\n'
              'Riot recordings, if selected, remain Riot property and are not GPL/CC licensed.\n'
              'The riot_en archive is a local private artifact; this tool does not publish it.\n'
              'No human listening or native game acceptance is claimed.\n')
    sources = {
        'mods/Volibear/Volibear.pck': pack,
        'AUDIO_SOURCES.json': PROFILES / (profile + '.json'),
        'OPEN_AUDIO_CREDITS.md': AUDIO / 'CREDITS.md',
        'OPEN_AUDIO_SOURCES.json': AUDIO / 'sources.json',
        'KENNEY-CC0.txt': AUDIO / 'source/kenney/License.txt',
        'LICENSE': ROOT / 'LICENSE',
        'LICENSE-ASSETS': ROOT / 'LICENSE-ASSETS',
        'LICENSING.md': ROOT / 'LICENSING.md',
    }
    if profile == 'riot_en':
        sources['RIOT_AUDIO_CREDITS.md'] = AUDIO / 'official/CREDITS.md'
    payload = {name: path.read_bytes() for name, path in sources.items()}
    payload['AUDIO_PROFILE.txt'] = notice.encode('utf-8')
    inventory = {'producer': 'volibear-audio-resource-package-v1', 'profile': profile,
                 'scope': 'resource-replacement; matching mod DLL/manifest and BaseLib required',
                 'game_version': '0.107.1', 'game_build': '59260271',
                 'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())}}
    payload['AUDIO_PACKAGE.json'] = (json.dumps(inventory, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with tempfile.NamedTemporaryFile(dir=directory, prefix='.audio-package-', suffix='.tmp', delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payload.items()):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, data)
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('fetch', 'prepare', 'verify', 'package'))
    parser.add_argument('--profile', choices=('open', 'riot_en'), default='open')
    parser.add_argument('--godot', type=Path, help='Godot 4.5.1 mono executable, only for package')
    args = parser.parse_args()
    if args.command == 'package':
        if args.godot is None:
            parser.error('package requires --godot')
        print('Audio resource archive: ' + str(package(args.profile, args.godot)))
    elif args.command == 'verify':
        result = verify_open()
        if args.profile == 'riot_en':
            runtime = verify_prepared()
            result.update(profile='riot_en', verified_overrides=len(runtime['overrides']))
        print(json.dumps(result))
    elif args.profile == 'open':
        print(json.dumps(verify_open()))
    elif args.command == 'fetch':
        print(json.dumps(fetch_sources()))
    else:
        print(json.dumps(prepare_profile(fetch=True)))


if __name__ == '__main__':
    main()
