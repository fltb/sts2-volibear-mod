"""Supplementary media checks; fake fixtures never claim native acceptance."""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import presentation_media_checks as media


class MediaChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'screen.png'
        self.image()
        self.payload = {'views': [], 'screens': [{'screenshot': {
            'path': 'screen.png', 'width': 8, 'height': 6}}], 'audio': None}

    def image(self, transparent=False):
        im = Image.new('RGBA', (8, 6), (0, 0, 0, 0 if transparent else 255))
        im.putpixel((1, 1), (255, 100, 0, 0 if transparent else 255))
        im.save(self.path)

    def report(self, errors=()):
        # Isolate only the new checks; production always runs existing validation.
        with patch.object(media.evidence, 'validate', return_value=list(errors)) as validate:
            result = media.build_report(self.payload, 'run', 'actions', self.root)
            validate.assert_called_once_with(self.payload, 'run', 'actions', self.root)
            return result

    def test_valid_decode_report_deterministic_no_sensory_claim(self):
        a = self.report()
        self.assertEqual(a, self.report())
        self.assertEqual(a['status'], 'PASS')
        self.assertEqual(len(a['images']), 1)
        self.assertFalse(any(a['claims'].values()))

    def test_existing_assertions_never_reduced(self):
        self.assertIn('native failure', self.report(['native failure'])['errors'])
        self.assertEqual(self.report(['native failure'])['status'], 'FAIL')

    def test_missing_empty_corrupt_truncated(self):
        for data in (b'', b'not png', self.path.read_bytes()[:45]):
            with self.subTest(data=data):
                self.path.write_bytes(data)
                self.assertEqual(self.report()['status'], 'FAIL')
        self.path.unlink()
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_wrong_dimensions(self):
        self.payload['screens'][0]['screenshot']['width'] = 9
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_blank_and_transparent(self):
        Image.new('RGB', (8, 6), (50, 50, 50)).save(self.path)
        self.assertEqual(self.report()['status'], 'FAIL')
        self.image(transparent=True)
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_crc_corruption(self):
        data = bytearray(self.path.read_bytes())
        data[29] ^= 1  # IHDR CRC, not just a truncated image.
        self.path.write_bytes(data)
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_no_screens(self):
        self.payload['screens'] = []
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_path_escape(self):
        self.payload['screens'][0]['screenshot']['path'] = '../screen.png'
        self.assertEqual(self.report()['status'], 'FAIL')

    def test_wav_exact_payload(self):
        path = self.root / 'mix.wav'
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
            wav.writeframes(struct.pack('<hhhh', 100, -100, 20, -20))
        self.payload['audio'] = {'wav': 'mix.wav', 'frames': 2,
                                 'sampleRate': 44100, 'voices': []}
        self.payload['audioProfile'] = {'profile': 'open'}
        self.assertEqual(self.report()['status'], 'PASS')
        path.write_bytes(path.read_bytes()[:-4])
        result = self.report()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('truncated decoded WAV payload', ' '.join(result['errors']))

    def test_real_validator_rejects_incomplete_fixture(self):
        result = media.build_report(self.payload, 'run', 'actions', self.root)
        self.assertEqual(result['status'], 'FAIL')

    def test_log_duplicate_keys_and_missing_result(self):
        for text in ('', media.evidence.MARKER + '{"token":1,"token":2}'):
            self.assertEqual(media.check_log(text, 'run', 'actions', self.root)['status'], 'FAIL')

    def shots(self, count):
        rows = []
        for index in range(count):
            name = f'shot-{index}.png'
            with Image.new('RGB', (8, 6)) as image:
                image.putpixel((1, 1), (1 + index % 255, index // 255, 90))
                image.save(self.root / name)
            rows.append({'screenshot': {'path': name, 'width': 8, 'height': 6, 'origin': 'native-viewport'}})
        return rows

    def test_both_decoders_use_four_real_workers_and_reduce_in_input_order(self):
        self.payload['screens'] = self.shots(8)
        for module, name in ((media, '_decode_image'), (media.evidence, '_decode_screenshot')):
            original = getattr(module, name)
            barrier = threading.Barrier(4)
            lock = threading.Lock()
            active = peak = calls = 0
            threads = set()
            def wrapped(root, shot):
                nonlocal active, peak, calls
                with lock:
                    active += 1; calls += 1; peak = max(peak, active)
                    threads.add(threading.get_ident())
                try:
                    barrier.wait(timeout=10)  # A serial implementation cannot pass.
                    return original(root, shot)  # Actual PNG decode, not a synthetic result.
                finally:
                    with lock:
                        active -= 1
            with patch.object(media.evidence, '_structure', side_effect=lambda *_: []), patch.object(module, name, wrapped):
                result = media.build_report(self.payload, 'run', 'actions', self.root)
            self.assertEqual(result['status'], 'PASS', result['errors'])
            self.assertEqual(calls, 8)
            self.assertEqual(peak, 4)
            self.assertEqual(len(threads), 4)
            self.assertEqual([row['path'] for row in result['images']], [row['screenshot']['path'] for row in self.payload['screens']])

    def test_mixed_errors_keep_order_continue_decoding_and_validate_audio(self):
        self.payload['screens'] = self.shots(6)
        (self.root / 'shot-0.png').write_bytes(b'malformed')
        path = self.root / 'shot-1.png'; path.write_bytes(path.read_bytes()[:45])
        with Image.new('RGBA', (8, 6)) as image:
            image.putpixel((1, 1), (255, 0, 0, 0))
            image.save(self.root / 'shot-2.png')
        self.payload['screens'][3]['screenshot']['path'] = '../outside.png'
        self.payload['audio'] = {'wav': 'missing.wav'}
        with patch.object(media.evidence, '_structure', side_effect=lambda *_: []):
            result = media.build_report(self.payload, 'run', 'actions', self.root)
            self.assertEqual(result, media.build_report(self.payload, 'run', 'actions', self.root))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual([row['path'] for row in result['images']], ['shot-4.png', 'shot-5.png'])
        image_errors = [e for e in result['errors'] if e.startswith('image ')]
        self.assertEqual(len(image_errors), 4)
        for error, name in zip(image_errors, ['shot-0.png', 'shot-1.png', 'shot-2.png', '../outside.png']):
            self.assertIn(repr(name), error)
        self.assertTrue(any('missing.wav' in error for error in result['errors']))
        self.assertTrue(any('blank visible viewport' in error for error in image_errors))

    def test_parallel_completion_order_does_not_reorder_errors(self):
        self.payload['screens'] = self.shots(4)
        first_finished = threading.Event()
        original = media._decode_image
        completed = []
        lock = threading.Lock()
        def delayed(root, shot):
            result = original(root, shot)
            if shot['path'] == 'shot-0.png':
                self.assertTrue(first_finished.wait(10))
            with lock:
                completed.append(shot['path'])
            if shot['path'] == 'shot-3.png':
                first_finished.set()
            return result
        for row in self.payload['screens']:
            row['screenshot']['width'] = 9
        with patch.object(media, '_decode_image', delayed):
            result = self.report()
        self.assertLess(completed.index('shot-3.png'), completed.index('shot-0.png'))
        self.assertEqual(len(result['errors']), 4)
        for index, error in enumerate(result['errors']):
            self.assertIn(f'shot-{index}.png', error)

    def test_no_pass_cache_and_both_independent_decodes_remain(self):
        self.payload['screens'] = self.shots(1)
        with patch.object(media.evidence, '_structure', side_effect=lambda *_: []), \
             patch.object(media.evidence, '_decode_screenshot', wraps=media.evidence._decode_screenshot) as first, \
             patch.object(media, '_decode_image', wraps=media._decode_image) as second:
            self.assertEqual(media.build_report(self.payload, 'run', 'actions', self.root)['status'], 'PASS')
            with Image.new('RGB', (8, 6)) as image:
                image.save(self.root / 'shot-0.png')
            result = media.build_report(self.payload, 'run', 'actions', self.root)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(first.call_count, 2)
            self.assertEqual(second.call_count, 2)
            self.assertTrue(any('flat/blank viewport' in error for error in result['errors']))
            self.assertTrue(any('blank visible viewport' in error for error in result['errors']))

    def test_catalog_unique_hash_and_duplicate_native_path_checks_retained(self):
        self.payload['views'] = self.shots(356)
        self.payload['screens'] = []
        with patch.object(media.evidence, '_structure', side_effect=lambda *_: []):
            self.assertEqual(media.evidence.validate(self.payload, 'run', 'cards', self.root), [])
            (self.root / 'shot-1.png').write_bytes((self.root / 'shot-0.png').read_bytes())
            self.assertIn('artifact evidence: catalog screenshots reused/not distinct',
                          media.evidence.validate(self.payload, 'run', 'cards', self.root))
            self.payload['views'][1]['screenshot']['path'] = 'shot-0.png'
            self.payload['views'][2]['screenshot']['origin'] = 'fake'
            errors = media.evidence.validate(self.payload, 'run', 'cards', self.root)
            self.assertEqual(errors.count('artifact evidence: duplicate/non-native screenshot'), 2)

    def test_cli_missing_log_returns_json_failure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = media.main(['--log', str(self.root / 'missing.log'), '--token', 'run',
                               '--mode', 'actions', '--artifact-dir', str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
