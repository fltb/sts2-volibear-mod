"""Recompute visible lightning from actual viewport PNGs, not node/check booleans."""
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import zlib
from manual_evidence import validate_png


class _Raster:
    def __init__(self, pixels, channels):
        self.pixels, self.channels = pixels, channels

    def load(self):
        return self

    def __getitem__(self, position):
        x, y = position
        offset = (y * 1280 + x) * self.channels
        return self.pixels[offset:offset + 3]


def _decode(content):
    # Reuse the existing strict complete-PNG/CRC/size validator. No optional imaging
    # packages are needed by the normal regression or the short development runner.
    validate_png(content, 1280, 720)
    channels = 3 if content[25] == 2 else 4
    compressed = []
    position = 8
    while position < len(content):
        length = struct.unpack_from('>I', content, position)[0]
        if content[position + 4:position + 8] == b'IDAT':
            compressed.append(content[position + 8:position + 8 + length])
        position += length + 12
    raw = zlib.decompress(b''.join(compressed))
    stride = 1280 * channels
    output = bytearray(stride * 720)
    for y in range(720):
        start = y * (stride + 1)
        kind = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        previous = output[(y - 1) * stride:y * stride] if y else bytes(stride)
        if kind:
            for x in range(stride):
                a = row[x - channels] if x >= channels else 0
                b = previous[x]
                c = previous[x - channels] if x >= channels else 0
                if kind == 1:
                    prediction = a
                elif kind == 2:
                    prediction = b
                elif kind == 3:
                    prediction = (a + b) // 2
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    prediction = a if pa <= pb and pa <= pc else b if pb <= pc else c
                row[x] = (row[x] + prediction) & 255
        output[y * stride:(y + 1) * stride] = row
    return _Raster(output, channels)

MARKER = '[Volibear] DOMAIN_VISUAL_RESULT '
PHASES = ('before', 'entered', 'sustained', 'moved', 'exited')


def _region(row):
    cx, cy = row['center']['x'], row['center']['y']
    rx, ry = row['radius']['x'], row['radius']['y']
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in (cx, cy, rx, ry)):
        raise ValueError('nonfinite/invalid pixel geometry')
    if not (20 < rx < 300 and 5 < ry < 100 and 0 <= cx - rx * 1.3 and cx + rx * 1.3 < 1280 and
            0 <= cy - ry * 1.3 and cy + ry * 1.3 < 720 and .18 < ry / rx < .3):
        raise ValueError('foot ellipse outside viewport or implausible')
    return cx, cy, rx, ry


def _pixels(image, reference, row, blue=True):
    cx, cy, rx, ry = _region(row)
    pixels, previous = image.load(), reference.load()
    bins = [0] * 16
    for y in range(int(cy - ry * 1.26), math.ceil(cy + ry * 1.26)):
        for x in range(int(cx - rx * 1.26), math.ceil(cx + rx * 1.26)):
            nx, ny = (x - cx) / rx, (y - cy) / ry
            if not .75 ** 2 <= nx * nx + ny * ny <= 1.25 ** 2:
                continue
            r, g, b = pixels[x, y]
            if blue and not (b >= 170 and g >= 95 and b - r >= 30 and g - r >= 15):
                continue
            if max(abs(a - z) for a, z in zip((r, g, b), previous[x, y])) < 30:
                continue
            sector = int((math.atan2(ny, nx) + math.pi) / (2 * math.pi) * 16) % 16
            bins[sector] += 1
    return {'pixels': sum(bins), 'sectors': sum(n >= 4 for n in bins), 'bins': bins}


