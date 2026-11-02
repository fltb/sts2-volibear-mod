"""Runtime staging supports painted sources without shipping obsolete SVG art."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('painted_icon_stage', ROOT / 'assets/animation/integration_sts2_v5/stage_assets.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class PaintedIconStagingTests(unittest.TestCase):
    def test_all_current_icons_have_runtime_exports(self):
        manifest = json.loads((ROOT / 'assets/animation/vfx/icons/manifest.json').read_text())
        painted = 0
        for row in manifest['icons']:
            paths = stage.icon_runtime_paths(row)
            self.assertTrue(paths)
            for path in paths:
                self.assertTrue((ROOT / 'assets/animation/vfx' / path).is_file(), path)
            if 'raster_source' in row:
                painted += 1
                self.assertEqual(len(paths), 4)
                self.assertNotIn(row['legacy_svg'], paths)
                self.assertNotIn(row['raster_source'], paths)
                self.assertTrue((ROOT / row['raster_source']).is_file())
            else:
                self.assertIn(row['editable_svg'], paths)
        self.assertEqual(painted, 10)

    def test_missing_authoring_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'requires editable_svg or raster_source'):
            stage.icon_runtime_paths({'id': 'broken', 'files': {'64': {'path': 'icons/64/broken.png'}}})


if __name__ == '__main__':
    unittest.main()
