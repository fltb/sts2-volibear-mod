#!/usr/bin/env python3
"""Download the explicitly listed public audio files without re-encoding them."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.partial')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=ROOT / 'inventory.json')
    parser.add_argument('--output', type=Path, default=ROOT)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    output = args.output.resolve()
    inventory_bytes = args.inventory.read_bytes()
    inventory = json.loads(inventory_bytes)
    entries = inventory['entries']
    assert entries and len({e['id'] for e in entries}) == len(entries)
    assert len({e['file'] for e in entries}) == len(entries)
    report_path = output / 'reports/download_report.json'
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    previous_by_id = {e['id']: e for e in previous.get('files', []) if e.get('status') == 'downloaded'}
    halt = threading.Event()

    def download(entry: dict) -> dict:
        result = dict(entry)
        if halt.is_set():
            return {**result, 'status': 'not_requested_after_access_error'}
        rel = Path(entry['file'])
        if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower() != '.ogg':
            raise ValueError('Unsafe or non-OGG output path: ' + str(rel))
        target = output / rel
        if not target.resolve().is_relative_to(output) or target.is_symlink():
            raise ValueError('Output escapes its destination: ' + str(rel))
        url = entry['download_url']
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'static.wikia.nocookie.net', 'game.gtimg.cn'}:
            raise ValueError('Unapproved public media host: ' + parsed.netloc)
        old = previous_by_id.get(entry['id'])
        if target.is_file() and old and old.get('download_url') == url:
            data = target.read_bytes()
            if data.startswith(b'OggS') and sha(data) == old['sha256']:
                return {**result, **{k: old[k] for k in ('bytes', 'sha256', 'content_type', 'resolved_url')},
                        'status': 'downloaded', 'transfer': 'reused_verified_local_file'}
            raise ValueError('Existing file changed; refusing to overwrite: ' + str(rel))
        try:
            # Ordinary public GET. No cookies, login, alternate user agent, or challenge bypass.
            with urllib.request.urlopen(url, timeout=35) as response:
                data = response.read(32 * 1024 * 1024 + 1)
                if len(data) > 32 * 1024 * 1024:
                    raise ValueError('Unexpectedly large individual clip')
                if not data.startswith(b'OggS'):
                    raise ValueError('Response is not an Ogg file')
                digest = sha(data)
                if entry.get('expected_sha256') and entry['expected_sha256'] != digest:
                    raise ValueError('Source bytes changed from the recorded original')
                if target.exists() and target.read_bytes() != data:
                    raise ValueError('Existing different file protected: ' + str(rel))
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    temporary = target.with_name(target.name + '.partial')
                    temporary.write_bytes(data)
                    temporary.replace(target)
                return {**result, 'status': 'downloaded', 'transfer': 'public_get',
                        'http_status': response.status, 'resolved_url': response.url,
                        'content_type': response.headers.get('Content-Type', ''),
                        'bytes': len(data), 'sha256': digest}
        except urllib.error.HTTPError as error:
            if error.code in {401, 402, 403, 429}:
                halt.set()
            return {**result, 'status': 'failed', 'http_status': error.code,
                    'error': str(error), 'automatic_retry': False}
        except Exception as error:
            return {**result, 'status': 'failed', 'error': type(error).__name__ + ': ' + str(error),
                    'automatic_retry': False}

    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as executor:
        futures = [executor.submit(download, entry) for entry in entries]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            ordered = sorted(results, key=lambda e: e['id'])
            downloaded = sum(r['status'] == 'downloaded' for r in ordered)
            report = {
                'schema_version': 1, 'checked_at': datetime.now(timezone.utc).isoformat(),
                'inventory_sha256': sha(inventory_bytes), 'expected_files': len(entries),
                'processed_files': len(results), 'downloaded_files': downloaded,
                'passed': len(results) == len(entries) and downloaded == len(entries),
                'public_get_only': True, 'reencoded': False, 'files': ordered,
            }
            write_json(report_path, report)
            if len(results) % 20 == 0 or result['status'] != 'downloaded' or len(results) == len(entries):
                print(f"{len(results)}/{len(entries)} processed, {downloaded} downloaded; {result['id']}: {result['status']}", flush=True)
    if not report['passed']:
        raise SystemExit('Some explicitly listed files were not downloaded; inspect reports/download_report.json')
    print(json.dumps({'passed': True, 'files': len(entries), 'bytes': sum(r['bytes'] for r in results)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
