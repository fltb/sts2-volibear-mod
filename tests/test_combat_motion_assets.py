"""Decode actual added animation frames and check rig/packing boundaries.

This validates independently drawn motion data; it is not an aesthetic verdict or
an in-game result. Real actor timing is exercised by preview_combat_motions.gd.
"""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from tools import build_assets


class CombatMotionAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_assets.read_combat_inputs()
        cls.root = build_assets.COMBAT_ANIMATIONS
        cls.manifest = json.loads((cls.root / 'manifest.json').read_text())

    def test_accepted_base_and_new_joint_authored_clips_are_independent(self):
        _, base, portraits = build_assets.read_inputs()
        self.assertEqual((26, 940), (len(base), sum(c['frame_count'] for c in base)))
        self.assertEqual((14, 358), (len(self.rows), sum(c['frame_count'] for c in self.rows)))
        self.assertTrue(set(c['name'] for c in base).isdisjoint(c['name'] for c in self.rows))
        self.assertEqual('VOLIBEAR_RESOURCE_PASS clips=40 frames=1298 portraits=178',
                         build_assets.resource_marker(base + self.rows, portraits))
        text = build_assets.sprite_frames(base + self.rows)
        self.assertEqual(1298, text.count('[sub_resource type="AtlasTexture"'))
        for row in self.rows:
            self.assertIn('res://VolibearArt/animations/' + row['atlas']['image'], text)

    def test_every_exported_frame_decodes_has_clear_edges_and_matches_record(self):
        distinct_sequences = set()
        for row in self.rows:
            with self.subTest(clip=row['name']):
                hashes = []
                with Image.open(build_assets.animation_source(row['atlas']['image'])) as atlas:
                    self.assertEqual('RGBA', atlas.mode)
                    for record in row['frames']:
                        x, y, width, height = record['rect']
                        self.assertEqual((512, 512), (width, height))
                        self.assertLessEqual(x + width, atlas.width)
                        self.assertLessEqual(y + height, atlas.height)
                        frame = atlas.crop((x, y, x + width, y + height))
                        box = frame.getbbox()
                        self.assertIsNotNone(box)
                        self.assertTrue(0 < box[0] < box[2] < 512 and 0 < box[1] < box[3] < 512,
                                        f'{row["name"]}/{record["frame"]}: clipped anatomy')
                        digest = hashlib.sha256(frame.tobytes()).hexdigest()
                        self.assertEqual(record['raw_rgba_sha256'], digest)
                        hashes.append(digest)
                # Repeated neutral endpoints are intentional; neither static nor
                # renamed copies of another action count as an authored sequence.
                self.assertGreaterEqual(len(set(hashes)), row['frame_count'] - 2)
                distinct_sequences.add(tuple(hashes))
        self.assertEqual(14, len(distinct_sequences))

    def test_multihit_has_distinct_contact_poses_and_stomps_move_real_feet(self):
        by_name = {row['name']: row for row in self.rows}
        for name, count in [('double_claw', 2), ('claw_flurry', 3), ('stomp_chain', 3), ('bite_rend', 2)]:
            row = by_name[name]
            self.assertEqual(count, len(row['contact_frames']))
            contacts = [row['frames'][index]['raw_rgba_sha256'] for index in row['contact_frames']]
            self.assertEqual(count, len(set(contacts)))
        stomp = json.loads((self.root / 'atlases/stomp_chain.json').read_text())
        for side in ('near', 'far'):
            heights = [pose['markers_px']['ankle_' + side][1] for pose in stomp['poses']]
            self.assertGreater(max(heights) - min(heights), 16, 'A stomp must lift the actual foot')

    def test_modified_atlas_cannot_be_packed(self):
        real_sha = build_assets.sha
        def mismatched(path):
            return '0' * 64 if str(path).endswith('/combat/atlases/backhand.png') else real_sha(path)
        with patch.object(build_assets, 'sha', side_effect=mismatched):
            with self.assertRaisesRegex(ValueError, 'Combat animation atlas hash mismatch'):
                build_assets.read_combat_inputs()

    def test_stage_keeps_actual_runtime_paths_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            art = Path(directory)
            (art / 'animations').mkdir()
            (art / 'animations/manifest.json').write_text('{"clips": []}')
            build_assets.stage_combat_animations(art, self.rows)
            copied = json.loads((art / 'animations/combat/manifest.json').read_text())
            self.assertEqual(14, len(copied['clips']))
            for row in self.rows:
                self.assertEqual(row['atlas_sha256'], build_assets.sha(art / 'animations' / row['atlas']['image']))
            merged = json.loads((art / 'animations/manifest.json').read_text())
            self.assertEqual(14, len(merged['combat_clips']))


if __name__ == '__main__':
    unittest.main()
