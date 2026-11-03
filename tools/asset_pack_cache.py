"""Local, content-bound evidence for a completed resource build (never game acceptance)."""
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

SCHEMA = 1


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def fingerprint(paths, identity):
    # Absolute names also prevent silently reusing evidence from a different tool install.
    files = {str(Path(p).resolve()): digest(p) for p in sorted(set(paths), key=str)}
    value = {'files': files, 'identity': identity}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def receipt_path(output):
    return Path(output).with_suffix('.pck.build-evidence.json')


def valid_log(text, markers):
    return all(marker in text for marker in markers) and 'ERROR:' not in text


def lookup(output, key, markers, evidence_root):
    """Fail closed on missing, old, truncated or altered evidence, including actual logs."""
    try:
        record = json.loads(receipt_path(output).read_text(encoding='utf-8'))
        if (record['schema'] != SCHEMA or record['input_digest'] != key
                or record['pack_sha256'] != digest(output)
                or set(record['receipts']) != set(markers)
                or not isinstance(record['cold_seconds'], (int, float))
                or not math.isfinite(record['cold_seconds']) or record['cold_seconds'] <= 0):
            return None
        for label, required in markers.items():
            receipt = record['receipts'][label]
            path = Path(receipt['path']).resolve()
            if (not path.is_relative_to(Path(evidence_root).resolve())
                    or receipt['returncode'] != 0 or receipt['sha256'] != digest(path)
                    or not valid_log(path.read_text(encoding='utf-8'), required)):
                return None
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None


def publish(output, key, markers, work, cold_seconds):
    # Called only after the complete existing build/validation path and final input recheck.
    receipts = {}
    for label, required in markers.items():
        path = work / (label + '.log')
        if not valid_log(path.read_text(encoding='utf-8'), required):
            raise ValueError('Incomplete resource validation receipt: ' + label)
        receipts[label] = {'path': str(path.resolve()), 'sha256': digest(path), 'returncode': 0}
    record = {'schema': SCHEMA, 'input_digest': key, 'pack_sha256': digest(output),
              'receipts': receipts, 'cold_seconds': cold_seconds}
    destination = receipt_path(output)
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.partial')
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, destination)
    return record