def _energy(payload, root):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    rows = payload['energyFrames']
    require(type(rows) is list and len(rows) == 2, 'exact empty/full energy captures required')
    images, evidence = [], []
    previous = payload['frames'][-1]['at']
    for phase, row in zip(('energy-empty', 'energy-full'), rows):
        require(row['phase'] == phase and row['path'] == phase + '.png' and row['origin'] == 'native-viewport', 'ordered actual energy PNGs')
        require(type(row['width']) is int and type(row['height']) is int and (row['width'], row['height']) == (1280, 720), 'energy viewport size')
        require(type(row['at']) in (int, float) and math.isfinite(row['at']) and previous < row['at'] <= payload['elapsed'], 'energy capture time')
        previous = row['at']
        require(type(row['energy']) is int and type(row['maxEnergy']) is int and row['maxEnergy'] > 0 and row['energy'] == (0 if phase == 'energy-empty' else row['maxEnergy']), 'actual empty/full model energy')
        script = row['script']
        # energy.gd sets _has_value after parsing any native numeric label,
        # including zero. Charging is determined separately by _energy_value > 0.
        require(script['hasValue'] is True and type(script['energy']) is int and script['energy'] == row['energy'], 'read-only script state follows native value')
        require(type(script['node']) is str and script['node'].endswith('/Layers/RotationLayers/StormRing'), 'actual energy script node')
        require(all(type(script[k]) in (int, float) and math.isfinite(script[k]) for k in ('pulse', 'phase')), 'finite read-only script animation')
        x, y, w, h = (row['rect'][k] for k in ('x', 'y', 'width', 'height'))
        require(all(type(n) in (int, float) and math.isfinite(n) for n in (x, y, w, h)) and 40 <= w <= 256 and 40 <= h <= 256 and 0 <= x and 0 <= y and x + w <= 1280 and y + h <= 720, 'actual visible energy rectangle')
        path = (root / row['path']).resolve(strict=True)
        require(path.parent == root, 'energy PNG in current isolated directory')
        content = path.read_bytes(); images.append(_decode(content))
        evidence.append({'phase': phase, 'path': str(path), 'sha256': sha256(content).hexdigest()})
    require(rows[0]['maxEnergy'] == rows[1]['maxEnergy'], 'unchanged maximum energy')
    require(all(abs(rows[0]['rect'][k] - rows[1]['rect'][k]) < 1 for k in ('x', 'y', 'width', 'height')), 'stable energy region')
    x, y, w, h = (rows[0]['rect'][k] for k in ('x', 'y', 'width', 'height'))
    samples = changed = blue_empty = blue_full = 0
    dark_luma = light_luma = 0.0
    for py in range(math.ceil(y), int(y + h)):
        for px in range(math.ceil(x), int(x + w)):
            nx, ny = (px - x - w / 2) / (w / 2), (py - y - h / 2) / (h / 2)
            # Central energy digits cannot satisfy the charging-appearance check.
            if not .55 ** 2 <= nx * nx + ny * ny <= .95 ** 2:
                continue
            empty, full = images[0][px, py], images[1][px, py]
            a = sum(v * weight for v, weight in zip(empty, (.2126, .7152, .0722)))
            b = sum(v * weight for v, weight in zip(full, (.2126, .7152, .0722)))
            samples += 1; dark_luma += a; light_luma += b
            changed += b - a >= 20
            def blue(rgb):
                r, g, b = rgb
                return b >= 100 and b - r >= 25 and g - r >= 10
            blue_empty += blue(empty); blue_full += blue(full)
    require(samples >= 500, 'sufficient actual rim pixels')
    metrics = {'samples': samples, 'emptyLuminance': dark_luma / samples, 'fullLuminance': light_luma / samples,
               'brightenedPixels': changed, 'emptyBluePixels': blue_empty, 'fullBluePixels': blue_full}
    errors = []
    if not (metrics['fullLuminance'] - metrics['emptyLuminance'] >= 8 and changed >= max(60, samples * .1)):
        errors.append('full energy must visibly brighten the rim, not only change digits')
    if not (blue_full >= max(40, samples * .08) and blue_empty <= blue_full * .35):
        errors.append('empty must lose blue charging glow while full restores it')
    return evidence, metrics, errors


