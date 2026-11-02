"""Supplementary media checks; fake fixtures never claim native acceptance."""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
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

    def test_cli_missing_log_returns_json_failure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = media.main(['--log', str(self.root / 'missing.log'), '--token', 'run',
                               '--mode', 'actions', '--artifact-dir', str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
