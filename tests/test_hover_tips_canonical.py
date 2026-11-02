"""Focused regression: canonical card hover tips never read mutable ownership.

The Lead fix in ``MechanicHoverTips.ForCard`` yields the static glossary tips and
then stops with ``if (card.IsCanonical) yield break;`` before ``card.Owner``.
The real native suite reached this through ``DustyTome.SetupForPlayer`` -> BaseLib
custom tome -> canonical ``Volibear_R18.HoverTips`` and threw
``CanonicalModelException``; ``test_canonical_preview_uses_real_native_guard``
now runs the production hover-tip composition against the pinned real
``sts2.dll``/``BaseLib.dll`` and would fail the same way if the guard moved.

``test_guard_order_source_text_is_not_gameplay`` is a source-text guard only. It
is labelled NOT gameplay on purpose and never stands in for the native suite.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(__file__).resolve().parent / 'hover_tips_canonical/HoverTipsCanonical.Tests.csproj'
SOURCE = ROOT / 'src/Volibear/Content/MechanicHoverTips.cs'


class CanonicalHoverTipsRegression(unittest.TestCase):
    def test_canonical_preview_uses_real_native_guard(self):
        # Missing pinned configuration is an environment limit, never a silent pass.
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native configuration unavailable; canonical hover tips NOT RUN')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        dotnet = Path(config['dotnet'])
        data_name = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
        data = Path(config['game_dir']) / data_name
        baselib = ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll'
        required = [dotnet, baselib, *(data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'))]
        if not all(path.is_file() for path in required):
            self.skipTest('Actual SDK/native/BaseLib references unavailable; canonical hover tips NOT RUN; no substitutes')

        # The fixture compiles current production source: it must not consume a
        # prebuilt shared DLL, so a stale bin cannot hide a broken guard.
        project_text = PROJECT.read_text(encoding='utf-8')
        for name in ('MechanicHoverTips.cs', 'VolibearCard.cs', 'MechanicGlossary.cs', 'VolibearLoc.cs'):
            self.assertIn('src/Volibear/Content/' + name, project_text)
        self.assertNotIn('src/Volibear/bin', project_text)
        self.assertNotIn('<Reference Include="Volibear"', project_text)

        environment = dict(os.environ, DOTNET_NOLOGO='1', DOTNET_CLI_TELEMETRY_OPTOUT='1',
                           DOTNET_ROOT=str(dotnet.resolve().parent))
        environment['PATH'] = str(dotnet.resolve().parent) + os.pathsep + environment.get('PATH', '')
        result = subprocess.run([
            str(dotnet), 'run', '--project', str(PROJECT), '-c', 'Release',
            '-p:Sts2DataDir=' + str(data), '-p:BaseLibPath=' + str(baselib), '--nologo',
        ], cwd=ROOT, capture_output=True, text=True, timeout=240, env=environment)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        match = re.search(
            r'HOVER_TIPS_CANONICAL_PASS checks=(\d+) '
            r'fixture=real-sts2\+BaseLib\+real-LocManager/LocTable '
            r'production-sources=MechanicHoverTips\+VolibearCard\+glossary\+loc '
            r'canonical-owner-throws=CanonicalModelException '
            r'static-tips=preserved live-state-tip=absent ledger-queries=0 '
            r'engagement-ledger=TEST-DOUBLE-NOT-GAMEPLAY '
            r'modeldb-and-dustytome-setup=NOT_RUN godot-render=NOT_RUN native-gameplay=NOT_RUN',
            output)
        self.assertIsNotNone(match, output)
        self.assertGreaterEqual(int(match.group(1)), 18)

    def test_guard_order_source_text_is_not_gameplay(self):
        """SOURCE-TEXT GUARD, NOT GAMEPLAY: static tips stay, then canonical stops, then Owner."""
        source = SOURCE.read_text(encoding='utf-8')
        body = source.split('internal static IEnumerable<IHoverTip> ForCard', 1)[1]
        static_tips = body.index('yield return tip')
        canonical_stop = body.index('if (card.IsCanonical) yield break;')
        owner_read = body.index('card.Owner')
        self.assertLess(static_tips, canonical_stop,
                        'canonical guard must not suppress the static glossary tips')
        self.assertLess(canonical_stop, owner_read,
                        'canonical guard must return before any card.Owner read')
        self.assertRegex(body[canonical_stop:canonical_stop + 64],
                         r'^if \(card\.IsCanonical\) yield break;',
                         'the canonical guard must depend on canonical state alone')


if __name__ == '__main__':
    unittest.main()
