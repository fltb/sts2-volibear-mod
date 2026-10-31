#!/usr/bin/env python3
"""Build the offline catalog after fully decoding every downloaded original."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify without changing the catalog or report')
    args = parser.parse_args()
    inventory_path = ROOT / 'inventory.json'
    download_path = ROOT / 'reports/download_report.json'
    inventory = json.loads(inventory_path.read_text())
    downloaded = json.loads(download_path.read_text())
    assert downloaded['passed'] and downloaded['inventory_sha256'] == digest(inventory_path)
    by_id = {r['id']: r for r in downloaded['files']}
    assert len(by_id) == len(inventory['entries'])

    def check(item: dict) -> dict:
        row = by_id[item['id']]
        assert row['status'] == 'downloaded'
        path = ROOT / item['file']
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
        assert path.read_bytes()[:4] == b'OggS'
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                                check=True, capture_output=True, text=True)
        probe = json.loads(result.stdout)
        streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
        assert len(streams) == 1 and len(probe['streams']) == 1
        stream = streams[0]
        assert stream['codec_name'] == 'vorbis'
        rate = int(stream['sample_rate'])
        channels = int(stream['channels'])
        duration = float(probe['format']['duration'])
        assert duration > 0 and channels in (1, 2) and rate in (22050, 24000, 32000, 44100, 48000)
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:a:0',
                                  '-f', 'f32le', '-acodec', 'pcm_f32le', '-'], check=True, capture_output=True)
        pcm = np.frombuffer(decoded.stdout, dtype='<f4')
        assert pcm.size > 0 and np.isfinite(pcm).all()
        peak = float(np.max(np.abs(pcm)))
        rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
        assert peak > 0 and rms > 0
        return {**item, 'bytes': row['bytes'], 'sha256': row['sha256'],
                'resolved_url': row['resolved_url'], 'content_type': row['content_type'],
                'codec': stream['codec_name'], 'duration_seconds': duration,
                'sample_rate': rate, 'channels': channels,
                'decoded_samples_per_channel': pcm.size // channels,
                'peak_linear': peak, 'rms_linear': rms, 'full_decode_passed': True,
                'original_bytes_preserved': True, 'filename_confirmed_by_download': True}

    with ThreadPoolExecutor(max_workers=4) as executor:
        entries = list(executor.map(check, inventory['entries']))
    catalog = {
        'schema_version': 1, 'revision': inventory.get('revision', 'V5.1'),
        'title': '沃利贝尔官方原始音频资料库',
        'scope': inventory['scope'],
        'complete_scope_verified': inventory.get('complete_scope_verified', False),
        'completeness_note': inventory.get('completeness_note', ''),
        'runtime_profile_activated': False,
        'copyright_holder': 'Riot Games, Inc.',
        'distribution_context': 'User-requested personal asset collection',
        'entries_count': len(entries), 'unique_audio_sha256_count': len({e['sha256'] for e in entries}),
        'total_bytes': sum(e['bytes'] for e in entries),
        'total_duration_seconds': round(sum(e['duration_seconds'] for e in entries), 6),
        'entries': entries,
    }
    catalog_path = ROOT / 'catalog.json'
    js = 'window.OFFICIAL_AUDIO_CATALOG = ' + json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + ';\n'
    if args.check:
        assert json.loads(catalog_path.read_text()) == catalog, 'Current catalog differs from actual originals'
        assert (ROOT / 'catalog.js').read_text() == js
        print(json.dumps({'passed': True, 'decoded_originals': len(entries), 'catalog_matches': True}))
        return
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'catalog.js').write_text(js)
    report = {
        'schema_version': 1, 'passed': True, 'checked_at': datetime.now(timezone.utc).isoformat(),
        'inventory_sha256': digest(inventory_path), 'download_report_sha256': digest(download_path),
        'catalog_sha256': digest(catalog_path), 'catalog_js_sha256': digest(ROOT / 'catalog.js'),
        'validator_sha256': digest(Path(__file__)),
        'downloaded_files': len(entries), 'fully_decoded_files': len(entries),
        'unique_audio_sha256_count': catalog['unique_audio_sha256_count'],
        'all_files_preserve_downloaded_bytes': True, 'reencoded_files': 0,
        'complete_wiki_site_claim': False,
        'auditory_review': 'No human listening approval is claimed; full decode, finite PCM, non-silence and browser playback are technical checks.',
        'scope': 'Every listed and downloaded original; scope completeness is reported separately in inventory.json.',
        'ffmpeg_version': subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True).stdout.splitlines()[0],
        'files': [{k: e[k] for k in ('id', 'file', 'sha256', 'duration_seconds', 'sample_rate', 'channels',
                                     'decoded_samples_per_channel', 'peak_linear', 'rms_linear', 'full_decode_passed')} for e in entries],
    }
    (ROOT / 'reports/technical_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: catalog[k] for k in ('entries_count', 'unique_audio_sha256_count', 'total_bytes', 'total_duration_seconds')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
