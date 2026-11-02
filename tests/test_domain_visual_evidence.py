"""Synthetic oracle fixtures only; these tests never claim actual gameplay pixels."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import struct
import zlib


def png(path, active=False, x=350, color=(45, 210, 255), partial=False, width=1280, height=720, energy=None):
    pixels = bytearray(bytes((35, 30, 25)) * width * height)
    if active:
        for y in range(420, 541):
            for px in range(x - 210, x + 211):
                nx, ny = (px - x) / 200, (y - 480) / 48
                if .94 ** 2 < nx * nx + ny * ny < 1.02 ** 2 and (not partial or nx > 0 and ny > 0):
                    start = (y * width + px) * 3
                    pixels[start:start + 3] = bytes(color)
    if energy in ('full', 'digits'):
        for y in range(550, 650):
            for px in range(100, 200):
                radius = ((px - 150) / 50) ** 2 + ((y - 600) / 50) ** 2
                if (.65 ** 2 < radius < .90 ** 2) if energy == 'full' else radius < .3 ** 2:
                    start = (y * width + px) * 3
                    pixels[start:start + 3] = bytes((45, 210, 255))
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
    stride = width * 3
    raw = b''.join(b'\0' + pixels[row * stride:(row + 1) * stride] for row in range(height))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
                          chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from domain_visual_evidence import PHASES, MARKER, check_log, validate, _decode


def fixture(directory):
    rows = []
    for i, phase in enumerate(PHASES):
        x, y = (500 if phase in ('moved', 'exited') else 350), 480
        active = phase in ('entered', 'sustained', 'moved')
        png(Path(directory) / (phase + '.png'), active=active, x=x,
            color=(40, 150, 220) if phase == 'entered' else (45, 210, 255))
        rows.append(dict(phase=phase, path=phase + '.png', width=1280, height=720, at=i + 1,
                         origin='native-viewport', center=dict(x=x, y=y), radius=dict(x=200, y=48), domain=active))
    energy_rows = []
    for i, state in enumerate(('empty', 'full')):
        phase = 'energy-' + state
        png(Path(directory) / (phase + '.png'), energy=state)
        energy_rows.append(dict(phase=phase, path=phase + '.png', width=1280, height=720, origin='native-viewport', at=6 + i,
            energy=3 if i else 0, maxEnergy=3, rect=dict(x=100, y=550, width=100, height=100),
            script=dict(node='/root/Run/Energy/Layers/RotationLayers/StormRing', hasValue=True, energy=3 if i else 0, pulse=.4, phase=.7)))
    return dict(schema=1, token='unit-domain-visual', scenario='domain-visual', fixture='single-combat-power-command-actor-tween',
                version='v0.107.1', commit='59260271', testMode=False, syntheticInput=False, frames=rows, energyFrames=energy_rows, elapsed=7.1)


class DomainVisualEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.payload = fixture(self.directory)

    def check(self, payload=None):
        return validate(self.payload if payload is None else payload, 'unit-domain-visual', self.directory)

    def test_pixel_geometry_fixture(self):
        result = self.check()
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['frames']), 5)
        for row in result['frames'][1:4]:
            self.assertGreaterEqual(row['visibleRing']['pixels'], 120)
            self.assertEqual(row['visibleRing']['sectors'], 16)
        self.assertTrue(check_log(MARKER + json.dumps(self.payload), 'unit-domain-visual', self.directory)['passed'])

    def test_energy_actual_rim_contrast(self):
        result = self.check()
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual(len(result['energyFrames']), 2)
        self.assertGreater(result['energyMetrics']['fullLuminance'], result['energyMetrics']['emptyLuminance'] + 8)

    def test_energy_state_flags_without_pixels_fail(self):
        png(self.directory / 'energy-full.png')
        result = self.check()
        self.assertFalse(result['passed'])
        self.assertEqual(result['energyMetrics']['brightenedPixels'], 0)
        self.assertEqual(len(result['energyFrames']), 2)

    def test_energy_digits_alone_do_not_count_as_charging(self):
        png(self.directory / 'energy-full.png', energy='digits')
        self.assertFalse(self.check()['passed'])

    def test_empty_retaining_charging_glow_fails(self):
        png(self.directory / 'energy-empty.png', energy='full')
        self.assertFalse(self.check()['passed'])

    def test_energy_metadata_and_region_mutations(self):
        for field, value in [('energy', 1), ('maxEnergy', 0), ('at', 4), ('origin', 'synthetic'), ('path', '../energy-full.png')]:
            payload = copy.deepcopy(self.payload); payload['energyFrames'][0][field] = value
            self.assertFalse(self.check(payload)['passed'], field)
        for field, value in [('x', -1), ('y', 800), ('width', 0), ('height', float('nan'))]:
            payload = copy.deepcopy(self.payload); payload['energyFrames'][0]['rect'][field] = value
            self.assertFalse(self.check(payload)['passed'], field)
        for index in (0, 1):
            for field, value in [('hasValue', False), ('hasValue', 1), ('energy', 99), ('energy', True)]:
                payload = copy.deepcopy(self.payload); payload['energyFrames'][index]['script'][field] = value
                self.assertFalse(self.check(payload)['passed'], (index, field, value))
        payload = copy.deepcopy(self.payload); payload['energyFrames'] = []
        self.assertFalse(self.check(payload)['passed'])

    def test_missing_energy_png_fails(self):
        (self.directory / 'energy-full.png').unlink()
        self.assertFalse(self.check()['passed'])

    def test_node_flags_without_actual_pixels_fail(self):
        for phase in ('entered', 'sustained', 'moved'):
            with self.subTest(phase=phase):
                fixture(self.directory)
                png(self.directory / (phase + '.png'))
                self.assertFalse(self.check()['passed'])

    def test_one_visible_arc_does_not_count_as_complete_ring(self):
        png(self.directory / 'entered.png', active=True, partial=True)
        self.assertFalse(self.check()['passed'])

    def test_static_ring_fails_animation(self):
        (self.directory / 'sustained.png').write_bytes((self.directory / 'entered.png').read_bytes())
        self.assertIn('actual ring pixels must animate between entered/sustained', self.check()['errors'])

    def test_failure_to_follow_actor_is_detected_from_pixels(self):
        (self.directory / 'moved.png').write_bytes((self.directory / 'sustained.png').read_bytes())
        self.assertFalse(self.check()['passed'])

    def test_failure_to_remove_ring_is_detected_from_pixels(self):
        (self.directory / 'exited.png').write_bytes((self.directory / 'moved.png').read_bytes())
        self.assertFalse(self.check()['passed'])

    def test_baseline_contamination_fails(self):
        (self.directory / 'before.png').write_bytes((self.directory / 'entered.png').read_bytes())
        self.assertFalse(self.check()['passed'])

    def test_missing_or_wrong_size_png_fails(self):
        (self.directory / 'entered.png').unlink()
        self.assertFalse(self.check()['passed'])
        png(self.directory / 'entered.png', width=64, height=64)
        self.assertFalse(self.check()['passed'])

    def test_metadata_and_coordinate_mutations(self):
        for key, value in [('schema', True), ('version', 'wrong'), ('testMode', True), ('syntheticInput', True), ('elapsed', 90)]:
            payload = copy.deepcopy(self.payload); payload[key] = value
            self.assertFalse(self.check(payload)['passed'])
        for field, value in [('phase', 'fake'), ('origin', 'synthetic'), ('path', '../entered.png'), ('domain', False), ('at', 0)]:
            payload = copy.deepcopy(self.payload); payload['frames'][1][field] = value
            self.assertFalse(self.check(payload)['passed'])
        payload = copy.deepcopy(self.payload); payload['frames'][1]['center']['x'] = float('nan')
        self.assertFalse(self.check(payload)['passed'])
        payload = copy.deepcopy(self.payload); payload['frames'][3]['center']['x'] = 350
        self.assertFalse(self.check(payload)['passed'])

    def test_decode_rgba_with_all_five_png_filters(self):
        stride = 1280 * 4
        previous = bytes(stride)
        encoded, originals = [], []
        for y in range(5):
            row = bytes((i * 37 + y * 31) & 255 for i in range(stride))
            originals.append(row)
            filtered = bytearray(stride)
            for i, byte in enumerate(row):
                left = row[i - 4] if i >= 4 else 0
                above = previous[i]
                diagonal = previous[i - 4] if i >= 4 else 0
                # Encoder predictor chooses nearest to a+b-c with PNG tie order.
                choices = (left, above, diagonal)
                paeth = min(enumerate(choices), key=lambda pair: (abs(pair[1] - (left + above - diagonal)), pair[0]))[1]
                predictor = (0, left, above, (left + above) // 2, paeth)[y]
                filtered[i] = (byte - predictor) % 256
            encoded.append(bytes([y]) + filtered)
            previous = row
        raw = b''.join(encoded) + (b'\0' * (stride + 1)) * 715
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
        data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1280, 720, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
        image = _decode(data)
        for y in range(5):
            for x in (0, 1, 2, 50, 1279):
                self.assertEqual(image[x, y], originals[y][x * 4:x * 4 + 3])

    def test_log_requires_one_current_result(self):
        line = MARKER + json.dumps(self.payload)
        for text, token in [(line, 'old'), (line + '\n' + line, 'unit-domain-visual'),
                (MARKER + '{', 'unit-domain-visual'), (line + '\nDOMAIN_VISUAL_ERROR failed', 'unit-domain-visual')]:
            self.assertFalse(check_log(text, token, self.directory)['passed'])
