"""Execute the actual retrieval/search bodies against mutable capacity boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method_body(path, signature):
    source = path.read_text(encoding='utf-8')
    start = source.index(signature)
    body = source.index('{', start)
    depth = 0
    for index in range(body, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError('Unterminated production method: ' + signature)


class HandCapacityBoundaries(unittest.TestCase):
    def test_foreign_limits_owner_scope_and_changes_during_selection(self):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        dotnet = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not dotnet or not Path(dotnet).is_file():
            raise unittest.SkipTest('SDK unavailable; hand-capacity production methods NOT_RUN')
        output = ROOT / 'artifacts/hand-capacity'
        output.mkdir(parents=True, exist_ok=True)
        body = '''using BaseLib.Patches.Hooks;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;
namespace Volibear.Content;
'''
        for file, name, signature in (
            ('ControlledEffects.cs', 'ControlledEffects', 'internal static async Task Retrieve('),
            ('BeastEffects.cs', 'BeastSelection', 'internal static async Task Search('),
        ):
            method = method_body(ROOT / 'src/Volibear/Content/Cards' / file, signature)
            body += 'internal static partial class ' + name + '\n{\n' + method + '\n}\n'
        methods = output / 'ProductionMethods.cs'
        methods.write_text(body, encoding='utf-8')
        project = ROOT / 'tests/hand_capacity/HandCapacity.csproj'
        build = subprocess.run([dotnet, 'build', str(project), '-c', 'Release', '--nologo',
                                f'-p:ProductionMethods={methods}', f'-p:BaseIntermediateOutputPath={output}/obj/',
                                f'-p:OutputPath={output}/bin/'], cwd=ROOT, capture_output=True,
                               text=True, encoding='utf-8', timeout=180)
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        result = subprocess.run([dotnet, str(output / 'bin/HandCapacity.dll')], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('HAND_CAPACITY_OK checks=21 engine=STUBBED native-gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