def validate(payload, token, directory):
    errors, evidence, energy_evidence, energy_metrics = [], [], [], {}
    def need(ok, message):
        if not ok:
            errors.append(message)
    try:
        expected = dict(schema=1, token=token, scenario='domain-visual', fixture='single-combat-power-command-actor-tween',
                        version='v0.107.1', commit='59260271', testMode=False, syntheticInput=False)
        need(bool(token), 'current token required')
        for key, value in expected.items():
            need(type(payload[key]) is type(value) and payload[key] == value, 'metadata ' + key)
        rows = payload['frames']
        need(type(rows) is list and len(rows) == 5, 'exact five actual captures required')
        if errors:
            return {'errors': errors, 'frames': evidence, 'passed': False}
        root = Path(directory).resolve(strict=True)
        images = {}
        previous_time = -1
        for phase, row in zip(PHASES, rows):
            need(row['phase'] == phase and row['path'] == phase + '.png', 'ordered unique phase/path')
            need(row['origin'] == 'native-viewport' and row['domain'] is (phase in ('entered', 'sustained', 'moved')), 'real viewport/domain phase')
            need(type(row['width']) is int and type(row['height']) is int and (row['width'], row['height']) == (1280, 720), 'normal-window viewport dimensions')
            at = row['at']
            need(type(at) in (int, float) and math.isfinite(at) and previous_time < at < 55, 'ordered bounded actual capture timestamps')
            previous_time = at
            _region(row)
            path = (root / row['path']).resolve(strict=True)
            need(path.parent == root, 'PNG must stay inside current isolated capture directory')
            if errors:
                continue
            content = path.read_bytes()
            images[phase] = _decode(content)
            evidence.append({'phase': phase, 'path': str(path), 'sha256': sha256(content).hexdigest()})
        elapsed = payload['elapsed']
        need(type(elapsed) in (int, float) and math.isfinite(elapsed) and previous_time <= elapsed < 55, 'short fixture elapsed time')
        if errors:
            return {'errors': errors, 'frames': evidence, 'passed': False}
        before, entered, sustained, moved, exited = rows
        for row in (entered, sustained):
            need(abs(row['center']['x'] - before['center']['x']) < 2 and abs(row['center']['y'] - before['center']['y']) < 2,
                 'unmoved real foot origin must be stable')
        for axis in ('x', 'y'):
            need(abs(moved['center'][axis] - exited['center'][axis]) < 2, 'exit comparison must use same moved foot origin')
            need(all(abs(row['radius'][axis] - before['radius'][axis]) < 2 for row in rows), 'ring follows outer actor transform without body-scale contamination')
        need(moved['center']['x'] - before['center']['x'] >= 50 and abs(moved['center']['y'] - before['center']['y']) < 3, 'actual horizontal movement required')
        need(sustained['at'] - entered['at'] >= .8, 'sustained capture must be distinct in time')
        for row, baseline in ((entered, 'before'), (sustained, 'before'), (moved, 'exited')):
            result = _pixels(images[row['phase']], images[baseline], row)
            evidence[PHASES.index(row['phase'])]['visibleRing'] = result
            need(result['pixels'] >= 120 and result['sectors'] >= 12,
                 row['phase'] + ': visible blue lightning must cover at least 12/16 foot-ring sectors and 120 changed pixels')
        animation = _pixels(images['sustained'], images['entered'], sustained, blue=False)
        evidence[2]['animationChangedPixels'] = animation['pixels']
        need(animation['pixels'] >= 40, 'actual ring pixels must animate between entered/sustained')
        # Reversing this comparison detects a bright residual ring left after removal.
        residual = _pixels(images['exited'], images['moved'], exited)
        evidence[4]['residualChangedBluePixels'] = residual['pixels']
        need(residual['pixels'] < 120, 'exit must restore the non-blue foot region rather than recolor/reposition a ring')
        energy_evidence, energy_metrics, energy_errors = _energy(payload, root)
        errors.extend(energy_errors)
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError) as exc:
        errors.append('invalid visual evidence: ' + str(exc))
    return {'errors': errors, 'frames': evidence, 'energyFrames': energy_evidence, 'energyMetrics': energy_metrics, 'passed': not errors}


def check_log(text, token, directory):
    rows, errors = [], []
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    for line in text.splitlines():
        if 'DOMAIN_VISUAL_ERROR' in line:
            errors.append('native visual fixture error')
        if MARKER in line:
            try:
                row = json.loads(line.split(MARKER, 1)[1], object_pairs_hook=unique)
                if isinstance(row, dict) and row.get('token') == token:
                    rows.append(row)
            except (ValueError, TypeError):
                errors.append('malformed visual result')
    if len(rows) != 1:
        errors.append('exactly one current-token visual result required')
    if errors:
        return {'errors': errors, 'frames': [], 'passed': False}
    return validate(rows[0], token, directory)
