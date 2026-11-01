"""Compiled production foreign-card registration; no native game/Harmony claim."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BeastAdapterRegistration(unittest.TestCase):
    def test_foreign_inheritance_late_load_idempotence_and_failure(self):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        dotnet = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not dotnet or not Path(dotnet).is_file():
            raise unittest.SkipTest('SDK unavailable; beast adapter registration NOT_RUN')
        project = ROOT / 'tests/beast_bookkeeping/BeastBookkeeping.csproj'
        build = subprocess.run([dotnet, 'build', str(project), '-c', 'Release', '--nologo'],
                               cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        dll = ROOT / 'artifacts/beast-bookkeeping/bin/net9.0/BeastBookkeeping.dll'
        result = subprocess.run([dotnet, str(dll)], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BEAST_ADAPTERS_OK assertions=22; harmony-gameplay=NOT_RUN', result.stdout)
        self.assertIn('BEAST_BOOKKEEPING_OK assertions=22; engine_cases=NOT_RUN', result.stdout)

    def test_conversion_registers_before_mutating_and_warms_all_loaded_mods(self):
        source = (ROOT / 'src/Volibear/Core/BeastForms.cs').read_text(encoding='utf-8')
        self.assertLess(source.index('cardAdapters!.Ensure(card.GetType())'), source.index('forms.Add(card, form)'))
        self.assertIn('BeastCardAdapterRegistry.LoadedCardTypes(typeof(CardModel))', source)
        self.assertIn('BeastCardAdapterRegistry.DeclaredOverrides(type, root)', source)
        self.assertIn('cardAdapters!.PatchOnce(method, handler, postfix,', source)
        self.assertIn('cardAdapters!.PatchOnce(method, handler, false,', source)


if __name__ == '__main__':
    unittest.main()
