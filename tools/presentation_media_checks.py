"""Deterministic current-run media evidence, not an aesthetic or hearing verdict.

Keeps every assertion in presentation_acceptance_evidence; adds full PNG integrity,
visible-pixel nonblank checks and exact WAV payload length. No game is launched.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import wave

try:
    from . import presentation_acceptance_evidence as evidence
except ImportError:
    import presentation_acceptance_evidence as evidence

SCOPE = 'decoded-current-run-media-and-native-receipts-not-sensory-review'


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _decode_image(root, shot):
    """One fresh decode; no shared PIL objects or result/error mutations."""
    from PIL import Image
    name = None
    try:
        name = shot.get('path')
        path = evidence._artifact(root, name)
        data = path.read_bytes()
        with Image.open(path) as image:
            if image.format != 'PNG':
                raise ValueError('not PNG')
            image.verify()  # CRC/chunk integrity, beyond lazy pixel loading.
        with Image.open(path) as image:
            image.load()
            if (type(shot['width']) is not int or type(shot['height']) is not int
                    or image.size != (shot['width'], shot['height'])
                    or min(image.size) <= 0):
                raise ValueError('decoded dimension mismatch')
            with image.convert('RGBA') as rgba, Image.new('RGBA', image.size, (0, 0, 0, 255)) as visible:
                visible.alpha_composite(rgba)
                with visible.convert('RGB') as rgb:
                    extrema = rgb.getextrema()
            if all(lo == hi for lo, hi in extrema):
                raise ValueError('blank visible viewport')
            return ({'path': name, 'width': image.width, 'height': image.height,
                     'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                     'decodedNonblank': True}, None)
    except (OSError, ValueError, TypeError, KeyError, SyntaxError, AttributeError, EOFError, OverflowError) as exc:
        return None, f'image {name!r}: {exc}'


def build_report(payload, token, mode, artifact_dir):
    """Validate one current-run producer payload; return JSON-safe report.

    Caller must still apply its full-log runtime-error gate (or use check_log).
    Token is supplied by the runner, never inferred from the producer payload.
    """
    errors = []
    try:
        errors.extend(evidence.validate(payload, token, mode, artifact_dir))
    except (ImportError, OSError, ValueError, TypeError, KeyError, AttributeError,
            IndexError, OverflowError, EOFError) as exc:
        errors.append('evidence validation failed: ' + str(exc))
    images = []
    audio = None
    try:
        from PIL import Image
        root = Path(artifact_dir).resolve(strict=True)
        shots = [r['screenshot'] for r in payload['views']] + [r['screenshot'] for r in payload['screens']]
        if not shots:
            errors.append('no current-run screenshots')
        # map yields input order, regardless of completion order. Only this thread
        # aggregates rows/errors; the second validator's decode remains independent.
        with ThreadPoolExecutor(max_workers=4) as workers:
            for image, error in workers.map(lambda shot: _decode_image(root, shot), shots):
                if image is not None:
                    images.append(image)
                if error is not None:
                    errors.append(error)
        receipt = payload['audio']
        if receipt is not None:
            path = evidence._artifact(root, receipt['wav'])
            with wave.open(str(path), 'rb') as wav:
                channels, width, rate, count = (wav.getnchannels(), wav.getsampwidth(),
                                                wav.getframerate(), wav.getnframes())
                pcm = wav.readframes(count)
                if len(pcm) != count * channels * width:
                    raise ValueError('truncated decoded WAV payload')
                if count != receipt['frames'] or rate != receipt['sampleRate']:
                    raise ValueError('decoded WAV differs from receipt')
            audio = {'path': receipt['wav'], 'frames': count, 'sampleRate': rate,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'profile': payload['audioProfile']['profile'],
                     'voices': [{'cue': v['cue'], 'file': v['file'], 'playing': v['playing']}
                                for v in receipt['voices']]}
    except (ImportError, OSError, ValueError, TypeError, KeyError, AttributeError,
            wave.Error, EOFError) as exc:
        errors.append('media artifacts: ' + str(exc))
    return {'schema': 1, 'scope': SCOPE, 'token': token, 'mode': mode,
            'status': 'FAIL' if errors else 'PASS', 'errors': errors,
            'images': images, 'audio': audio,
            'claims': {'subjectiveVisualQuality': False, 'humanHearing': False,
                       'perCueAudibility': False}}


def check_log(text, token, mode, artifact_dir):
    """Strict full log entry point; no baseline-noise filtering is performed here."""
    try:
        lines = [line.split(evidence.MARKER, 1)[1] for line in text.splitlines()
                 if evidence.MARKER in line]
        if len(lines) != 1:
            raise ValueError('expected exactly one presentation result')
        payload = json.loads(lines[0], object_pairs_hook=_unique)
        report = build_report(payload, token, mode, artifact_dir)
        # Preserve the established strict log semantics as well as media checks.
        log_errors = evidence.check_log(text, token, mode, artifact_dir)
        report['errors'].extend(e for e in log_errors if e not in report['errors'])
        report['status'] = 'FAIL' if report['errors'] else 'PASS'
        return report
    except (ValueError, TypeError, OSError, ImportError, AttributeError) as exc:
        return {'schema': 1, 'scope': SCOPE, 'token': token, 'mode': mode,
                'status': 'FAIL', 'errors': ['invalid evidence log: ' + str(exc)],
                'images': [], 'audio': None,
                'claims': {'subjectiveVisualQuality': False, 'humanHearing': False,
                           'perCueAudibility': False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', required=True, type=Path)
    parser.add_argument('--token', required=True)
    parser.add_argument('--mode', required=True, choices=('all', 'cards', 'actions'))
    parser.add_argument('--artifact-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        text = args.log.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        print(json.dumps({'schema': 1, 'scope': SCOPE, 'status': 'FAIL',
                          'errors': ['cannot read log: ' + str(exc)]}, sort_keys=True))
        return 1
    report = check_log(text, args.token, args.mode, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
